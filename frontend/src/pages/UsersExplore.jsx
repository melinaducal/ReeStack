import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './UsersExplore.css'

function UsersExplore() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  const search = async (p = 1) => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await api.get('/users/search', { params: { q: query.trim(), page: p, limit: 12 } })
      setResults(res.data || [])
      setPage(p)
      setHasSearched(true)
    } catch (e) {
      console.error(e)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  return (
    <div className="users-page">
      <header className="users-header">
        <div>
          <h1>Explorar usuarios</h1>
          <p>Descubrí perfiles culturales de la comunidad</p>
        </div>
      </header>

      <div className="users-search">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar por nombre o username"
          onKeyDown={(e) => e.key === 'Enter' && search(1)}
        />
        <button onClick={() => search(1)} className="users-search-btn">Buscar</button>
      </div>

      {loading && <p className="users-state">Buscando...</p>}
      {!loading && hasSearched && results.length === 0 && <p className="users-state">Sin resultados</p>}

      <div className="users-grid">
        {results.map(user => (
          <Link to={`/users/${user.id}`} key={user.id} className="users-card">
            <div className="users-card-avatar">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.display_name || user.username} />
              ) : (
                <div className="users-card-avatar-placeholder">{getInitials(user.display_name || user.username)}</div>
              )}
            </div>
            <div className="users-card-body">
              <p className="users-card-name">{user.display_name || user.username}</p>
              <p className="users-card-username">@{user.username}</p>
              {user.bio && <p className="users-card-bio">{user.bio}</p>}
            </div>
          </Link>
        ))}
      </div>

      {hasSearched && results.length > 0 && (
        <div className="users-pagination">
          <button disabled={page <= 1} onClick={() => search(page - 1)}>Anterior</button>
          <span>Página {page}</span>
          <button onClick={() => search(page + 1)}>Siguiente</button>
        </div>
      )}
    </div>
  )
}

export default UsersExplore
