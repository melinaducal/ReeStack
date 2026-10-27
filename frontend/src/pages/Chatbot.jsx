import { useState, useRef, useEffect } from 'react'
import api from '../services/api'
import './Chatbot.css'

function Chatbot() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hola! Soy tu asistente de recomendaciones. Solo tengo en cuenta lo que ya hay en tu biblioteca para sugerirte contenido nuevo.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)
    setError('')

    try {
      const response = await api.post('/chat/recommend', { message: userMessage })
      const recommendations = response.data.recommendations || []
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: recommendations.length > 0 ? 'Te dejo estas recomendaciones basadas en tu biblioteca:' : 'No encontré recomendaciones nuevas para tu consulta.',
        recommendations 
      }])
    } catch (error) {
      setError(error.response?.data?.detail || 'Error de conexión')
    }
    setLoading(false)
  }

  const saveRecommendation = async (rec) => {
    try {
      await api.post('/chat/save', rec)
      alert('Agregado a tu biblioteca')
    } catch (error) {
      alert(error.response?.data?.detail || 'Error al guardar')
    }
  }

  return (
    <div className="chatbot-container">
      <header className="chatbot-header">
        <h1>Asistente de recomendaciones</h1>
        <p className="chatbot-subtitle">Descubrí contenido según tus gustos</p>
      </header>

      <div className="chatbot-messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            <div className="message-content">
              <p>{msg.content}</p>
              {msg.recommendations && (
                <div className="recommendations-list">
                  {msg.recommendations.map((rec, i) => (
                    <div key={i} className="recommendation-card">
                      <div className="recommendation-header">
                        <h3>{rec.title}</h3>
                        <span className="recommendation-type">{rec.type}</span>
                      </div>
                      {rec.creator && <p className="recommendation-creator">{rec.creator}</p>}
                      <p className="recommendation-reason">{rec.reason}</p>
                      <button onClick={() => saveRecommendation(rec)} className="save-recommendation-btn">
                        Agregar a mi biblioteca
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-content">
              <p className="typing">Pensando...</p>
            </div>
          </div>
        )}
        {error && (
          <div className="message error">
            <div className="message-content">
              <p>{error}</p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="chatbot-input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ej: Recomendame una novela corta de misterio"
          className="chatbot-input"
          disabled={loading}
        />
        <button type="submit" className="chatbot-send" disabled={loading || !input.trim()}>
          Enviar
        </button>
      </form>
    </div>
  )
}

export default Chatbot
