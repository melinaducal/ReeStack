import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { isPost, sanitizeRichText } from '../utils/richText'
import './Feed.css'

const TYPE_LABELS = {
  book: 'Libro',
  movie: 'Película',
  series: 'Serie',
  music: 'Música',
  paper: 'Paper',
  post: 'Publicación'
}

function Feed() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [likeStates, setLikeStates] = useState({})
  const [commentCounts, setCommentCounts] = useState({})
  const [openComments, setOpenComments] = useState({})
  const [comments, setComments] = useState({})
  const [commentInputs, setCommentInputs] = useState({})
  const [commentLoading, setCommentLoading] = useState({})
  const [commentSubmitting, setCommentSubmitting] = useState({})
  const [currentUser, setCurrentUser] = useState(null)
  const commentInputRefs = useRef({})

  useEffect(() => {
    fetchCurrentUser()
    fetchFeed()
  }, [])

  const fetchCurrentUser = async () => {
    try {
      const res = await api.get('/auth/me')
      setCurrentUser(res.data)
    } catch (e) {
      // ignore
    }
  }

  const fetchFeed = async () => {
    try {
      setLoading(true)
      const response = await api.get('/items/feed')
      const data = response.data || []
      setPosts(data)
      const states = {}
      const counts = {}
      for (const post of data) {
        try {
          const likeRes = await api.get(`/likes/item/${post.id}`)
          states[post.id] = likeRes.data
        } catch (e) {
          states[post.id] = { liked: false, likes_count: 0 }
        }
        try {
          const commentRes = await api.get(`/comments/item/${post.id}`)
          counts[post.id] = (commentRes.data || []).length
        } catch (e) {
          counts[post.id] = 0
        }
      }
      setLikeStates(states)
      setCommentCounts(counts)
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

  const toggleComments = async (itemId) => {
    const willOpen = !openComments[itemId]
    setOpenComments(prev => ({ ...prev, [itemId]: willOpen }))
    if (willOpen && !comments[itemId]) {
      setCommentLoading(prev => ({ ...prev, [itemId]: true }))
      try {
        const res = await api.get(`/comments/item/${itemId}`)
        setComments(prev => ({ ...prev, [itemId]: res.data || [] }))
        setCommentCounts(prev => ({ ...prev, [itemId]: (res.data || []).length }))
      } catch (err) {
        console.error('Error fetching comments:', err)
      } finally {
        setCommentLoading(prev => ({ ...prev, [itemId]: false }))
      }
    }
    if (willOpen) {
      setTimeout(() => {
        commentInputRefs.current[itemId]?.focus()
      }, 50)
    }
  }

  const handleCommentSubmit = async (itemId, e) => {
    e.preventDefault()
    const text = (commentInputs[itemId] || '').trim()
    if (!text) return
    setCommentSubmitting(prev => ({ ...prev, [itemId]: true }))
    try {
      const res = await api.post(`/comments/item/${itemId}`, {
        content: text,
        has_spoiler: false,
        rating: null
      })
      setComments(prev => ({ ...prev, [itemId]: [...(prev[itemId] || []), res.data] }))
      setCommentCounts(prev => ({ ...prev, [itemId]: (prev[itemId] || 0) + 1 }))
      setCommentInputs(prev => ({ ...prev, [itemId]: '' }))
    } catch (err) {
      console.error('Error posting comment:', err)
      alert(err.response?.data?.detail || 'No se pudo publicar el comentario')
    } finally {
      setCommentSubmitting(prev => ({ ...prev, [itemId]: false }))
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
    return post.owner?.display_name || post.owner?.name || post.owner?.username || post.owner?.first_name || post.username || (post.user_id ? `Usuario ${post.user_id}` : 'Usuario')
  }

  const getUserHandle = (post) => post.owner?.username || post.username || ''
  const getUserAvatar = (post) => post.owner?.avatar_url || post.owner?.profile_picture || post.avatar_url || null

  const renderItemCard = (post) => {
    const socialPost = isPost(post)
    const isBook = post.type === 'book'
    const isMedia = ['movie', 'series', 'music'].includes(post.type)

    if (socialPost) {
      return (
        <div className="feed-card-body">
          {post.thoughts && (
            <div
              className="feed-card-rich"
              dangerouslySetInnerHTML={{ __html: sanitizeRichText(post.thoughts) }}
            />
          )}
          {post.cover_url && (
            <img src={post.cover_url} alt={post.title || 'Imagen'} className="feed-card-media" />
          )}
        </div>
      )
    }

    if (isBook) {
      return (
        <div className="feed-card-body feed-card-book">
          {post.cover_url ? (
            <img src={post.cover_url} alt={post.title} className="feed-card-book-cover" />
          ) : (
            <div className="feed-card-book-cover placeholder"><span>{post.type?.[0]?.toUpperCase() || 'L'}</span></div>
          )}
          <div className="feed-card-book-info">
            <Link to={`/item/${post.id}`} className="feed-card-title">{post.title}</Link>
            {(post.creator || post.year) && (
              <p className="feed-card-meta">{post.creator}{post.creator && post.year ? ' · ' : ''}{post.year}</p>
            )}
            {post.rating && <p className="feed-card-rating">★ {post.rating}/5</p>}
            {post.thoughts && <p className="feed-card-excerpt">{post.thoughts}</p>}
          </div>
        </div>
      )
    }

    if (isMedia) {
      return (
        <div className="feed-card-body">
          <Link to={`/item/${post.id}`} className="feed-card-title">{post.title}</Link>
          {(post.creator || post.year) && (
            <p className="feed-card-meta">{post.creator}{post.creator && post.year ? ' · ' : ''}{post.year}</p>
          )}
          {post.rating && <p className="feed-card-rating">★ {post.rating}/5</p>}
          {post.cover_url && (
            <img src={post.cover_url} alt={post.title} className="feed-card-media media-item" />
          )}
          {post.thoughts && <p className="feed-card-excerpt">{post.thoughts}</p>}
        </div>
      )
    }

    return (
      <div className="feed-card-body">
        <Link to={`/item/${post.id}`} className="feed-card-title">{post.title}</Link>
        {post.thoughts && <p className="feed-card-excerpt">{post.thoughts}</p>}
      </div>
    )
  }

  return (
    <div className="feed-shell">
      <div className="feed-layout">
        <main className="feed-main">
          <header className="feed-header">
            <h1>Inicio</h1>
            <p>Publicaciones recientes de la comunidad</p>
          </header>
          {loading && <p className="feed-state">Cargando feed...</p>}
          {error && <p className="feed-state feed-error">{error}</p>}
          {!loading && !error && posts.length === 0 && (
            <p className="feed-state">Aún no hay publicaciones en la comunidad.</p>
          )}
          <div className="feed-list">
            {posts.map(post => {
              const like = likeStates[post.id] || { liked: false, likes_count: 0 }
              const count = commentCounts[post.id] ?? 0
              const isOpen = !!openComments[post.id]
              const postComments = comments[post.id] || []
              return (
                <article key={post.id} className="feed-card">
                  <div className="feed-card-header">
                    {getUserAvatar(post) ? (
                      <img src={getUserAvatar(post)} alt={getUserName(post)} className="feed-avatar" />
                    ) : (
                      <div className="feed-avatar placeholder">{getInitials(getUserName(post))}</div>
                    )}
                    <div className="feed-card-user">
                      <div className="feed-card-user-line">
                        <span className="feed-card-name">{getUserName(post)}</span>
                        {getUserHandle(post) && <span className="feed-card-handle">@{getUserHandle(post)}</span>}
                      </div>
                      <span className="feed-card-date">{formatDate(post)} {post.type ? `· ${TYPE_LABELS[post.type] || post.type}` : ''}</span>
                    </div>
                  </div>

                  {renderItemCard(post)}

                  <div className="feed-card-actions">
                    <button
                      onClick={() => handleLike(post.id)}
                      className={`feed-action-btn ${like.liked ? 'liked' : ''}`}
                      aria-label={like.liked ? 'Quitar me gusta' : 'Me gusta'}
                    >
                      <span className="feed-action-icon">{like.liked ? '♥' : '♡'}</span>
                      <span>{like.likes_count || 0}</span>
                    </button>
                    <button
                      onClick={() => toggleComments(post.id)}
                      className="feed-action-btn"
                      aria-label="Comentar"
                    >
                      <span className="feed-action-icon">💬</span>
                      <span>{count}</span>
                    </button>
                    <Link to={`/item/${post.id}`} className="feed-action-link">Ver detalle</Link>
                  </div>

                  {isOpen && (
                    <div className="feed-comments">
                      <form onSubmit={(e) => handleCommentSubmit(post.id, e)} className="feed-comment-form">
                        <textarea
                          ref={(el) => { commentInputRefs.current[post.id] = el }}
                          value={commentInputs[post.id] || ''}
                          onChange={(e) => setCommentInputs(prev => ({ ...prev, [post.id]: e.target.value }))}
                          placeholder="Escribí un comentario..."
                          className="feed-comment-input"
                          rows={2}
                          required
                        />
                        <button type="submit" className="feed-comment-submit" disabled={commentSubmitting[post.id]}>
                          {commentSubmitting[post.id] ? 'Enviando...' : 'Enviar'}
                        </button>
                      </form>
                      {commentLoading[post.id] && <p className="feed-comment-state">Cargando comentarios...</p>}
                      {!commentLoading[post.id] && postComments.length === 0 && (
                        <p className="feed-comment-state">Aún no hay comentarios</p>
                      )}
                      <div className="feed-comment-list">
                        {postComments.map(c => (
                          <div key={c.id} className="feed-comment-item">
                            <span className="feed-comment-user">{c.username || 'Usuario'}</span>
                            <span className="feed-comment-text">{c.content}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </main>
        <aside className="feed-sidebar">
          <div className="feed-sidebar-card">
            <h3>Explorar</h3>
            <nav className="feed-sidebar-nav">
              <Link to="/stack">Mi Stack</Link>
              <Link to="/add">Buscar y agregar</Link>
              <Link to="/chatbot">Asistente IA</Link>
            </nav>
          </div>
        </aside>
      </div>
    </div>
  )
}

export default Feed
