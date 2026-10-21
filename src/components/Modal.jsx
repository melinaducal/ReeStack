import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

function focusableItems(panel) {
  const candidates = panel.querySelectorAll('button, [href], input, select, textarea, [tabindex]')
  return Array.from(candidates).filter((element) => {
    if (element.tabIndex < 0 || element.matches(':disabled, input[type="hidden"]')) return false
    if (element.closest('[hidden], [inert]')) return false
    // offsetParent is null for visible fixed-position controls and in non-layout DOMs.
    for (let node = element; node; node = node.parentElement) {
      const style = window.getComputedStyle(node)
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') return false
    }
    return true
  })
}

/**
 * Accessible modal: focus moves in on open, Tab stays inside, Escape closes,
 * and focus returns to the trigger on close.
 */
export default function Modal({ open, title, onClose, children, labelledBy = 'modal-title', initialFocusRef }) {
  const panelRef = useRef(null)
  const lastFocused = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  // Read onClose through a ref so new callbacks cannot steal focus on every keystroke.
  useEffect(() => {
    if (!open) return undefined
    lastFocused.current = document.activeElement
    const panel = panelRef.current
    const preferred = initialFocusRef?.current
    if (preferred) preferred.focus()
    else if (panel) focusableItems(panel)[0]?.focus()

    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current?.()
        return
      }
      if (event.key !== 'Tab' || !panel) return
      const items = focusableItems(panel)
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      lastFocused.current?.focus?.()
    }
  }, [open, initialFocusRef])

  if (!open) return null

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={labelledBy} ref={panelRef}>
        <header className="modal__head">
          <h2 id={labelledBy}>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close dialog">
            <X size={18} strokeWidth={1.6} aria-hidden="true" />
          </button>
        </header>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  )
}
