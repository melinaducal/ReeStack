import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import AddItem from './pages/AddItem'
import ItemDetail from './pages/ItemDetail'
import BookSearch from './pages/BookSearch'
import Feed from './pages/Feed'
import AddLibrarySelector from './pages/AddLibrarySelector'
import AddLibraryBrowse from './pages/AddLibraryBrowse'
import Login from './pages/Login'
import Register from './pages/Register'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import Chatbot from './pages/Chatbot'
import Settings from './pages/Settings'
import Profile from './pages/Profile'
import UsersExplore from './pages/UsersExplore'
import UserPublicProfile from './pages/UserPublicProfile'
import CreatePost from './pages/CreatePost'
import './App.css'

const themePalettes = [
  { id: 'default', accent: '#6B46C1', bg: '#fbf7f3', surface: '#ffffff', border: '#e6dfd6' },
  { id: 'rose', accent: '#B98A9D', bg: '#f8f5f7', surface: '#ffffff', border: '#e7dfe6' },
  { id: 'lavender', accent: '#9B8BFF', bg: '#f7f6fb', surface: '#ffffff', border: '#e5e1f3' },
  { id: 'plum', accent: '#7C3FBF', bg: '#f7f5fa', surface: '#ffffff', border: '#e4dff0' },
  { id: 'moss', accent: '#7C8B5A', bg: '#f7f8f4', surface: '#ffffff', border: '#e6e7dd' },
  { id: 'midnight', accent: '#5B6BFF', bg: '#f6f7fb', surface: '#ffffff', border: '#e2e4f3' },
  { id: 'sky', accent: '#7AA2FF', bg: '#f6f9ff', surface: '#ffffff', border: '#e3e8f6' },
  { id: 'dusty', accent: '#B9A07E', bg: '#f8f6f2', surface: '#ffffff', border: '#e7e1d6' }
]

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'))

  useEffect(() => {
    const themeAccent = localStorage.getItem('themeAccent')
    const themePalette = localStorage.getItem('themePalette') || 'default'
    const palette = themePalettes.find(p => p.id === themePalette) || themePalettes[0]
    const finalAccent = themeAccent || palette.accent

    document.documentElement.style.setProperty('--accent-violet', finalAccent)
    document.documentElement.style.setProperty('--accent-hover', finalAccent)
    document.documentElement.style.setProperty('--page-bg', palette.bg)
    document.documentElement.style.setProperty('--surface', palette.surface)
    document.documentElement.style.setProperty('--border-color', palette.border)
    document.documentElement.style.setProperty('--bg-primary', palette.bg)
    document.documentElement.style.setProperty('--bg-card', palette.surface)

    const checkToken = () => setToken(localStorage.getItem('token'))
    window.addEventListener('storage', checkToken)
    window.addEventListener('focus', checkToken)
    return () => {
      window.removeEventListener('storage', checkToken)
      window.removeEventListener('focus', checkToken)
    }
  }, [])

  useEffect(() => {
    setToken(localStorage.getItem('token'))
  })

  const isAuthenticated = !!token

  return (
    <Router>
      {isAuthenticated && <Navbar />}
      <div className={isAuthenticated ? "container" : ""}>
        <Routes>
          <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/" replace />} />
          <Route path="/register" element={!isAuthenticated ? <Register /> : <Navigate to="/" replace />} />
          <Route path="/forgot-password" element={!isAuthenticated ? <ForgotPassword /> : <Navigate to="/" replace />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/" element={isAuthenticated ? <Feed /> : <Navigate to="/login" replace />} />
          <Route path="/stack" element={isAuthenticated ? <Home /> : <Navigate to="/login" replace />} />
          <Route path="/settings" element={isAuthenticated ? <Settings /> : <Navigate to="/login" replace />} />
          <Route path="/profile" element={isAuthenticated ? <Profile /> : <Navigate to="/login" replace />} />
          <Route path="/users" element={isAuthenticated ? <UsersExplore /> : <Navigate to="/login" replace />} />
          <Route path="/users/:id" element={isAuthenticated ? <UserPublicProfile /> : <Navigate to="/login" replace />} />
          <Route path="/create-post" element={isAuthenticated ? <CreatePost /> : <Navigate to="/login" replace />} />
          <Route path="/add" element={isAuthenticated ? <AddLibrarySelector /> : <Navigate to="/login" replace />} />
          <Route path="/add-item" element={isAuthenticated ? <AddItem /> : <Navigate to="/login" replace />} />
          <Route path="/add-library/browse" element={isAuthenticated ? <AddLibraryBrowse /> : <Navigate to="/login" replace />} />
          <Route path="/item/:id" element={isAuthenticated ? <ItemDetail /> : <Navigate to="/login" replace />} />
          <Route path="/book-search" element={isAuthenticated ? <BookSearch /> : <Navigate to="/login" replace />} />
          <Route path="/chatbot" element={isAuthenticated ? <Chatbot /> : <Navigate to="/login" replace />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
