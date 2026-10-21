import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { api } from './api.js'
import { PREVIEW_CONTENTS, PREVIEW_POSTS } from './catalog.js'

/**
 * Central application state.
 *
 * Two rules matter for correctness:
 * 1. A failed write is never converted into an optimistic success.
 * 2. Private or mutation data never falls back to sample data. Preview
 *    content appears only when the read-only public API is unreachable, and
 *    every mutation is blocked in that mode.
 */

const EMPTY_STATE = {
  user: null,
  contents: [],
  posts: [],
  collection: [],
  assistant: { configured: false, model: null },
}

export function useReesatck() {
  const [state, setState] = useState(EMPTY_STATE)
  const [booting, setBooting] = useState(true)
  const [offline, setOffline] = useState(false)
  const [libraryError, setLibraryError] = useState(null)
  const [catalogLoading, setCatalogLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const [authOpen, setAuthOpen] = useState(false)
  const generation = useRef(0)

  const notify = useCallback((message, tone = 'info') => {
    setToast({ message, tone, id: Date.now() })
  }, [])

  const dismissToast = useCallback(() => setToast(null), [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(timer)
  }, [toast])

  const loadPublic = useCallback(async (token) => {
    const [contents, posts] = await Promise.all([api.listContents(), api.listPosts({ sort: 'latest' })])
    if (generation.current !== token) return
    setState((prev) => ({ ...prev, contents, posts }))
    setOffline(false)
  }, [])

  const loadPrivate = useCallback(async (token) => {
    const [assistant] = await Promise.all([api.assistantStatus()])
    if (generation.current !== token) return
    let collection = null
    let error = null
    try {
      collection = await api.getCollection()
      error = null
    } catch (err) {
      error = err?.detail || 'Your library could not be loaded.'
    }
    if (generation.current !== token) return
    setLibraryError(error)
    setState((prev) => ({ ...prev, assistant, collection: collection ?? prev.collection }))
  }, [])

  /** Reloads only the private collection. Used by the library's retry action. */
  const retryLibrary = useCallback(async () => {
    if (!state.user) return
    const token = generation.current
    setLibraryError(null)
    try {
      const collection = await api.getCollection()
      if (generation.current !== token) return
      setState((prev) => ({ ...prev, collection }))
    } catch (err) {
      if (generation.current !== token) return
      setLibraryError(err?.detail || 'Your library could not be loaded.')
    }
  }, [state.user])

  /**
   * The feed is filtered by the API, not in the browser: the catalog and the
   * post list can outgrow what a client should hold. `params` mirrors the
   * query the server understands (kind, q, sort).
   */
  const loadPosts = useCallback(
    async (params) => {
      const token = generation.current
      const posts = await api.listPosts(params)
      if (generation.current !== token) return null
      setState((prev) => ({ ...prev, posts }))
      return posts
    },
    [],
  )

  /**
   * The catalog is searched by the API too: a query is a server round trip, so
   * the client never has to hold the whole shared catalog.
   */
  const loadContents = useCallback(async (params) => {
    const token = generation.current
    setCatalogLoading(true)
    try {
      const contents = await api.listContents(params)
      if (generation.current !== token) return null
      setState((prev) => ({ ...prev, contents }))
      return contents
    } finally {
      if (generation.current === token) setCatalogLoading(false)
    }
  }, [])

  const refresh = useCallback(async () => {
    const token = generation.current
    try {
      const [contents, posts, assistant] = await Promise.all([
        api.listContents(),
        api.listPosts({ sort: 'latest' }),
        api.assistantStatus(),
      ])
      if (generation.current !== token) return
      setState((prev) => ({ ...prev, contents, posts, assistant }))
      setOffline(false)
    } catch {
      if (generation.current !== token) return
      setOffline(true)
      setState((prev) => ({
        ...prev,
        contents: prev.contents.length ? prev.contents : PREVIEW_CONTENTS,
        posts: prev.posts.length ? prev.posts : PREVIEW_POSTS,
      }))
    }
    if (state.user) {
      try {
        const collection = await api.getCollection()
        if (generation.current !== token) return
        setState((prev) => ({ ...prev, collection }))
      } catch {
        /* private data is not replaced with samples on failure */
      }
    }
  }, [state.user])

  // Boot: resolve the session, then load what that identity may see.
  useEffect(() => {
    let cancelled = false
    const boot = async () => {
      const token = generation.current
      let user = null
      try {
        user = await api.me()
      } catch {
        user = null
      }
      if (cancelled || generation.current !== token) return
      setState((prev) => ({ ...prev, user }))
      try {
        await loadPublic(token)
      } catch {
        if (!cancelled && generation.current === token) {
          setOffline(true)
          setState((prev) => ({ ...prev, contents: PREVIEW_CONTENTS, posts: PREVIEW_POSTS }))
        }
      }
if (!cancelled) setBooting(false)
      if (user) {
        try {
          await loadPrivate(token)
        } catch {
          /* stays empty, never sampled */
        }
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [loadPublic, loadPrivate])

  const handleAuth = useCallback(
    async ({ mode, username, display_name, password }) => {
      const user =
        mode === 'register'
          ? await api.register({ username, display_name: display_name || username, password })
          : await api.login({ username, password })
      generation.current += 1
      const token = generation.current
      setState({ ...EMPTY_STATE, user, assistant: { configured: false, model: null } })
      setOffline(false)
      try {
        await loadPublic(token)
        await loadPrivate(token)
      } catch {
        /* session is valid even if the follow-up read fails */
      }
      notify(mode === 'register' ? `Welcome to Reesatck, ${user.display_name}.` : `Welcome back, ${user.display_name}.`)
      return user
    },
    [loadPrivate, loadPublic, notify],
  )

  const handleLogout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      /* the local session is cleared regardless */
    }
    generation.current += 1
    setState(EMPTY_STATE)
    setAuthOpen(false)
    notify('Signed out. Your library stays private.')
    try {
      await loadPublic(generation.current)
    } catch {
      setOffline(true)
      setState((prev) => ({ ...prev, contents: PREVIEW_CONTENTS, posts: PREVIEW_POSTS }))
    }
  }, [loadPublic, notify])

  const requireAuth = useCallback(() => {
    if (state.user) return true
    setAuthOpen(true)
    notify('Sign in to save to your library.', 'info')
    return false
  }, [notify, state.user])

  const guardPreview = useCallback(() => {
    if (offline) {
      notify('Preview mode is read-only. Start the API to save your activity.', 'warn')
      return false
    }
    return true
  }, [notify, offline])

  const saveContent = useCallback(
    async (contentId) => {
      // Order matters: an unauthenticated visitor is asked to sign in even in
      // preview mode, because that is the next useful step either way.
      if (!requireAuth()) return null
      if (!guardPreview()) return null
      const entry = await api.saveContent(contentId)
      setState((prev) => {
        const others = prev.collection.filter((item) => item.id !== entry.id)
        return { ...prev, collection: [entry, ...others] }
      })
      notify('Saved to your library.')
      return entry
    },
    [guardPreview, notify, requireAuth],
  )

  const updateEntry = useCallback(
    async (entryId, patch) => {
      const entry = await api.patchEntry(entryId, patch)
      setState((prev) => ({
        ...prev,
        collection: prev.collection.map((item) => (item.id === entry.id ? entry : item)),
      }))
      return entry
    },
    [],
  )

  const removeEntry = useCallback(
    async (entryId) => {
      await api.removeEntry(entryId)
      setState((prev) => ({ ...prev, collection: prev.collection.filter((item) => item.id !== entryId) }))
      notify('Removed from your library.')
      return true
    },
    [notify],
  )

  const createContent = useCallback(async (payload) => {
    const content = await api.createContent(payload)
    setState((prev) => ({ ...prev, contents: [content, ...prev.contents] }))
    return content
  }, [])

  const publishPost = useCallback(
    async (payload) => {
      const post = await api.createPost(payload)
      setState((prev) => ({ ...prev, posts: [post, ...prev.posts] }))
      notify('Published to the community feed.')
      return post
    },
    [notify],
  )

  const toggleLike = useCallback(
    async (postId) => {
      const target = state.posts.find((post) => post.id === postId)
      const result = target?.liked ? await api.unlikePost(postId) : await api.likePost(postId)
      setState((prev) => ({
        ...prev,
        posts: prev.posts.map((post) =>
          post.id === postId ? { ...post, liked: result.liked, like_count: result.like_count } : post,
        ),
      }))
      return result
    },
    [state.posts],
  )

  const createComment = useCallback(async (postId, body) => {
    const comment = await api.createComment(postId, body)
    setState((prev) => ({
      ...prev,
      posts: prev.posts.map((post) =>
        post.id === postId ? { ...post, comment_count: post.comment_count + 1 } : post,
      ),
    }))
    return comment
  }, [])

  const loadComments = useCallback((postId) => api.listComments(postId), [])

  const askAssistant = useCallback(async (message) => {
    const result = await api.assistantChat(message)
    return result.reply
  }, [])

  const reloadAssistant = useCallback(async () => {
    try {
      const assistant = await api.assistantStatus()
      setState((prev) => ({ ...prev, assistant }))
    } catch {
      /* status is advisory; a failure leaves the previous value */
    }
  }, [])

  const isSaved = useCallback(
    (contentId) => state.collection.some((entry) => entry.content.id === contentId),
    [state.collection],
  )

  return useMemo(
    () => ({
      ...state,
      booting,
      offline,
      libraryError,
      catalogLoading,
      toast,
      authOpen,
      setAuthOpen,
      dismissToast,
      refresh,
      retryLibrary,
      loadPosts,
      loadContents,
      handleAuth,
      handleLogout,
      requireAuth,
      saveContent,
      updateEntry,
      removeEntry,
      createContent,
      publishPost,
      toggleLike,
      createComment,
      loadComments,
      askAssistant,
      reloadAssistant,
      isSaved,
    }),
    [
      state,
      booting,
      offline,
      libraryError,
      catalogLoading,
      toast,
      authOpen,
      dismissToast,
      refresh,
      retryLibrary,
      loadPosts,
      loadContents,
      handleAuth,
      handleLogout,
      requireAuth,
      saveContent,
      updateEntry,
      removeEntry,
      createContent,
      publishPost,
      toggleLike,
      createComment,
      loadComments,
      askAssistant,
      reloadAssistant,
      isSaved,
    ],
  )
}
