import { useState, useEffect } from 'react'
import api from '../services/api'
import './Appearance.css'

const presets = [
  { name: 'Violeta', color: '#6B46C1' },
  { name: 'Rosa viejo', color: '#B98A9D' },
  { name: 'Malva', color: '#9B59B6' },
  { name: 'Ciruela', color: '#8E44AD' }
]

function Appearance() {
  const [selectedColor, setSelectedColor] = useState('#6B46C1')
  const [email, setEmail] = useState('')

  useEffect(() => {
    const saved = localStorage.getItem('themeAccent')
    if (saved) setSelectedColor(saved)
    const userEmail = localStorage.getItem('userEmail')
    if (userEmail) setEmail(userEmail)
  }, [])

  const applyTheme = async (color) => {
    setSelectedColor(color)
    document.documentElement.style.setProperty('--accent-violet', color)
    document.documentElement.style.setProperty('--accent-hover', color + 'CC')
    localStorage.setItem('themeAccent', color)
    
    if (email) {
      try {
        await api.put(`/auth/me/theme?email=${email}`, { theme_accent: color })
      } catch (error) {
        console.error('Error saving theme:', error)
      }
    }
  }

  const resetTheme = async () => {
    const defaultColor = '#6B46C1'
    setSelectedColor(defaultColor)
    document.documentElement.style.setProperty('--accent-violet', defaultColor)
    document.documentElement.style.setProperty('--accent-hover', '#5A3AA8')
    localStorage.removeItem('themeAccent')
    
    if (email) {
      try {
        await api.put(`/auth/me/theme?email=${email}`, { theme_accent: null })
      } catch (error) {
        console.error('Error resetting theme:', error)
      }
    }
  }

  return (
    <div className="appearance-page">
      <header className="appearance-header">
        <h1>Apariencia</h1>
        <p className="appearance-subtitle">Personalizá el color de acento de tu tema</p>
      </header>

      <section className="appearance-section">
        <h2>Color de acento</h2>
        <div className="color-presets">
          {presets.map(preset => (
            <button
              key={preset.color}
              onClick={() => applyTheme(preset.color)}
              className={`color-swatch ${selectedColor === preset.color ? 'active' : ''}`}
              style={{ backgroundColor: preset.color }}
              title={preset.name}
            />
          ))}
        </div>
        
        <div className="custom-color">
          <label>Color personalizado</label>
          <input
            type="color"
            value={selectedColor}
            onChange={(e) => applyTheme(e.target.value)}
            className="color-picker"
          />
        </div>

        <button onClick={resetTheme} className="reset-button">Restablecer tema original</button>
      </section>

      <section className="appearance-section">
        <h2>Vista previa</h2>
        <div className="preview-card">
          <button className="preview-button">Botón primario</button>
          <a href="#" className="preview-link">Enlace de ejemplo</a>
          <span className="preview-badge">Badge</span>
        </div>
      </section>
    </div>
  )
}

export default Appearance
