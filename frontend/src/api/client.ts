import axios from 'axios'

import { clearToken, getToken } from '../auth/tokenStorage'

export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({ baseURL: API_BASE_URL })

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let unauthorizedHandler: (() => void) | null = null

/** `AuthProvider` registra aquí la reacción a un 401 (pasar a estado anónimo). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined
    const url = axios.isAxiosError(error) ? (error.config?.url ?? '') : ''
    // El 401 de /auth/login son credenciales inválidas: lo maneja la pantalla de login.
    if (status === 401 && !url.includes('/auth/login')) {
      clearToken()
      unauthorizedHandler?.()
    }
    return Promise.reject(error)
  },
)
