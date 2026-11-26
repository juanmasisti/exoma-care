# Frontend

Aplicación web de Exoma Care desarrollada con React y Vite. El punto de entrada
actual es `src/main.jsx`, que monta `App.jsx` dentro del router. Los comandos
disponibles están declarados en `package.json` (`npm run dev`, `npm run build`
y `npm run lint`).

## Carpetas

- [`public/`](./public/README.md): archivos estáticos publicados sin procesar
  por el empaquetador.
- [`src/`](./src/README.md): código fuente de la aplicación.
- [`src/assets/`](./src/assets/README.md): imágenes, fuentes y medios
  importados desde el código.
- [`src/components/`](./src/components/README.md): componentes de interfaz
  genéricos compartidos.
- [`src/features/`](./src/features/README.md): funcionalidades completas
  agrupadas por dominio; cada feature puede contener páginas y piezas propias.
- [`src/services/`](./src/services/README.md): comunicación con servicios y
  APIs externas.
- [`src/store/`](./src/store/README.md): estado global compartido.

Cada carpeta del árbol de código incluye su propio `README.md` con el alcance
esperado para sus archivos. No guardar aquí secretos, tokens ni datos reales de
pacientes.
