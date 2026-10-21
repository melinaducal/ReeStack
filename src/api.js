export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function errorMessage(detail, status) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.filter(item => typeof item?.msg === 'string').map(item => {
      const field = Array.isArray(item.loc)
        ? item.loc.filter(part => typeof part === 'string' && part !== 'body').join('.')
        : '';
      return field ? `${field}: ${item.msg}` : item.msg;
    });
    if (messages.length) return messages.join('; ');
  }
  return `The request could not be completed (${status}).`;
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') headers['X-Reesatck-Request'] = '1';
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method, credentials: 'include', headers, signal,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch (error) {
    if (error.name === 'AbortError' || signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    throw new ApiError('Cannot reach the API. Check your connection and try again.', 0);
  }
  // A mock, proxy, or already-buffered response may settle after cancellation.
  if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
  if (response.status === 204 && response.ok) return null;
  let data;
  try {
    data = await response.json();
  } catch {
    if (!response.ok) throw new ApiError(errorMessage(null, response.status), response.status);
    throw new ApiError('The API returned an unreadable response. Please try again.', 502);
  }
  if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
  if (!response.ok) throw new ApiError(errorMessage(data?.detail, response.status), response.status);
  return data;
}

export function query(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) search.set(key, value);
  });
  return search.size ? `?${search}` : '';
}
