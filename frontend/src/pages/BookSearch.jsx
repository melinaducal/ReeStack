import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import './BookSearch.css'

const genres = [
  'Ficción', 'Romance', 'Misterio', 'Fantasía', 'Ciencia Ficción',
  'Terror', 'Histórico', 'Biografía', 'Autoayuda', 'Poesía',
  'Thriller', 'Aventura', 'Drama', 'Infantil', 'Juvenil'
]

function BookSearch() {
  const navigate = useNavigate()
  const [selectedGenres, setSelectedGenres] = useState([])
  const [step, setStep] = useState(1)
  const [books, setBooks] = useState([])
  const [loading, setLoading] = useState(false)
  const [userItems, setUserItems] = useState([])
  const [adding, setAdding] = useState({})
  const [searchQuery, setSearchQuery] = useState('')
  const [mode, setMode] = useState('genre')

  useEffect(() => {
    fetchUserItems()
  }, [])

  const fetchUserItems = async () => {
    try {
      const response = await api.get('/items', { params: { mine: true, include_posts: false } })
      setUserItems(response.data || [])
    } catch (error) {
      console.error('Error fetching user items:', error)
    }
  }

  const isInLibrary = (title) => {
    if (!title) return false
    return userItems.some(item => item.title && item.title.toLowerCase() === title.toLowerCase())
  }

  const toggleGenre = (genre) => {
    setSelectedGenres(prev => 
      prev.includes(genre) 
        ? prev.filter(g => g !== genre)
        : [...prev, genre]
    )
  }

  const handleNext = async () => {
    setLoading(true)
    setStep(2)
    try {
      if (mode === 'search' && searchQuery.trim()) {
        const response = await api.get('/books/search', {
          params: {
            q: searchQuery.trim()
          }
        })
        setBooks(response.data.results || [])
      } else if (selectedGenres.length > 0) {
        const response = await api.get('/books/search', {
          params: {
            genres: selectedGenres.join(','),
            mode: 'or'
          }
        })
        setBooks(response.data.results || [])
      } else {
        setBooks([])
      }
    } catch (error) {
      console.error('Error fetching books:', error)
      setBooks([])
    } finally {
      setLoading(false)
    }
  }

  const addBook = async (book) => {
    const title = book.title
    if (!title) return
    if (isInLibrary(title)) {
      return
    }
    setAdding(prev => ({ ...prev, [title]: true }))
    try {
      const authors = Array.isArray(book.authors) ? book.authors.join(', ') : book.authors || ''
      const year = book.published_date ? parseInt(String(book.published_date).substring(0, 4)) : null
      await api.post('/items', {
        title: title,
        type: 'book',
        creator: authors,
        year: isNaN(year) ? null : year,
        rating: null,
        thoughts: book.description || '',
        cover_url: book.cover_url || null
      })
      await fetchUserItems()
    } catch (error) {
      console.error('Error adding book:', error)
    } finally {
      setAdding(prev => ({ ...prev, [title]: false }))
    }
  }

  return (
    <div className="book-search">
      {step === 1 && (
        <div className="genre-step">
          <header className="search-header">
            <h1>Buscar libros</h1>
            <p className="search-subtitle">Buscá por nombre o seleccioná géneros</p>
          </header>
          <div className="search-mode">
            <button onClick={() => setMode('search')} className={mode === 'search' ? 'active' : ''}>Buscar por nombre</button>
            <button onClick={() => setMode('genre')} className={mode === 'genre' ? 'active' : ''}>Buscar por género</button>
          </div>
          {mode === 'search' && (
            <div className="search-bar">
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Título, autor o palabra clave"
                onKeyDown={(e) => e.key === 'Enter' && handleNext()}
              />
              <button onClick={handleNext} disabled={!searchQuery.trim()}>Buscar</button>
            </div>
          )}
          {mode === 'genre' && (
            <>
              <div className="genres-grid">
                {genres.map(genre => (
                  <button
                    key={genre}
                    onClick={() => toggleGenre(genre)}
                    className={`genre-button ${selectedGenres.includes(genre) ? 'selected' : ''}`}
                  >
                    {genre}
                  </button>
                ))}
              </div>
              <button 
                onClick={handleNext} 
                className="next-button"
                disabled={selectedGenres.length === 0}
              >
                Siguiente
              </button>
            </>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="results-step">
          <header className="search-header">
            <h1>Libros recomendados</h1>
            <p className="search-subtitle">Selecciona los libros que quieras agregar a tu stack</p>
          </header>
          {loading ? (
            <p className="loading">Buscando libros...</p>
          ) : books.length === 0 ? (
            <p className="loading">No encontramos libros para esos géneros. Probá con otros o con un solo género.</p>
          ) : (
            <div className="books-grid">
              {books.map((book, idx) => {
                const title = book.title
                const authors = Array.isArray(book.authors) ? book.authors.join(', ') : book.authors
                const genres = Array.isArray(book.genres) ? book.genres.join(', ') : book.genres
                const inLib = isInLibrary(title)
                return (
                  <div key={book.isbn || title || idx} className="book-card">
                    {book.cover_url && (
                      <img 
                        src={book.cover_url} 
                        alt={title}
                        className="book-cover"
                      />
                    )}
                    <div className="book-info">
                      <h3>{title}</h3>
                      {authors && <p className="book-author">{authors}</p>}
                      {genres && <p className="book-author">{genres}</p>}
                      <button 
                        onClick={() => addBook(book)} 
                        className="add-book-button"
                        disabled={inLib || adding[title]}
                      >
                        {inLib ? 'Ya en mi biblioteca' : (adding[title] ? 'Agregando...' : 'Agregar a mi biblioteca')}
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default BookSearch
