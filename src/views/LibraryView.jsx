import { useMemo, useState } from 'react'
import { BookMarked } from 'lucide-react'

import Cover from '../components/Cover.jsx'
import Modal from '../components/Modal.jsx'
import { KIND_LABEL, STATUS_LABEL } from '../lib/catalog.js'

const STATUSES = ['all', 'planned', 'in_progress', 'completed']

const RATING_OPTIONS = [
  { value: '', label: 'No rating' },
  { value: '1', label: '1 / 5' },
  { value: '2', label: '2 / 5' },
  { value: '3', label: '3 / 5' },
  { value: '4', label: '4 / 5' },
  { value: '5', label: '5 / 5' },
]

/**
 * Editing happens in a dialog so each entry keeps one bounded form, and
 * progress can never exceed the work's own total.
 */
function EntryDialog({ entry, open, onClose, onUpdate, onRemove }) {
  const total = entry.content.total_units
  const unitLabel = entry.content.unit_label || 'units'

  const [status, setStatus] = useState(entry.status)
  const [progress, setProgress] = useState(String(entry.progress ?? 0))
  const [rating, setRating] = useState(entry.rating ? String(entry.rating) : '')
  const [review, setReview] = useState(entry.review || '')
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  const close = () => {
    setConfirmRemove(false)
    setError(null)
    onClose()
  }

  const save = async (event) => {
    event.preventDefault()
    setError(null)

    const numeric = Number(progress)
    if (Number.isNaN(numeric) || numeric < 0) {
      setError('Progress must be a positive number.')
      return
    }
    if (total != null && numeric > total) {
      setError('Progress exceeds the total.')
      return
    }

    setPending(true)
    try {
      await onUpdate(entry.id, {
        status,
        progress: numeric,
        rating: rating ? Number(rating) : null,
        review,
      })
      close()
    } catch (err) {
      setError(err?.detail || 'Could not save your changes.')
    } finally {
      setPending(false)
    }
  }

  const remove = async () => {
    setError(null)
    if (!confirmRemove) {
      setConfirmRemove(true)
      return
    }
    setPending(true)
    try {
      await onRemove(entry.id)
      close()
    } catch (err) {
      setError(err?.detail || 'Could not remove this item.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title={`Edit ${entry.content.title}`} labelledBy="entry-title">
      <form className="stack" onSubmit={save} noValidate>
        <div className="entry-dialog__work">
          <Cover content={entry.content} size="sm" />
          <div>
            <span className="eyebrow">{KIND_LABEL[entry.content.kind] || 'Item'}</span>
            <strong>{entry.content.title}</strong>
            <span className="muted small">{entry.content.creator}</span>
          </div>
        </div>

        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Progress ({unitLabel})
          <input
            type="number"
            min="0"
            max={total ?? undefined}
            value={progress}
            onChange={(event) => setProgress(event.target.value)}
          />
        </label>

        <label>
          Rating
          <select value={rating} onChange={(event) => setRating(event.target.value)}>
            {RATING_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Private review
          <textarea rows={3} value={review} onChange={(event) => setReview(event.target.value)} />
        </label>

        <p className="muted small">Only you can see your progress, rating and review.</p>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <div className="entry-dialog__actions">
          <button type="submit" className="button button--primary" disabled={pending}>
            {pending ? 'Saving…' : 'Save changes'}
          </button>
          <button type="button" className="button button--ghost" onClick={remove} disabled={pending}>
            {confirmRemove ? 'Remove permanently' : 'Remove from library'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export default function LibraryView({ app }) {
  const [status, setStatus] = useState('all')
  const [kind, setKind] = useState('all')
  const [editing, setEditing] = useState(null)

  const entries = useMemo(
    () =>
      app.collection.filter((entry) => {
        const matchesStatus = status === 'all' || entry.status === status
        const matchesKind = kind === 'all' || entry.content.kind === kind
        return matchesStatus && matchesKind
      }),
    [app.collection, status, kind],
  )

  if (app.libraryError) {
    return (
      <div className="page">
        <p className="form-error" role="alert">
          {app.libraryError}
        </p>
        <button type="button" className="button button--primary" onClick={app.retryLibrary}>
          Retry library
        </button>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <span className="eyebrow">My library</span>
          <h1>A little space of your own.</h1>
          <p className="muted">Only you can see this page. Publish a reflection when you want to share it.</p>
        </div>
      </header>

      <div className="toolbar" role="group" aria-label="Filter your library">
        <div className="chips">
          {STATUSES.map((value) => (
            <button
              key={value}
              type="button"
              className={`chip ${status === value ? 'is-active' : ''}`}
              aria-pressed={status === value}
              onClick={() => setStatus(value)}
            >
              {value === 'all' ? 'All' : STATUS_LABEL[value]}
            </button>
          ))}
        </div>
        <label className="select-inline">
          <span className="sr-only">Filter by type</span>
          <select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="all">All types</option>
            {Object.entries(KIND_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {entries.length === 0 ? (
        <div className="empty">
          <BookMarked size={26} strokeWidth={1.4} aria-hidden="true" />
          <p>
            <strong>Your next discovery belongs here.</strong>
          </p>
          <p className="muted small">Save something from Discover to start tracking it.</p>
        </div>
      ) : (
        <ul className="entries">
          {entries.map((entry) => (
            <li key={entry.id} className="card entry">
              <Cover content={entry.content} size="sm" />
              <div className="entry__body">
                <span className="eyebrow">{KIND_LABEL[entry.content.kind] || 'Item'}</span>
                <strong>{entry.content.title}</strong>
                <span className="muted small">
                  {entry.progress}
                  {entry.content.total_units ? ` / ${entry.content.total_units}` : ''}{' '}
                  {entry.content.unit_label || ''}
                </span>
                {entry.rating ? (
                  <span className="stars" aria-label={`Rated ${entry.rating} out of 5`}>
                    {'★'.repeat(entry.rating)}
                    <span className="stars__off">{'★'.repeat(5 - entry.rating)}</span>
                  </span>
                ) : (
                  <span className="muted small">Not rated</span>
                )}
              </div>
              <button
                type="button"
                className="button button--ghost button--tiny"
                onClick={() => setEditing(entry)}
                aria-label={`Edit ${entry.content.title}`}
              >
                Edit
              </button>
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <EntryDialog
          key={editing.id}
          entry={editing}
          open
          onClose={() => setEditing(null)}
          onUpdate={app.updateEntry}
          onRemove={app.removeEntry}
        />
      )}
    </div>
  )
}
