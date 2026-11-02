import { useNavigate } from 'react-router-dom'
import './AddLibrarySelector.css'

const types = [
  { id: 'book', label: 'Libro', description: 'Novelas, ensayo, poesía y más' },
  { id: 'movie', label: 'Película', description: 'Largometrajes, documentales' },
  { id: 'series', label: 'Serie', description: 'Series de TV y miniseries' },
  { id: 'music', label: 'Música', description: 'Álbumes, EPs y discos' },
  { id: 'paper', label: 'Paper', description: 'Artículos científicos y académicos' }
]

function AddLibrarySelector() {
  const navigate = useNavigate()

  const handleSelect = (type) => {
    navigate('/add-library/browse', { state: { type } })
  }

  return (
    <div className="library-selector">
      <button onClick={() => navigate(-1)} className="back-button">← Volver</button>
      <header className="selector-header">
        <h1>Agregar a mi biblioteca</h1>
        <p className="selector-subtitle">¿Qué querés agregar?</p>
      </header>
      <div className="type-grid">
        {types.map(type => (
          <button
            key={type.id}
            onClick={() => handleSelect(type.id)}
            className="type-card"
          >
            <h3>{type.label}</h3>
            <p>{type.description}</p>
          </button>
        ))}
      </div>
    </div>
  )
}

export default AddLibrarySelector
