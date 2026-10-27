import { useState } from 'react'
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
      const query = selectedGenres.join('+')
      const response = await fetch(
        `https://www.googleapis.com/books/v1/volumes?q=subject:${query}&maxResults=20&langRestrict=es`
      )
      const data = await response.json()
      setBooks(data.items || [])
    } catch (error) {
      console.error('Error fetching books:', error)
    }
    setLoading(false)
  }

  const addBook = async (book) => {
    const volumeInfo = book.volumeInfo
    try {
      await api.post('/items', {
        title: volumeInfo.title,
        type: 'book',
        creator: volumeInfo.authors?.join(', ') || '',
        year: volumeInfo.publishedDate ? parseInt(volumeInfo.publishedDate.substring(0, 4)) : null,
        rating: null,
        thoughts: ''
      })
      navigate('/')
    } catch (error) {
      console.error('Error adding book:', error)
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
          ) : (
            <div className="books-grid">
              {books.map(book => {
                const volumeInfo = book.volumeInfo
                return (
                  <div key={book.id} className="book-card">
                    {volumeInfo.imageLinks?.thumbnail && (
                      <img 
                        src={volumeInfo.imageLinks.thumbnail} 
                        alt={volumeInfo.title}
                        className="book-cover"
                      />
                    )}
                    <div className="book-info">
                      <h3>{volumeInfo.title}</h3>
                      {volumeInfo.authors && <p className="book-author">{volumeInfo.authors.join(', ')}</p>}
                      <button onClick={() => addBook(book)} className="add-book-button">
                        Agregar a mi stack
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
