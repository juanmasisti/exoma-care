// Sesión en memoria: no se persisten credenciales ni tokens en localStorage.
let session = null
const listeners = new Set()

export function getSession() { return session }
export function setSession(value) {
  session = value
  listeners.forEach((listener) => listener())
}
export function subscribeSession(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
