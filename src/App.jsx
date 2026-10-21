import { useEffect, useState } from 'react'
import { Menu, RefreshCw, WifiOff } from 'lucide-react'

import AuthDialog from './components/AuthDialog.jsx'
import Composer from './components/Composer.jsx'
import Sidebar from './components/Sidebar.jsx'
import AssistantView from './views/AssistantView.jsx'
import CommunityView from './views/CommunityView.jsx'
import { AddContentDialog } from './views/DiscoverView.jsx'
import InsightsView from './views/InsightsView.jsx'
import LibraryView from './views/LibraryView.jsx'
import { useReesatck } from './lib/useReesatck.js'
import { useRoute } from './lib/useRoute.js'

const TITLES = {
  community: 'Community',
  discover: 'Discover',
  library: 'My library',
  insights: 'Insights',
  assistant: 'Assistant',
}

export default function App() {
  const app = useReesatck()
  const { route, navigate } = useRoute()
  const [mobileNav, setMobileNav] = useState(false)
  const [composerOpen, setComposerOpen] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [chatKey, setChatKey] = useState(0)

  // Signing out must erase any assistant conversation held in memory.
  useEffect(() => {
    if (!app.user) setChatKey((key) => key + 1)
  }, [app.user])

  const openComposer = () => {
    if (!app.user) {
      app.setAuthOpen(true)
      return
    }
    if (app.offline) return
    setComposerOpen(true)
  }

  const publish = async (payload) => {
    const post = await app.publishPost(payload)
    if (route !== 'community') navigate('community')
    return post
  }

  return (
    <div className="app">
      <Sidebar
        route={route}
        navigate={navigate}
        user={app.user}
        offline={app.offline}
        onSignIn={() => app.setAuthOpen(true)}
        onLogout={app.handleLogout}
        onCompose={openComposer}
        onAddContent={() => {
          setMobileNav(false)
          setAddOpen(true)
        }}
        onOpenAssistant={() => setAssistantOpen(true)}
        mobileOpen={mobileNav}
        onCloseMobile={() => setMobileNav(false)}
      />

      <div className="app__body">
        <header className="topbar">
          <button
            type="button"
            className="icon-button topbar__menu"
            onClick={() => setMobileNav((open) => !open)}
            aria-expanded={mobileNav}
            aria-label="Toggle navigation"
          >
            <Menu size={18} strokeWidth={1.7} aria-hidden="true" />
          </button>
          <span className="topbar__crumb">
            <span className="muted small">Reesatck</span>
            <strong>{TITLES[route]}</strong>
          </span>
          <div className="topbar__actions">
            {app.offline && (
              <span className="badge badge--warn">
                <WifiOff size={13} strokeWidth={1.8} aria-hidden="true" />
                Read-only
              </span>
            )}
            <button
              type="button"
              className="icon-button"
              onClick={app.refresh}
              aria-label={app.offline ? 'Reconnect' : 'Refresh data'}
            >
              <RefreshCw size={17} strokeWidth={1.7} aria-hidden="true" />
            </button>
          </div>
        </header>

        {app.offline && (
          <p className="banner" role="status">
            Preview mode · Start the API to save your activity
          </p>
        )}

        <main className="app__main" id="main">
          {/* Discover reuses the embedded catalog without resetting its search.
              Assistant deep links keep the same useful view behind the dialog. */}
          {(route === 'community' || route === 'discover' || route === 'assistant') && (
            <CommunityView app={app} onAddContent={() => setAddOpen(true)} />
          )}
          {route === 'library' && <LibraryView app={app} />}
          {route === 'insights' && <InsightsView app={app} />}
        </main>

        <footer className="footer">
          <span>Reesatck</span>
          <span className="muted small">Stay curious. Keep a record.</span>
        </footer>
      </div>

      <AuthDialog open={app.authOpen} onClose={() => app.setAuthOpen(false)} onSubmit={app.handleAuth} />

      {addOpen && (
        <AddContentDialog
          open
          onClose={() => setAddOpen(false)}
          onCreate={app.createContent}
          onSave={app.saveContent}
        />
      )}

      {app.user && (
        <Composer
          open={composerOpen}
          onClose={() => setComposerOpen(false)}
          contents={app.contents}
          onSubmit={publish}
        />
      )}

      <AssistantView
        key={chatKey}
        app={app}
        open={assistantOpen || route === 'assistant'}
        onClose={() => {
          setAssistantOpen(false)
          if (route === 'assistant') navigate('community')
        }}
      />

      {app.toast && (
        <div className={`toast toast--${app.toast.tone}`} role="status" onClick={app.dismissToast}>
          {app.toast.message}
        </div>
      )}
    </div>
  )
}
