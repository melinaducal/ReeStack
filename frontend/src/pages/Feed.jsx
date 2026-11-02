import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './Feed.css'

function Feed() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [likeStates, setLikeStates] = useState({})

  useEffect(() => {
    fetchFeed()
  }, [])

  const fetchFeed = async () => {
    try {
      setLoading(true)
      const response = await api.get('/items/feed')
      setPosts(response.data || [])
      const states = {}
      for (const post of response.data || []) {
        try {
          const likeRes = await api.get(`/likes/item/${post.id}`)
          states[post.id] = likeRes.data
        } catch (e) {
          states[post.id] = { liked: false, likes_count: 0 }
        }
      }
      setLikeStates(states)
      setError('')
    } catch (err) {
      console.error('Error fetching feed:', err)
      setError('Error al cargar el feed comunitario')
    } finally {
      setLoading(false)
    }
  }

  const handleLike = async (itemId) => {
    try {
      const current = likeStates[itemId] || { liked: false, likes_count: 0 }
      if (current.liked) {
        const res = await api.delete(`/likes/item/${itemId}`)
        setLikeStates(prev => ({ ...prev, [itemId]: res.data }))
      } else {
        const res = await api.post(`/likes/item/${itemId}`)
        setLikeStates(prev => ({ ...prev, [itemId]: res.data }))
      }
    } catch (err) {
      console.error('Error toggling like:', err)
    }
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  const formatDate = (post) => {
    if (post.created_at) {
      try {
        const d = new Date(post.created_at)
        return d.toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: 'numeric' })
      } catch (e) {}
    }
    return ''
  }

  const getUserName = (post) => {
    return post.owner?.username || post.owner?.first_name || post.username || (post.user_id ? `Usuario ${post.user_id}` : 'Usuario')
  }

  return (
    <div className="feed-shell">
      <header className="feed-hero">
        <div className="feed-hero-inner">
          <p className="feed-kicker">Comunidad cultural</p>
          <h1 className="feed-hero-title">Descubre, reseña y comparte</h1>
          <p className="feed-hero-subtitle">Un espacio editorial para libros, películas, series, música y papers.</p>
        </div>
      </header>
      <div className="feed-layout">
        <main className="feed-main">
          <div className="feed-section-header">
            <h2>Publicaciones recientes</h2>
            <p>Lo que la comunidad está leyendo y pensando</p>
          </div>
          {loading && <p className="feed-state">Cargando feed...</p>}
          {error && <p className="feed-state feed-error">{error}</p>}
          {!loading && !error && posts.length === 0 && (
            <p className="feed-state">Aún no hay publicaciones en la comunidad.</p>
          )}
          <div className="posts-list">
            {posts.map(post => (
              <article key={post.id} className="post-card">
                <div className="post-card-header">
                  <div className="post-user">
                    <div className="post-avatar">
                      {getInitials(getUserName(post))}
                    </div>
                    <div className="post-user-meta">
                      <p className="post-user-name">{getUserName(post)}</p>
                      <p className="post-timestamp">{formatDate(post)} {post.type ? `· ${post.type}` : ''}</p>
                    </div>
                  </div>
                </div>
                <div className="post-body">
                  <div className="post-media">
                    {post.cover_url ? (
                      <img src={post.cover_url} alt={post.title} className="post-cover-large" />
                    ) : (
                      <div className="post-cover-placeholder">
                        <span>{post.type?.[0]?.toUpperCase() || 'R'}</span>
                      </div>
                    )}
                  </div>
                  <div className="post-details">
                    <div className="post-work">
                      <Link to={`/item/${post.id}`} className="post-work-title">{post.title}</Link>
                      {(post.creator || post.year) && (
                        <p className="post-work-meta">
                          {post.creator}{post.creator && post.year ? ' · ' : ''}{post.year}
                        </p>
                      )}
                      {post.rating && (
                        <div className="post-rating">
                          <span className="post-rating-stars">★</span>
                          <span>{post.rating}/10</span>
                        </div>
                      )}
                    </div>
                    {post.thoughts && (
                      <div className="post-review">
                        {(() => {
                          const text = post.thoughts || ''
                          if (text.trim().startsWith('<')) {
                            return <div dangerouslySetInnerHTML={{ __html: text }} />
                          }
                          const formatText = (t) => {
                            let result = t
                            result = result.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="post-link">$1</a>')
                            result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
                            result = result.replace(/__([^_]+)__/g, '<u>$1</u>')
                            result = result.replace(/~~([^~]+)~~/g, '<s>$1</s>')
                            result = result.replace(/\*([^*]+)\*/g, '<em>$1</em>')
                            result = result.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer" class="post-link">Ver enlace</a>')
                            return result
                          }
                          return <div dangerouslySetInnerHTML={{ __html: formatText(text).replace(/\n/g, '<br/>') }} />
                        })()}
                      </div>
                    )}
                  </div>
                </div>
                <div className="post-card-footer">
                  <div className="post-actions">
                    <button 
                      onClick={() => handleLike(post.id)} 
                      className={`post-action-btn ${likeStates[post.id]?.liked ? 'liked' : ''}`}
                      aria-label="Me gusta"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                      </svg>
                      <span>{likeStates[post.id]?.likes_count || 0}</span>
                    </button>
                    <Link to={`/item/${post.id}`} className="post-action-btn">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                      </svg>
                      <span>Comentar</span>
                    </Link>
                  </div>
                  <Link to={`/item/${post.id}`} className="post-detail-link">Ver publicación</Link>
                </div>
              </article>
            ))}
          </div>
        </main>
        <aside className="feed-sidebar">
          <section className="sidebar-card">
            <h3 className="sidebar-card-title">Explorar</h3>
            <nav className="sidebar-nav">
              <Link to="/stack" className="sidebar-nav-item">
                <span>Mi Stack</span>
                <span className="sidebar-nav-arrow">→</span>
              </Link>
              <Link to="/add" className="sidebar-nav-item">
                <span>Agregar contenido</span>
                <span className="sidebar-nav-arrow">→</span>
              </Link>
              <Link to="/book-search" className="sidebar-nav-item">
                <span>Buscar por género</span>
                <span className="sidebar-nav-arrow">→</span>
              </Link>
              <Link to="/chatbot" className="sidebar-nav-item">
                <span>Asistente IA</span>
                <span className="sidebar-nav-arrow">→</span>
              </Link>
            </nav>
          </section>
          <section className="sidebar-card sidebar-card-subtle">
            <h3 className="sidebar-card-title">Sobre ReeStack</h3>
            <p className="sidebar-card-text">Una red social cultural para registrar, compartir y descubrir libros, películas, series, música y papers.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}

export default Feed
