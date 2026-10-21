import { KIND_LABEL, coverStyle, initials } from '../lib/catalog.js'

/**
 * Local cover art: a generated, deterministic composition per content item.
 * No remote images, nothing to break offline, and no user text is ever
 * rendered as HTML.
 */
export default function Cover({ content, size = 'md' }) {
  if (!content) return null
  const style = coverStyle(content.cover_key)
  const label = KIND_LABEL[content.kind] || 'Item'

  return (
    <div
      className={`cover cover--${size}`}
      style={{ background: style.bg, color: style.ink }}
      role="img"
      aria-label={`${label} cover: ${content.title}`}
    >
      <span className="cover__kind" style={{ color: style.accent }}>
        {label}
      </span>
      <span className="cover__title">{content.title}</span>
      <span className="cover__creator">{content.creator}</span>
      <span className="cover__mark" style={{ borderColor: style.accent, color: style.accent }} aria-hidden="true">
        {initials(content.title)}
      </span>
    </div>
  )
}
