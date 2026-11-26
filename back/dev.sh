#!/usr/bin/env bash
set -euo pipefail

# Usar siempre back como directorio de trabajo, incluso al llamar desde la raíz.
backend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$backend_dir"

backend_python=".venv/Scripts/python.exe"
if [[ ! -f "$backend_python" ]]; then
  backend_python=".venv/bin/python"
fi
if [[ ! -f "$backend_python" ]]; then
  printf '%s\n' 'Falta el entorno virtual. Seguí la preparación de back/README.md.' >&2
  exit 1
fi

# La aplicación lee back/.env. Este script no instala ni migra la base.
exec "$backend_python" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 "$@"
