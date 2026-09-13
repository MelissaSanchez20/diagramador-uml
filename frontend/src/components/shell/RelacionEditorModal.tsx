import { useState } from 'react'
import type { FormEvent } from 'react'

import type { TipoRelacion } from '../../api/types'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'
import { TextField } from '../ui/TextField'
import type { DetallesRelacion } from './useDiagrama'
import './diagramModals.css'
import { OPCIONES_MULTIPLICIDAD, OPCIONES_TIPO_RELACION } from './umlFormat'

type Props = {
  titulo: string
  valorInicial: DetallesRelacion
  onClose: () => void
  onGuardar: (detalles: DetallesRelacion) => void
  onEliminar?: () => void
}

export function RelacionEditorModal({ titulo, valorInicial, onClose, onGuardar, onEliminar }: Props) {
  const [tipo, setTipo] = useState<TipoRelacion>(valorInicial.tipo)
  const [etiqueta, setEtiqueta] = useState(valorInicial.etiqueta ?? '')
  const [multOrigen, setMultOrigen] = useState(valorInicial.multiplicidad_origen ?? '')
  const [multDestino, setMultDestino] = useState(valorInicial.multiplicidad_destino ?? '')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onGuardar({
      tipo,
      etiqueta: etiqueta.trim() || null,
      multiplicidad_origen: multOrigen.trim() || null,
      multiplicidad_destino: multDestino.trim() || null,
    })
    onClose()
  }

  const handleEliminar = () => {
    if (window.confirm('¿Eliminar esta relación?')) {
      onEliminar?.()
      onClose()
    }
  }

  return (
    <Modal
      title={titulo}
      onClose={onClose}
      footer={
        <>
          {onEliminar && (
            <Button variant="danger" onClick={handleEliminar}>
              Eliminar relación
            </Button>
          )}
          <Button onClick={onClose}>Cancelar</Button>
          <Button variant="primary" form="relacion-form" type="submit">
            Guardar
          </Button>
        </>
      }
    >
      <form id="relacion-form" className="modal-form" onSubmit={handleSubmit}>
        <div className="field">
          <label className="field__label" htmlFor="relacion-tipo">
            Tipo de relación
          </label>
          <select
            id="relacion-tipo"
            className="field__input"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoRelacion)}
          >
            {OPCIONES_TIPO_RELACION.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <TextField
          label="Etiqueta"
          placeholder="ej. administra"
          maxLength={100}
          value={etiqueta}
          onChange={(e) => setEtiqueta(e.target.value)}
        />

        <div className="relacion-form__multiplicidades">
          <div className="field">
            <label className="field__label" htmlFor="relacion-mult-origen">
              Multiplicidad origen
            </label>
            <select
              id="relacion-mult-origen"
              className="field__input"
              value={multOrigen}
              onChange={(e) => setMultOrigen(e.target.value)}
            >
              {OPCIONES_MULTIPLICIDAD.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="relacion-mult-destino">
              Multiplicidad destino
            </label>
            <select
              id="relacion-mult-destino"
              className="field__input"
              value={multDestino}
              onChange={(e) => setMultDestino(e.target.value)}
            >
              {OPCIONES_MULTIPLICIDAD.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </form>
    </Modal>
  )
}
