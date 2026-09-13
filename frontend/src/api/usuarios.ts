import { api } from './client'
import type { PerfilUpdate, Usuario } from './types'

/** CU03 — perfil del usuario autenticado. */
export async function getMe(): Promise<Usuario> {
  const { data } = await api.get<Usuario>('/usuarios/me')
  return data
}

/** CU03 — editar el perfil (nombre, email y/o contraseña). */
export async function updateMe(payload: PerfilUpdate): Promise<Usuario> {
  const { data } = await api.put<Usuario>('/usuarios/me', payload)
  return data
}
