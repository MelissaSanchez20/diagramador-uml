import { api } from './client'
import type { DiagramaData } from './types'

/** CU09 — diagrama de clases de un proyecto propio o colaborado. */
export async function getDiagrama(proyectoId: number): Promise<DiagramaData> {
  const { data } = await api.get<DiagramaData>(`/proyectos/${proyectoId}/diagrama`)
  return data
}

/** Reemplaza el diagrama completo (autoguardado). */
export async function guardarDiagrama(
  proyectoId: number,
  datos: DiagramaData,
): Promise<DiagramaData> {
  const { data } = await api.put<DiagramaData>(`/proyectos/${proyectoId}/diagrama`, datos)
  return data
}
