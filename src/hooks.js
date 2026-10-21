import { useCallback, useEffect, useRef, useState } from 'react';
import { api, query } from './api';
import { matches } from './domain';
import { sampleCatalog, samplePosts } from './data';

export function useSession() {
  const scope = useRef({ version: 0, controller: new AbortController() });
  const [state, setState] = useState({ user: null, ready: false, version: 0 });
  const [logout, setLogout] = useState({ pending: false, error: '', message: '' });
  const logoutLock = useRef(false);

  const transition = useCallback(user => {
    scope.current.controller.abort();
    scope.current = { version: scope.current.version + 1, controller: new AbortController() };
    setState({ user, ready: true, version: scope.current.version });
    return scope.current.version;
  }, []);

  useEffect(() => {
    if (scope.current.controller.signal.aborted) scope.current.controller = new AbortController();
    const controller = new AbortController();
    const version = scope.current.version;
    api('/auth/me', { signal: controller.signal }).then(user => {
      if (!controller.signal.aborted && version === scope.current.version) transition(user);
    }).catch(error => {
      if (error.name !== 'AbortError' && version === scope.current.version) setState(current => ({ ...current, ready: true }));
    });
    return () => { controller.abort(); scope.current.controller.abort(); };
  }, [transition]);

  const authenticate = async (mode, body) => {
    if (logoutLock.current) return;
    const current = scope.current;
    const user = await api(`/auth/${mode}`, { method: 'POST', body, signal: current.controller.signal });
    if (current === scope.current) {
      setLogout({ pending: false, error: '', message: '' });
      transition(user);
    }
  };

  const signOut = async () => {
    if (logoutLock.current) return;
    logoutLock.current = true;
    const version = transition(null); // Remount and erase private UI before waiting for the network.
    setLogout({ pending: true, error: '', message: '' });
    try {
      await api('/auth/logout', { method: 'POST' });
      if (version === scope.current.version) setLogout({ pending: false, error: '', message: 'Signed out. Your private activity has been cleared from this screen.' });
    } catch (error) {
      if (version === scope.current.version) setLogout({ pending: false, message: '', error: `Private activity is cleared from this screen, but the server session could not be revoked. ${error.message}` });
    } finally {
      logoutLock.current = false;
    }
  };

  const request = useCallback(async (path, options = {}) => {
    const current = scope.current;
    try {
      return await api(path, { ...options, signal: current.controller.signal });
    } catch (error) {
      if (error.status === 401 && current === scope.current) {
        transition(null);
        setLogout({ pending: false, error: '', message: 'Your session has expired. Sign in again to continue.' });
      }
      throw error;
    }
  }, [transition]);

  return { ...state, authenticate, signOut, request, logout };
}

export function useAction() {
  const lock = useRef(false);
  const mounted = useRef(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const run = async (operation, onError) => {
    if (lock.current) return false;
    lock.current = true;
    setPending(true);
    setError('');
    try {
      await operation();
      return mounted.current;
    } catch (failure) {
      if (mounted.current && failure.name !== 'AbortError') {
        if (onError) onError(failure.message);
        else setError(failure.message);
      }
      return false;
    } finally {
      lock.current = false;
      if (mounted.current) setPending(false);
    }
  };
  return { run, pending, error, clearError: () => setError('') };
}

export function usePublicData({ view, kind, text, sort }) {
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState({ contents: [], posts: [], loading: true, preview: false, error: '' });
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    const feedQuery = query({ kind: view === 'community' ? kind : '', q: view === 'community' ? text : '', sort });
    const catalogQuery = query({ kind: view === 'discover' ? kind : '', q: view === 'discover' ? text : '' });
    setData(previous => ({ ...previous, loading: true, error: '' }));
    Promise.all([
      api(`/contents${catalogQuery}`, { signal: controller.signal }),
      api(`/posts${feedQuery}`, { signal: controller.signal }),
    ]).then(([contents, posts]) => {
      if (!controller.signal.aborted) setData({ contents, posts, loading: false, preview: false, error: '' });
    }).catch(error => {
      if (controller.signal.aborted || error.name === 'AbortError') return;
      if (error.status === 0 || error.status >= 500) {
        const contents = sampleCatalog.filter(content => view !== 'discover' || matches(content, kind, text));
        const posts = samplePosts.filter(post => view !== 'community' || ((!kind || post.content?.kind === kind) && (!text || `${post.body} ${post.content?.title || ''}`.toLowerCase().includes(text.toLowerCase()))));
        setData({ contents, posts, loading: false, preview: true, error: error.message });
      } else {
        setData(previous => ({ ...previous, loading: false, error: error.message }));
      }
    });
    return () => controller.abort();
  }, [view, kind, text, sort, revision]);
  const updatePost = (id, update) => setData(previous => ({ ...previous, posts: previous.posts.map(post => post.id === id ? { ...post, ...update } : post) }));
  return { ...data, refresh, updatePost };
}

export function useCollection(session) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(Boolean(session.user));
  const [error, setError] = useState('');
  const sequence = useRef(0);
  const userId = session.user?.id;
  const request = session.request;
  const refresh = useCallback(async () => {
    if (!userId) return;
    const current = ++sequence.current;
    setLoading(true);
    setError('');
    try {
      const result = await request('/collection');
      if (current === sequence.current) setEntries(result);
    } catch (failure) {
      if (current === sequence.current && failure.name !== 'AbortError') setError(failure.message);
    } finally {
      if (current === sequence.current) setLoading(false);
    }
  }, [userId, request]);
  useEffect(() => {
    refresh();
    return () => { sequence.current += 1; };
  }, [refresh]);

  const acceptEntry = entry => {
    sequence.current += 1;
    setEntries(previous => {
      const exists = previous.some(item => item.id === entry.id);
      return exists ? previous.map(item => item.id === entry.id ? entry : item) : [entry, ...previous];
    });
  };
  const save = async content => {
    const saved = await request('/collection', { method: 'POST', body: { content_id: content.id, status: 'planned' } });
    acceptEntry(saved);
    await refresh();
  };
  const update = async (id, body) => {
    acceptEntry(await request(`/collection/${id}`, { method: 'PATCH', body }));
    await refresh();
  };
  const remove = async id => {
    await request(`/collection/${id}`, { method: 'DELETE' });
    sequence.current += 1;
    setEntries(previous => previous.filter(entry => entry.id !== id));
    await refresh();
  };
  return { entries, loading, error, refresh, save, update, remove };
}
