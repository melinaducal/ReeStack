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

  useEffect(() => {
    fetchUserItems()
  }, [])

  const fetchUserItems = async () => {
    try {
      const response = await api.get('/items', { params: { mine: true } })
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
    if (selectedGenres.length === 0) return
    setLoading(true)
    setStep(2)
    try {
      const response = await api.get('/books/search', {
        params: {
          genres: selectedGenres.join(','),
          mode: 'or'
        }
      })
      setBooks(response.data.results || [])
    } catch (error) {
      console.error('Error fetching books:', error)
      setBooks([])
    }
    setLoading(false)
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
            <h1>Buscar libros por género</h1>
            <p className="search-subtitle">Selecciona uno o varios géneros para encontrar libros</p>
          </header>
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
