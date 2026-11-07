import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import StarRating from '../components/StarRating'
import './ExploreAdd.css'

const TYPES = [
  { id: 'book', label: 'Libros' },
  { id: 'movie', label: 'Películas' },
  { id: 'series', label: 'Series' },
  { id: 'music', label: 'Música' },
  { id: 'paper', label: 'Papers' }
]

const TYPE_LABELS = {
  book: 'Libro',
  movie: 'Película',
  series: 'Serie',
  music: 'Música',
  paper: 'Paper'
}

const GENRES = [
  'Ficción', 'Romance', 'Misterio', 'Fantasía', 'Ciencia Ficción',
  'Terror', 'Histórico', 'Biografía', 'Autoayuda', 'Poesía',
  'Thriller', 'Aventura', 'Drama', 'Infantil', 'Juvenil'
]

const getPlaceholder = (t) => ({ book: 'L', movie: 'P', series: 'S', music: 'M', paper: 'A' }[t] || 'R')

const getItemGenres = (item) => {
  if (!item) return []
  if (Array.isArray(item.genres)) return item.genres.filter(Boolean)
  if (typeof item.genres === 'string') {
    return item.genres.split(',').map((genre) => genre.trim()).filter(Boolean)
  }
  return []
}

function ExploreAdd() {
  const navigate = useNavigate()
  const [type, setType] = useState('book')
  const [mode, setMode] = useState('search') // search | genre (books)
  const [query, setQuery] = useState('')
  const [selectedGenres, setSelectedGenres] = useState([])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedItem, setSelectedItem] = useState(null)
  const [pages, setPages] = useState('')
  // 0-10 contract in form state (4.5 stars = 9/10); converted to 1-5 for backend on save.
  const [rating, setRating] = useState(null)
  const [thoughts, setThoughts] = useState('')
  const [isPublic, setIsPublic] = useState(true)
  const [userItems, setUserItems] = useState([])
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const redirectTimer = useRef(null)

  useEffect(() => {
    fetchUserItems()
  }, [])

  useEffect(() => {
    if (type !== 'book') setMode('search')
    setResults([])
    setSelectedItem(null)
    setRating(null)
    setError('')
    setSaved(false)
  }, [type])

  useEffect(() => () => {
    if (redirectTimer.current) clearTimeout(redirectTimer.current)
  }, [])

  const fetchUserItems = async () => {
    try {
      const res = await api.get('/items', { params: { mine: true, include_posts: false } })
      setUserItems(res.data || [])
    } catch (e) {
      // ignore
    }
  }

  const isInLibrary = (title) => {
    if (!title) return false
    return userItems.some(item => item.title && item.title.toLowerCase() === title.toLowerCase() && item.type === type)
  }

  const toggleGenre = (g) => {
    setSelectedGenres(prev => prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g])
  }

  const runSearch = async () => {
    setError('')
    setSelectedItem(null)
    if (mode === 'genre' && type === 'book') {
      if (selectedGenres.length === 0) return
      setLoading(true)
      try {
        const res = await api.get('/books/search', { params: { genres: selectedGenres.join(','), mode: 'or' } })
        setResults(res.data.results || [])
      } catch (e) {
        setError('No se pudo buscar por género')
        setResults([])
      } finally {
        setLoading(false)
      }
      return
    }
    if (!query.trim() || query.trim().length < 2) {
      setError('Escribí al menos 2 caracteres para buscar')
      return
    }
    setLoading(true)
    try {
      const res = await api.get('/catalog/search', { params: { q: query.trim(), type } })
      setResults(res.data.results || [])
    } catch (e) {
      setError(e.response?.data?.detail || 'No se pudo buscar')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const selectItem = (item) => {
    if (isInLibrary(item.title)) return
    setSelectedItem(item)
    setPages('')
    setRating(null)
    setThoughts(item.description || '')
    setIsPublic(true)
    setError('')
    setSaved(false)
  }

  const confirmAdd = async () => {
    if (!selectedItem) return
    if (isInLibrary(selectedItem.title)) return
    if (saving || saved) return
    setSaving(true)
    setError('')
    try {
      const payload = {
        title: selectedItem.title,
        type,
        creator: selectedItem.creator || selectedItem.author || selectedItem.artist || null,
        year: selectedItem.year || selectedItem.first_publish_year || null,
        // 0-10 contract in UI: 4.5 stars = 9/10. Backend stores 1-5 stars (fractions allowed).
        rating: rating != null ? rating / 2 : null,
        thoughts: thoughts || null,
        cover_url: selectedItem.cover_url || null,
        pages: type === 'book' && pages ? parseInt(pages) : null,
        is_public: isPublic
      }
      const res = await api.post('/items', payload)
      await fetchUserItems()
      setSaved(true)
      redirectTimer.current = setTimeout(() => {
        navigate(`/item/${res.data.id}`)
      }, 700)
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(
        Array.isArray(detail)
          ? 'No se pudo guardar la obra. Revisá los datos ingresados.'
          : detail || 'No se pudo guardar la obra. Intentá de nuevo.'
      )
      setSaving(false)
    }
  }

  const backToSearch = () => {
    if (saving || saved) return
    setSelectedItem(null)
    setError('')
  }

  const itemGenres = getItemGenres(selectedItem)
  const description = (selectedItem?.description || '').trim()
  const year = selectedItem ? (selectedItem.year || selectedItem.first_publish_year) : null
  const creator = selectedItem
    ? (selectedItem.creator || selectedItem.author || selectedItem.artist)
    : null

  return (
    <div className="explore-add">
      <header className="explore-add-header">
        <h1>Buscar y agregar</h1>
        <p>Buscá contenido y sumalo a tu biblioteca</p>
      </header>

      <div className="explore-add-types" role="tablist" aria-label="Tipo de contenido">
        {TYPES.map(t => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={type === t.id}
            className={`explore-type-btn ${type === t.id ? 'active' : ''}`}
            onClick={() => setType(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!selectedItem && (
        <>
          {type === 'book' && (
            <div className="explore-modes">
              <button type="button" className={mode === 'search' ? 'active' : ''} onClick={() => setMode('search')}>Por nombre</button>
              <button type="button" className={mode === 'genre' ? 'active' : ''} onClick={() => setMode('genre')}>Por género</button>
            </div>
          )}

          {mode === 'genre' && type === 'book' ? (
            <div className="explore-genre-block">
              <div className="explore-genres">
                {GENRES.map(g => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => toggleGenre(g)}
                    className={`explore-genre-btn ${selectedGenres.includes(g) ? 'selected' : ''}`}
                  >
                    {g}
                  </button>
                ))}
              </div>
              <button type="button" className="explore-search-btn" onClick={runSearch} disabled={selectedGenres.length === 0 || loading}>
                {loading ? 'Buscando...' : 'Buscar'}
              </button>
            </div>
          ) : (
            <div className="explore-search-bar">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runSearch()}
                placeholder="Título, autor, artista..."
                aria-label="Buscar"
              />
              <button type="button" className="explore-search-btn" onClick={runSearch} disabled={loading}>
                {loading ? 'Buscando...' : 'Buscar'}
              </button>
            </div>
          )}

          {error && <p className="explore-error">{error}</p>}
          {loading && <p className="explore-state">Buscando...</p>}

          <div className="explore-results">
            {results.map((item, idx) => {
              const inLib = isInLibrary(item.title)
              return (
                <button
                  key={item.external_id || item.id || `${item.title}-${idx}`}
                  type="button"
                  className={`explore-result-card ${inLib ? 'in-library' : ''}`}
                  onClick={() => selectItem(item)}
                  disabled={inLib}
                >
                  {item.cover_url ? (
                    <img src={item.cover_url} alt={item.title} className="explore-result-cover" />
                  ) : (
                    <div className="explore-result-cover placeholder"><span>{getPlaceholder(type)}</span></div>
                  )}
                  <div className="explore-result-info">
                    <p className="explore-result-title">{item.title}</p>
                    {(item.creator || item.author || item.artist) && (
                      <p className="explore-result-creator">{item.creator || item.author || item.artist}</p>
                    )}
                    {(item.year || item.first_publish_year) && (
                      <p className="explore-result-year">{item.year || item.first_publish_year}</p>
                    )}
                    {inLib && <span className="explore-in-lib">Ya está en tu biblioteca</span>}
                  </div>
                </button>
              )
            })}
          </div>
        </>
      )}

      {selectedItem && (
        <div className="explore-confirm">
          <div className="explore-confirm-header">
            <div className="explore-confirm-cover-wrap">
              {selectedItem.cover_url ? (
                <img src={selectedItem.cover_url} alt={selectedItem.title} className="explore-confirm-cover" />
              ) : (
                <div className="explore-confirm-cover placeholder"><span>{getPlaceholder(type)}</span></div>
              )}
            </div>
            <div className="explore-confirm-info">
              <span className="explore-confirm-type">{TYPE_LABELS[type] || 'Obra'}</span>
              <h2 className="explore-confirm-title">{selectedItem.title}</h2>
              {creator && <p className="explore-confirm-creator">{creator}</p>}
              <div className="explore-confirm-meta">
                {year && <span className="explore-confirm-year">{year}</span>}
                {itemGenres.map((genre) => (
                  <span className="explore-confirm-genre-chip" key={genre}>{genre}</span>
                ))}
              </div>
              {description && (
                <p className="explore-confirm-synopsis">{description}</p>
              )}
            </div>
          </div>

          {error && <p className="explore-error" role="alert">{error}</p>}

          <div className="explore-confirm-form">
            <div className="explore-field explore-field--full">
              <span className="explore-field-label">Tu puntuación</span>
              <StarRating
                value={rating}
                onChange={setRating}
                scale={10}
                min={1}
                disabled={saving || saved}
                ariaLabel="Tu puntuación de 0 a 10"
              />
            </div>

            {type === 'book' && (
              <div className="explore-field">
                <label className="explore-field-label" htmlFor="explore-pages">Cantidad de páginas</label>
                <input
                  id="explore-pages"
                  type="number"
                  min="1"
                  inputMode="numeric"
                  value={pages}
                  onChange={(e) => setPages(e.target.value)}
                  disabled={saving || saved}
                  placeholder="Opcional"
                />
              </div>
            )}

            <div className="explore-field explore-field--full">
              <label className="explore-field-label" htmlFor="explore-thoughts">Reseña personal</label>
              <textarea
                id="explore-thoughts"
                value={thoughts}
                onChange={(e) => setThoughts(e.target.value)}
                rows={5}
                disabled={saving || saved}
                placeholder="¿Qué te pareció esta obra? Compartí tus impresiones..."
              />
            </div>

            <div className="explore-field explore-field--full">
              <span className="explore-field-label">Visibilidad</span>
              <label className="explore-visibility" htmlFor="explore-visibility">
                <input
                  id="explore-visibility"
                  type="checkbox"
                  checked={isPublic}
                  onChange={(e) => setIsPublic(e.target.checked)}
                  disabled={saving || saved}
                />
                <span className="explore-visibility-text">
                  <span className="explore-visibility-title">{isPublic ? 'Pública' : 'Privada'}</span>
                  <span className="explore-visibility-hint">
                    {isPublic
                      ? 'Visible en tu perfil y en el feed.'
                      : 'Solo vos podés verla.'}
                  </span>
                </span>
              </label>
            </div>
          </div>

          {saved && (
            <p className="explore-confirm-success" role="status">
              Guardado en tu stack. Abriendo el detalle…
            </p>
          )}

          <div className="explore-confirm-actions">
            <button
              type="button"
              className="explore-btn secondary"
              onClick={backToSearch}
              disabled={saving || saved}
            >
              Volver a buscar
            </button>
            <button
              type="button"
              className="explore-btn primary"
              onClick={confirmAdd}
              disabled={saving || saved}
            >
              {saved ? 'Guardado ✓' : saving ? 'Guardando...' : 'Guardar en Mi Stack'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExploreAdd
