import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import api from '../services/api'
import StarRating from '../components/StarRating'
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
  // UI contract 0-10 (4.5★ = 9/10). Backend (verified: ItemCreate.rating) accepts 1-5 stars; convert /2 on save.
  const [rating, setRating] = useState(null)
  const [thoughts, setThoughts] = useState('')
  const [visibility, setVisibility] = useState('public')
  const [saving, setSaving] = useState(false)

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
    setRating(null)
    setThoughts('')
    setVisibility('public')
  }

  const confirmAdd = async () => {
    if (!selectedItem || saving) return
    setSaving(true)
    try {
      const payload = {
        title: selectedItem.title,
        type: type,
        creator: selectedItem.creator || selectedItem.author || selectedItem.artist || '',
        year: selectedItem.year || selectedItem.first_publish_year || null,
        rating: rating != null ? rating / 2 : null,
        thoughts: thoughts || '',
        cover_url: selectedItem.cover_url || null,
        pages: type === 'book' && pages ? parseInt(pages) : null,
        is_public: visibility === 'public'
      }
      const res = await api.post('/items', payload)
      const itemId = res.data.id
      navigate(`/item/${itemId}`)
    } catch (error) {
      console.error('Error adding item:', error)
      setSaving(false)
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
            <div className="confirm-row confirm-row--full">
              <span className="confirm-label">Tu puntuación</span>
              <StarRating
                value={rating}
                onChange={setRating}
                scale={10}
                min={1}
                disabled={saving}
                ariaLabel="Tu puntuación de 0 a 10"
              />
            </div>
            {type === 'book' && (
              <div className="confirm-row">
                <label className="confirm-label" htmlFor="alb-pages">Páginas</label>
                <input id="alb-pages" type="number" min="1" inputMode="numeric" value={pages} onChange={(e) => setPages(e.target.value)} disabled={saving} placeholder="Opcional" />
              </div>
            )}
            <div className="confirm-row confirm-row--full">
              <label className="confirm-label" htmlFor="alb-thoughts">Reseña personal</label>
              <textarea id="alb-thoughts" value={thoughts} onChange={(e) => setThoughts(e.target.value)} rows={5} disabled={saving} placeholder="¿Qué te pareció esta obra? Compartí tus impresiones..." />
            </div>
            <div className="confirm-row confirm-row--full">
              <label className="confirm-label" htmlFor="alb-visibility">Visibilidad</label>
              <select id="alb-visibility" value={visibility} onChange={(e) => setVisibility(e.target.value)} disabled={saving}>
                <option value="public">Pública</option>
                <option value="private">Privada</option>
              </select>
            </div>
          </div>

          <div className="confirm-actions">
            <button type="button" onClick={() => !saving && setSelectedItem(null)} className="confirm-back" disabled={saving}>Volver a buscar</button>
            <button type="button" onClick={confirmAdd} className="confirm-save" disabled={saving}>{saving ? 'Guardando...' : 'Guardar en Mi Stack'}</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default AddLibraryBrowse

