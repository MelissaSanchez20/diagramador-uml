export type RolUsuario = 'ADMINISTRADOR' | 'COLABORADOR'

export type Usuario = {
  id: number
  nombre_completo: string
  email: string
  rol: RolUsuario
  fecha_registro: string
}

export type PerfilUpdate = {
  nombre_completo?: string
  email?: string
  password_actual?: string
  password_nuevo?: string
}

export type Proyecto = {
  id: number
  nombre: string
  descripcion: string | null
  id_administrador: number
  fecha_creacion: string
  rol_en_proyecto: RolUsuario
}

export type ProyectoInput = {
  nombre: string
  descripcion?: string | null
}

export type RegistroInput = {
  nombre_completo: string
  email: string
  password: string
}

export type Colaborador = {
  id: number
  id_proyecto: number
  id_usuario: number
  fecha_asignacion: string
  activo: boolean
  usuario: Usuario
}

export type Token = {
  access_token: string
  token_type: string
}

export type Visibilidad = 'PUBLICO' | 'PRIVADO' | 'PROTEGIDO' | 'PAQUETE'
export type TipoRelacion = 'ASOCIACION' | 'HERENCIA' | 'AGREGACION' | 'COMPOSICION'

export type AtributoUml = {
  id: string
  nombre: string
  tipo: string | null
  visibilidad: Visibilidad
  orden: number
}

export type MetodoUml = {
  id: string
  nombre: string
  parametros: string | null
  tipo_retorno: string | null
  visibilidad: Visibilidad
  orden: number
}

export type ClaseUml = {
  id: string
  nombre: string
  estereotipo: string | null
  es_abstracta: boolean
  pos_x: number
  pos_y: number
  atributos: AtributoUml[]
  metodos: MetodoUml[]
}

export type RelacionUml = {
  id: string
  id_clase_origen: string
  id_clase_destino: string
  tipo: TipoRelacion
  etiqueta: string | null
  multiplicidad_origen: string | null
  multiplicidad_destino: string | null
  handle_origen: string | null
  handle_destino: string | null
}

export type DiagramaData = {
  clases: ClaseUml[]
  relaciones: RelacionUml[]
}
