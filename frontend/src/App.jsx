import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
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
  const isAuthenticated = localStorage.getItem('token')

  useEffect(() => {
    const themeAccent = localStorage.getItem('themeAccent')
    if (themeAccent) {
      document.documentElement.style.setProperty('--accent-violet', themeAccent)
      document.documentElement.style.setProperty('--accent-hover', themeAccent)
    }
  }, [])

  return (
    <Router>
      {isAuthenticated && <Navbar />}
      <div className={isAuthenticated ? "container" : ""}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/" element={isAuthenticated ? <Feed /> : <Navigate to="/login" />} />
          <Route path="/stack" element={isAuthenticated ? <Home /> : <Navigate to="/login" />} />
          <Route path="/add" element={isAuthenticated ? <AddLibrarySelector /> : <Navigate to="/login" />} />
          <Route path="/add-item" element={isAuthenticated ? <AddItem /> : <Navigate to="/login" />} />
          <Route path="/add-library/browse" element={isAuthenticated ? <AddLibraryBrowse /> : <Navigate to="/login" />} />
          <Route path="/item/:id" element={isAuthenticated ? <ItemDetail /> : <Navigate to="/login" />} />
          <Route path="/book-search" element={isAuthenticated ? <BookSearch /> : <Navigate to="/login" />} />
          <Route path="/appearance" element={isAuthenticated ? <Appearance /> : <Navigate to="/login" />} />
          <Route path="/chatbot" element={isAuthenticated ? <Chatbot /> : <Navigate to="/login" />} />
        </Routes>
      </div>
    </Router>
  )
}

export default App
