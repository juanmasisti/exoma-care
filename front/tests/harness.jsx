import { MemoryRouter } from 'react-router-dom'
import App from '../src/App.jsx'

export default function Harness({ initialEntries = ['/catalogo/patologias'] }) {
  return <MemoryRouter initialEntries={initialEntries}><App /></MemoryRouter>
}
