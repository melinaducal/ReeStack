# Reesatck frontend

Reesatck combines a personal cultural and scientific tracker with community reflections. The React client uses hash navigation, a shared catalog/feed, and dialogs for focused actions. Discover and Assistant deep links render usable content rather than an empty page.

## Run locally

With Node.js 22.12 or newer and the project dependencies already installed, run from the repository root:

```sh
npm run dev
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` to `http://127.0.0.1:8000`; run the API separately for sign-in, saved activity, and assistant requests. Without it, the public screen enters the read-only preview described below.

## Routes and navigation

| Hash | Visible UI |
|------|------------|
| `#/community` | Community catalog, inline search, type filters, and reflections. This is also the default when no hash is present. |
| `#/discover` | The same catalog/feed composition, with Discover selected in navigation and shown in the top bar. Switching between Community and Discover keeps the current search and type filter. |
| `#/library` | My library: the signed-in reader's saved works, progress, ratings, and private reviews; otherwise a sign-in prompt. |
| `#/insights` | Insights calculated from the signed-in collection. |
| `#/assistant` | The existing Assistant dialog over the Community catalog/feed. Dismissing it navigates to `#/community`. |

The router also accepts hashes without the slash, such as `#discover` and `#assistant`. Route names are exact and lowercase. Unknown hashes render Community without rewriting the address; navigation buttons write the canonical `#/route` form. Hash changes, including browser history navigation, update the UI without requiring server rewrite rules.

The **Assistant** sidebar button is still a modal action, not a page navigation: it opens over the current page and leaves its hash unchanged. Closing and reopening the dialog retains the conversation until logout or a page reload. There is only one Assistant instance, shared by the sidebar action and the deep link.

Community and Discover reuse the catalog section exported by `DiscoverView.jsx` through `CommunityView.jsx`. Type filters use `book`, `movie`, `series`, `music`, and `paper`; All omits `kind`. Search sends a trimmed `q` to the catalog API after the existing debounce. Type selection also filters the feed, and Sort posts retains its Latest/Most liked behavior. Routing does not introduce separate results, collection state, or API calls.

## Keyboard and small screens

- On small screens, **Toggle navigation** opens or closes the navigation panel; choosing a destination closes it.
- Opening a dialog moves focus to its preferred input or first eligible control. Tab and Shift+Tab cycle through enabled dialog controls.
- Escape, **Close dialog**, or clicking the backdrop dismisses the dialog. Focus returns to its opening control when that control still exists; a direct hash has no opening button to restore.
- The Assistant input and Send message remain disabled when the server reports it is not configured. A failed answer shows an error and **Retry message**, rather than a fabricated response.

The shared `Modal.jsx` owns focus behavior. Routes reuse it instead of installing a second keyboard handler.

## Session clearing and read-only preview

**Signing out clears local private state.** The central `useReesatck` hook clears the current user, collection, and assistant status, invalidates older session-bound loads, and reloads public content. App remounts the Assistant with a fresh key so previous messages and drafts do not appear when it is reopened. A failed sign-out request still clears the local UI; that alone does not confirm server-side session revocation.

Authentication uses API cookies, not a token embedded in the route. Catalog saves and other actions keep using the shared API helpers and authentication checks. Private collection failures show an error/retry state and never substitute sample library entries.

**Preview is not an offline write queue.** If the public API cannot be loaded at startup, the client shows sample public content, a **Read-only** badge, and `Preview mode · Start the API to save your activity`. Write controls are disabled or guarded; preview activity is not persisted. Start the API and use **Reconnect** to retry loading real data. Catalog searches still require the API; preview samples are not a local search service.

## Tests and production build

Run these commands from the repository root:

```sh
# Focused routing regression tests
npm test -- src/routes.test.jsx

# Existing interactions affected by App composition
npm test -- src/App.test.jsx src/flows.test.jsx

# Full frontend suite and production bundle
npm test
npm run build

# Serve the built frontend locally
npm run preview
```

The interaction tests run in jsdom with the existing mocked API contract. They cover navigation and direct hashes, exact request parameters, catalog saves, modal closure, and chat clearing on logout. They do not prove live backend/provider integration or visual layout at every viewport. The production build writes `dist/`; serving it with working API access requires the corresponding `/api` backend/proxy configuration.

## Implementation boundaries

| File | Responsibility |
|------|----------------|
| `src/App.jsx` | Route composition, top-bar titles, dialog visibility, and assistant remount on logout. |
| `src/lib/useRoute.js` | Allowed routes, hash parsing, hash-change subscription, and navigation updates. |
| `src/lib/useReesatck.js` / `src/lib/api.js` | Shared application state, session boundaries, and API transport. |
| `src/routes.test.jsx` | Public-interface routing and preservation regressions. |

See the [API contract](api-contract.md) for endpoint details. Provider credentials and backend setup belong on the server, not in frontend code or hashes.
