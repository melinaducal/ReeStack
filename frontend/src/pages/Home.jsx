import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './Home.css'

function Home() {
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    fetchItems()
  }, [filter])

  const fetchItems = async () => {
    try {
      const params = filter !== 'all' ? { type: filter, mine: true } : { mine: true }
      const response = await api.get('/items', { params })
      setItems(response.data)
    } catch (error) {
      console.error('Error fetching items:', error)
    }
  }

  return (
    <div className="home">
      <header className="home-header">
        <h1>Mi Stack</h1>
        <p className="home-subtitle">Tu colección</p>
      </header>
      <div className="filters">
        <button onClick={() => setFilter('all')} className={filter === 'all' ? 'active' : ''}>Todos</button>
        <button onClick={() => setFilter('book')} className={filter === 'book' ? 'active' : ''}>Libros</button>
        <button onClick={() => setFilter('movie')} className={filter === 'movie' ? 'active' : ''}>Películas</button>
        <button onClick={() => setFilter('series')} className={filter === 'series' ? 'active' : ''}>Series</button>
        <button onClick={() => setFilter('music')} className={filter === 'music' ? 'active' : ''}>Música</button>
        <button onClick={() => setFilter('paper')} className={filter === 'paper' ? 'active' : ''}>Papers</button>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">
          <p className="empty-message">Aún no hay nada aquí... es hora de llenar tu biblioteca con historias que te marquen.</p>
          <Link to="/add" className="empty-button">Agregar mi primer contenido</Link>
        </div>
      ) : (
        <div className="items-grid">
          {items.map(item => (
            <Link to={`/item/${item.id}`} key={item.id} className="item-card">
              <h3>{item.title}</h3>
              <p className="item-type">{item.type}</p>
              {item.rating && <p className="item-rating">★ {item.rating}/10</p>}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export default Home
