import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import api from '../services/api'
import {
  ProfileCollectionGrid,
  ProfileHeader,
  ProfilePostCard,
  ProfileStats,
  ProfileTabNav
} from '../components/ProfileSections'
import './Profile.css'
import './UserPublicProfile.css'

const TABS = [
  { id: 'publicaciones', label: 'Publicaciones' },
  { id: 'coleccion', label: 'Mi colección' },
  { id: 'actividad', label: 'Actividad' }
]

function UserPublicProfile() {
  const { id } = useParams()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [items, setItems] = useState([])
  const [posts, setPosts] = useState([])
  const [activeTab, setActiveTab] = useState('publicaciones')
  const [currentUser, setCurrentUser] = useState(null)
  const [friendship, setFriendship] = useState({ status: 'none', friendship_id: null })
  const [friendBusy, setFriendBusy] = useState(false)
  const [friendError, setFriendError] = useState('')

  useEffect(() => {
    setProfile(null)
    setItems([])
    setPosts([])
    setActiveTab('publicaciones')
    setFriendship({ status: 'none', friendship_id: null })
    setFriendError('')
    setLoading(true)
    fetchProfile()
    fetchCurrentUser()
    fetchFriendship()
  }, [id])

  const fetchCurrentUser = async () => {
    try {
      const res = await api.get('/auth/me')
      setCurrentUser(res.data)
    } catch (e) {
      // ignore
    }
  }

  const fetchFriendship = async () => {
    try {
      const res = await api.get(`/friends/status/${id}`)
      setFriendship(res.data)
    } catch (e) {
      setFriendship({ status: 'none', friendship_id: null })
    }
  }

  const fetchCollection = async (userId, params) => {
    const collected = []
    let page = 1
    let pages = 1
    do {
      const res = await api.get(`/users/${userId}/collection`, {
        params: { ...params, page, limit: 100 }
      })
      collected.push(...(res.data?.items || []))
      pages = res.data?.pages || 1
      page += 1
    } while (page <= pages)
    return collected
  }

  const fetchPublicContent = async (userId) => {
    const [postsResult, itemsResult] = await Promise.allSettled([
      fetchCollection(userId, { include_posts: true, type: 'post' }),
      fetchCollection(userId, {})
    ])

    setPosts(postsResult.status === 'fulfilled' ? postsResult.value : [])
    setItems(itemsResult.status === 'fulfilled' ? itemsResult.value : [])
  }

  const fetchProfile = async () => {
    try {
      const res = await api.get(`/users/${id}/public`)
      setProfile(res.data)
      await fetchPublicContent(res.data.id)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const sendFriendRequest = async () => {
    setFriendBusy(true)
    setFriendError('')
    try {
      const res = await api.post(`/friends/requests/${profile.id}`)
      setFriendship(res.data)
    } catch (e) {
      setFriendError(e.response?.data?.detail || 'No se pudo enviar la solicitud')
    } finally {
      setFriendBusy(false)
    }
  }

  const respondFriendRequest = async (action) => {
    setFriendBusy(true)
    setFriendError('')
    try {
      const res = await api.post(`/friends/requests/${friendship.friendship_id}/${action}`)
      setFriendship(res.data)
    } catch (e) {
      setFriendError(e.response?.data?.detail || 'No se pudo responder la solicitud')
    } finally {
      setFriendBusy(false)
    }
  }

  const removeFriend = async () => {
    const name = profile.display_name || profile.username
    if (!window.confirm(`¿Eliminar a ${name} de tus amigos?`)) return
    setFriendBusy(true)
    setFriendError('')
    try {
      await api.delete(`/friends/${profile.id}`)
      setFriendship({ status: 'none', friendship_id: null })
    } catch (e) {
      setFriendError(e.response?.data?.detail || 'No se pudo eliminar la amistad')
    } finally {
      setFriendBusy(false)
    }
  }

  if (loading) return <div className="profile-page"><p>Cargando...</p></div>
  if (!profile) return <div className="profile-page"><p>Perfil no encontrado</p></div>

  const displayName = profile.display_name || profile.username
  const isOtherUser = currentUser && currentUser.id !== profile.id

  return (
    <div className="profile-page">
      <ProfileHeader
        profile={profile}
        displayName={displayName}
        actions={isOtherUser ? (
          <div className="public-profile-friend-actions">
            {friendship.status === 'friends' && (
              <>
                <span className="public-profile-friend-status">Amigos</span>
                <button
                  type="button"
                  className="public-profile-friend-btn danger"
                  disabled={friendBusy}
                  onClick={removeFriend}
                >
                  Eliminar amigo
                </button>
              </>
            )}
            {friendship.status === 'pending_outgoing' && (
              <span className="public-profile-friend-status">Solicitud enviada</span>
            )}
            {friendship.status === 'pending_incoming' && (
              <>
                <button
                  type="button"
                  className="public-profile-friend-btn primary"
                  disabled={friendBusy}
                  onClick={() => respondFriendRequest('accept')}
                >
                  Aceptar solicitud
                </button>
                <button
                  type="button"
                  className="public-profile-friend-btn"
                  disabled={friendBusy}
                  onClick={() => respondFriendRequest('reject')}
                >
                  Rechazar
                </button>
              </>
            )}
            {(friendship.status === 'none' || friendship.status === 'rejected') && (
              <button
                type="button"
                className="public-profile-friend-btn primary"
                disabled={friendBusy}
                onClick={sendFriendRequest}
              >
                Agregar amigo
              </button>
            )}
          </div>
        ) : null}
      >
        {friendError && <p className="public-profile-friend-error">{friendError}</p>}
      </ProfileHeader>

      <ProfileStats stats={profile.stats} />

      <section className="profile-tabs">
        <ProfileTabNav tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

        {activeTab === 'publicaciones' && (
          <div className="profile-tab-panel">
            {posts.length === 0 ? (
              <div className="profile-empty">
                <p>Aún no hay publicaciones públicas</p>
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
            subtitle={`Contenido público de @${profile.username}`}
            emptyMessage="No hay elementos públicos visibles"
          />
        )}

        {activeTab === 'actividad' && (
          <div className="profile-tab-panel">
            <div className="profile-section-header">
              <h2>Actividad</h2>
              <p>Actividad pública de @{profile.username}</p>
            </div>
            <div className="profile-empty">
              <p>Sin actividad pública disponible</p>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

export default UserPublicProfile
