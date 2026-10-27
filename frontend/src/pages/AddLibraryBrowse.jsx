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
  const [selectedBook, setSelectedBook] = useState(null)
  const [pages, setPages] = useState('')

  const typeLabels = {
    paper: 'papers',
    book: 'libros',
    music: 'discos',
    media: 'series/películas'
  }

  const search = async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    setSelectedBook(null)
    try {
      if (type === 'book') {
        const response = await fetch(
          `https://openlibrary.org/search.json?q=${encodeURIComponent(searchQuery)}&limit=20`
        )
        const data = await response.json()
        setResults(data.docs || [])
      } else {
        setResults([
          { key: '1', title: `${searchQuery} - Ejemplo`, author_name: ['Autor Ejemplo'] },
          { key: '2', title: `${searchQuery} (variante)`, author_name: ['Artista Ejemplo'] }
        ])
      }
    } catch (error) {
      console.error('Error searching:', error)
    }
    setLoading(false)
  }

  const selectBook = async (book) => {
    if (type === 'book') {
      setSelectedBook(book)
      setPages('')
    } else {
      addItem(book)
    }
  }

  const addBook = async () => {
    try {
      const book = selectedBook
      const coverId = book.cover_i
      const coverUrl = coverId 
        ? `https://covers.openlibrary.org/b/id/${coverId}-M.jpg`
        : 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&h=300&fit=crop'
      
      await api.post('/items', {
        title: book.title,
        type: 'book',
        creator: book.author_name?.join(', ') || '',
        year: book.first_publish_year || null,
        rating: null,
        thoughts: '',
        cover_url: coverUrl,
        pages: pages ? parseInt(pages) : null
      })
      navigate('/')
    } catch (error) {
      console.error('Error adding item:', error)
    }
  }

  const addItem = async (item) => {
    try {
      if (type === 'book') {
        const coverUrl = item.cover_i 
          ? `https://covers.openlibrary.org/b/id/${item.cover_i}-M.jpg`
          : 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&h=300&fit=crop'
        await api.post('/items', {
          title: item.title,
          type: 'book',
          creator: item.author_name?.join(', ') || '',
          year: item.first_publish_year || null,
          rating: null,
          thoughts: '',
          cover_url: coverUrl,
          pages: null
        })
      } else {
        await api.post('/items', {
          title: item.title || searchQuery,
          type: type === 'media' ? 'series' : type,
          creator: item.author_name?.join(', ') || '',
          year: null,
          rating: null,
          thoughts: ''
        })
      }
      navigate('/')
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

      {!selectedBook && (
        <>
          <div className="search-bar">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && search()}
              placeholder="Escribí el nombre del libro, autor o artista..."
              className="search-input"
            />
            <button onClick={search} className="search-button">Buscar</button>
          </div>

          {loading && <p className="loading-text">Buscando...</p>}

          <div className="results-grid">
            {results.map((item, idx) => {
              const coverId = item.cover_i
              const coverUrl = coverId 
                ? `https://covers.openlibrary.org/b/id/${coverId}-M.jpg`
                : 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&h=300&fit=crop'
              return (
                <button
                  key={item.key || idx}
                  onClick={() => selectBook(item)}
                  className="result-card"
                >
                  <img src={coverUrl} alt={item.title} className="result-cover" />
                  <div className="result-info">
                    <p className="result-title">{item.title}</p>
                    {item.author_name && <p className="result-author">{item.author_name.join(', ')}</p>}
                  </div>
                </button>
              )
            })}
          </div>
        </>
      )}

      {selectedBook && type === 'book' && (
        <div className="book-details">
          <div className="book-details-header">
            <img 
              src={selectedBook.cover_i 
                ? `https://covers.openlibrary.org/b/id/${selectedBook.cover_i}-L.jpg`
                : 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&h=300&fit=crop'
              } 
              alt={selectedBook.title} 
              className="book-details-cover"
            />
            <div className="book-details-info">
              <h2>{selectedBook.title}</h2>
              {selectedBook.author_name && <p className="book-details-author">{selectedBook.author_name.join(', ')}</p>}
              {selectedBook.first_publish_year && <p className="book-details-year">{selectedBook.first_publish_year}</p>}
            </div>
          </div>
          <div className="pages-input-section">
            <label>Cantidad de páginas (opcional)</label>
            <input
              type="number"
              value={pages}
              onChange={(e) => setPages(e.target.value)}
              placeholder="Ingresar cantidad de páginas"
              className="pages-input"
            />
          </div>
          <div className="book-details-actions">
            <button onClick={() => setSelectedBook(null)} className="back-to-search">Volver a buscar</button>
            <button onClick={addBook} className="add-book-confirm">Agregar a Mi Stack</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default AddLibraryBrowse
