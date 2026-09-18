import { useCallback, useEffect, useRef, useState } from 'react'

import { interpretarComandoVoz } from '../../api/comandosVoz'
import { getApiErrorMessage } from '../../api/errors'
import { aplicarAccionVoz } from './aplicarAccionVoz'
import type { useDiagrama } from './useDiagrama'

/**
 * CU11 — tipos mínimos de la Web Speech API (no vienen en el lib.dom.d.ts de
 * TypeScript). Solo se declara lo que se usa acá.
 */
interface SpeechRecognitionResultado {
  transcript: string
}
interface SpeechRecognitionEvento extends Event {
  results: { [index: number]: { [index: number]: SpeechRecognitionResultado } }
}
interface SpeechRecognitionErrorEvento extends Event {
  error: string
}
interface SpeechRecognitionInstancia extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  onresult: ((ev: SpeechRecognitionEvento) => void) | null
  onerror: ((ev: SpeechRecognitionErrorEvento) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionInstancia

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor
    webkitSpeechRecognition?: SpeechRecognitionConstructor
  }
}

const MENSAJES_ERROR_RECONOCIMIENTO: Record<string, string> = {
  'not-allowed': 'Se necesita permiso de micrófono para usar comandos de voz.',
  'service-not-allowed': 'Se necesita permiso de micrófono para usar comandos de voz.',
  'no-speech': 'No se detectó voz. Intenta de nuevo.',
  'audio-capture': 'No se encontró un micrófono disponible.',
}

function obtenerConstructorReconocimiento(): SpeechRecognitionConstructor | undefined {
  return window.SpeechRecognition ?? window.webkitSpeechRecognition
}

/** Frase corta hablada, best-effort: nunca debe romper el flujo si el
 * navegador no soporta síntesis de voz o no tiene voces instaladas. */
function hablar(mensaje: string): void {
  try {
    if (!window.speechSynthesis) return
    const utterance = new SpeechSynthesisUtterance(mensaje)
    utterance.lang = 'es-419'
    window.speechSynthesis.speak(utterance)
  } catch {
    // best-effort, sin fallback
  }
}

type Diagrama = ReturnType<typeof useDiagrama>

export function useComandoVoz(proyectoId: number, diagrama: Diagrama) {
  const [escuchando, setEscuchando] = useState(false)
  const [procesando, setProcesando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mensajeConfirmacion, setMensajeConfirmacion] = useState<string | null>(null)
  // Espejo siempre-actualizado de `diagrama`, para que `aplicarAccion` (que
  // se dispara desde el callback async de la API) lea el estado más
  // reciente -- mismo patrón que nodesRef/edgesRef en useDiagrama.ts.
  const diagramaRef = useRef(diagrama)
  useEffect(() => {
    diagramaRef.current = diagrama
  }, [diagrama])

  const soportado = obtenerConstructorReconocimiento() !== undefined

  const confirmarAccion = useCallback((mensaje: string) => {
    setMensajeConfirmacion(mensaje)
    hablar(mensaje)
  }, [])

  const aplicarAccion = useCallback((texto: string) => {
    setProcesando(true)
    setError(null)
    interpretarComandoVoz(proyectoId, texto)
      .then((resultado) => {
        aplicarAccionVoz(resultado, diagramaRef.current)
        confirmarAccion(resultado.resumen)
      })
      .catch((err) => {
        setError(getApiErrorMessage(err, 'No se pudo interpretar el comando de voz'))
      })
      .finally(() => setProcesando(false))
  }, [proyectoId, confirmarAccion])

  const iniciarEscucha = useCallback(() => {
    const Constructor = obtenerConstructorReconocimiento()
    if (!Constructor) {
      setError('Tu navegador no soporta reconocimiento de voz.')
      return
    }
    setError(null)
    setMensajeConfirmacion(null)

    const reconocimiento = new Constructor()
    reconocimiento.lang = 'es-419'
    reconocimiento.continuous = false
    reconocimiento.interimResults = false
    reconocimiento.maxAlternatives = 1

    reconocimiento.onresult = (ev) => {
      const texto = ev.results[0]?.[0]?.transcript?.trim()
      if (texto) aplicarAccion(texto)
      else setError('No se pudo escuchar, intenta de nuevo.')
    }
    reconocimiento.onerror = (ev) => {
      setError(MENSAJES_ERROR_RECONOCIMIENTO[ev.error] ?? 'No se pudo escuchar, intenta de nuevo.')
    }
    reconocimiento.onend = () => setEscuchando(false)

    setEscuchando(true)
    reconocimiento.start()
  }, [aplicarAccion])

  return {
    soportado,
    escuchando,
    procesando,
    error,
    mensajeConfirmacion,
    iniciarEscucha,
    cerrarError: () => setError(null),
    cerrarConfirmacion: () => setMensajeConfirmacion(null),
  }
}
