import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { getErrorMessage } from '../services/errors'
import './Profile.css'

function Profile() {
  const [profile, setProfile] = useState(null)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    display_name: '',
    bio: '',
    avatar_url: '',
    username: ''
  })
  const [stats, setStats] = useState({ items_count: 0, books: 0, movies: 0, series: 0, music: 0, papers: 0 })
  const [avatarUploading, setAvatarUploading] = useState(false)
  const [avatarError, setAvatarError] = useState('')

  useEffect(() => {
    fetchProfile()
    fetchItems()
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
      const s = {
        items_count: res.data.length,
        books: res.data.filter(i => i.type === 'book').length,
        movies: res.data.filter(i => i.type === 'movie').length,
        series: res.data.filter(i => i.type === 'series').length,
        music: res.data.filter(i => i.type === 'music').length,
        papers: res.data.filter(i => i.type === 'paper').length
      }
      setStats(s)
    } catch (e) {
      console.error(e)
    }
  }

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
          <p className="profile-stat-number">{stats.items_count}</p>
          <p className="profile-stat-label">Elementos</p>
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

      <section className="profile-collection">
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
      </section>
    </div>
  )
}

export default Profile
