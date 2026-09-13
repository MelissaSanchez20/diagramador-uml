import { api } from './client'
import type { Colaborador } from './types'

/** CU04 — colaboradores activos de un proyecto propio. */
export async function listColaboradores(proyectoId: number): Promise<Colaborador[]> {
  const { data } = await api.get<Colaborador[]>(`/proyectos/${proyectoId}/colaboradores`)
  return data
}

export async function agregarColaborador(proyectoId: number, email: string): Promise<Colaborador> {
  const { data } = await api.post<Colaborador>(`/proyectos/${proyectoId}/colaboradores`, { email })
  return data
}

export async function quitarColaborador(proyectoId: number, colaboradorId: number): Promise<void> {
  await api.delete(`/proyectos/${proyectoId}/colaboradores/${colaboradorId}`)
}
