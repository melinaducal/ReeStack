import { Link } from 'react-router-dom'
import { sanitizeRichText } from '../utils/richText'
import { getInitials, TYPE_LABELS } from '../utils/profile'

const STAT_CARDS = [
  { key: 'posts_count', label: 'Publicaciones' },
  { key: 'books', label: 'Libros' },
  { key: 'movies', label: 'Películas' },
  { key: 'series', label: 'Series' },
  { key: 'music', label: 'Música' },
  { key: 'papers', label: 'Papers' }
]

export function ProfileHeader({ profile, displayName, actions, children }) {
  return (
    <header className="profile-hero">
      <div className="profile-hero-inner">
        <div className="profile-avatar-wrap">
          {profile.avatar_url ? (
            <img src={profile.avatar_url} alt={displayName} className="profile-avatar" />
          ) : (
            <div className="profile-avatar-placeholder">{getInitials(displayName)}</div>
          )}
        </div>
        <div className="profile-hero-info">
          <div className="profile-hero-top">
            <div>
              <h1 className="profile-name">{displayName}</h1>
              <p className="profile-username">@{profile.username}</p>
            </div>
            {actions && <div className="profile-hero-actions">{actions}</div>}
          </div>
          {profile.bio && <p className="profile-bio">{profile.bio}</p>}
          {children}
        </div>
      </div>
    </header>
  )
}

export function ProfileStats({ stats }) {
  return (
    <section className="profile-stats">
      {STAT_CARDS.map(card => (
        <div key={card.key} className="profile-stat-card">
          <p className="profile-stat-number">{stats?.[card.key] || 0}</p>
          <p className="profile-stat-label">{card.label}</p>
        </div>
      ))}
    </section>
  )
}

export function ProfileTabNav({ tabs, activeTab, onChange }) {
  return (
    <div className="profile-tabs-header">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`profile-tab ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function ProfilePostCard({ post, owner }) {
  const displayName =
    owner.display_name ||
    `${owner.first_name || ''} ${owner.last_name || ''}`.trim() ||
    owner.username
  const date = post.created_at ? new Date(post.created_at).toLocaleDateString('es-AR') : ''

  return (
    <article className="profile-post-card">
      <header className="profile-post-header">
        <div className="profile-post-author">
          {owner.avatar_url ? (
            <img src={owner.avatar_url} alt={displayName} className="profile-post-avatar" />
          ) : (
            <div className="profile-post-avatar-placeholder">{getInitials(displayName)}</div>
          )}
          <div>
            <p className="profile-post-name">{displayName}</p>
            <p className="profile-post-username">@{owner.username}</p>
          </div>
        </div>
        <div className="profile-post-meta">
          {date && <span>{date}</span>}
          <span className="profile-post-type">{TYPE_LABELS[post.type] || post.type}</span>
        </div>
      </header>
      <div className="profile-post-content">
        {post.thoughts && (
          <div className="profile-post-text">
            <div dangerouslySetInnerHTML={{ __html: sanitizeRichText(post.thoughts) }} />
          </div>
        )}
        {post.cover_url && (
          <div className="profile-post-media">
            <img src={post.cover_url} alt={post.title} />
          </div>
        )}
      </div>
      <footer className="profile-post-interactions">
        <span className={`profile-post-interaction ${post.likes_count ? 'active' : ''}`}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill={post.likes_count ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
          <span>{post.likes_count || 0}</span>
        </span>
        <span className="profile-post-interaction">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
          </svg>
          <span>{post.comments_count || 0}</span>
        </span>
      </footer>
    </article>
  )
}

export function ProfileCollectionGrid({
  items,
  title,
  subtitle,
  emptyMessage,
  emptyAction,
  formatType = item => TYPE_LABELS[item.type] || item.type
}) {
  return (
    <div className="profile-tab-panel">
      <div className="profile-section-header">
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {items.length === 0 ? (
        <div className="profile-empty">
          <p>{emptyMessage}</p>
          {emptyAction}
        </div>
      ) : (
        <div className="profile-items-grid">
          {items.map(item => (
            <Link to={`/item/${item.id}`} key={item.id} className="profile-item-card">
              <div className="profile-item-cover-wrap">
                {item.cover_url ? (
                  <img src={item.cover_url} alt={item.title} className="profile-item-cover" />
                ) : (
                  <div className="profile-item-cover-placeholder">
                    <span>{item.type?.[0]?.toUpperCase() || 'R'}</span>
                  </div>
                )}
              </div>
              <div className="profile-item-body">
                <h3 className="profile-item-title">{item.title}</h3>
                {item.creator && <p className="profile-item-creator">{item.creator}</p>}
                <div className="profile-item-meta">
                  <span className="profile-item-badge">{formatType(item)}</span>
                  {item.rating && <span className="profile-item-rating">★ {item.rating}/10</span>}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
