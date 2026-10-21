import { useState } from 'react'
import { Bot } from 'lucide-react'

import Modal from '../components/Modal.jsx'

/**
 * The assistant is a dialog, not a page: it is a tool you open, use, and
 * dismiss without leaving the feed behind.
 *
 * Chat state lives in the parent so closing the dialog keeps the conversation,
 * while signing out clears it (the parent remounts with a fresh key).
 */
export default function AssistantView({ app, open, onClose }) {
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)

  const { configured, model } = app.assistant

  const send = async (message) => {
    setError(null)
    setPending(true)
    try {
      const reply = await app.askAssistant(message)
      setMessages((prev) => [...prev, { role: 'assistant', text: reply }])
    } catch (err) {
      setError(err?.detail || 'The assistant could not answer right now.')
    } finally {
      setPending(false)
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    const question = draft.trim()
    if (!question) return
    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setDraft('')
    await send(question)
  }

  const retry = async () => {
    const last = [...messages].reverse().find((message) => message.role === 'user')
    if (!last) return
    await send(last.text)
  }

  return (
    <Modal open={open} onClose={onClose} title="Assistant" labelledBy="assistant-title">
      <div className="stack">
        {configured ? (
          <p className="muted small">
            The assistant reads your own collection and posts and sends them to the configured LLM. Nothing else is
            shared, and your private library is never exposed to other people.
          </p>
        ) : (
          <p className="muted small" role="status">
            The assistant is not configured in this server environment. Set <code>OPENAI_API_KEY</code> and restart
            the API to enable it.
          </p>
        )}

        <div className="chat" aria-live="polite">
          {messages.length === 0 && (
            <p className="muted small">Try: “What am I partway through?” or “Which paper should I revisit?”</p>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`bubble bubble--${message.role}`}>
              <span className="bubble__icon" aria-hidden="true">
                <Bot size={14} strokeWidth={1.8} />
              </span>
              <p>{message.text}</p>
            </div>
          ))}
          {pending && <p className="muted small">Thinking…</p>}
        </div>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {error && (
          <button type="button" className="button button--ghost button--tiny" onClick={retry} disabled={pending}>
            Retry message
          </button>
        )}

        <form className="chat-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="assistant-input">
            Message the assistant
          </label>
          <input
            id="assistant-input"
            aria-label="Message the assistant"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={configured ? 'Ask about your library…' : 'The assistant is not configured'}
            disabled={!configured || pending}
          />
          <button type="submit" className="button button--primary" disabled={!configured || pending || !draft.trim()}>
            Send message
          </button>
        </form>
      </div>
    </Modal>
  )
}
