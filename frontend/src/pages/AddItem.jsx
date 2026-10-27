import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import './AddItem.css'

function AddItem() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    title: '',
    type: 'book',
    creator: '',
    year: '',
    rating: '',
    thoughts: ''
  })

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const data = {
        ...formData,
        year: formData.year ? parseInt(formData.year) : null,
        rating: formData.rating ? parseInt(formData.rating) : null
      }
      await api.post('/items', data)
      navigate('/')
    } catch (error) {
      console.error('Error adding item:', error)
    }
  }

  return (
    <div className="add-item">
      <h1>Agregar Elemento</h1>
      <form onSubmit={handleSubmit} className="add-form">
        <div className="form-group">
          <label>Título *</label>
          <input type="text" name="title" value={formData.title} onChange={handleChange} required />
        </div>
        <div className="form-group">
          <label>Tipo *</label>
          <select name="type" value={formData.type} onChange={handleChange} required>
            <option value="book">Libro</option>
            <option value="movie">Película</option>
            <option value="series">Serie</option>
            <option value="music">Música</option>
            <option value="paper">Paper</option>
          </select>
        </div>
        <div className="form-group">
          <label>Autor/Creador/Artista</label>
          <input type="text" name="creator" value={formData.creator} onChange={handleChange} />
        </div>
        <div className="form-group">
          <label>Año</label>
          <input type="number" name="year" value={formData.year} onChange={handleChange} />
        </div>
        <div className="form-group">
          <label>Calificación (0-10)</label>
          <input type="number" name="rating" min="0" max="10" value={formData.rating} onChange={handleChange} />
        </div>
        <div className="form-group">
          <label>Pensamientos y Opiniones</label>
          <textarea name="thoughts" value={formData.thoughts} onChange={handleChange} rows="5"></textarea>
        </div>
        <button type="submit" className="submit-btn">Guardar</button>
      </form>
    </div>
  )
}

export default AddItem
