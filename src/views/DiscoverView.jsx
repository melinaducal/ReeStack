import { useEffect, useMemo, useRef, useState } from 'react'
import { Plus, Search } from 'lucide-react'

import Cover from '../components/Cover.jsx'
import Modal from '../components/Modal.jsx'
import { KIND_LABEL, KINDS, UNIT_DEFAULT, kindIcon } from '../lib/catalog.js'

const EMPTY_FORM = {
  title: '',
  creator: '',
  kind: 'book',
  year: '',
  description: '',
  total_units: '',
  unit_label: '',
}

/**
 * Adding to the catalog has two steps: create the work, then save it to the
 * reader's library. If the first succeeds and the second fails, the created
 * work is kept so retrying never duplicates it — the second step is retried,
 * never the first.
 */
export function AddContentDialog({ open, onClose, onCreate, onSave }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [created, setCreated] = useState(null)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  const reset = () => {
    setForm(EMPTY_FORM)
    setCreated(null)
    setError(null)
  }

  const close = () => {
    reset()
    onClose()
  }

  const update = (field) => (event) => setForm((prev) => ({ ...prev, [field]: event.target.value }))

  const payload = () => ({
    title: form.title.trim(),
    creator: form.creator.trim(),
    kind: form.kind,
    year: form.year ? Number(form.year) : null,
    description: form.description.trim(),
    total_units: form.total_units ? Number(form.total_units) : null,
    unit_label: form.unit_label || UNIT_DEFAULT[form.kind],
  })

  const saveCreated = async (content) => {
    await onSave(content.id)
    close()
  }

  const submit = async (event) => {
    event.preventDefault()
    setError(null)
    if (!form.title.trim()) {
      setError('A title is required.')
      return
    }
    if (!form.creator.trim()) {
      setError('A creator is required.')
      return
    }

    setPending(true)
    try {
      // The work already exists from a previous attempt: only the save failed.
      if (created) {
        await saveCreated(created)
        return
      }
      const content = await onCreate(payload())
      setCreated(content)
      await saveCreated(content)
    } catch (err) {
      setError(err?.detail || 'Could not add this item.')
    } finally {
      setPending(false)
    }
  }

  const retry = async () => {
    setError(null)
    setPending(true)
    try {
      await saveCreated(created)
    } catch (err) {
      setError(err?.detail || 'Could not save this item.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Add something worth discovering" labelledBy="add-title">
      <form className="stack" onSubmit={submit} noValidate>
        <label>
          Title
          <input value={form.title} onChange={update('title')} required />
        </label>
        <label>
          Creator
          <input value={form.creator} onChange={update('creator')} required />
        </label>
        <div className="row">
          <label>
            Type
            <select value={form.kind} onChange={update('kind')}>
              {KINDS.filter((item) => item.id !== 'all').map((item) => (
                <option key={item.id} value={item.id}>
                  {KIND_LABEL[item.id]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Year
            <input type="number" min="0" max="3000" value={form.year} onChange={update('year')} />
          </label>
        </div>
        <div className="row">
          <label>
            Total units
            <input type="number" min="1" value={form.total_units} onChange={update('total_units')} />
          </label>
          <label>
            Unit label
            <input
              value={form.unit_label}
              onChange={update('unit_label')}
              placeholder={UNIT_DEFAULT[form.kind]}
            />
          </label>
        </div>
        <label>
          Description
          <textarea rows={3} value={form.description} onChange={update('description')} />
        </label>

        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        {created && (
          <p className="muted small">
            {created.title} is already in the public catalog. Only saving it to your library is left.
          </p>
        )}

        <div className="entry-dialog__actions">
          {created ? (
            <button type="button" className="button button--primary" onClick={retry} disabled={pending}>
              Retry saving
            </button>
          ) : (
            <button type="submit" className="button button--primary" disabled={pending}>
              {pending ? 'Adding…' : 'Add to catalog'}
            </button>
          )}
        </div>
      </form>
    </Modal>
  )
}

/**
 * The public catalog browser: search, filter and open a work. It is embedded
 * in the default page so discovery and the feed live side by side.
 */
export default function CatalogSection({ app, kind, query, onQuery, onAddOpen, onClear, searchRef }) {
  const results = app.contents

  return (
    <section className="catalog" aria-label="Catalog">
      <header className="catalog__head">
        <h2 className="rail-card__title">Browse the catalog</h2>
        <button
          type="button"
          className="button button--ghost button--tiny"
          onClick={onAddOpen}
          disabled={app.offline}
        >
          Add something new
        </button>
      </header>

      <div className="toolbar" role="group" aria-label="Search the catalog">
        <label className="search">
          <span className="sr-only">Search the catalog</span>
          <Search size={15} strokeWidth={1.7} aria-hidden="true" />
          <input
            ref={searchRef}
            type="search"
            aria-label="Search the catalog"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
          />
        </label>
      </div>

      {app.catalogLoading ? (
        <div className="stack">
          <div className="skeleton" />
        </div>
      ) : results.length === 0 ? (
        <div className="empty">
          <p>
            <strong>Nothing here just yet.</strong>
          </p>
          <p className="muted small">Try a different search, or add the content yourself.</p>
          <button type="button" className="button button--ghost" onClick={onClear}>
            Clear filters
          </button>
        </div>
      ) : (
        <ul className="grid grid--catalog">
          {results.map((content) => {
            const saved = app.isSaved(content.id)
            return (
              <li key={content.id} className="card grid__item">
                <div className="grid__meta">
                  <span className="eyebrow">{KIND_LABEL[content.kind]}</span>
                  <strong>{content.title}</strong>
                  <span className="muted small">
                    {content.creator}
                    {content.year ? ` · ${content.year}` : ''}
                  </span>
                </div>
                <button
                  type="button"
                  className={`button ${saved ? 'button--ghost' : 'button--primary'} button--tiny`}
                  disabled={saved || app.offline}
                  onClick={() => app.saveContent(content.id)}
                  aria-label={saved ? `Saved for later: ${content.title}` : `Save for later: ${content.title}`}
                >
                  {saved ? 'In your library' : 'Save for later'}
                </button>
                <button
                  type="button"
                  className="button button--ghost button--tiny"
                  onClick={() => app.saveContent(content.id)}
                  aria-label={`View ${content.title}`}
                >
                  View
                </button>
                <Cover content={content} size="xs" />
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
