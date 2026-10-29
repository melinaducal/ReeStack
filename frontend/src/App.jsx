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
import Appearance from './pages/Appearance'
import Chatbot from './pages/Chatbot'
import './App.css'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'))

  useEffect(() => {
    const themeAccent = localStorage.getItem('themeAccent')
    if (themeAccent) {
      document.documentElement.style.setProperty('--accent-violet', themeAccent)
      document.documentElement.style.setProperty('--accent-hover', themeAccent)
    } else {
      document.documentElement.style.removeProperty('--accent-violet')
      document.documentElement.style.removeProperty('--accent-hover')
    }
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
          <Route path="/" element={isAuthenticated ? <Feed /> : <Navigate to="/login" replace />} />
          <Route path="/stack" element={isAuthenticated ? <Home /> : <Navigate to="/login" replace />} />
          <Route path="/add" element={isAuthenticated ? <AddLibrarySelector /> : <Navigate to="/login" replace />} />
          <Route path="/add-item" element={isAuthenticated ? <AddItem /> : <Navigate to="/login" replace />} />
          <Route path="/add-library/browse" element={isAuthenticated ? <AddLibraryBrowse /> : <Navigate to="/login" replace />} />
          <Route path="/item/:id" element={isAuthenticated ? <ItemDetail /> : <Navigate to="/login" replace />} />
          <Route path="/book-search" element={isAuthenticated ? <BookSearch /> : <Navigate to="/login" replace />} />
          <Route path="/appearance" element={isAuthenticated ? <Appearance /> : <Navigate to="/login" replace />} />
          <Route path="/chatbot" element={isAuthenticated ? <Chatbot /> : <Navigate to="/login" replace />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
