import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../services/api'
import './AddLibraryBrowse.css'

function AddLibraryBrowse() {
  const navigate = useNavigate()
  const location = useLocation()
  const type = location.state?.type || 'book'

  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedItem, setSelectedItem] = useState(null)
  const [pages, setPages] = useState('')
  const [rating, setRating] = useState('')
  const [thoughts, setThoughts] = useState('')
  const [visibility, setVisibility] = useState('public')

  const typeLabels = {
    paper: 'papers',
    book: 'libros',
    music: 'música',
    movie: 'películas',
    series: 'series'
  }

  const getPlaceholder = (t) => {
    const map = { book: 'L', movie: 'P', series: 'S', music: 'M', paper: 'A' }
    return map[t] || 'R'
  }

  const search = async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    setSelectedItem(null)
    try {
      const response = await api.get('/catalog/search', { params: { q: searchQuery, type } })
      setResults(response.data.results || [])
    } catch (error) {
      console.error('Error searching:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const selectItem = (item) => {
    setSelectedItem(item)
    setPages('')
    setRating('')
    setThoughts('')
    setVisibility('public')
  }

  const confirmAdd = async () => {
    if (!selectedItem) return
    try {
      const payload = {
        title: selectedItem.title,
        type: type,
        creator: selectedItem.creator || selectedItem.author || selectedItem.artist || '',
        year: selectedItem.year || selectedItem.first_publish_year || null,
        rating: rating !== '' ? parseInt(rating) : null,
        thoughts: thoughts || '',
        cover_url: selectedItem.cover_url || null,
        pages: type === 'book' && pages ? parseInt(pages) : null
      }
      const res = await api.post('/items', payload)
      const itemId = res.data.id
      navigate(`/item/${itemId}`)
    } catch (error) {
      console.error('Error adding item:', error)
    }
  }

  return (
    <div className="library-browse">
      <button onClick={() => navigate(-1)} className="back-button">← Volver</button>
      <header className="browse-header">
        <h1>Agregar {typeLabels[type]}</h1>
        <p className="browse-subtitle">Buscá por nombre, autor o artista</p>
      </header>

      {!selectedItem && (
        <>
          <div className="search-bar">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && search()}
              placeholder="Escribí el nombre, autor o artista..."
              className="search-input"
            />
            <button onClick={search} className="search-button">Buscar</button>
          </div>

          {loading && <p className="loading-text">Buscando...</p>}

          <div className="results-grid">
            {results.map((item, idx) => (
              <button
                key={item.id || idx}
                onClick={() => selectItem(item)}
                className="result-card"
              >
                {item.cover_url ? (
                  <img src={item.cover_url} alt={item.title} className="result-cover" />
                ) : (
                  <div className="result-cover-placeholder">
                    <span>{getPlaceholder(type)}</span>
                  </div>
                )}
                <div className="result-info">
                  <p className="result-title">{item.title}</p>
                  {(item.creator || item.author || item.artist) && (
                    <p className="result-author">{item.creator || item.author || item.artist}</p>
                  )}
                  {(item.year || item.first_publish_year) && (
                    <p className="result-year">{item.year || item.first_publish_year}</p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      {selectedItem && (
        <div className="confirm-panel">
          <div className="confirm-header">
            {selectedItem.cover_url ? (
              <img src={selectedItem.cover_url} alt={selectedItem.title} className="confirm-cover" />
            ) : (
              <div className="confirm-cover-placeholder">
                <span>{getPlaceholder(type)}</span>
              </div>
            )}
            <div className="confirm-info">
              <h2>{selectedItem.title}</h2>
              {(selectedItem.creator || selectedItem.author || selectedItem.artist) && (
                <p className="confirm-creator">{selectedItem.creator || selectedItem.author || selectedItem.artist}</p>
              )}
              {(selectedItem.year || selectedItem.first_publish_year) && (
                <p className="confirm-year">{selectedItem.year || selectedItem.first_publish_year}</p>
              )}
            </div>
          </div>

          <div className="confirm-form">
            <div className="confirm-row">
              <label>Puntuación (0-10)</label>
              <input type="number" min="0" max="10" value={rating} onChange={(e) => setRating(e.target.value)} />
            </div>
            {type === 'book' && (
              <div className="confirm-row">
                <label>Páginas</label>
                <input type="number" value={pages} onChange={(e) => setPages(e.target.value)} />
              </div>
            )}
            <div className="confirm-row">
              <label>Reseña</label>
              <textarea value={thoughts} onChange={(e) => setThoughts(e.target.value)} rows={4} />
            </div>
            <div className="confirm-row">
              <label>Visibilidad</label>
              <select value={visibility} onChange={(e) => setVisibility(e.target.value)}>
                <option value="public">Pública</option>
                <option value="private">Privada</option>
              </select>
            </div>
          </div>

          <div className="confirm-actions">
            <button onClick={() => setSelectedItem(null)} className="confirm-back">Volver a buscar</button>
            <button onClick={confirmAdd} className="confirm-save">Guardar y ver detalle</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default AddLibraryBrowse

