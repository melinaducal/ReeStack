import { useCallback, useEffect, useState } from 'react'

/**
 * Minimal hash router. Hash routing keeps deep links working when the built
 * bundle is served as static files, with no server rewrite rules needed.
 */
export const ROUTES = ['community', 'discover', 'library', 'insights', 'assistant']

function currentRoute() {
  const raw = window.location.hash.replace(/^#\/?/, '')
  return ROUTES.includes(raw) ? raw : 'community'
}

export function useRoute() {
  const [route, setRoute] = useState(currentRoute)

  useEffect(() => {
    const onChange = () => setRoute(currentRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  // State is updated directly instead of waiting for `hashchange`: the event is
  // asynchronous (and not dispatched synchronously by every environment), so
  // the UI must reflect the new route on the same tick as the click.
  const navigate = useCallback((next) => {
    if (!ROUTES.includes(next)) return
    setRoute(next)
    const target = `#/${next}`
    if (window.location.hash !== target) window.location.hash = target
  }, [])

  return { route, navigate }
}
