import { useState, useEffect } from 'react'
import api from '../services/api'
import './Settings.css'

const themePalettes = [
  { id: 'default', name: 'Clásico editorial', description: 'Violeta tenue con acentos cálidos', accent: '#6B46C1', bg: '#fbf7f3', surface: '#ffffff', border: '#e6dfd6' },
  { id: 'rose', name: 'Rosa empolvado', description: 'Tonos malva y rosa vintage', accent: '#B98A9D', bg: '#f8f5f7', surface: '#ffffff', border: '#e7dfe6' },
  { id: 'lavender', name: 'Lavanda tenue', description: 'Suave, aireado y editorial', accent: '#9B8BFF', bg: '#f7f6fb', surface: '#ffffff', border: '#e5e1f3' },
  { id: 'plum', name: 'Ciruela', description: 'Profundo y sofisticado', accent: '#7C3FBF', bg: '#f7f5fa', surface: '#ffffff', border: '#e4dff0' }
]

function Settings() {
  const [activePalette, setActivePalette] = useState(localStorage.getItem('themePalette') || 'default')
  const [customAccent, setCustomAccent] = useState(localStorage.getItem('themeAccent') || '#6B46C1')
  const [email, setEmail] = useState('')

  useEffect(() => {
    const userEmail = localStorage.getItem('userEmail')
    if (userEmail) setEmail(userEmail)
    applyPalette(activePalette, customAccent)
  }, [])

  useEffect(() => {
    applyPalette(activePalette, customAccent)
  }, [activePalette, customAccent])

  const applyPalette = (paletteId, accent) => {
    const palette = themePalettes.find(p => p.id === paletteId) || themePalettes[0]
    const finalAccent = accent || palette.accent
    document.documentElement.style.setProperty('--accent-violet', finalAccent)
    document.documentElement.style.setProperty('--accent-hover', finalAccent)
    document.documentElement.style.setProperty('--page-bg', palette.bg)
    document.documentElement.style.setProperty('--surface', palette.surface)
    document.documentElement.style.setProperty('--border-color', palette.border)
    localStorage.setItem('themePalette', paletteId)
    localStorage.setItem('themeAccent', finalAccent)
  }

  const selectPalette = async (paletteId) => {
    setActivePalette(paletteId)
    const palette = themePalettes.find(p => p.id === paletteId) || themePalettes[0]
    setCustomAccent(palette.accent)
    if (email) {
      try {
        await api.put(`/auth/me/theme?email=${email}`, { theme_accent: palette.accent })
      } catch (error) {
        console.error('Error saving theme:', error)
      }
    }
  }

  const applyCustomAccent = async (color) => {
    setCustomAccent(color)
    setActivePalette('custom')
    localStorage.setItem('themePalette', 'custom')
    if (email) {
      try {
        await api.put(`/auth/me/theme?email=${email}`, { theme_accent: color })
      } catch (error) {
        console.error('Error saving theme:', error)
      }
    }
  }

  return (
    <div className="settings-page">
      <header className="settings-page-header">
        <h1>Configuración</h1>
        <p className="settings-page-subtitle">Personalización del tema</p>
      </header>

      <section className="settings-card">
        <div className="settings-card-header">
          <h2>Paletas completas</h2>
          <p>Seleccioná una paleta coherente para toda la aplicación</p>
        </div>
        <div className="palette-grid">
          {themePalettes.map(palette => (
            <button
              key={palette.id}
              onClick={() => selectPalette(palette.id)}
              className={`palette-option ${activePalette === palette.id ? 'active' : ''}`}
              style={{ borderColor: activePalette === palette.id ? palette.accent : 'rgba(139, 123, 168, 0.25)' }}
            >
              <div className="palette-option-header">
                <div className="palette-dots">
                  <span style={{ background: palette.accent }} />
                  <span style={{ background: palette.surface }} />
                  <span style={{ background: palette.bg }} />
                </div>
                {activePalette === palette.id && <span className="palette-check">✓</span>}
              </div>
              <div className="palette-option-body">
                <p className="palette-option-name">{palette.name}</p>
                <p className="palette-option-desc">{palette.description}</p>
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="settings-card">
        <div className="settings-card-header">
          <h2>Color personalizado</h2>
          <p>Personalizá el acento a tu gusto</p>
        </div>
        <div className="custom-row">
          <div className="custom-info">
            <p className="custom-label">Color de acento</p>
            <p className="custom-value">{customAccent}</p>
          </div>
          <input
            type="color"
            value={customAccent}
            onChange={(e) => applyCustomAccent(e.target.value)}
            className="color-input"
          />
        </div>
      </section>
    </div>
  )
}

export default Settings
