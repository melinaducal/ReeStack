import { useEffect, useRef, useState } from 'react'

import PostCard from '../components/PostCard.jsx'
import CatalogSection from './DiscoverView.jsx'
import { KINDS, kindIcon } from '../lib/catalog.js'

/**
 * The default page: one place to browse the shared catalog and read what the
 * community is reflecting on. Discovery and the feed are deliberately together
 * — saving something and then posting about it should not mean leaving the page.
 *
 * A single category control drives both halves, so the catalog filter and the
 * feed stay in step: the same click narrows the works and the reflections.
 */
export default function CommunityView({ app, onAddContent }) {
  const [kind, setKind] = useState('all')
  const [sort, setSort] = useState('latest')
  const [query, setQuery] = useState('')
  const [comments, setComments] = useState({})
  const [feedError, setFeedError] = useState(null)

  const firstFeedRun = useRef(true)
  const firstCatalogRun = useRef(true)

  useEffect(() => {
    if (firstFeedRun.current) {
      firstFeedRun.current = false
      return undefined
    }
    let cancelled = false
    app
      .loadPosts({ kind, sort })
      .catch((err) => {
        if (!cancelled) setFeedError(err?.detail || 'The feed could not be loaded.')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, sort])

  useEffect(() => {
    if (firstCatalogRun.current) {
      firstCatalogRun.current = false
      return undefined
    }
    let cancelled = false
    const handle = setTimeout(
      () => {
        app.loadContents({ kind, q: query.trim() }).catch(() => {
          if (!cancelled) return
        })
      },
      query ? 200 : 0,
    )
    return () => {
      cancelled = true
      clearTimeout(handle)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, query])

  const handleLoadComments = async (postId) => {
    const data = await app.loadComments(postId)
    setComments((prev) => ({ ...prev, [postId]: data }))
  }

  return (
    <div className="layout">
      <div className="layout__main">
        <section className="hero">
          <div className="hero__text">
            <span className="eyebrow">Your cultural &amp; scientific record</span>
            <h1>A curious mind. A world to explore.</h1>
            <p className="muted">
              Track books, films, series, music and papers. Reflect on what you are partway through — no need to
              finish first — and discover what others are reading into.
            </p>
          </div>
          <svg className="hero__art" viewBox="0 0 200 150" aria-hidden="true">
            <circle cx="140" cy="52" r="46" fill="none" stroke="#c9d8bd" strokeWidth="1.4" />
            <ellipse cx="140" cy="52" rx="62" ry="20" fill="none" stroke="#b06b4a" strokeWidth="1.2" opacity="0.6" />
            <rect x="40" y="66" width="58" height="42" rx="5" fill="#253d32" />
            <rect x="74" y="60" width="26" height="48" rx="3" fill="#dcebb7" />
            <circle cx="140" cy="52" r="7" fill="#b06b4a" />
          </svg>
        </section>

        <div className="toolbar" role="group" aria-label="Filter by type">
          <div className="chips">
            {KINDS.map((item) => {
              const Icon = kindIcon(item.icon)
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`chip ${kind === item.id ? 'is-active' : ''}`}
                  aria-pressed={kind === item.id}
                  onClick={() => setKind(item.id)}
                >
                  <Icon size={14} strokeWidth={1.7} aria-hidden="true" />
                  {item.label}
                </button>
              )
            })}
          </div>
          <label className="select-inline">
            <span className="sr-only">Sort posts</span>
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="latest">Latest</option>
              <option value="popular">Most liked</option>
            </select>
          </label>
        </div>

        <CatalogSection
          app={app}
          kind={kind}
          query={query}
          onQuery={setQuery}
          onAddOpen={onAddContent}
          onClear={() => {
            setQuery('')
            setKind('all')
          }}
        />

        <section className="feed-section" aria-label="Community reflections">
          <h2 className="rail-card__title">From the community</h2>

          {feedError && (
            <p className="form-error" role="alert">
              {feedError}
            </p>
          )}

          {app.booting ? (
            <div className="stack">
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
          ) : app.posts.length === 0 ? (
            <div className="empty">
              <p>
                <strong>No reflections match this view.</strong>
              </p>
              <button type="button" className="button button--ghost" onClick={() => setKind('all')}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="feed">
              {app.posts.map((post) => (
                <PostCard
                  key={post.id}
                  post={post}
                  comments={comments}
                  onLoadComments={handleLoadComments}
                  onToggleLike={app.toggleLike}
                  onSave={app.saveContent}
                  onComment={app.createComment}
                  disabled={app.offline}
                  saved={Boolean(post.content) && app.isSaved(post.content.id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <aside className="layout__rail" aria-label="Sidebar">
        <section className="card rail-card">
          <h2 className="rail-card__title">On your radar</h2>
          <p className="muted small">
            Save a work from the catalog above to keep it close. Your library holds progress and private notes.
          </p>
        </section>

        <section className="card rail-card rail-card--invite">
          <h2 className="rail-card__title">Make room for curiosity</h2>
          <p className="muted small">
            Reflect on what stuck with you — finished or not. Comments and likes are how the community finds its next
            read.
          </p>
        </section>
      </aside>
    </div>
  )
}
