import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../services/api'
import './Register.css'

function Register() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    username: '',
    first_name: '',
    last_name: '',
    email: '',
    birth_date: '',
    password: ''
  })
  const [error, setError] = useState('')
  const [passwordErrors, setPasswordErrors] = useState([])

  const validatePassword = (password) => {
    const errors = []
    if (password.length < 8) errors.push('Mínimo 8 caracteres')
    if (!/[A-Z]/.test(password)) errors.push('Al menos una mayúscula')
    if (!/[a-z]/.test(password)) errors.push('Al menos una minúscula')
    if (!/[0-9]/.test(password)) errors.push('Al menos un número')
    if (!/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password)) errors.push('Al menos un carácter especial')
    return errors
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData({
      ...formData,
      [name]: value
    })
    setError('')
    if (name === 'password') {
      setPasswordErrors(validatePassword(value))
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errors = validatePassword(formData.password)
    if (errors.length > 0) {
      setError('La contraseña no cumple con los requisitos de seguridad')
      return
    }

    // Check age
    const birthDate = new Date(formData.birth_date)
    const today = new Date()
    let age = today.getFullYear() - birthDate.getFullYear()
    const monthDiff = today.getMonth() - birthDate.getMonth()
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--
    }
    if (age < 14) {
      setError('Debes ser mayor de 14 años para crear una cuenta')
      return
    }

    try {
      await api.post('/auth/register', formData)
      navigate('/login')
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al registrarse')
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-illustration">
          <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg">
            <rect x="60" y="100" width="120" height="150" rx="6" fill="rgba(201, 143, 134, 0.6)" stroke="#BC6042" strokeWidth="2"/>
            <rect x="220" y="120" width="120" height="150" rx="6" fill="rgba(188, 96, 66, 0.6)" stroke="#BC6042" strokeWidth="2"/>
            <rect x="50" y="90" width="120" height="150" rx="6" fill="rgba(201, 143, 134, 0.8)" stroke="#BC6042" strokeWidth="2"/>
            <rect x="210" y="110" width="120" height="150" rx="6" fill="rgba(188, 96, 66, 0.8)" stroke="#BC6042" strokeWidth="2"/>
            <circle cx="200" cy="300" r="40" fill="rgba(35, 63, 73, 0.1)" stroke="#233F49" strokeWidth="2"/>
            <path d="M 185 295 L 195 305 L 215 285" stroke="#BC6042" strokeWidth="3" fill="none"/>
          </svg>
          <p className="illustration-text">Únete a nuestra comunidad cultural</p>
        </div>
        <div className="auth-form-section register-section">
          <h1>Crear Cuenta</h1>
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-row">
              <div className="form-group">
                <label>Nombre</label>
                <input type="text" name="first_name" value={formData.first_name} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <label>Apellido</label>
                <input type="text" name="last_name" value={formData.last_name} onChange={handleChange} required />
              </div>
            </div>
            <div className="form-group">
              <label>Nombre de usuario</label>
              <input type="text" name="username" value={formData.username} onChange={handleChange} minLength="3" required />
            </div>
            <div className="form-group">
              <label>Correo electrónico</label>
              <input type="email" name="email" value={formData.email} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label>Fecha de nacimiento</label>
              <input type="date" name="birth_date" value={formData.birth_date} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label>Contraseña</label>
              <input type="password" name="password" value={formData.password} onChange={handleChange} required />
              {formData.password && (
                <ul className="password-requirements">
                  <li className={formData.password.length >= 8 ? 'valid' : ''}>Mínimo 8 caracteres</li>
                  <li className={/[A-Z]/.test(formData.password) ? 'valid' : ''}>Una mayúscula</li>
                  <li className={/[a-z]/.test(formData.password) ? 'valid' : ''}>Una minúscula</li>
                  <li className={/[0-9]/.test(formData.password) ? 'valid' : ''}>Un número</li>
                  <li className={/[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(formData.password) ? 'valid' : ''}>Un carácter especial</li>
                </ul>
              )}
            </div>
            {error && <p className="error-message">{error}</p>}
            <button type="submit" className="auth-button">Registrarse</button>
          </form>
          <div className="auth-links">
            <Link to="/login">¿Ya tenés cuenta? Iniciá sesión</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Register
