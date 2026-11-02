import { useState, useRef, useEffect } from 'react'
import api from '../services/api'
import './Chatbot.css'

function Chatbot() {
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hola! Soy tu asistente de recomendaciones. Solo tengo en cuenta lo que ya hay en tu biblioteca para sugerirte contenido nuevo.' }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    fetchConversations()
  }, [])

  const fetchConversations = async () => {
    try {
      const res = await api.get('/chat/conversations')
      setConversations(res.data || [])
    } catch (err) {
      console.error('Error fetching conversations:', err)
    }
  }

  const loadConversation = async (conversationId) => {
    setLoadingHistory(true)
    setError('')
    try {
      const res = await api.get(`/chat/conversations/${conversationId}`)
      const turns = res.data || []
      const loadedMessages = []
      turns.forEach((turn) => {
        if (turn.role === 'user') {
          loadedMessages.push({ role: 'user', content: turn.content })
        } else if (turn.role === 'assistant') {
          loadedMessages.push({
            role: 'assistant',
            content: turn.content,
            recommendations: turn.recommendations || []
          })
        }
      })
      if (loadedMessages.length === 0) {
        loadedMessages.push({ role: 'assistant', content: 'Hola! Continuemos esta conversación.' })
      }
      setMessages(loadedMessages)
      setCurrentConversationId(conversationId)
      fetchConversations()
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al cargar la conversación')
    } finally {
      setLoadingHistory(false)
    }
  }

  const startNewConversation = () => {
    setCurrentConversationId(null)
    setMessages([
      { role: 'assistant', content: 'Hola! Soy tu asistente de recomendaciones. Solo tengo en cuenta lo que ya hay en tu biblioteca para sugerirte contenido nuevo.' }
    ])
    setError('')
  }

  const ensureConversation = async () => {
    if (currentConversationId) return currentConversationId
    try {
      const res = await api.post('/chat/conversations', {})
      const conversationId = res.data?.id
      if (conversationId) {
        setCurrentConversationId(conversationId)
        fetchConversations()
        return conversationId
      }
    } catch (err) {
      console.error('Error creating conversation:', err)
    }
    return null
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = input
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)
    setError('')

    try {
      let conversationId = currentConversationId
      if (!conversationId) {
        conversationId = await ensureConversation()
      }

      const payload = { message: userMessage }
      if (conversationId) {
        payload.conversation_id = conversationId
      }

      const response = await api.post('/chat/recommend', payload)
      const recommendations = response.data.recommendations || []
      if (response.data.conversation_id) {
        setCurrentConversationId(response.data.conversation_id)
        fetchConversations()
      }

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: recommendations.length > 0 ? 'Te dejo estas recomendaciones basadas en tu biblioteca:' : (response.data.message || 'No encontré recomendaciones nuevas para tu consulta.'),
        recommendations
      }])
    } catch (err) {
      setError(err.response?.data?.detail || 'Error de conexión')
    } finally {
      setLoading(false)
    }
  }

  const saveRecommendation = async (rec) => {
    try {
      await api.post('/chat/save', rec)
      alert('Agregado a tu biblioteca')
    } catch (err) {
      alert(err.response?.data?.detail || 'Error al guardar')
    }
  }

  return (
    <div className="chatbot-page">
      <aside className="chatbot-sidebar">
        <div className="chatbot-sidebar-header">
          <button className="new-chat-btn" onClick={startNewConversation}>+ Nueva conversación</button>
        </div>
        <div className="chatbot-conversations">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
              onClick={() => loadConversation(conv.id)}
            >
              <div className="conversation-title">{conv.title || 'Conversación'}</div>
              <div className="conversation-meta">{conv.turns} mensajes</div>
            </button>
          ))}
          {conversations.length === 0 && (
            <p className="conversations-empty">Sin conversaciones aún</p>
          )}
        </div>
      </aside>

      <div className="chatbot-container">
        <header className="chatbot-header">
          <h1>Asistente de recomendaciones</h1>
          <p className="chatbot-subtitle">Descubrí contenido según tus gustos</p>
        </header>

        <div className="chatbot-messages">
          {loadingHistory && (
            <div className="message assistant">
              <div className="message-content">
                <p className="typing">Cargando conversación...</p>
              </div>
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">
                <p>{msg.content}</p>
                {msg.recommendations && msg.recommendations.length > 0 && (
                  <div className="recommendations-list">
                    {msg.recommendations.map((rec, i) => (
                      <div key={i} className="recommendation-card">
                        {rec.cover_url && (
                          <img src={rec.cover_url} alt={rec.title} className="recommendation-cover" />
                        )}
                        <div className="recommendation-header">
                          <h3>{rec.title}</h3>
                          <span className="recommendation-type">{rec.type}</span>
                        </div>
                        {rec.creator && <p className="recommendation-creator">{rec.creator}</p>}
                        {rec.year && <p className="recommendation-year">{rec.year}</p>}
                        {rec.reason && <p className="recommendation-reason">{rec.reason}</p>}
                        <button onClick={() => saveRecommendation(rec)} className="save-recommendation-btn">
                          Agregar a Mi Stack
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
            disabled={loading || loadingHistory}
          />
          <button type="submit" className="chatbot-send" disabled={loading || loadingHistory || !input.trim()}>
            Enviar
          </button>
        </form>
      </div>
    </div>
  )
}

export default Chatbot

