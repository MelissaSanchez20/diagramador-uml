import { useState } from 'react'
import type { ReactNode } from 'react'
import { toPng } from 'html-to-image'
import { getNodesBounds, getViewportForBounds, useReactFlow } from 'reactflow'
import { Link, useNavigate } from 'react-router-dom'

import { descargarArchivo, generarBackend } from '../../api/generacion'
import { generarReportePdf } from '../../api/reportes'
import { getApiErrorMessage } from '../../api/errors'
import type { Proyecto } from '../../api/types'
import { useAuth } from '../../auth/useAuth'
import { iniciales } from '../../lib/format'
import { ColaboradoresModal } from '../../pages/ColaboradoresModal'

const MENSAJE_SIN_CONTENIDO = 'No hay contenido disponible para exportar. Agrega al menos una clase al diagrama.'

/** Nombre de archivo seguro (sin acentos ni caracteres especiales) a partir del nombre del proyecto. */
function slugNombreArchivo(nombre: string): string {
  const limpio = nombre
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
  return limpio || 'diagrama'
}

function descargarDataUrl(dataUrl: string, nombreArchivo: string): void {
  const a = document.createElement('a')
  a.href = dataUrl
  a.download = nombreArchivo
  document.body.appendChild(a)
  a.click()
  a.remove()
}

type ToolButtonProps = {
  children: ReactNode
  icon?: ReactNode
  primary?: boolean
  disabled?: boolean
  onClick?: () => void
}

function ToolButton({ children, icon, primary, disabled, onClick }: ToolButtonProps) {
  return (
    <button
      type="button"
      className={primary ? 'tool-btn tool-btn--primary' : 'tool-btn'}
      disabled={disabled}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  )
}

function IconPlus() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function IconFit() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M2 5V2h3M12 5V2H9M2 9v3h3M12 9v3H9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function IconUsers() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M5 6.5a2 2 0 100-4 2 2 0 000 4zM1.5 12c0-2 1.5-3.5 3.5-3.5S8.5 10 8.5 12M9.5 4a1.8 1.8 0 110 3.6M9 8.7c1.6.1 2.9 1.5 3 3.3"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconDownload() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path
        d="M7 1.5v7m0 0L4 5.5M7 8.5l3-3M2 10.5v1.5a1 1 0 001 1h8a1 1 0 001-1v-1.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

type ToolbarProps = {
  project: Proyecto
  onNuevaClase: () => void
  guardando: boolean
  errorGuardado: string | null
  onReintentarGuardado: () => void
}

export function Toolbar({
  project,
  onNuevaClase,
  guardando,
  errorGuardado,
  onReintentarGuardado,
}: ToolbarProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { fitView, getNodes } = useReactFlow()
  const [mostrarColaboradores, setMostrarColaboradores] = useState(false)
  const [generandoBackend, setGenerandoBackend] = useState(false)
  const [errorGeneracion, setErrorGeneracion] = useState<string | null>(null)
  const [formatoReporte, setFormatoReporte] = useState<'pdf' | 'imagen'>('pdf')
  const [generandoReporte, setGenerandoReporte] = useState(false)
  const [errorReporte, setErrorReporte] = useState<string | null>(null)
  const esAdministrador = user?.id === project.id_administrador

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleGenerarBackend = async () => {
    setErrorGeneracion(null)
    setGenerandoBackend(true)
    try {
      const { blob, nombreArchivo } = await generarBackend(project.id)
      descargarArchivo(blob, nombreArchivo)
    } catch (err) {
      setErrorGeneracion(getApiErrorMessage(err, 'No se pudo generar el backend'))
    } finally {
      setGenerandoBackend(false)
    }
  }

  // CU07 — el PDF se pide al backend (formato técnico: clases, atributos,
  // métodos, relaciones); la imagen se exporta enteramente en el navegador
  // capturando el lienzo de React Flow tal cual está, sin llamar al backend.
  const handleExportarReporte = async () => {
    setErrorReporte(null)
    if (getNodes().length === 0) {
      setErrorReporte(MENSAJE_SIN_CONTENIDO)
      return
    }

    setGenerandoReporte(true)
    try {
      if (formatoReporte === 'pdf') {
        const { blob, nombreArchivo } = await generarReportePdf(project.id)
        descargarArchivo(blob, nombreArchivo)
      } else {
        const viewportEl = document.querySelector('.react-flow__viewport') as HTMLElement | null
        if (!viewportEl) throw new Error('No se pudo capturar el lienzo')

        const ancho = 1400
        const alto = 900
        const bounds = getNodesBounds(getNodes())
        const viewport = getViewportForBounds(bounds, ancho, alto, 0.1, 2, 0.1)

        const dataUrl = await toPng(viewportEl, {
          backgroundColor: '#ffffff',
          width: ancho,
          height: alto,
          style: {
            width: `${ancho}px`,
            height: `${alto}px`,
            transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
          },
        })
        descargarDataUrl(dataUrl, `${slugNombreArchivo(project.nombre)}-reporte.png`)
      }
    } catch (err) {
      setErrorReporte(getApiErrorMessage(err, 'No se pudo exportar el reporte'))
    } finally {
      setGenerandoReporte(false)
    }
  }

  return (
    <header className="app-toolbar">
      <div className="app-toolbar__brand">
        <Link to="/" className="app-toolbar__back">
          ← Proyectos
        </Link>
        <span className="app-toolbar__divider" aria-hidden="true" />
        <span className="app-toolbar__project">{project.nombre}</span>
      </div>

      <div className="app-toolbar__group">
        <ToolButton primary icon={<IconPlus />} onClick={onNuevaClase}>
          Nueva clase
        </ToolButton>
        <ToolButton icon={<IconFit />} onClick={() => fitView({ padding: 0.25 })}>
          Ajustar vista
        </ToolButton>
        {esAdministrador && (
          <ToolButton icon={<IconUsers />} onClick={() => setMostrarColaboradores(true)}>
            Colaboradores
          </ToolButton>
        )}
        <ToolButton icon={<IconDownload />} disabled={generandoBackend} onClick={handleGenerarBackend}>
          {generandoBackend ? 'Generando…' : 'Generar backend'}
        </ToolButton>
        {esAdministrador && (
          <>
            <select
              className="app-toolbar__select"
              aria-label="Formato del reporte"
              value={formatoReporte}
              disabled={generandoReporte}
              onChange={(e) => setFormatoReporte(e.target.value as 'pdf' | 'imagen')}
            >
              <option value="pdf">PDF</option>
              <option value="imagen">Imagen</option>
            </select>
            <ToolButton icon={<IconDownload />} disabled={generandoReporte} onClick={handleExportarReporte}>
              {generandoReporte ? 'Exportando…' : 'Exportar reporte'}
            </ToolButton>
          </>
        )}
        {guardando && <span className="app-toolbar__guardando">Guardando…</span>}
        {!guardando && errorGuardado && (
          <span className="app-toolbar__error">
            {errorGuardado}
            <button type="button" className="app-toolbar__reintentar" onClick={onReintentarGuardado}>
              Reintentar
            </button>
          </span>
        )}
        {errorGeneracion && (
          <span className="app-toolbar__error">
            {errorGeneracion}
            <button type="button" className="app-toolbar__reintentar" onClick={() => setErrorGeneracion(null)}>
              Cerrar
            </button>
          </span>
        )}
        {errorReporte && (
          <span className="app-toolbar__error">
            {errorReporte}
            <button type="button" className="app-toolbar__reintentar" onClick={() => setErrorReporte(null)}>
              Cerrar
            </button>
          </span>
        )}
      </div>

      <div className="app-toolbar__user">
        {user && (
          <span className="app-toolbar__chip">
            <span className="app-toolbar__avatar" aria-hidden="true">
              {iniciales(user.nombre_completo)}
            </span>
            {user.nombre_completo}
          </span>
        )}
        <button type="button" className="app-toolbar__logout" onClick={handleLogout}>
          Salir
        </button>
      </div>

      {mostrarColaboradores && (
        <ColaboradoresModal proyectoId={project.id} onClose={() => setMostrarColaboradores(false)} />
      )}
    </header>
  )
}
