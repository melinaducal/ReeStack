import { useState } from 'react'

import Cover from './Cover.jsx'
import Modal from './Modal.jsx'

const MAX = 5000

/**
 * Publishes a public reflection. The work link is optional on purpose: a post
 * may exist before the item is finished, saved, or even in the catalog.
 */
export default function Composer({ open, onClose, contents, onSubmit }) {
  const [body, setBody] = useState('')
  const [contentId, setContentId] = useState('')
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  const close = () => {
    setBody('')
    setContentId('')
    setError(null)
    onClose()
  }

  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    if (!body.trim()) {
      setError('Write something before publishing.')
      return
    }
    setPending(true)
    try {
      await onSubmit({ body: body.trim(), content_id: contentId ? Number(contentId) : null })
      close()
    } catch (err) {
      setError(err?.detail || 'Could not publish your reflection.')
    } finally {
      setPending(false)
    }
  }

  const linked = contents.find((item) => String(item.id) === contentId)

  return (
    <Modal open={open} onClose={close} title="A thought worth sharing" labelledBy="composer-title">
      <form className="stack" onSubmit={submit} noValidate>
        <label>
          <span className="sr-only">Your reflection</span>
          <textarea
            aria-label="Your reflection"
            rows={4}
            value={body}
            onChange={(event) => setBody(event.target.value.slice(0, MAX))}
            placeholder="What are you reading, watching or listening to? You do not need to finish it first."
          />
        </label>

        <label>
          Link a work (optional)
          <select value={contentId} onChange={(event) => setContentId(event.target.value)}>
            <option value="">No linked work</option>
            {contents.map((content) => (
              <option key={content.id} value={content.id}>
                {content.title} — {content.creator}
              </option>
            ))}
          </select>
        </label>

        {linked && (
          <div className="composer__linked">
            <Cover content={linked} size="xs" />
            <p className="muted small">Public · your private progress and review stay hidden.</p>
          </div>
        )}

        <p className="muted small">
          {body.length} / {MAX} characters · Reflections are public and appear in the community feed.
        </p>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="button button--primary" disabled={pending}>
          {pending ? 'Publishing…' : 'Publish reflection'}
        </button>
      </form>
    </Modal>
  )
}
