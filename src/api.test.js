import { api } from './api';

describe('the API transport contract', () => {
  it('uses cookie credentials and the mutation header for every write', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetch);
    for (const method of ['POST', 'PATCH', 'PUT', 'DELETE']) {
      expect(await api('/collection/3', { method, body: { progress: 2 } })).toBeNull();
      expect(fetch).toHaveBeenLastCalledWith('/api/collection/3', expect.objectContaining({
        method,
        credentials: 'include',
        headers: expect.objectContaining({ 'X-Reesatck-Request': '1', 'Content-Type': 'application/json' }),
        body: JSON.stringify({ progress: 2 }),
      }));
    }
  });

  it('reads public JSON without a mutation header and forwards cancellation', async () => {
    const signal = new AbortController().signal;
    const fetch = vi.fn().mockResolvedValue(Response.json([{ id: 1 }]));
    vi.stubGlobal('fetch', fetch);
    expect(await api('/contents', { signal })).toEqual([{ id: 1 }]);
    expect(fetch).toHaveBeenCalledWith('/api/contents', expect.objectContaining({
      credentials: 'include', method: 'GET', signal,
    }));
    expect(fetch.mock.calls[0][1].headers).not.toHaveProperty('X-Reesatck-Request');
  });

  it.each([
    [{ detail: 'Your session has expired.' }, 'Your session has expired.'],
    [{ detail: [{ loc: ['body', 'progress'], msg: 'Input should be less than or equal to 10' }] },
      'progress: Input should be less than or equal to 10'],
    [{ detail: { unexpected: '<script>unsafe</script>' } }, 'The request could not be completed (422).'],
  ])('maps error details to safe readable text', async (body, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(body, { status: 422 })));
    await expect(api('/collection', { method: 'POST' })).rejects.toMatchObject({ message, status: 422 });
  });

  it('does not interpret a failed non-JSON response as success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>Unavailable</html>', { status: 503 })));
    await expect(api('/posts')).rejects.toMatchObject({ status: 503, message: 'The request could not be completed (503).' });
  });
});
