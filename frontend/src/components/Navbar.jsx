import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import './Navbar.css'

function Navbar() {
  const navigate = useNavigate()
  const isAuthenticated = localStorage.getItem('token')
  const [profileOpen, setProfileOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!isAuthenticated) return

    let cancelled = false
    const loadUnreadCount = async () => {
      try {
        const res = await api.get('/notifications/unread-count')
        if (!cancelled) setUnreadCount(res.data?.count || 0)
      } catch (e) {
        // A failed badge refresh must never break navigation.
      }
    }

    loadUnreadCount()
    const interval = setInterval(loadUnreadCount, 30000)
    window.addEventListener('focus', loadUnreadCount)
    window.addEventListener('notifications:updated', loadUnreadCount)
    return () => {
      cancelled = true
      clearInterval(interval)
      window.removeEventListener('focus', loadUnreadCount)
      window.removeEventListener('notifications:updated', loadUnreadCount)
    }
  }, [isAuthenticated])

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login', { replace: true })
    window.location.reload()
  }

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">ReeStack</Link>
        <ul className="navbar-menu">
          {isAuthenticated && (
            <>
              <li className="navbar-item">
                <Link to="/" className="navbar-link">Inicio</Link>
              </li>
              <li className="navbar-item">
                <Link to="/stack" className="navbar-link">Mi Stack</Link>
              </li>
              <li className="navbar-item">
                <Link to="/users" className="navbar-link">Buscar usuarios</Link>
              </li>
              <li className="navbar-item">
                <Link to="/friends" className="navbar-link">Amigos</Link>
              </li>
              <li className="navbar-item">
                <Link to="/chatbot" className="navbar-link">ReeIA</Link>
              </li>
              <li className="navbar-item">
                <Link to="/add" className="navbar-link">Buscar y agregar</Link>
              </li>
              <li className="navbar-item">
                <Link to="/create-post" className="navbar-link">Publicar</Link>
              </li>
              <li className="navbar-item">
                <Link to="/notifications" className="navbar-icon-btn" aria-label="Notificaciones" title="Notificaciones">
                  <span className="navbar-bell" aria-hidden="true">🔔</span>
                  {unreadCount > 0 && (
                    <span className="navbar-badge navbar-badge-icon">{unreadCount > 99 ? '99+' : unreadCount}</span>
                  )}
                </Link>
              </li>
              <li className="navbar-item navbar-profile">
                <button className="navbar-profile-btn" onClick={() => setProfileOpen(!profileOpen)}>
                  Perfil
                </button>
                {profileOpen && (
                  <div className="navbar-profile-menu">
                    <Link to="/profile" className="navbar-profile-item" onClick={() => setProfileOpen(false)}>Mi perfil</Link>
                    <Link to="/settings" className="navbar-profile-item" onClick={() => setProfileOpen(false)}>Configuración</Link>
                    <button onClick={handleLogout} className="navbar-profile-item navbar-profile-logout">Cerrar sesión</button>
                  </div>
                )}
              </li>
            </>
          )}
        </ul>
      </div>
    </nav>
  )
}

export default Navbar
