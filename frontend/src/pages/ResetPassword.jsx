import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../services/api'
import { getErrorMessage } from '../services/errors'
import './ForgotPassword.css'
import './ResetPassword.css'

const PASSWORD_RULES = [
  'Al menos 8 caracteres',
  'Una mayúscula y una minúscula',
  'Al menos un número',
  'Al menos un carácter especial'
]

function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [formData, setFormData] = useState({ password: '', confirm: '' })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value })
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!token) {
      setError('El enlace no incluye un token de recuperación. Solicitá uno nuevo.')
      return
    }
    if (formData.password !== formData.confirm) {
      setError('Las contraseñas no coinciden.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await api.post('/auth/reset-password', {
        token,
        new_password: formData.password
      })
      // The backend invalidated every previous session, so the stored token
      // must not stay in the browser.
      localStorage.removeItem('token')
      localStorage.removeItem('userEmail')
      window.dispatchEvent(new Event('storage'))
      setMessage(response.data.message || 'Contraseña actualizada correctamente.')
      setError('')
      setFormData({ password: '', confirm: '' })
    } catch (requestError) {
      setError(getErrorMessage(requestError, 'No se pudo actualizar la contraseña'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-illustration">
          <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
            <rect x="80" y="90" width="240" height="220" rx="8" fill="rgba(188, 96, 66, 0.2)" stroke="#BC6042" strokeWidth="3" />
            <circle cx="200" cy="160" r="28" fill="none" stroke="#BC6042" strokeWidth="3" />
            <rect x="195" y="160" width="10" height="42" rx="5" fill="#BC6042" />
            <rect x="150" y="235" width="100" height="16" rx="8" fill="rgba(35, 63, 73, 0.18)" />
            <rect x="150" y="260" width="70" height="16" rx="8" fill="rgba(35, 63, 73, 0.12)" />
          </svg>
          <p className="illustration-text">Elegí una nueva contraseña para tu cuenta</p>
        </div>

        <div className="auth-form-section">
          <h1>Nueva Contraseña</h1>

          {message ? (
            <div className="reset-success">
              <p className="success-message">{message}</p>
              <Link to="/login" className="reset-success-link">Ir al inicio de sesión</Link>
            </div>
          ) : (
            <>
              <p className="forgot-description">
                El enlace vence a los 30 minutos y solo puede usarse una vez.
              </p>
              <form onSubmit={handleSubmit} className="auth-form">
                <div className="form-group">
                  <label htmlFor="password">Nueva contraseña</label>
                  <input
                    id="password"
                    type="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    autoComplete="new-password"
                    minLength={8}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="confirm">Repetí la contraseña</label>
                  <input
                    id="confirm"
                    type="password"
                    name="confirm"
                    value={formData.confirm}
                    onChange={handleChange}
                    autoComplete="new-password"
                    minLength={8}
                    required
                  />
                </div>

                <ul className="password-hint">
                  {PASSWORD_RULES.map((rule) => <li key={rule}>{rule}</li>)}
                </ul>

                {error && <p className="error-message">{error}</p>}
                {!token && (
                  <p className="error-message">
                    El enlace está incompleto. <Link to="/forgot-password">Solicitá uno nuevo</Link>.
                  </p>
                )}

                <button type="submit" className="auth-button" disabled={isSubmitting || !token}>
                  {isSubmitting ? 'Guardando…' : 'Guardar contraseña'}
                </button>
              </form>
              <div className="auth-links">
                <Link to="/forgot-password">Solicitar otro enlace</Link>
                <Link to="/login">Volver al inicio de sesión</Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ResetPassword
