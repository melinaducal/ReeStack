import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../services/api'
import RichTextEditor from '../components/RichTextEditor'
import { isPost, sanitizeRichText } from '../utils/richText'
import './ItemDetail.css'

const TYPE_LABELS = {
  book: 'Libro',
  movie: 'Película',
  series: 'Serie',
  music: 'Música',
  paper: 'Paper',
  post: 'Publicación'
}

const getCommentAuthor = (comment) =>
  comment.display_name || comment.username || 'Usuario'

const formatCommentDate = (value) => {
  if (!value) return ''
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasTimezone ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' })
}

function ItemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const menuRef = useRef(null)
  const [item, setItem] = useState(null)
  const [currentPageInput, setCurrentPageInput] = useState('')
  const [showProgressUpdate, setShowProgressUpdate] = useState(false)
  const [error, setError] = useState('')
  const [comments, setComments] = useState([])
  const [ratingSummary, setRatingSummary] = useState({ average: 0, count: 0 })
  const [showSpoilers, setShowSpoilers] = useState(false)
  const [newComment, setNewComment] = useState({
    rating: '',
    content: '',
    has_spoiler: false
  })
  const [currentUser, setCurrentUser] = useState(null)
  const [showEdit, setShowEdit] = useState(false)
  const [editData, setEditData] = useState({})
  const [likeState, setLikeState] = useState({ liked: false, likes_count: 0 })
  const [menuOpen, setMenuOpen] = useState(false)
  const postItem = isPost(item)

  useEffect(() => {
    fetchItem()
    fetchComments()
    fetchRatingSummary()
    fetchCurrentUser()
    fetchLikeState()
  }, [id])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchCurrentUser = async () => {
    try {
      const res = await api.get('/auth/me')
      setCurrentUser(res.data)
    } catch (e) {
      // ignore
    }
  }

  const fetchLikeState = async () => {
    try {
      const res = await api.get(`/likes/item/${id}`)
      setLikeState(res.data)
    } catch (e) {
      setLikeState({ liked: false, likes_count: 0 })
    }
  }

  const handleLikeToggle = async () => {
    try {
      if (likeState.liked) {
        const res = await api.delete(`/likes/item/${id}`)
        setLikeState(res.data)
      } else {
        const res = await api.post(`/likes/item/${id}`)
        setLikeState(res.data)
      }
    } catch (e) {
      console.error('Error toggling like:', e)
    }
  }

  const fetchItem = async () => {
    try {
      const response = await api.get(`/items/${id}`)
      setItem(response.data)
      setCurrentPageInput(response.data.current_page || 0)
      setEditData({
        title: response.data.title || '',
        type: response.data.type || '',
        creator: response.data.creator || '',
        year: response.data.year || '',
        thoughts: response.data.thoughts || '',
        cover_url: response.data.cover_url || '',
        pages: response.data.pages || '',
        rating: response.data.rating || ''
      })
    } catch (error) {
      console.error('Error fetching item:', error)
    }
  }

  const fetchComments = async () => {
    try {
      const response = await api.get(`/comments/item/${id}`)
      setComments(response.data)
    } catch (error) {
      console.error('Error fetching comments:', error)
    }
  }

  const fetchRatingSummary = async () => {
    try {
      const response = await api.get(`/comments/item/${id}/rating`)
      setRatingSummary(response.data)
    } catch (error) {
      console.error('Error fetching rating:', error)
    }
  }

  const handleProgressUpdate = async () => {
    setError('')
    try {
      const page = parseInt(currentPageInput)
      await api.put(`/items/${id}/progress`, { current_page: page })
      await fetchItem()
      setShowProgressUpdate(false)
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al actualizar progreso')
    }
  }

  const handleCommentSubmit = async (e) => {
    e.preventDefault()
    try {
      await api.post(`/comments/item/${id}`, {
        rating: !postItem && newComment.rating ? parseInt(newComment.rating) : null,
        content: newComment.content,
        has_spoiler: newComment.has_spoiler
      })
      setNewComment({ rating: '', content: '', has_spoiler: false })
      fetchComments()
      fetchRatingSummary()
    } catch (error) {
      console.error('Error adding comment:', error)
    }
  }

  const handleDeleteComment = async (commentId) => {
    if (!window.confirm('¿Eliminar este comentario?')) return
    try {
      await api.delete(`/comments/${commentId}`)
      await fetchComments()
    } catch (error) {
      alert(error.response?.data?.detail || 'No se pudo eliminar el comentario')
    }
  }

  const handleDelete = async () => {
    if (window.confirm('¿Estás seguro de eliminar este elemento?')) {
      try {
        await api.delete(`/items/${id}`)
        navigate('/')
      } catch (error) {
        console.error('Error deleting item:', error)
      }
    }
  }

  const handleEditSave = async () => {
    try {
      const payload = {}
      if (postItem) {
        // A post stays a post: the type is never changed or inferred here.
        if (editData.title !== undefined) payload.title = editData.title
        payload.thoughts = editData.thoughts || ''
      } else {
        for (const key in editData) {
          if (editData[key] === '' || editData[key] === null) continue
          if (key === 'year' || key === 'pages' || key === 'rating') {
            payload[key] = parseInt(editData[key])
          } else {
            payload[key] = editData[key]
          }
        }
      }
      const res = await api.put(`/items/${id}`, payload)
      setItem(res.data)
      setShowEdit(false)
    } catch (error) {
      console.error('Error updating item:', error)
      alert(error.response?.data?.detail || 'Error al actualizar')
    }
  }

  if (!item) return <div>Cargando...</div>

  const filteredComments = showSpoilers ? comments : comments.filter(c => !c.has_spoiler)

  const owner = item.owner || {}
  const isOwner = currentUser && item.user_id === currentUser.id
  const createdAt = item.created_at ? new Date(item.created_at).toLocaleDateString('es-AR', { day: 'numeric', month: 'long', year: 'numeric' }) : ''
  const ownerName = owner.display_name || owner.name || owner.username || [owner.first_name, owner.last_name].filter(Boolean).join(' ') || 'Usuario'
  const ownerHandle = owner.username || ''
  const ownerAvatar = owner.avatar_url || owner.profile_picture || null

  if (postItem) {
    return (
      <div className="post-detail-page">
        <article className="post-detail-article">
          <header className="post-detail-article-header">
            <div className="post-detail-author">
              {ownerAvatar ? (
                <img src={ownerAvatar} alt={ownerName} className="post-detail-avatar" />
              ) : (
                <div className="post-detail-avatar placeholder">{(ownerName || 'U')[0].toUpperCase()}</div>
              )}
              <div className="post-detail-author-info">
                <div className="post-detail-author-line">
                  <span className="post-detail-author-name">{ownerName}</span>
                  {ownerHandle && <span className="post-detail-author-username">@{ownerHandle}</span>}
                </div>
                {createdAt && <span className="post-detail-date">{createdAt}</span>}
              </div>
            </div>
            {isOwner && (
              <div className="post-detail-menu" ref={menuRef}>
                <button className="post-detail-menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menú">
                  ⋮
                </button>
                {menuOpen && (
                  <div className="post-detail-menu-dropdown">
                    <button onClick={() => { setShowEdit(true); setMenuOpen(false) }}>Editar</button>
                    <button onClick={() => { setMenuOpen(false); handleDelete() }} className="danger">Eliminar</button>
                  </div>
                )}
              </div>
            )}
          </header>

          {showEdit && isOwner && (
            <div className="post-detail-edit">
              <label className="post-detail-edit-label">Contenido</label>
              <RichTextEditor
                value={editData.thoughts || ''}
                onChange={(html) => setEditData(prev => ({ ...prev, thoughts: html }))}
              />
              <div className="post-detail-edit-actions">
                <button onClick={handleEditSave} className="post-detail-btn primary">Guardar cambios</button>
                <button onClick={() => setShowEdit(false)} className="post-detail-btn">Cancelar</button>
              </div>
            </div>
          )}

          {!showEdit && item.thoughts && (
            <div
              className="post-detail-content"
              dangerouslySetInnerHTML={{ __html: sanitizeRichText(item.thoughts) }}
            />
          )}

          {!showEdit && item.cover_url && (
            <img
              src={item.cover_url}
              alt={item.title || 'Imagen de la publicación'}
              className="post-detail-media"
            />
          )}

          <div className="post-detail-interactions">
            <button onClick={handleLikeToggle} className={`post-detail-like ${likeState.liked ? 'liked' : ''}`}>
              <span>{likeState.liked ? '♥' : '♡'}</span>
              <span>{likeState.likes_count}</span>
            </button>
            <div className="post-detail-comments-count">
              <span>💬</span>
              <span>{comments.length}</span>
            </div>
          </div>

          <section className="post-detail-comments-section">
            <h2>Comentarios</h2>
            <form onSubmit={handleCommentSubmit} className="post-detail-comment-form">
              <div className="post-detail-comment-input-row">
                {currentUser?.avatar_url ? (
                  <img src={currentUser.avatar_url} alt={getCommentAuthor(currentUser)} className="post-detail-comment-avatar" />
                ) : (
                  <div className="post-detail-comment-avatar placeholder">{getCommentAuthor(currentUser)[0].toUpperCase()}</div>
                )}
                <div className="post-detail-comment-input-wrap">
                  <textarea
                    value={newComment.content}
                    onChange={(e) => setNewComment({...newComment, content: e.target.value})}
                    required
                    rows="2"
                    className="post-detail-comment-textarea"
                    placeholder="Escribí un comentario..."
                  />
                </div>
              </div>
              <div className="post-detail-comment-meta">
                <label className="post-detail-spoiler-check">
                  <input 
                    type="checkbox" 
                    checked={newComment.has_spoiler} 
                    onChange={(e) => setNewComment({...newComment, has_spoiler: e.target.checked})} 
                  />
                  Contiene spoilers
                </label>
                <button type="submit" className="post-detail-btn primary">Enviar</button>
              </div>
            </form>

            <div className="post-detail-spoiler-toggle">
              <label>
                <input 
                  type="checkbox" 
                  checked={showSpoilers} 
                  onChange={(e) => setShowSpoilers(e.target.checked)} 
                />
                Mostrar spoilers
              </label>
            </div>

            <div className="post-detail-comments-list">
              {filteredComments.length === 0 ? (
                <p className="post-detail-no-comments">Aún no hay comentarios</p>
              ) : (
                filteredComments.map(comment => (
                  <div key={comment.id} className="post-detail-comment-card">
                    <div className="post-detail-comment-card-header">
                      {comment.avatar_url ? (
                        <img src={comment.avatar_url} alt={getCommentAuthor(comment)} className="post-detail-comment-avatar small" />
                      ) : (
                        <div className="post-detail-comment-avatar small placeholder">{getCommentAuthor(comment)[0].toUpperCase()}</div>
                      )}
                      <div className="post-detail-comment-card-info">
                        <span className="post-detail-comment-username">{getCommentAuthor(comment)}</span>
                        {comment.created_at && (
                          <span className="post-detail-comment-date">{formatCommentDate(comment.created_at)}</span>
                        )}
                        {comment.has_spoiler && <span className="post-detail-spoiler-badge">Spoiler</span>}
                      </div>
                      {comment.is_owner && (
                        <button
                          type="button"
                          className="post-detail-comment-delete"
                          onClick={() => handleDeleteComment(comment.id)}
                          aria-label="Eliminar comentario"
                        >
                          Eliminar
                        </button>
                      )}
                    </div>
                    {comment.has_spoiler && !showSpoilers ? (
                      <p className="post-detail-spoiler-hidden">Este comentario contiene spoilers. Activa "Mostrar spoilers" para verlo.</p>
                    ) : (
                      <p className="post-detail-comment-content">{comment.content}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>
        </article>
      </div>
    )
  }

  return (
    <div className="item-detail-layout">
      <div className="item-detail-main">
        <div className={`item-detail-header ${postItem ? 'item-detail-header-post' : ''}`}>
          {!postItem && (item.cover_url ? (
            <img 
              src={item.cover_url} 
              alt={item.title}
              className="item-detail-cover"
            />
          ) : (
            <div className="item-detail-cover-placeholder">
              <span>{item.type?.[0]?.toUpperCase() || 'R'}</span>
            </div>
          ))}
          <div className="item-detail-info">
            {postItem ? <h1 className="sr-only">Publicación</h1> : <h1>{item.title}</h1>}
            <div className="item-meta">
              <span className={`badge ${postItem ? 'badge-post' : ''}`}>
                {TYPE_LABELS[item.type] || item.type}
              </span>
              {!postItem && item.creator && <span>por {item.creator}</span>}
              {!postItem && item.year && <span>{item.year}</span>}
              {!postItem && item.pages && <span>{item.pages} páginas</span>}
            </div>
            {!postItem && ratingSummary.count > 0 && (
              <div className="rating-summary">
                <span className="rating-stars">★ {ratingSummary.average}</span>
                <span className="rating-count">({ratingSummary.count} {ratingSummary.count === 1 ? 'calificación' : 'calificaciones'})</span>
              </div>
            )}
          </div>
        </div>

        {!postItem && item.type === 'book' && item.pages && (
          <div className="reading-progress-section">
            <h2>Seguimiento de lectura</h2>
            <div className="progress-info">
              <span className="progress-text">Página {item.current_page || 0} de {item.pages}</span>
              <span className="progress-percentage">{item.reading_progress || 0}%</span>
            </div>
            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${item.reading_progress || 0}%` }}></div>
            </div>
            {!showProgressUpdate ? (
              <button onClick={() => setShowProgressUpdate(true)} className="update-progress-btn">Actualizar progreso</button>
            ) : (
              <div className="progress-update-form">
                <input
                  type="number"
                  value={currentPageInput}
                  onChange={(e) => setCurrentPageInput(e.target.value)}
                  min="0"
                  max={item.pages}
                  placeholder="Página actual"
                  className="progress-input"
                />
                <button onClick={handleProgressUpdate} className="save-progress-btn">Guardar</button>
                <button onClick={() => setShowProgressUpdate(false)} className="cancel-progress-btn">Cancelar</button>
                {error && <p className="progress-error">{error}</p>}
              </div>
            )}
          </div>
        )}

        {!postItem && item.thoughts && !showEdit && (
          <div className="thoughts-section">
            <h2>Pensamientos y Opiniones</h2>
            <p>{item.thoughts}</p>
          </div>
        )}

        {currentUser && item.user_id === currentUser.id && (
          <div className="owner-actions" style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            {!showEdit ? (
              <button onClick={() => setShowEdit(true)} className="update-progress-btn">Editar contenido/publicación</button>
            ) : (
              <button onClick={() => setShowEdit(false)} className="cancel-progress-btn">Cancelar edición</button>
            )}
            <button onClick={handleDelete} className="delete-btn">Eliminar</button>
          </div>
        )}

        {showEdit && currentUser && item.user_id === currentUser.id && (
          <div className="edit-section" style={{ marginTop: '1.5rem', padding: '1rem', border: '1px solid #D4B896' }}>
            <h2>{postItem ? 'Editar publicación' : 'Editar elemento'}</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <label>Título
                <input type="text" value={editData.title} onChange={(e) => setEditData({...editData, title: e.target.value})} className="progress-input" style={{ width: '100%' }} />
              </label>
              {postItem ? (
                <label>Contenido
                  <RichTextEditor
                    value={editData.thoughts || ''}
                    onChange={(html) => setEditData(prev => ({ ...prev, thoughts: html }))}
                  />
                </label>
              ) : (
                <>
                  <label>Tipo
                    <select value={editData.type} onChange={(e) => setEditData({...editData, type: e.target.value})} className="rating-select">
                      <option value="book">Libro</option>
                      <option value="movie">Película</option>
                      <option value="series">Serie</option>
                      <option value="music">Música</option>
                      <option value="paper">Paper</option>
                    </select>
                  </label>
                  <label>Creador/Autor
                    <input type="text" value={editData.creator} onChange={(e) => setEditData({...editData, creator: e.target.value})} className="progress-input" style={{ width: '100%' }} />
                  </label>
                  <label>Año
                    <input type="number" value={editData.year} onChange={(e) => setEditData({...editData, year: e.target.value})} className="progress-input" style={{ width: '100%' }} />
                  </label>
                  <label>URL de portada
                    <input type="text" value={editData.cover_url} onChange={(e) => setEditData({...editData, cover_url: e.target.value})} className="progress-input" style={{ width: '100%' }} />
                  </label>
                  <label>Páginas (para libros)
                    <input type="number" value={editData.pages} onChange={(e) => setEditData({...editData, pages: e.target.value})} className="progress-input" style={{ width: '100%' }} />
                  </label>
                  <label>Pensamientos/Opinión
                    <textarea value={editData.thoughts} onChange={(e) => setEditData({...editData, thoughts: e.target.value})} rows="4" className="comment-textarea" />
                  </label>
                </>
              )}
              <button onClick={handleEditSave} className="save-progress-btn">Guardar cambios</button>
            </div>
          </div>
        )}
      </div>

      <aside className="item-detail-sidebar">
        <section className="likes-section" style={{ marginBottom: '1.5rem' }}>
          <h2>Me gusta</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button 
              onClick={handleLikeToggle}
              style={{ 
                background: likeState.liked ? '#C98F86' : 'transparent',
                color: likeState.liked ? '#F5EBDD' : '#C98F86',
                border: '1px solid #C98F86',
                padding: '0.4rem 1rem',
                cursor: 'pointer',
                fontFamily: 'inherit'
              }}
            >
              {likeState.liked ? '♥ Te gusta' : '♡ Me gusta'}
            </button>
            <span>{likeState.likes_count} {likeState.likes_count === 1 ? 'me gusta' : 'me gusta'}</span>
          </div>
        </section>
        <section className="comments-section">
          <h2>{postItem ? 'Comentarios' : 'Comentarios y calificaciones'}</h2>
          
          <div className="spoiler-toggle">
            <label>
              <input 
                type="checkbox" 
                checked={showSpoilers} 
                onChange={(e) => setShowSpoilers(e.target.checked)} 
              />
              Mostrar spoilers
            </label>
          </div>

          <form onSubmit={handleCommentSubmit} className="comment-form">
            {!postItem && (
              <div className="form-group">
                <label>Calificación (opcional)</label>
                <select 
                  value={newComment.rating} 
                  onChange={(e) => setNewComment({...newComment, rating: e.target.value})}
                  className="rating-select"
                >
                  <option value="">Sin calificar</option>
                  <option value="1">1 ★</option>
                  <option value="2">2 ★</option>
                  <option value="3">3 ★</option>
                  <option value="4">4 ★</option>
                  <option value="5">5 ★</option>
                </select>
              </div>
            )}
            <div className="form-group">
              <label>Comentario</label>
              <textarea
                value={newComment.content}
                onChange={(e) => setNewComment({...newComment, content: e.target.value})}
                required
                rows="3"
                className="comment-textarea"
              />
            </div>
            <label className="spoiler-checkbox">
              <input 
                type="checkbox" 
                checked={newComment.has_spoiler} 
                onChange={(e) => setNewComment({...newComment, has_spoiler: e.target.checked})} 
              />
              Contiene spoilers
            </label>
            <button type="submit" className="comment-submit">Publicar comentario</button>
          </form>

          <div className="comments-list">
            {filteredComments.length === 0 ? (
              <p className="no-comments">No hay comentarios para mostrar</p>
            ) : (
              filteredComments.map(comment => (
                <div key={comment.id} className="comment-card">
                  <div className="comment-header">
                    {comment.avatar_url ? (
                      <img src={comment.avatar_url} alt={getCommentAuthor(comment)} className="comment-avatar" />
                    ) : (
                      <div className="comment-avatar placeholder">{getCommentAuthor(comment)[0].toUpperCase()}</div>
                    )}
                    <div className="comment-header-info">
                      <span className="comment-username">{getCommentAuthor(comment)}</span>
                      {comment.created_at && (
                        <span className="comment-date">{formatCommentDate(comment.created_at)}</span>
                      )}
                    </div>
                    {comment.rating && <span className="comment-rating">★ {comment.rating}</span>}
                    {comment.has_spoiler && <span className="spoiler-badge">Spoiler</span>}
                    {comment.is_owner && (
                      <button
                        type="button"
                        className="comment-delete"
                        onClick={() => handleDeleteComment(comment.id)}
                        aria-label="Eliminar comentario"
                      >
                        Eliminar
                      </button>
                    )}
                  </div>
                  {comment.has_spoiler && !showSpoilers ? (
                    <p className="spoiler-hidden">Este comentario contiene spoilers. Activa "Mostrar spoilers" para verlo.</p>
                  ) : (
                    <p className="comment-content">{comment.content}</p>
                  )}
                </div>
              ))
            )}
          </div>
        </section>
      </aside>
    </div>
  )
}

export default ItemDetail
