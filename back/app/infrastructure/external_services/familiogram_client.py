"""Bounded provider client. Provider error text and credentials never escape."""
import base64
import binascii
import colorsys
import json
import re
import xml.etree.ElementTree as ET
from io import BytesIO

import httpx
from fpdf import FPDF

MAX_SVG = 2 * 1024 * 1024
MAX_RESPONSE = 3 * 1024 * 1024

class FamiliogramUnavailable(RuntimeError):
    pass


def safe_svg(raw: bytes) -> bytes:
    if not raw or len(raw) > MAX_SVG:
        raise FamiliogramUnavailable("La imagen recibida excede el límite permitido.")
    try:
        text = raw.decode("utf-8")
        if "<!" in text or "<?" in text:
            raise ValueError()
        root = ET.fromstring(text)
        # Provider CSS is deliberately limited to text/tag and single class selectors.
        # Inline it before rendering; no CSS parser may load imports or resources.
        for parent in root.iter():
            for style in list(parent):
                if style.tag != "{http://www.w3.org/2000/svg}style":
                    continue
                css = style.text or ""
                props = {"font-family", "font-size", "font-weight", "fill", "stroke", "stroke-width", "stroke-linejoin", "stroke-linecap", "opacity"}
                rules = re.findall(r"([.\w-]+)\s*\{([^{}]*)\}", css)
                if re.sub(r"([.\w-]+)\s*\{([^{}]*)\}", "", css).strip() or len(css) > 10000:
                    raise ValueError()
                for selector, declarations in rules:
                    attrs = {}
                    for declaration in declarations.split(";"):
                        if not declaration.strip():
                            continue
                        key, value = (x.strip() for x in declaration.split(":", 1))
                        if key not in props or not re.fullmatch(r"[\w#., %-]+", value):
                            raise ValueError()
                        attrs[key] = value
                    for node in root.iter():
                        if (selector.startswith(".") and selector[1:] in node.get("class", "").split()) or node.tag.split("}")[-1] == selector:
                            for key, value in attrs.items():
                                node.attrib.setdefault(key, value)
                parent.remove(style)
        allowed = {"svg", "g", "defs", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "tspan", "title", "desc", "clipPath", "pattern"}
        nodes = list(root.iter())
        if root.tag != "{http://www.w3.org/2000/svg}svg" or len(nodes) > 10000:
            raise ValueError()
        for node in nodes:
            if node.tag.split("}")[-1] not in allowed:
                raise ValueError()
            for key, value in node.attrib.items():
                key = key.split("}")[-1].lower()
                if key.startswith("on") or key in ("href", "src", "base") or "@" in value or "expression" in value.lower():
                    raise ValueError()
                # Only local fragment paint/clip references, never file/network resources.
                for match in re.finditer(r"url\s*\((.*?)\)", value, re.I):
                    if not re.fullmatch(r"#[A-Za-z_][\w.-]*", match.group(1).strip()):
                        raise ValueError()
                if re.search(r"(?:https?:|file:|data:|javascript:|//)", value, re.I):
                    raise ValueError()
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        return ET.tostring(root, encoding="utf-8")
    except (ValueError, ET.ParseError, UnicodeError):
        raise FamiliogramUnavailable("El proveedor devolvió una imagen SVG no segura o inválida.") from None


def svg_pdf(svg: bytes) -> bytes:
    try:
        # fpdf2 does not support the provider's HSL diagnosis palette.
        # Convert only strict CSS hsl colors to their mathematically equivalent RGB.
        root = ET.fromstring(safe_svg(svg))
        for node in root.iter():
            for key in ("fill", "stroke"):
                value = node.get(key, "")
                match = re.fullmatch(r"hsl\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)%\s*,\s*(\d+(?:\.\d+)?)%\s*\)", value)
                if match:
                    hue, saturation, lightness = map(float, match.groups())
                    if not 0 <= saturation <= 100 or not 0 <= lightness <= 100:
                        raise ValueError()
                    rgb = colorsys.hls_to_rgb((hue % 360) / 360, lightness / 100, saturation / 100)
                    node.set(key, "#" + "".join(f"{round(channel * 255):02x}" for channel in rgb))
        # fpdf2 applies clips to shapes, not groups, and expects word-only IDs.
        clips = {node.get("id"): f"clip_{i}" for i, node in enumerate(root.iter())
                 if node.tag.endswith("}clipPath") and node.get("id")}
        for node in root.iter():
            if node.get("id") in clips:
                node.set("id", clips[node.get("id")])
            clip = node.get("clip-path")
            if clip:
                match = re.fullmatch(r"url\(#([\w.-]+)\)", clip)
                if not match or match[1] not in clips:
                    raise ValueError("Unsupported clipping reference")
                node.set("clip-path", f"url(#{clips[match[1]]})")
        def propagate_clip(node, inherited=None):
            current = node.get("clip-path")
            if current and inherited and current != inherited:
                raise ValueError("Nested clipping intersection is unsupported")
            clip = current or inherited
            if node.tag.endswith("}g"):
                node.attrib.pop("clip-path", None)
                for child in node:
                    propagate_clip(child, clip)
            else:
                if clip:
                    node.set("clip-path", clip)
                for child in node:
                    propagate_clip(child)
        propagate_clip(root)
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        svg = ET.tostring(root, encoding="utf-8")
        pdf = FPDF(orientation="L")
        pdf.add_page()
        pdf.set_font("Helvetica", size=10)
        pdf.image(BytesIO(safe_svg(svg)), x=10, y=10, w=277, h=190, keep_aspect_ratio=True)
        output = bytes(pdf.output())
        if not output.startswith(b"%PDF-") or len(output) > 5 * 1024 * 1024:
            raise ValueError()
        return output
    except Exception:
        raise FamiliogramUnavailable("No se pudo convertir la imagen a PDF. La información familiar sigue guardada.") from None


class FamiliogramClient:
    def __init__(self, base_url, api_key, transport=None):
        self.base_url, self.api_key, self.transport = base_url, api_key, transport

    def request(self, method, suffix="", payload=None):
        if not self.base_url or not self.api_key:
            raise FamiliogramUnavailable("El servicio de familiograma no está configurado.")
        if payload is not None and len(json.dumps(payload).encode()) > 1024 * 1024:
            raise ValueError("La familia excede el tamaño permitido por el proveedor.")
        try:
            with httpx.Client(timeout=30, transport=self.transport, follow_redirects=False) as client:
                with client.stream(method, self.base_url.rstrip("/") + suffix, headers={"x-api-key": self.api_key}, json=payload) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE:
                            raise FamiliogramUnavailable("Respuesta del proveedor demasiado grande.")
                        chunks.append(chunk)
                    if response.status_code == 422:
                        raise ValueError("El proveedor no puede ubicar la familia. Revisá los parentescos detallados, progenitores y su sexo: hermanos necesitan progenitores; abuelos necesitan el progenitor de su lado; primos, sobrinos y nietos necesitan una única persona de referencia.")
                    if response.status_code != 200:
                        raise FamiliogramUnavailable("El servicio de familiograma no está disponible. Reintentá más tarde.")
                    return json.loads(b"".join(chunks))
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeError):
            raise FamiliogramUnavailable("No se pudo consultar el servicio de familiograma.") from None

    def relationships(self):
        data = self.request("GET", "/parentescos")
        if not isinstance(data, list) or len(data) != 16 or any(not isinstance(x, dict) or type(x.get("id")) is not int or not isinstance(x.get("parentesco"), str) or len(x["parentesco"]) > 100 for x in data) or {x["id"] for x in data} != set(range(16)):
            raise FamiliogramUnavailable("Catálogo de parentescos inválido.")
        return [x for x in data if x["id"] != 0]

    def generate(self, payload):
        data = self.request("POST", payload=payload)
        try:
            image, warnings = data["imagen"], data["advertencias"]
            if image["tipo"] != "image/svg+xml" or not isinstance(warnings, list) or len(warnings) > 100:
                raise ValueError()
            warnings = [{"codigo": str(x["codigo"])[:100], "mensaje": str(x["mensaje"])[:500]} for x in warnings]
            svg = safe_svg(base64.b64decode(image["base64"], validate=True))
            return svg, warnings
        except (KeyError, TypeError, ValueError, binascii.Error):
            raise FamiliogramUnavailable("Respuesta de imagen inválida del proveedor.") from None
