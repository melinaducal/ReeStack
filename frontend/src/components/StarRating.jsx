import { useRef, useState } from 'react'
import { ratingFromKey, ratingFromPointer } from '../utils/starRating'
import './StarRating.css'

const STAR_PATH =
  'M12 2.4l2.94 5.96 6.58.96-4.76 4.64 1.12 6.55L12 17.42l-5.88 3.09 1.12-6.55L2.48 9.32l6.58-.96L12 2.4z'

const SIZE_CLASSES = {
  sm: 'star-rating--sm',
  md: 'star-rating--md',
  lg: 'star-rating--lg'
}

const formatValue = (value) => String(value).replace('.', ',')

export const starsToBackend = (stars) => (stars == null ? null : Math.round(stars * 2 * 10) / 10)
export const backendToStars = (backend) => {
  if (backend == null || backend === '') return null
  const n = Number(backend)
  if (!Number.isFinite(n)) return null
  return Math.round((n / 2) / 0.5) * 0.5
}

/**
 * Accessible five-star rating with half-star precision (0.5 steps).
 * - Click left half of a star = half star; right half = full star.
 * - Hover preview, optional clear, keyboard support.
 * - Props: value, onChange, readOnly, disabled.
 * - Backend compatibility (0-10): stars × 2. Use scale={10} to work in backend units.
 */
function StarRating({
  value = null,
  onChange,
  readOnly = false,
  disabled = false,
  size = 'md',
  min = 0.5,
  max = 5,
  step = 0.5,
  allowClear = true,
  showValue = true,
  ariaLabel = 'Puntuación',
  className = '',
  scale = 5,
  clearLabel = 'Quitar puntuación'
}) {
  const [hover, setHover] = useState(null)
  const starsRef = useRef(null)

  const backendMode = scale === 10
  const toStars = (v) => {
    if (v == null || v === '') return null
    return backendMode ? backendToStars(v) : v
  }
  const fromStars = (s) => {
    if (s == null) return null
    return backendMode ? starsToBackend(s) : s
  }

  const config = { min, max, step }
  const interactive = !readOnly && !disabled
  const starCount = Math.ceil(max)
  const starValue = toStars(value)
  const preview = hover ?? starValue ?? 0
  const displayValue = backendMode && preview > 0 ? Math.round(preview * 2) : preview
  const displayMax = backendMode ? 10 : formatValue(max)
  const currentLabel = preview > 0
    ? (backendMode ? `${displayValue} de 10 (${formatValue(preview)} estrellas)` : `${formatValue(preview)} de ${formatValue(max)} estrellas`)
    : 'Sin puntuar'

  const valueFromPointer = (event) => {
    const rect = starsRef.current?.getBoundingClientRect()
    return ratingFromPointer(event.clientX, rect, config)
  }

  const emit = (nextStars) => {
    setHover(null)
    onChange?.(fromStars(nextStars))
  }

  const handlePointerMove = (event) => {
    if (!interactive) return
    const next = valueFromPointer(event)
    if (next != null) setHover(next)
  }

  const handlePointerLeave = () => {
    if (interactive) setHover(null)
  }

  const handleClick = (event) => {
    if (!interactive) return
    const next = valueFromPointer(event)
    if (next != null) emit(next)
  }

  const handleClear = () => {
    if (!interactive) return
    emit(null)
  }

  const handleKeyDown = (event) => {
    if (!interactive) return
    const next = ratingFromKey(event.key, starValue, { ...config, allowClear })
    if (next === undefined) return
    event.preventDefault()
    emit(next)
  }

  const sizeClass = typeof size === 'number' ? '' : SIZE_CLASSES[size] || SIZE_CLASSES.md
  const sizeStyle = typeof size === 'number' ? { '--star-size': `${size}px` } : undefined

  const stars = (
    <div
      ref={starsRef}
      className={[
        'star-rating__stars',
        interactive ? 'is-interactive' : '',
        disabled ? 'is-disabled' : ''
      ].filter(Boolean).join(' ')}
      role={readOnly ? 'img' : 'slider'}
      tabIndex={readOnly || disabled ? undefined : 0}
      aria-label={readOnly ? `${ariaLabel}: ${currentLabel}` : ariaLabel}
      aria-valuemin={readOnly ? undefined : (backendMode ? Math.round(min * 2) : min)}
      aria-valuemax={readOnly ? undefined : (backendMode ? Math.round(max * 2) : max)}
      aria-valuenow={readOnly ? undefined : (backendMode ? (starValue ? Math.round(starValue * 2) : Math.round(min * 2)) : (starValue ?? min))}
      aria-valuetext={readOnly ? undefined : currentLabel}
      aria-disabled={disabled || undefined}
      onPointerMove={readOnly ? undefined : handlePointerMove}
      onPointerLeave={readOnly ? undefined : handlePointerLeave}
      onClick={readOnly ? undefined : handleClick}
      onKeyDown={readOnly ? undefined : handleKeyDown}
    >
      {Array.from({ length: starCount }, (_, index) => {
        const fill = Math.max(0, Math.min(1, preview - index))
        return (
          <span className="star-rating__star" key={index} aria-hidden="true">
            <svg className="star-rating__base" viewBox="0 0 24 24" focusable="false">
              <path d={STAR_PATH} />
            </svg>
            <span className="star-rating__clip" style={{ width: `${fill * 100}%` }}>
              <svg className="star-rating__fill" viewBox="0 0 24 24" focusable="false">
                <path d={STAR_PATH} />
              </svg>
            </span>
          </span>
        )
      })}
    </div>
  )

  return (
    <div
      className={['star-rating', sizeClass, readOnly ? 'is-readonly' : '', className]
        .filter(Boolean)
        .join(' ')}
      style={sizeStyle}
    >
      {stars}
      {(showValue || (interactive && allowClear && starValue != null)) && (
        <div className="star-rating__meta">
          {showValue && <span className="star-rating__legend">{currentLabel}</span>}
          {interactive && allowClear && starValue != null && (
            <button
              type="button"
              className="star-rating__clear"
              onClick={handleClear}
              disabled={disabled}
              aria-label={clearLabel}
            >
              {clearLabel}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default StarRating
