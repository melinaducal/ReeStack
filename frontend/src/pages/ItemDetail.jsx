import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../services/api'
import './ItemDetail.css'

function ItemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
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

  useEffect(() => {
    fetchItem()
    fetchComments()
    fetchRatingSummary()
    fetchCurrentUser()
    fetchLikeState()
  }, [id])

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
        rating: newComment.rating ? parseInt(newComment.rating) : null,
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
      for (const key in editData) {
        if (editData[key] === '' || editData[key] === null) continue
        if (key === 'year' || key === 'pages' || key === 'rating') {
          payload[key] = parseInt(editData[key])
        } else {
          payload[key] = editData[key]
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

  return (
    <div className="item-detail-layout">
      <div className="item-detail-main">
        <div className="item-detail-header">
          {(item.cover_url || item.type === 'book') && (
            <img 
              src={item.cover_url || 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=200&h=300&fit=crop'} 
              alt={item.title} 
              className="item-detail-cover"
            />
          )}
          <div className="item-detail-info">
            <h1>{item.title}</h1>
            <div className="item-meta">
              <span className="badge">{item.type}</span>
              {item.creator && <span>por {item.creator}</span>}
              {item.year && <span>{item.year}</span>}
              {item.pages && <span>{item.pages} páginas</span>}
            </div>
            {ratingSummary.count > 0 && (
              <div className="rating-summary">
                <span className="rating-stars">★ {ratingSummary.average}</span>
                <span className="rating-count">({ratingSummary.count} {ratingSummary.count === 1 ? 'calificación' : 'calificaciones'})</span>
              </div>
            )}
          </div>
        </div>

        {item.type === 'book' && item.pages && (
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

        {item.thoughts && !showEdit && (
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
            <h2>Editar publicación</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <label>Título
                <input type="text" value={editData.title} onChange={(e) => setEditData({...editData, title: e.target.value})} className="progress-input" style={{ width: '100%' }} />
              </label>
              <label>Tipo
                <select value={editData.type} onChange={(e) => setEditData({...editData, type: e.target.value})} className="rating-select">
                  <option value="book">book</option>
                  <option value="movie">movie</option>
                  <option value="series">series</option>
                  <option value="music">music</option>
                  <option value="paper">paper</option>
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
          <h2>Comentarios y calificaciones</h2>
          
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
                    <span className="comment-username">{comment.username || 'Usuario'}</span>
                    {comment.rating && <span className="comment-rating">★ {comment.rating}</span>}
                    {comment.has_spoiler && <span className="spoiler-badge">Spoiler</span>}
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
