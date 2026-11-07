import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './Friends.css'

const formatDate = (value) => {
  if (!value) return ''
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasTimezone ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('es-AR', { day: 'numeric', month: 'long', year: 'numeric' })
}

const getInitials = (name) => {
  if (!name) return 'U'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const displayName = (user) => user?.display_name || user?.username || 'Usuario'

function Friends() {
  const [friends, setFriends] = useState([])
  const [requests, setRequests] = useState([])
  const [sentRequests, setSentRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    loadFriends()
  }, [])

  const loadFriends = async () => {
    try {
      setLoading(true)
      const [friendsRes, requestsRes, sentRes] = await Promise.all([
        api.get('/friends'),
        api.get('/friends/requests'),
        api.get('/friends/requests/sent')
      ])
      setFriends(friendsRes.data || [])
      setRequests(requestsRes.data || [])
      setSentRequests(sentRes.data || [])
      setError('')
    } catch (err) {
      console.error('Error loading friends:', err)
      setError('No se pudieron cargar tus amistades')
    } finally {
      setLoading(false)
    }
  }

  const respondRequest = async (requestId, action) => {
    setBusyId(requestId)
    try {
      await api.post(`/friends/requests/${requestId}/${action}`)
      await loadFriends()
    } catch (err) {
      console.error(`Error trying to ${action} friend request:`, err)
      setError(err.response?.data?.detail || 'No se pudo responder la solicitud')
    } finally {
      setBusyId(null)
    }
  }

  const removeFriend = async (user) => {
    if (!window.confirm(`¿Eliminar a ${displayName(user)} de tus amigos?`)) return
    setBusyId(user.id)
    try {
      await api.delete(`/friends/${user.id}`)
      await loadFriends()
    } catch (err) {
      console.error('Error removing friend:', err)
      setError(err.response?.data?.detail || 'No se pudo eliminar la amistad')
    } finally {
      setBusyId(null)
    }
  }

  const renderAvatar = (user, size = 'normal') => {
    if (user?.avatar_url) {
      return (
        <img
          src={user.avatar_url}
          alt={displayName(user)}
          className={`friends-avatar ${size}`}
        />
      )
    }
    return (
      <div className={`friends-avatar placeholder ${size}`}>
        {getInitials(displayName(user))}
      </div>
    )
  }

  return (
    <div className="friends-page">
      <header className="friends-header">
        <div>
          <h1>Amigos</h1>
          <p>Gestioná tus solicitudes y descubrí con quién compartís intereses</p>
        </div>
        <Link to="/users" className="friends-discover-link">Buscar usuarios</Link>
      </header>

      {loading && <p className="friends-state">Cargando amistades...</p>}
      {error && <p className="friends-state friends-error">{error}</p>}

      {!loading && (
        <>
          <section className="friends-section">
            <div className="friends-section-header">
              <h2>Solicitudes recibidas</h2>
              <span className="friends-count">{requests.length}</span>
            </div>
            {requests.length === 0 ? (
              <p className="friends-empty">No tenés solicitudes pendientes.</p>
            ) : (
              <div className="friends-list">
                {requests.map(request => (
                  <article key={request.friendship_id} className="friends-row">
                    <Link to={`/users/${request.user.id}`} className="friends-person">
                      {renderAvatar(request.user)}
                      <div>
                        <p className="friends-name">{displayName(request.user)}</p>
                        <p className="friends-username">@{request.user.username}</p>
                      </div>
                    </Link>
                    <div className="friends-row-actions">
                      <span className="friends-date">{formatDate(request.created_at)}</span>
                      <button
                        type="button"
                        className="friends-btn primary"
                        disabled={busyId === request.friendship_id}
                        onClick={() => respondRequest(request.friendship_id, 'accept')}
                      >
                        Aceptar
                      </button>
                      <button
                        type="button"
                        className="friends-btn"
                        disabled={busyId === request.friendship_id}
                        onClick={() => respondRequest(request.friendship_id, 'reject')}
                      >
                        Rechazar
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="friends-section">
            <div className="friends-section-header">
              <h2>Tus amigos</h2>
              <span className="friends-count">{friends.length}</span>
            </div>
            {friends.length === 0 ? (
              <p className="friends-empty">Todavía no tenés amigos en ReeStack.</p>
            ) : (
              <div className="friends-grid">
                {friends.map(friend => (
                  <article key={friend.friendship_id} className="friends-card">
                    <Link to={`/users/${friend.user.id}`} className="friends-card-top">
                      {renderAvatar(friend.user, 'large')}
                      <div>
                        <p className="friends-name">{displayName(friend.user)}</p>
                        <p className="friends-username">@{friend.user.username}</p>
                      </div>
                    </Link>
                    <p className="friends-date">Amigos desde {formatDate(friend.since)}</p>
                    <button
                      type="button"
                      className="friends-btn danger"
                      disabled={busyId === friend.user.id}
                      onClick={() => removeFriend(friend.user)}
                    >
                      Eliminar amigo
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="friends-section">
            <div className="friends-section-header">
              <h2>Solicitudes enviadas</h2>
              <span className="friends-count">{sentRequests.length}</span>
            </div>
            {sentRequests.length === 0 ? (
              <p className="friends-empty">No tenés solicitudes enviadas pendientes.</p>
            ) : (
              <div className="friends-list">
                {sentRequests.map(request => (
                  <article key={request.friendship_id} className="friends-row">
                    <Link to={`/users/${request.user.id}`} className="friends-person">
                      {renderAvatar(request.user)}
                      <div>
                        <p className="friends-name">{displayName(request.user)}</p>
                        <p className="friends-username">@{request.user.username}</p>
                      </div>
                    </Link>
                    <div className="friends-row-actions">
                      <span className="friends-badge">Pendiente</span>
                      <span className="friends-date">{formatDate(request.created_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}

export default Friends
