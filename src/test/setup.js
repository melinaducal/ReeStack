import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  // Hash routing is real browser state and jsdom keeps it between tests in the
  // same file. Reset it so every test starts on the default route.
  window.location.hash = ''
})
