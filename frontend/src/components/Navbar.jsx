import { Link, useNavigate } from 'react-router-dom'
import './Navbar.css'

function Navbar() {
  const navigate = useNavigate()
  const isAuthenticated = localStorage.getItem('token')

  const handleLogout = () => {
    localStorage.clear()
    navigate('/login', { replace: true })
    window.location.reload()
  }

  return (
    <nav className="navbar">
      <div className="navbar-container">
        <Link to="/" className="navbar-logo">ReeStack</Link>
        <ul className="navbar-menu">
          {isAuthenticated && (
            <>
              <li className="navbar-item">
                <Link to="/" className="navbar-link">Inicio</Link>
              </li>
              <li className="navbar-item">
                <Link to="/stack" className="navbar-link">Mi Stack</Link>
              </li>
              <li className="navbar-item">
                <Link to="/chatbot" className="navbar-link">Recomendador</Link>
              </li>
              <li className="navbar-item">
                <Link to="/book-search" className="navbar-link">Buscar libros</Link>
              </li>
              <li className="navbar-item">
                <Link to="/add" className="navbar-link">Agregar</Link>
              </li>
              <li className="navbar-item">
                <Link to="/settings" className="navbar-link">Configuración</Link>
              </li>
              <li className="navbar-item">
                <button onClick={handleLogout} className="navbar-logout">Cerrar sesión</button>
              </li>
            </>
          )}
        </ul>
      </div>
    </nav>
  )
}

export default Navbar
