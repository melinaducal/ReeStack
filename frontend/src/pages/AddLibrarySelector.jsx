import { useNavigate } from 'react-router-dom'
import './AddLibrarySelector.css'

const types = [
  { id: 'paper', label: 'Paper', description: 'Artículos científicos y académicos' },
  { id: 'book', label: 'Libro', description: 'Novelas, ensayo, poesía y más' },
  { id: 'music', label: 'Disco', description: 'Álbumes, EPs y música' },
  { id: 'media', label: 'Serie / Película', description: 'Series, películas y documentales' }
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
