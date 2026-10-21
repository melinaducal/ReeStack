import { initials } from '../lib/catalog.js'

export default function Avatar({ user, size = 'md' }) {
  if (!user) return null
  return (
    <span
      className={`avatar avatar--${size}`}
      style={{ background: user.avatar_color || '#5b7f68' }}
      aria-hidden="true"
      title={user.display_name}
    >
      {initials(user.display_name || user.username)}
    </span>
  )
}
