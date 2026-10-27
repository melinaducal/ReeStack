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
      setPosts(response.data)
      // Initialize like states for each post
      const states = {}
      for (const post of response.data) {
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

  return (
    <div className="feed-layout">
      <main className="feed-main">
        <header className="feed-header">
          <h1>Feed</h1>
          <p className="feed-subtitle">Pensamientos y reseñas de la comunidad</p>
        </header>
        {loading && <p>Cargando feed...</p>}
        {error && <p className="error">{error}</p>}
        {!loading && !error && posts.length === 0 && (
          <p className="empty-message">Aún no hay publicaciones en la comunidad.</p>
        )}
        <div className="posts-list">
          {posts.map(post => (
            <article key={post.id} className="post-card">
              <div className="post-header">
                <div className="post-avatar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#C98F86', color: '#F5EBDD', fontWeight: 'bold' }}>
                  {getInitials(post.owner?.username || post.username || 'Usuario')}
                </div>
                <div className="post-meta">
                  <p className="post-author">{post.owner?.username || post.username || (post.user_id ? `Usuario ${post.user_id}` : 'Usuario')}</p>
                  <p className="post-date">{post.type}</p>
                </div>
              </div>
              <div className="post-related">
                {(post.cover_url || post.type === 'book') && (
                  <img 
                    src={post.cover_url || 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=80&h=120&fit=crop'} 
                    alt={post.title} 
                    className="post-cover" 
                  />
                )}
                <p className="post-related-text">
                  Relacionado con: <Link to={`/item/${post.id}`} className="post-related-title">{post.title}</Link>
                  {post.creator && <span> · {post.creator}</span>}
                  {post.year && <span> · {post.year}</span>}
                </p>
              </div>
              {post.thoughts && (
                <div className="post-content">
                  <p>{post.thoughts}</p>
                </div>
              )}
              <div className="post-actions" style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem' }}>
                <button 
                  onClick={() => handleLike(post.id)} 
                  className="like-btn"
                  style={{ 
                    background: likeStates[post.id]?.liked ? '#C98F86' : 'transparent',
                    color: likeStates[post.id]?.liked ? '#F5EBDD' : '#C98F86',
                    border: '1px solid #C98F86',
                    padding: '0.3rem 0.8rem',
                    cursor: 'pointer',
                    fontFamily: 'inherit'
                  }}
                >
                  {likeStates[post.id]?.liked ? '♥ Me gusta' : '♡ Me gusta'}
                </button>
                <span className="likes-count">{likeStates[post.id]?.likes_count || 0} {likeStates[post.id]?.likes_count === 1 ? 'me gusta' : 'me gusta'}</span>
                <Link to={`/item/${post.id}`} style={{ marginLeft: 'auto', color: '#C98F86', textDecoration: 'none' }}>Ver detalle / Comentar</Link>
              </div>
            </article>
          ))}
        </div>
      </main>

      <aside className="feed-sidebar">
        <section className="sidebar-section sidebar-stack">
          <Link to="/stack" className="stack-link">
            <h2 className="sidebar-title">Mi Stack</h2>
            <p className="stack-description">Ver toda mi colección</p>
          </Link>
        </section>
        <section className="sidebar-section sidebar-stack">
          <Link to="/add" className="stack-link">
            <h2 className="sidebar-title">Agregar contenido</h2>
            <p className="stack-description">Añadir a mi biblioteca</p>
          </Link>
        </section>
        <section className="sidebar-section sidebar-stack">
          <Link to="/chatbot" className="stack-link">
            <h2 className="sidebar-title">Asistente IA</h2>
            <p className="stack-description">Recomendaciones personalizadas</p>
          </Link>
        </section>
      </aside>
    </div>
  )
}

export default Feed
