import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import { getErrorMessage } from '../services/errors'
import libraryImage from '../assets/library-oil.png'
import libraryOpenImage from '../assets/library-open.png'
import './Login.css'

function Login() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })
  const [error, setError] = useState('')
  const [isAnimating, setIsAnimating] = useState(false)

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await api.post('/auth/login', formData)
      localStorage.setItem('token', response.data.access_token)
      localStorage.setItem('userEmail', formData.email)
      if (response.data.theme_accent) {
        localStorage.setItem('themeAccent', response.data.theme_accent)
        document.documentElement.style.setProperty('--accent-violet', response.data.theme_accent)
      }
      
      const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (prefersReducedMotion) {
        navigate('/', { replace: true })
        window.location.reload()
      } else {
        setIsAnimating(true)
        setTimeout(() => {
          navigate('/', { replace: true })
          window.location.reload()
        }, 1200)
      }
    } catch (error) {
      setError(getErrorMessage(error, 'Error al iniciar sesión'))
    }
  }

  return (
    <div className="auth-page">
      {isAnimating && (
        <div className="entrance-animation">
          <div className="animation-scene">
            <img src={libraryImage} alt="Librería" className="library-scene closed" />
            <img src={libraryOpenImage} alt="Librería puerta abierta" className="library-scene open" />
            <div className="door-container">
              <div className="door"></div>
            </div>
          </div>
        </div>
      )}
      <div className="auth-container">
        <div className="auth-illustration">
          <img src={libraryImage} alt="Librería al óleo" className="library-illustration" />
          <p className="illustration-text">Bienvenido a tu biblioteca cultural</p>
        </div>
        <div className="auth-form-section">
          <h1>Iniciar Sesión</h1>
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label>Correo electrónico</label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Contraseña</label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                required
              />
            </div>
            {error && <p className="error-message">{error}</p>}
            <button type="submit" className="auth-button">Ingresar</button>
          </form>
          <div className="auth-links">
            <Link to="/forgot-password">¿Olvidaste tu contraseña?</Link>
            <Link to="/register">¿No tenés cuenta? Registrate</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
