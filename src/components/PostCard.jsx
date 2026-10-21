import { useState } from 'react'
import { Bookmark, Heart, MessageSquare } from 'lucide-react'

import Avatar from './Avatar.jsx'
import Cover from './Cover.jsx'
import { KIND_LABEL } from '../lib/catalog.js'

function relativeTime(value) {
  if (!value) return ''
  const then = new Date(value)
  if (Number.isNaN(then.getTime())) return ''
  const minutes = Math.round((Date.now() - then.getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return days === 1 ? 'yesterday' : `${days}d ago`
}

/** Comments arrive either preloaded on the post (seed/preview) or from a
 *  per-post cache keyed by id. Both shapes resolve to a list. */
function commentList(comments, post) {
  if (Array.isArray(comments?.[post.id])) return comments[post.id]
  if (Array.isArray(post.comments)) return post.comments
  return []
}

export default function PostCard({
  post,
  onToggleLike,
  onSave,
  onComment,
  comments,
  onLoadComments,
  disabled = false,
  saved = false,
  savedLabel,
}) {
  const [showComments, setShowComments] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  const list = commentList(comments, post)

  const toggleComments = async () => {
    const next = !showComments
    setShowComments(next)
    if (next) {
      try {
        await onLoadComments(post.id)
      } catch (err) {
        setError(err?.detail || 'Could not load comments.')
      }
    }
  }

  const submitComment = async (event) => {
    event.preventDefault()
    setError(null)
    if (!draft.trim()) return
    setPending(true)
    try {
      await onComment(post.id, draft.trim())
      setDraft('')
      await onLoadComments(post.id)
    } catch (err) {
      setError(err?.detail || 'Could not post your comment.')
    } finally {
      setPending(false)
    }
  }

  const like = async () => {
    setError(null)
    try {
      await onToggleLike(post.id)
    } catch (err) {
      setError(err?.detail || 'Could not update the like.')
    }
  }

  const save = async () => {
    setError(null)
    try {
      if (post.content) await onSave(post.content.id)
    } catch (err) {
      setError(err?.detail || 'Could not save this item.')
    }
  }

  const likeLabel = post.liked
    ? `Unlike reflection · ${post.like_count} likes`
    : `Like reflection · ${post.like_count} likes`

  return (
    <article className="post card" aria-labelledby={`post-${post.id}-body`}>
      <header className="post__head">
        <Avatar user={post.author} />
        <div className="post__who">
          <strong>{post.author.display_name}</strong>
          <span className="muted small">
            @{post.author.username} · {relativeTime(post.created_at)}
          </span>
        </div>
        {post.is_demo && <span className="badge badge--demo">Sample reflection</span>}
      </header>

      <p className="post__body" id={`post-${post.id}-body`}>
        {post.body}
      </p>

      {post.content && (
        <div className="post__content">
          <Cover content={post.content} size="sm" />
          <div className="post__content-meta">
            <span className="eyebrow">{KIND_LABEL[post.content.kind] || 'Item'}</span>
            <strong>{post.content.title}</strong>
            <span className="muted small">{post.content.creator}</span>
            {post.rating ? (
              <span className="stars" aria-label={`Rated ${post.rating} out of 5`}>
                {'★'.repeat(post.rating)}
                <span className="stars__off">{'★'.repeat(5 - post.rating)}</span>
              </span>
            ) : null}
          </div>
          <button
            type="button"
            className="button button--ghost button--tiny"
            onClick={save}
            disabled={disabled || saved}
            aria-label={saved ? `Saved ${post.content.title}` : `Save ${post.content.title}`}
          >
            <Bookmark size={14} strokeWidth={1.7} aria-hidden="true" />
            {saved ? 'Saved' : 'Save'}
          </button>
        </div>
      )}

      <footer className="post__actions">
        <button
          type="button"
          className={`action ${post.liked ? 'is-on' : ''}`}
          onClick={like}
          disabled={disabled}
          aria-pressed={post.liked}
          aria-label={likeLabel}
        >
          <Heart size={16} strokeWidth={1.7} aria-hidden="true" fill={post.liked ? 'currentColor' : 'none'} />
          {post.like_count}
        </button>
        <button
          type="button"
          className="action"
          onClick={toggleComments}
          aria-expanded={showComments}
          aria-label={`Comments · ${post.comment_count} comments`}
        >
          <MessageSquare size={16} strokeWidth={1.7} aria-hidden="true" />
          {post.comment_count}
        </button>
      </footer>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {showComments && (
        <section className="comments" aria-label={`Comments on ${post.author.display_name}'s post`}>
          {list.length === 0 && <p className="muted small">No comments yet.</p>}
          {list.map((comment) => (
            <div key={comment.id} className="comment">
              <Avatar user={comment.author} size="xs" />
              <div>
                <strong className="small">{comment.author.display_name}</strong>
                <p>{comment.body}</p>
              </div>
            </div>
          ))}
          <form className="comment-form" onSubmit={submitComment}>
            <label className="sr-only" htmlFor={`comment-${post.id}`}>
              Your comment
            </label>
            <input
              id={`comment-${post.id}`}
              aria-label="Your comment"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Add a thoughtful reply…"
            />
            <button type="submit" className="button button--ghost button--tiny" disabled={pending || disabled}>
              {pending ? 'Sending…' : 'Post comment'}
            </button>
          </form>
        </section>
      )}
    </article>
  )
}
