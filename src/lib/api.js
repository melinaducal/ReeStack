/**
 * Single transport for every API call.
 *
 * Cookies carry the session (HttpOnly, so JavaScript never sees a token),
 * and unsafe methods send the header the API requires. Failed writes always
 * throw: the UI must never pretend a mutation succeeded.
 */

export const MUTATION_HEADER = 'X-Reesatck-Request'

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function describeDetail(payload, status) {
  const detail = payload?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : null
    const message = first?.msg || 'Invalid value'
    return field ? `${field}: ${message}` : message
  }
  return `Request failed (${status})`
}

export async function request(path, { method = 'GET', body, signal } = {}) {
  const method_ = method.toUpperCase()
  const options = {
    method: method_,
    credentials: 'include',
    headers: {},
    signal,
  }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  if (method_ !== 'GET' && method_ !== 'HEAD') {
    options.headers[MUTATION_HEADER] = '1'
  }

  let response
  try {
    response = await fetch(path, options)
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the Reesatck API. Is the backend running on port 8000?')
  }

  if (response.status === 204) return null

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, describeDetail(payload, response.status))
  }
  return payload
}

export const api = {
  health: () => request('/api/health'),
  me: () => request('/api/auth/me'),
  register: (payload) => request('/api/auth/register', { method: 'POST', body: payload }),
  login: (payload) => request('/api/auth/login', { method: 'POST', body: payload }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),

  listContents: ({ q, kind } = {}) => {
    const params = new URLSearchParams()
    if (q) params.set('q', q)
    if (kind && kind !== 'all') params.set('kind', kind)
    const suffix = params.toString()
    return request(`/api/contents${suffix ? `?${suffix}` : ''}`)
  },
  createContent: (payload) => request('/api/contents', { method: 'POST', body: payload }),

  getCollection: () => request('/api/collection'),
  saveContent: (contentId) =>
    request('/api/collection', { method: 'POST', body: { content_id: contentId, status: 'planned' } }),
  patchEntry: (entryId, payload) => request(`/api/collection/${entryId}`, { method: 'PATCH', body: payload }),
  removeEntry: (entryId) => request(`/api/collection/${entryId}`, { method: 'DELETE' }),

  listPosts: ({ kind, q, sort } = {}) => {
    const params = new URLSearchParams()
    if (kind && kind !== 'all') params.set('kind', kind)
    if (q) params.set('q', q)
    if (sort) params.set('sort', sort)
    const suffix = params.toString()
    return request(`/api/posts${suffix ? `?${suffix}` : ''}`)
  },
  createPost: (payload) => request('/api/posts', { method: 'POST', body: payload }),
  listComments: (postId) => request(`/api/posts/${postId}/comments`),
  createComment: (postId, body) =>
    request(`/api/posts/${postId}/comments`, { method: 'POST', body: { body } }),
  likePost: (postId) => request(`/api/posts/${postId}/like`, { method: 'PUT' }),
  unlikePost: (postId) => request(`/api/posts/${postId}/like`, { method: 'DELETE' }),

  assistantStatus: () => request('/api/assistant/status'),
  assistantChat: (message) => request('/api/assistant/chat', { method: 'POST', body: { message } }),
}
