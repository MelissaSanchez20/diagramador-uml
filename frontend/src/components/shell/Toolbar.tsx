import { useState } from 'react'
import type { ReactNode } from 'react'
import { useReactFlow } from 'reactflow'
import { Link, useNavigate } from 'react-router-dom'

import { descargarArchivo, generarBackend } from '../../api/generacion'
import { getApiErrorMessage } from '../../api/errors'
import type { Proyecto } from '../../api/types'
import { useAuth } from '../../auth/useAuth'
import { iniciales } from '../../lib/format'
import { ColaboradoresModal } from '../../pages/ColaboradoresModal'

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
  const { fitView } = useReactFlow()
  const [mostrarColaboradores, setMostrarColaboradores] = useState(false)
  const [generandoBackend, setGenerandoBackend] = useState(false)
  const [errorGeneracion, setErrorGeneracion] = useState<string | null>(null)
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
