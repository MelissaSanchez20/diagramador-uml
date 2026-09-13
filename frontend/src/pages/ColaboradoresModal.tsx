import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import { agregarColaborador, listColaboradores, quitarColaborador } from '../api/colaboradores'
import { getApiErrorMessage, getApiErrorStatus } from '../api/errors'
import type { Colaborador } from '../api/types'
import { Banner } from '../components/ui/Banner'
import { Button } from '../components/ui/Button'
import { Modal } from '../components/ui/Modal'
import { TextField } from '../components/ui/TextField'
import { iniciales } from '../lib/format'

type Props = {
  proyectoId: number
  onClose: () => void
}

type Carga = 'cargando' | 'listo' | 'error'

export function ColaboradoresModal({ proyectoId, onClose }: Props) {
  const [carga, setCarga] = useState<Carga>('cargando')
  const [colaboradores, setColaboradores] = useState<Colaborador[]>([])
  const [cargaError, setCargaError] = useState<string | null>(null)

  const [email, setEmail] = useState('')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [quitandoId, setQuitandoId] = useState<number | null>(null)

  useEffect(() => {
    let alive = true
    listColaboradores(proyectoId)
      .then((data) => {
        if (!alive) return
        setColaboradores(data)
        setCarga('listo')
      })
      .catch((err) => {
        if (!alive) return
        setCargaError(getApiErrorMessage(err, 'No se pudieron cargar los colaboradores'))
        setCarga('error')
      })
    return () => {
      alive = false
    }
  }, [proyectoId])

  const recargar = () => {
    setCarga('cargando')
    listColaboradores(proyectoId)
      .then((data) => {
        setColaboradores(data)
        setCarga('listo')
      })
      .catch((err) => {
        setCargaError(getApiErrorMessage(err, 'No se pudieron cargar los colaboradores'))
        setCarga('error')
      })
  }

  const handleAgregar = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setEmailError(null)

    const emailLimpio = email.trim()
    if (!emailLimpio) {
      setEmailError('El email es obligatorio')
      return
    }

    setSubmitting(true)
    try {
      await agregarColaborador(proyectoId, emailLimpio)
      setEmail('')
      recargar()
    } catch (err) {
      const status = getApiErrorStatus(err)
      if (status === 404 || status === 409 || status === 400) {
        setEmailError(getApiErrorMessage(err))
      } else {
        setError(getApiErrorMessage(err))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleQuitar = async (colaborador: Colaborador) => {
    setError(null)
    setQuitandoId(colaborador.id)
    try {
      await quitarColaborador(proyectoId, colaborador.id)
      setColaboradores((actual) => actual.filter((c) => c.id !== colaborador.id))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setQuitandoId(null)
    }
  }

  return (
    <Modal title="Colaboradores del proyecto" onClose={onClose} footer={<Button onClick={onClose}>Cerrar</Button>}>
      <form className="modal-form colaborador-form" onSubmit={handleAgregar}>
        {error && <Banner>{error}</Banner>}
        <div className="colaborador-form-row">
          <TextField
            label="Agregar por email"
            type="email"
            required
            value={email}
            error={emailError ?? undefined}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button variant="primary" type="submit" loading={submitting}>
            Agregar
          </Button>
        </div>
      </form>

      {carga === 'cargando' && <p className="page__muted">Cargando colaboradores…</p>}
      {carga === 'error' && <Banner>{cargaError}</Banner>}
      {carga === 'listo' && colaboradores.length === 0 && (
        <p className="page__muted">Este proyecto todavía no tiene colaboradores.</p>
      )}

      {carga === 'listo' && colaboradores.length > 0 && (
        <ul className="proyecto-list">
          {colaboradores.map((c) => (
            <li key={c.id} className="proyecto-row">
              <div className="proyecto-row__info">
                <span className="app-toolbar__chip">
                  <span className="app-toolbar__avatar" aria-hidden="true">
                    {iniciales(c.usuario.nombre_completo)}
                  </span>
                  {c.usuario.nombre_completo}
                </span>
                <p className="proyecto-row__meta">{c.usuario.email}</p>
              </div>
              <div className="proyecto-row__actions">
                <Button variant="danger" loading={quitandoId === c.id} onClick={() => handleQuitar(c)}>
                  Quitar
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}
