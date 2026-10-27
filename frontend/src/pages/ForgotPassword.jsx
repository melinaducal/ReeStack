import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './ForgotPassword.css'

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await api.post('/auth/forgot-password', { email })
      setMessage(response.data.message)
      setError('')
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al enviar solicitud')
      setMessage('')
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-illustration">
          <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
            <rect x="80" y="100" width="240" height="200" rx="8" fill="rgba(188, 96, 66, 0.2)" stroke="#BC6042" strokeWidth="3"/>
            <circle cx="200" cy="150" r="30" fill="none" stroke="#BC6042" strokeWidth="3"/>
            <rect x="195" y="150" width="10" height="40" rx="5" fill="#BC6042"/>
            <rect x="120" y="220" width="160" height="50" rx="6" fill="rgba(35, 63, 73, 0.1)"/>
            <text x="200" y="250" fontSize="24" fill="#233F49" textAnchor="middle" fontFamily="Lora">?</text>
          </svg>
          <p className="illustration-text">Recuperá el acceso a tu cuenta</p>
        </div>
        <div className="auth-form-section">
          <h1>Recuperar Contraseña</h1>
          <p className="forgot-description">
            Ingresá tu correo electrónico y te enviaremos instrucciones para restablecer tu contraseña.
          </p>
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group">
              <label>Correo electrónico</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            {error && <p className="error-message">{error}</p>}
            {message && <p className="success-message">{message}</p>}
            <button type="submit" className="auth-button">Enviar</button>
          </form>
          <div className="auth-links">
            <Link to="/login">Volver al inicio de sesión</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ForgotPassword
