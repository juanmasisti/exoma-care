const SESSION_STORAGE_KEY = 'exoma-care-session'

let session = null
const listeners = new Set()

export function getSession() { return session }

export function setSession(value) {
  if (typeof window !== 'undefined') {
    if (value) {
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(value))
    } else {
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
    }
  }
  session = value
  listeners.forEach((listener) => listener())
}

export function restoreSession() {
  if (typeof window === 'undefined') return null

  const stored = window.sessionStorage.getItem(SESSION_STORAGE_KEY)
  if (!stored) {
    session = null
    return session
  }

  try {
    const value = JSON.parse(stored)
    if (
      !value
      || typeof value !== 'object'
      || typeof value.access_token !== 'string'
      || !value.access_token
      || typeof value.role !== 'string'
      || !value.role
    ) {
      throw new TypeError('La sesión guardada no tiene un formato válido.')
    }
    session = value
  } catch {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
    session = null
  }
  return session
}

export function subscribeSession(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

restoreSession()
