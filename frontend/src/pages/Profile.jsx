import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { getErrorMessage } from '../services/errors'
import './Profile.css'

function Profile() {
  const [profile, setProfile] = useState(null)
  const [items, setItems] = useState([])
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [activeTab, setActiveTab] = useState('publicaciones')
  const [activity, setActivity] = useState([])
  const [activityError, setActivityError] = useState('')
  const [form, setForm] = useState({
    display_name: '',
    bio: '',
    avatar_url: '',
    username: ''
  })
  const [stats, setStats] = useState({ items_count: 0, books: 0, movies: 0, series: 0, music: 0, papers: 0, posts_count: 0 })
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [avatarError, setAvatarError] = useState('')

  useEffect(() => {
    fetchProfile()
    fetchItems()
    fetchPosts()
  }, [])

  const fetchProfile = async () => {
    try {
      const res = await api.get('/users/me')
      setProfile(res.data)
      setForm({
        display_name: res.data.display_name || '',
        bio: res.data.bio || '',
        avatar_url: res.data.avatar_url || '',
        username: res.data.username || ''
      })
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const fetchItems = async () => {
    try {
      const res = await api.get('/items', { params: { mine: true } })
      setItems(res.data || [])
      const data = res.data || []
      const s = {
        items_count: data.length,
        books: data.filter(i => i.type === 'book').length,
        movies: data.filter(i => i.type === 'movie').length,
        series: data.filter(i => i.type === 'series').length,
        music: data.filter(i => i.type === 'music').length,
        papers: data.filter(i => i.type === 'paper').length,
        posts_count: data.length
      }
      setStats(s)
    } catch (e) {
      console.error(e)
    }
  }

  const fetchPosts = async () => {
    try {
      const res = await api.get('/items', { params: { mine: true } })
      const data = res.data || []
      const sorted = [...data].sort((a, b) => {
        const aTime = a.created_at ? new Date(a.created_at).getTime() : (b.id - a.id)
        const bTime = b.created_at ? new Date(b.created_at).getTime() : (b.id - a.id)
        if (a.created_at && b.created_at) return new Date(b.created_at) - new Date(a.created_at)
        return b.id - a.id
      })
      setPosts(sorted)
      setStats(prev => ({ ...prev, posts_count: sorted.length, items_count: sorted.length }))
    } catch (e) {
      console.error(e)
    }
  }

  const fetchActivity = async () => {
    setActivityError('')
    try {
      const res = await api.get('/users/me/activity')
      setActivity(res.data || [])
    } catch (e) {
      setActivityError('No existe endpoint para actividad del usuario. Solicitar a @backend: GET /users/me/activity o equivalente con acciones reales del usuario.')
      setActivity([])
    }
  }

  useEffect(() => {
    if (activeTab === 'actividad') {
      fetchActivity()
    }
  }, [activeTab])

  const handleSave = async () => {
    try {
      const res = await api.put('/users/me', form)
      setProfile(res.data)
      setEditing(false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleAvatarChange = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 2 * 1024 * 1024) {
      setAvatarError('La imagen no puede superar los 2 MB')
      return
    }
    setAvatarError('')
    setAvatarUploading(true)
    try {
      const data = new FormData()
      data.append('file', file)
      const res = await api.post('/users/me/avatar', data)
      setProfile(res.data)
      setForm(prev => ({ ...prev, avatar_url: res.data.avatar_url || '' }))
    } catch (error) {
      setAvatarError(getErrorMessage(error, 'No se pudo subir la foto'))
    } finally {
      setAvatarUploading(false)
    }
  }

  const handleAvatarRemove = async () => {
    setAvatarError('')
    setAvatarUploading(true)
    try {
      const res = await api.delete('/users/me/avatar')
      setProfile(res.data)
      setForm(prev => ({ ...prev, avatar_url: '' }))
    } catch (error) {
      setAvatarError(getErrorMessage(error, 'No se pudo quitar la foto'))
    } finally {
      setAvatarUploading(false)
    }
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  if (loading) return <div className="profile-page"><p>Cargando...</p></div>
  if (!profile) return <div className="profile-page"><p>No se pudo cargar el perfil</p></div>

  const displayName = profile.display_name || `${profile.first_name} ${profile.last_name}`

  return (
    <div className="profile-page">
      <header className="profile-hero">
        <div className="profile-hero-inner">
          <div className="profile-avatar-wrap">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt={displayName} className="profile-avatar" />
            ) : (
              <div className="profile-avatar-placeholder">{getInitials(displayName)}</div>
            )}
          </div>
          <div className="profile-hero-info">
            <div className="profile-hero-top">
              <div>
                <h1 className="profile-name">{displayName}</h1>
                <p className="profile-username">@{profile.username}</p>
              </div>
              <div className="profile-hero-actions">
                <button onClick={() => setEditing(!editing)} className="profile-btn">{editing ? 'Cancelar' : 'Editar perfil'}</button>
                <Link to="/settings" className="profile-btn profile-btn-ghost">Configuración</Link>
              </div>
            </div>
            {profile.bio && <p className="profile-bio">{profile.bio}</p>}
          </div>
        </div>
      </header>

      {editing && (
        <section className="profile-edit-card">
          <div className="profile-avatar-editor">
            <div className="profile-avatar-preview">
              {profile.avatar_url ? (
                <img src={profile.avatar_url} alt={displayName} className="profile-avatar" />
              ) : (
                <div className="profile-avatar-placeholder">{getInitials(displayName)}</div>
              )}
            </div>
            <div className="profile-avatar-actions">
              <span>Foto de perfil</span>
              <div className="profile-avatar-buttons">
                <label className="profile-btn profile-file-btn">
                  {avatarUploading ? 'Subiendo...' : 'Subir foto'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    onChange={handleAvatarChange}
                    disabled={avatarUploading}
                    hidden
                  />
                </label>
                {profile.avatar_url && (
                  <button
                    type="button"
                    className="profile-btn profile-btn-ghost"
                    onClick={handleAvatarRemove}
                    disabled={avatarUploading}
                  >
                    Quitar foto
                  </button>
                )}
              </div>
              <small>JPG, PNG, WebP o GIF. Máximo 2 MB.</small>
              {avatarError && <p className="profile-error">{avatarError}</p>}
            </div>
          </div>
          <div className="profile-edit-grid">
            <label className="profile-field">
              <span>Nombre visible</span>
              <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </label>
            <label className="profile-field">
              <span>Username</span>
              <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </label>
            <label className="profile-field profile-field-full">
              <span>O usá una URL de imagen</span>
              <input value={form.avatar_url} onChange={(e) => setForm({ ...form, avatar_url: e.target.value })} />
            </label>
            <label className="profile-field profile-field-full">
              <span>Biografía</span>
              <textarea value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} rows={4} />
            </label>
          </div>
          <div className="profile-edit-actions">
            <button onClick={handleSave} className="profile-btn">Guardar cambios</button>
          </div>
        </section>
      )}

      <section className="profile-stats">
        <div className="profile-stat-card">
          <p className="profile-stat-number">{posts.length || stats.posts_count || stats.items_count}</p>
          <p className="profile-stat-label">Publicaciones</p>
        </div>
        <div className="profile-stat-card">
          <p className="profile-stat-number">{stats.books}</p>
          <p className="profile-stat-label">Libros</p>
        </div>
        <div className="profile-stat-card">
          <p className="profile-stat-number">{stats.movies}</p>
          <p className="profile-stat-label">Películas</p>
        </div>
        <div className="profile-stat-card">
          <p className="profile-stat-number">{stats.series}</p>
          <p className="profile-stat-label">Series</p>
        </div>
        <div className="profile-stat-card">
          <p className="profile-stat-number">{stats.music}</p>
          <p className="profile-stat-label">Música</p>
        </div>
        <div className="profile-stat-card">
          <p className="profile-stat-number">{stats.papers}</p>
          <p className="profile-stat-label">Papers</p>
        </div>
      </section>

      <section className="profile-tabs">
        <div className="profile-tabs-header">
          <button className={`profile-tab ${activeTab === 'publicaciones' ? 'active' : ''}`} onClick={() => setActiveTab('publicaciones')}>Publicaciones</button>
          <button className={`profile-tab ${activeTab === 'coleccion' ? 'active' : ''}`} onClick={() => setActiveTab('coleccion')}>Mi colección</button>
          <button className={`profile-tab ${activeTab === 'actividad' ? 'active' : ''}`} onClick={() => setActiveTab('actividad')}>Actividad</button>
        </div>

        {activeTab === 'publicaciones' && (
          <div className="profile-tab-panel">
            {posts.length === 0 ? (
              <div className="profile-empty">
                <p>Aún no hay publicaciones</p>
                <Link to="/create-post" className="profile-btn">Crear publicación</Link>
              </div>
            ) : (
              <div className="profile-posts-list">
                {posts.map(post => {
                  const date = post.created_at ? new Date(post.created_at).toLocaleDateString('es-AR') : ''
                  const displayNameUser = profile.display_name || `${profile.first_name} ${profile.last_name}`
                  return (
                    <article key={post.id} className="profile-post-card">
                      <header className="profile-post-header">
                        <div className="profile-post-author">
                          {profile.avatar_url ? (
                            <img src={profile.avatar_url} alt={displayNameUser} className="profile-post-avatar" />
                          ) : (
                            <div className="profile-post-avatar-placeholder">{getInitials(displayNameUser)}</div>
                          )}
                          <div>
                            <p className="profile-post-name">{displayNameUser}</p>
                            <p className="profile-post-username">@{profile.username}</p>
                          </div>
                        </div>
                        <div className="profile-post-meta">
                          {date && <span>{date}</span>}
                          <span className="profile-post-type">{post.type}</span>
                        </div>
                      </header>
                      <div className="profile-post-content">
                        {post.thoughts && (
                          <div className="profile-post-text" dangerouslySetInnerHTML={{ __html: post.thoughts }} />
                        )}
                        {post.cover_url && (
                          <div className="profile-post-media">
                            <img src={post.cover_url} alt={post.title} />
                          </div>
                        )}
                      </div>
                      {(post.title || post.creator || post.rating) && (
                        <div className="profile-post-related">
                          <Link to={`/item/${post.id}`} className="profile-post-related-link">
                            <div>
                              <p className="profile-post-related-title">{post.title}</p>
                              {(post.creator || post.rating) && (
                                <p className="profile-post-related-meta">
                                  {post.creator}{post.creator && post.rating ? ' · ' : ''}{post.rating ? `★ ${post.rating}/10` : ''}
                                </p>
                              )}
                            </div>
                          </Link>
                        </div>
                      )}
                      <footer className="profile-post-interactions">
                        <span className={`profile-post-interaction ${post.likes_count ? 'active' : ''}`}>
                          <svg width="18" height="18" viewBox="0 0 24 24" fill={post.likes_count ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                          </svg>
                          <span>{post.likes_count || 0}</span>
                        </span>
                        <span className="profile-post-interaction">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                          </svg>
                          <span>{post.comments_count || 0}</span>
                        </span>
                      </footer>
                    </article>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === 'coleccion' && (
          <div className="profile-tab-panel">
            <div className="profile-section-header">
              <h2>Mi colección</h2>
              <p>Contenido guardado en tu stack</p>
            </div>
            {items.length === 0 ? (
              <div className="profile-empty">
                <p>Aún no hay elementos en tu colección</p>
                <Link to="/add" className="profile-btn">Agregar contenido</Link>
              </div>
            ) : (
              <div className="profile-items-grid">
                {items.map(item => (
                  <Link to={`/item/${item.id}`} key={item.id} className="profile-item-card">
                    <div className="profile-item-cover-wrap">
                      {item.cover_url ? (
                        <img src={item.cover_url} alt={item.title} className="profile-item-cover" />
                      ) : (
                        <div className="profile-item-cover-placeholder">
                          <span>{item.type?.[0]?.toUpperCase() || 'R'}</span>
                        </div>
                      )}
                    </div>
                    <div className="profile-item-body">
                      <h3 className="profile-item-title">{item.title}</h3>
                      {item.creator && <p className="profile-item-creator">{item.creator}</p>}
                      <div className="profile-item-meta">
                        <span className="profile-item-badge">{item.type}</span>
                        {item.rating && <span className="profile-item-rating">★ {item.rating}/10</span>}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'actividad' && (
          <div className="profile-tab-panel">
            <div className="profile-section-header">
              <h2>Actividad</h2>
              <p>Acciones reales del usuario</p>
            </div>
            {activityError && <div className="profile-empty"><p>{activityError}</p></div>}
            {!activityError && activity.length === 0 && <div className="profile-empty"><p>Sin actividad registrada</p></div>}
            {!activityError && activity.length > 0 && (
              <div className="profile-activity-list">
                {activity.map((act, idx) => (
                  <div key={idx} className="profile-activity-item">
                    <p className="profile-activity-text">{act.description || act.action}</p>
                    {act.created_at && <span className="profile-activity-date">{new Date(act.created_at).toLocaleString('es-AR')}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

export default Profile
