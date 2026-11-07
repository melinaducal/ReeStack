import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import { getErrorMessage } from '../services/errors'
import {
  ProfileCollectionGrid,
  ProfileHeader,
  ProfilePostCard,
  ProfileStats,
  ProfileTabNav
} from '../components/ProfileSections'
import { getInitials } from '../utils/profile'
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
      const res = await api.get('/items', { params: { mine: true, include_posts: false } })
      setItems(res.data || [])
      const data = res.data || []
      setStats(prev => ({
        ...prev,
        items_count: data.length,
        books: data.filter(i => i.type === 'book').length,
        movies: data.filter(i => i.type === 'movie').length,
        series: data.filter(i => i.type === 'series').length,
        music: data.filter(i => i.type === 'music').length,
        papers: data.filter(i => i.type === 'paper').length
      }))
    } catch (e) {
      console.error(e)
    }
  }

  const fetchPosts = async () => {
    try {
      const res = await api.get('/items', { params: { mine: true, type: 'post' } })
      const data = res.data || []
      const sorted = [...data].sort((a, b) => {
        const aTime = a.created_at ? new Date(a.created_at).getTime() : (b.id - a.id)
        const bTime = b.created_at ? new Date(b.created_at).getTime() : (b.id - a.id)
        if (a.created_at && b.created_at) return new Date(b.created_at) - new Date(a.created_at)
        return b.id - a.id
      })
      setPosts(sorted)
      setStats(prev => ({ ...prev, posts_count: sorted.length }))
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

  if (loading) return <div className="profile-page"><p>Cargando...</p></div>
  if (!profile) return <div className="profile-page"><p>No se pudo cargar el perfil</p></div>

  const displayName = profile.display_name || `${profile.first_name} ${profile.last_name}`

  return (
    <div className="profile-page">
      <ProfileHeader
        profile={profile}
        displayName={displayName}
        actions={(
          <>
            <button onClick={() => setEditing(!editing)} className="profile-btn">{editing ? 'Cancelar' : 'Editar perfil'}</button>
            <Link to="/settings" className="profile-btn profile-btn-ghost">Configuración</Link>
          </>
        )}
      />

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

      <ProfileStats stats={stats} />

      <section className="profile-tabs">
        <ProfileTabNav
          tabs={[
            { id: 'publicaciones', label: 'Publicaciones' },
            { id: 'coleccion', label: 'Mi colección' },
            { id: 'actividad', label: 'Actividad' }
          ]}
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        {activeTab === 'publicaciones' && (
          <div className="profile-tab-panel">
            {posts.length === 0 ? (
              <div className="profile-empty">
                <p>Aún no hay publicaciones</p>
                <Link to="/create-post" className="profile-btn">Crear publicación</Link>
              </div>
            ) : (
              <div className="profile-posts-list">
                {posts.map(post => (
                  <ProfilePostCard key={post.id} post={post} owner={profile} />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'coleccion' && (
          <ProfileCollectionGrid
            items={items}
            title="Mi colección"
            subtitle="Contenido guardado en tu stack"
            emptyMessage="Aún no hay elementos en tu colección"
            emptyAction={<Link to="/add" className="profile-btn">Agregar contenido</Link>}
            formatType={item => item.type}
          />
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
