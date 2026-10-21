import { useRef, useState } from 'react'
import Modal from './Modal.jsx'

export default function AuthDialog({ open, onClose, onSubmit }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', display_name: '', password: '' })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const usernameRef = useRef(null)

  const update = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    if (!form.username.trim() || !form.password) return
    if (mode === 'register' && form.password.length < 10) {
      setError('Choose a password with at least 10 characters.')
      return
    }
    setPending(true)
    try {
      await onSubmit({ mode, ...form })
      setForm({ username: '', display_name: '', password: '' })
      setMode('login')
      onClose()
    } catch (err) {
      setError(err?.detail || 'Something went wrong. Please try again.')
    } finally {
      setPending(false)
    }
  }

  const switchMode = (next) => {
    setMode(next)
    setError(null)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Welcome back"
      labelledBy="auth-title"
      initialFocusRef={usernameRef}
    >
      <p className="muted">
        Sign in to keep your library, progress and reviews. Only what you publish appears in the public feed.
      </p>

      <div className="segmented" role="tablist" aria-label="Authentication mode">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'login'}
          className={mode === 'login' ? 'is-active' : ''}
          onClick={() => switchMode('login')}
        >
          Sign in
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'register'}
          className={mode === 'register' ? 'is-active' : ''}
          onClick={() => switchMode('register')}
        >
          Register
        </button>
      </div>

      <form className="stack" onSubmit={submit} noValidate>
        <label>
          Username
          <input
            ref={usernameRef}
            name="username"
            autoComplete="username"
            value={form.username}
            onChange={update('username')}
            required
            minLength={3}
            placeholder="lowercase, no spaces"
          />
        </label>

        {mode === 'register' && (
          <label>
            Display name
            <input
              name="display_name"
              autoComplete="nickname"
              value={form.display_name}
              onChange={update('display_name')}
              required
              placeholder="How others see you"
            />
          </label>
        )}

        <label>
          Password
          <input
            name="password"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={form.password}
            onChange={update('password')}
            required
            minLength={mode === 'register' ? 10 : 1}
            placeholder={mode === 'register' ? 'at least 10 characters' : 'your password'}
          />
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button button--primary" disabled={pending}>
          {pending ? 'Working…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>
    </Modal>
  )
}
