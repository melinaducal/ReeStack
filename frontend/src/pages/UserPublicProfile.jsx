import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import api from '../services/api'
import './UserPublicProfile.css'

function UserPublicProfile() {
  const { id } = useParams()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState([])

  useEffect(() => {
    fetchProfile()
  }, [id])

  const fetchProfile = async () => {
    try {
      const res = await api.get(`/users/${id}/public`)
      setProfile(res.data)
      try {
        const itemsRes = await api.get('/items', { params: { mine: false } })
        // Can't easily filter by user; only show if any public items exist via feed? Try feed
        const feedRes = await api.get('/items/feed')
        const userItems = (feedRes.data || []).filter(i => i.user_id === res.data.id)
        setItems(userItems)
      } catch (e) {
        setItems([])
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const getInitials = (name) => {
    if (!name) return 'U'
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  if (loading) return <div className="public-profile-page"><p>Cargando...</p></div>
  if (!profile) return <div className="public-profile-page"><p>Perfil no encontrado</p></div>

  const displayName = profile.display_name || profile.username

  return (
    <div className="public-profile-page">
      <header className="public-profile-hero">
        <div className="public-profile-hero-inner">
          <div className="public-profile-avatar-wrap">
            {profile.avatar_url ? (
              <img src={profile.avatar_url} alt={displayName} className="public-profile-avatar" />
            ) : (
              <div className="public-profile-avatar-placeholder">{getInitials(displayName)}</div>
            )}
          </div>
          <div className="public-profile-hero-info">
            <div>
              <h1 className="public-profile-name">{displayName}</h1>
              <p className="public-profile-username">@{profile.username}</p>
            </div>
            {profile.bio && <p className="public-profile-bio">{profile.bio}</p>}
          </div>
        </div>
      </header>

      <section className="public-profile-stats">
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.items_count || 0}</p>
          <p className="public-profile-stat-label">Elementos</p>
        </div>
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.books || 0}</p>
          <p className="public-profile-stat-label">Libros</p>
        </div>
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.movies || 0}</p>
          <p className="public-profile-stat-label">Películas</p>
        </div>
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.series || 0}</p>
          <p className="public-profile-stat-label">Series</p>
        </div>
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.music || 0}</p>
          <p className="public-profile-stat-label">Música</p>
        </div>
        <div className="public-profile-stat-card">
          <p className="public-profile-stat-number">{profile.stats?.papers || 0}</p>
          <p className="public-profile-stat-label">Papers</p>
        </div>
      </section>

      <section className="public-profile-collection">
        <div className="public-profile-section-header">
          <h2>Colección pública</h2>
          <p>Contenido visible en la comunidad</p>
        </div>
        {items.length === 0 ? (
          <div className="public-profile-empty">
            <p>No hay elementos públicos visibles</p>
          </div>
        ) : (
          <div className="public-profile-items-grid">
            {items.map(item => (
              <Link to={`/item/${item.id}`} key={item.id} className="public-profile-item-card">
                <div className="public-profile-item-cover-wrap">
                  {item.cover_url ? (
                    <img src={item.cover_url} alt={item.title} className="public-profile-item-cover" />
                  ) : (
                    <div className="public-profile-item-cover-placeholder">
                      <span>{item.type?.[0]?.toUpperCase() || 'R'}</span>
                    </div>
                  )}
                </div>
                <div className="public-profile-item-body">
                  <h3 className="public-profile-item-title">{item.title}</h3>
                  {item.creator && <p className="public-profile-item-creator">{item.creator}</p>}
                  <div className="public-profile-item-meta">
                    <span className="public-profile-item-badge">{item.type}</span>
                    {item.rating && <span className="public-profile-item-rating">★ {item.rating}/10</span>}
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

export default UserPublicProfile
