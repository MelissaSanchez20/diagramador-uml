type ClaseResumen = { id: string; nombre: string }

type Props = {
  clases: ClaseResumen[]
  seleccionadas: string[]
  onSeleccionar: (id: string) => void
  onCrear: () => void
}

function SectionHeader({ label, onAdd }: { label: string; onAdd?: () => void }) {
  return (
    <div className="sidebar__section-header">
      <span>{label}</span>
      {onAdd && (
        <button type="button" className="sidebar__add" aria-label={`Añadir a ${label}`} onClick={onAdd}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
            <path d="M6 2v8M2 6h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  )
}

export function Sidebar({ clases, seleccionadas, onSeleccionar, onCrear }: Props) {
  return (
    <aside className="app-sidebar">
      <div className="sidebar__section sidebar__section--grow">
        <SectionHeader label="Clases" onAdd={onCrear} />
        <ul className="sidebar__list">
          {clases.length === 0 && <li className="sidebar__empty">Sin clases todavía</li>}
          {clases.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={
                  seleccionadas.includes(c.id) ? 'sidebar__item sidebar__item--active' : 'sidebar__item'
                }
                onClick={() => onSeleccionar(c.id)}
              >
                {c.nombre || 'Sin nombre'}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="sidebar__section">
        <SectionHeader label="Diagramas" />
        <ul className="sidebar__list">
          <li>
            <button type="button" className="sidebar__item sidebar__item--sans sidebar__item--active">
              Diagrama de clases
            </button>
          </li>
        </ul>
      </div>
    </aside>
  )
}
