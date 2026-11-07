import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './Notifications.css'

const formatDate = (value) => {
  if (!value) return ''
  const hasTimezone = /(Z|[+-]\d{2}:?\d{2})$/.test(value)
  const date = new Date(hasTimezone ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('es-AR', { dateStyle: 'medium', timeStyle: 'short' })
}

const actorName = (notification) =>
  notification.actor?.display_name ||
  notification.actor?.username ||
  'Alguien'

const getInitials = (name) => {
  if (!name) return 'U'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

function Notifications() {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchNotifications()
  }, [filter])

  const fetchNotifications = async () => {
    try {
      setLoading(true)
      const params = filter === 'unread' ? { unread_only: true } : {}
      const [listRes, countRes] = await Promise.all([
        api.get('/notifications', { params }),
        api.get('/notifications/unread-count')
      ])
      setNotifications(listRes.data || [])
      setUnreadCount(countRes.data?.count || 0)
      setError('')
    } catch (err) {
      console.error('Error fetching notifications:', err)
      setError('No se pudieron cargar las notificaciones')
    } finally {
      setLoading(false)
    }
  }

  const markAsRead = async (notificationId) => {
    try {
      const res = await api.post(`/notifications/${notificationId}/read`)
      setNotifications(prev => filter === 'unread'
        ? prev.filter(notification => notification.id !== notificationId)
        : prev.map(notification =>
            notification.id === notificationId ? res.data : notification
          )
      )
      setUnreadCount(prev => Math.max(0, prev - 1))
      window.dispatchEvent(new Event('notifications:updated'))
    } catch (err) {
      console.error('Error marking notification as read:', err)
    }
  }

  const markAllAsRead = async () => {
    try {
      await api.post('/notifications/read-all')
      setNotifications(prev => filter === 'unread'
        ? []
        : prev.map(notification => ({ ...notification, is_read: true }))
      )
      setUnreadCount(0)
      window.dispatchEvent(new Event('notifications:updated'))
    } catch (err) {
      console.error('Error marking all notifications as read:', err)
    }
  }

  const targetLink = (notification) => {
    if (notification.item) return `/item/${notification.item.id}`
    if (notification.type === 'friend_request') return '/friends'
    if (notification.actor) return `/users/${notification.actor.id}`
    return null
  }

  const renderMessage = (notification) => {
    const name = actorName(notification)
    if (notification.type === 'friend_request') {
      return <><strong>{name}</strong> te envió una solicitud de amistad</>
    }
    if (notification.type === 'friend_accepted') {
      return <><strong>{name}</strong> aceptó tu solicitud de amistad</>
    }
    if (notification.type === 'like') {
      return <><strong>{name}</strong> le dio me gusta a tu publicación {notification.item ? `“${notification.item.title}”` : ''}</>
    }
    if (notification.type === 'comment') {
      return <><strong>{name}</strong> comentó tu publicación {notification.item ? `“${notification.item.title}”` : ''}</>
    }
    return <><strong>{name}</strong> realizó una acción</>
  }

  return (
    <div className="notifications-page">
      <header className="notifications-header">
        <div>
          <h1>Notificaciones</h1>
          <p>Solicitudes de amistad, me gusta y comentarios en tus publicaciones</p>
        </div>
        <button
          type="button"
          className="notifications-mark-all"
          onClick={markAllAsRead}
          disabled={unreadCount === 0}
        >
          Marcar todas como leídas
        </button>
      </header>

      <div className="notifications-tabs" role="tablist" aria-label="Filtrar notificaciones">
        <button
          type="button"
          className={filter === 'all' ? 'active' : ''}
          onClick={() => setFilter('all')}
        >
          Todas
        </button>
        <button
          type="button"
          className={filter === 'unread' ? 'active' : ''}
          onClick={() => setFilter('unread')}
        >
          No leídas {unreadCount > 0 && <span className="notifications-tab-badge">{unreadCount}</span>}
        </button>
      </div>

      {loading && <p className="notifications-state">Cargando notificaciones...</p>}
      {error && <p className="notifications-state notifications-error">{error}</p>}
      {!loading && !error && notifications.length === 0 && (
        <div className="notifications-empty">
          <p>{filter === 'unread' ? 'No tenés notificaciones sin leer.' : 'Todavía no tenés notificaciones.'}</p>
          <Link to="/users">Explorar usuarios</Link>
        </div>
      )}

      {!loading && !error && notifications.length > 0 && (
        <ul className="notifications-list">
          {notifications.map(notification => {
            const name = actorName(notification)
            const target = targetLink(notification)
            return (
              <li
                key={notification.id}
                className={`notification-card ${notification.is_read ? 'read' : 'unread'}`}
              >
                <div className="notification-avatar-wrap">
                  {notification.actor?.avatar_url ? (
                    <img
                      src={notification.actor.avatar_url}
                      alt={name}
                      className="notification-avatar"
                    />
                  ) : (
                    <div className="notification-avatar placeholder">{getInitials(name)}</div>
                  )}
                </div>

                <div className="notification-body">
                  <p className="notification-message">{renderMessage(notification)}</p>
                  {notification.comment_preview && (
                    <p className="notification-preview">“{notification.comment_preview}”</p>
                  )}
                  <div className="notification-meta">
                    <span>{formatDate(notification.created_at)}</span>
                    {target && <Link to={target} className="notification-link">Ver</Link>}
                    {!notification.is_read && (
                      <button
                        type="button"
                        className="notification-read-btn"
                        onClick={() => markAsRead(notification.id)}
                      >
                        Marcar como leída
                      </button>
                    )}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default Notifications
