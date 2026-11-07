export const DEFAULT_RATING_CONFIG = { min: 0.5, max: 5, step: 0.5 }

/**
 * Round a raw rating to the nearest allowed step and clamp it to the range.
 */
export function clampRating(raw, { min = 0.5, max = 5, step = 0.5 } = {}) {
  if (!Number.isFinite(raw)) return min
  const stepped = Math.round(raw / step) * step
  return Number(Math.min(max, Math.max(min, stepped)).toFixed(2))
}

/**
 * Translate a pointer x coordinate into a rating value.
 *
 * The row is split into `starCount` equal cells. Clicking the left half of a
 * star selects the half step, clicking its right half selects the full star,
 * matching the interaction described for the component.
 */
export function ratingFromPointer(clientX, rect, config = {}) {
  if (!rect || !rect.width) return null
  const { max = 5, min = 0.5 } = config
  const starCount = Math.ceil(max)
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
  const position = ratio * starCount
  const starIndex = Math.min(starCount - 1, Math.floor(position))
  const withinStar = position - starIndex
  const candidate = starIndex + (withinStar <= 0.5 ? 0.5 : 1)
  return clampRating(Math.min(candidate, max) || min, config)
}

/**
 * Translate a keyboard key into the next rating value.
 *
 * Returns `undefined` for keys the component does not handle, `null` when the
 * rating should be cleared, and a number otherwise.
 */
export function ratingFromKey(key, value, { allowClear = true, ...config } = {}) {
  const { min = 0.5, max = 5, step = 0.5 } = config

  if (key === 'Delete' || key === 'Backspace' || key === '0') {
    return allowClear ? null : (value ?? min)
  }

  if (key === 'Home') return clampRating(min, config)
  if (key === 'End') return clampRating(max, config)

  const forward = key === 'ArrowRight' || key === 'ArrowUp'
  const backward = key === 'ArrowLeft' || key === 'ArrowDown'
  if (!forward && !backward) return undefined

  const base = value == null ? (forward ? min - step : min) : value
  return clampRating(base + (forward ? step : -step), config)
}
