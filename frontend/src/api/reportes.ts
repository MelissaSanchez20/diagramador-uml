import axios from 'axios'

import { api } from './client'

type ReportePdf = {
  blob: Blob
  nombreArchivo: string
}

function nombreDesdeContentDisposition(disposition: string | undefined, proyectoId: number): string {
  const match = disposition?.match(/filename="?([^";]+)"?/)
  return match?.[1] ?? `reporte-${proyectoId}.pdf`
}

/**
 * CU07 — descarga el reporte PDF del diagrama de clases del proyecto. Mismo
 * manejo de error que `generarBackend` (CU08): con `responseType: 'blob'`
 * axios también entrega el cuerpo de error como Blob en vez de JSON
 * parseado, así que hay que leerlo a mano para extraer el `detail`.
 */
export async function generarReportePdf(proyectoId: number): Promise<ReportePdf> {
  try {
    const resp = await api.get(`/proyectos/${proyectoId}/reporte`, {
      params: { formato: 'pdf' },
      responseType: 'blob',
    })
    return {
      blob: resp.data as Blob,
      nombreArchivo: nombreDesdeContentDisposition(resp.headers['content-disposition'], proyectoId),
    }
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.data instanceof Blob) {
      const texto = await err.response.data.text()
      let detalle: string | undefined
      try {
        detalle = (JSON.parse(texto) as { detail?: string }).detail
      } catch {
        /* el cuerpo del error no era JSON */
      }
      if (detalle) throw new Error(detalle)
    }
    throw err
  }
}
