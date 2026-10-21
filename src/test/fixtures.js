export const user = { id: 1, username: 'alex', display_name: 'Alex Reed', bio: '', avatar_color: '#526758' };
export const book = {
  id: 1, title: 'The Creative Act', creator: 'Rick Rubin', kind: 'book', year: 2023,
  description: 'A practice of paying attention.', cover_key: 'creative-act',
  total_units: 432, unit_label: 'pages', tags: ['Creativity'],
};
export const movie = {
  ...book, id: 2, title: 'Interstellar', creator: 'Christopher Nolan', kind: 'movie',
  year: 2014, cover_key: 'interstellar', total_units: 169, unit_label: 'minutes', tags: ['Space'],
};
export const entry = { id: 8, content: book, status: 'in_progress', progress: 42, rating: null, review: '', updated_at: '2026-10-20T10:00:00Z' };
export const post = {
  id: 9, author: user, body: 'A creative life begins with noticing.', content: book,
  rating: null, created_at: '2026-10-20T10:00:00Z', like_count: 2,
  comment_count: 0, liked: false, is_demo: false,
};

export function mockApi({ signedIn = false, entries = [], fail = {}, handlers = {} } = {}) {
  const calls = [];
  let posts = [{ ...post }, { ...post, id: 10, body: 'Looking beyond the horizon.', content: movie }];
  let collection = structuredClone(entries);
  const comments = [];
  const fetch = vi.fn(async (url, options = {}) => {
    const parsed = new URL(url, 'http://localhost');
    const path = parsed.pathname.replace('/api', '');
    const method = options.method || 'GET';
    const key = `${method} ${path}`;
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ key, body, search: parsed.searchParams.toString() });
    if (handlers[key]) return handlers[key]({ body, options });
    if (fail[key]) return Response.json({ detail: fail[key] }, { status: 422 });
    if (key === 'GET /auth/me') return Response.json(signedIn ? user : { detail: 'Authentication required' }, { status: signedIn ? 200 : 401 });
    if (key === 'POST /auth/login' || key === 'POST /auth/register') return Response.json(user);
    if (key === 'POST /auth/logout') return new Response(null, { status: 204 });
    if (key === 'GET /contents') {
      return Response.json([book, movie].filter(content => (!parsed.searchParams.get('kind') || content.kind === parsed.searchParams.get('kind')) && (!parsed.searchParams.get('q') || content.title.toLowerCase().includes(parsed.searchParams.get('q').toLowerCase()))));
    }
    if (key === 'GET /posts') return Response.json(posts.filter(item => !parsed.searchParams.get('kind') || item.content?.kind === parsed.searchParams.get('kind')));
    if (key === 'GET /collection') return Response.json(collection);
    if (key === 'POST /collection') {
      const saved = { ...entry, content: body.content_id === movie.id ? movie : book, status: 'planned', progress: 0 };
      collection = [...collection, saved];
      return Response.json(saved, { status: 201 });
    }
    if (key === 'PATCH /collection/8') {
      collection = collection.map(item => item.id === 8 ? { ...item, ...body } : item);
      return Response.json(collection[0]);
    }
    if (key === 'DELETE /collection/8') {
      collection = [];
      return new Response(null, { status: 204 });
    }
    if (key === 'POST /posts') {
      const created = { ...post, id: 11, body: body.body, content: body.content_id ? book : null };
      posts = [created, ...posts];
      return Response.json(created, { status: 201 });
    }
    if (key === 'GET /posts/9/comments') return Response.json(comments);
    if (key === 'POST /posts/9/comments') {
      const comment = { id: 1, author: user, body: body.body, created_at: post.created_at };
      comments.push(comment);
      posts[0].comment_count += 1;
      return Response.json(comment, { status: 201 });
    }
    if (key === 'PUT /posts/9/like' || key === 'DELETE /posts/9/like') {
      const liked = method === 'PUT';
      posts[0] = { ...posts[0], liked, like_count: liked ? 3 : 2 };
      return Response.json({ liked, like_count: posts[0].like_count });
    }
    if (key === 'GET /assistant/status') return Response.json({ configured: false, model: null });
    throw new Error(`Unexpected API call: ${key}`);
  });
  vi.stubGlobal('fetch', fetch);
  return { calls, fetch };
}
