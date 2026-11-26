import { useEffect } from 'react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import App from '../src/App.jsx'

function Navigation({ to }) {
  const navigate = useNavigate()
  useEffect(() => { if (to) navigate(to) }, [to, navigate])
  return null
}

export default function Harness({ initialEntries = ['/catalogo/patologias'], navigateTo }) {
  return <MemoryRouter initialEntries={initialEntries}><Navigation to={navigateTo} /><App /></MemoryRouter>
}
