import { BookMarked, Compass, Home, LineChart, LogOut, MessageCircleQuestion, PenLine, UserRound } from 'lucide-react'

import Avatar from './Avatar.jsx'

const NAV = [
  { id: 'community', label: 'Community', icon: Home },
  { id: 'discover', label: 'Discover', icon: Compass },
  { id: 'library', label: 'My library', icon: BookMarked },
  { id: 'insights', label: 'Insights', icon: LineChart },
]

export default function Sidebar({
  route,
  navigate,
  user,
  onSignIn,
  onLogout,
  onCompose,
  onAddContent,
  onOpenAssistant,
  offline,
  mobileOpen,
  onCloseMobile,
}) {
  const go = (id) => {
    navigate(id)
    onCloseMobile?.()
  }

  return (
    <aside className={`sidebar ${mobileOpen ? 'is-open' : ''}`} aria-label="Main navigation">
      <div className="brand" onClick={() => go('community')} role="presentation">
        <span className="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 28 28" width="26" height="26">
            <rect x="1" y="1" width="26" height="26" rx="7" fill="#253d32" />
            <path d="M8 9h8a3 3 0 0 1 3 3v9H11a3 3 0 0 1-3-3z" fill="none" stroke="#dcebb7" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M12 9v12" stroke="#dcebb7" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </span>
        <span className="brand__text">
          <strong>Reesatck</strong>
          <small>Keep a record</small>
        </span>
      </div>

      <nav className="nav">
        {NAV.map((item) => {
          const Icon = item.icon
          const active = route === item.id
          return (
            <button
              key={item.id}
              type="button"
              className={`nav__item ${active ? 'is-active' : ''}`}
              aria-current={active ? 'page' : undefined}
              onClick={() => go(item.id)}
            >
              <Icon size={18} strokeWidth={1.6} aria-hidden="true" />
              <span>{item.label}</span>
            </button>
          )
        })}
      </nav>

      <button
        type="button"
        className="nav__item nav__item--accent"
        onClick={() => {
          onOpenAssistant()
          onCloseMobile?.()
        }}
      >
        <MessageCircleQuestion size={18} strokeWidth={1.6} aria-hidden="true" />
        <span>Assistant</span>
      </button>

      <button
        type="button"
        className="button button--primary sidebar__compose"
        onClick={onCompose}
        disabled={offline}
      >
        <PenLine size={16} strokeWidth={1.8} aria-hidden="true" />
        Write a reflection
      </button>

      <button
        type="button"
        className="button button--ghost sidebar__add"
        onClick={onAddContent}
        disabled={offline}
      >
        Add content
      </button>

      <div className="sidebar__foot">
        {user ? (
          <div className="profile">
            <Avatar user={user} size="sm" />
            <span className="profile__text">
              <strong>{user.display_name}</strong>
              <small>@{user.username}</small>
            </span>
            <button type="button" className="icon-button" onClick={onLogout} aria-label="Sign out">
              <LogOut size={16} strokeWidth={1.6} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <button type="button" className="button button--ghost sidebar__signin" onClick={onSignIn}>
            <UserRound size={16} strokeWidth={1.6} aria-hidden="true" />
            Sign in
          </button>
        )}
      </div>
    </aside>
  )
}
