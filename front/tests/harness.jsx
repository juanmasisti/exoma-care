import { MemoryRouter } from 'react-router-dom'
import App from '../src/App.jsx'

export default function Harness() {
  return <MemoryRouter initialEntries={['/catalogo/patologias']}><App /></MemoryRouter>
}
