import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import api from '../services/api'
import './CreatePost.css'

function CreatePost() {
  const navigate = useNavigate()
  const photoInputRef = useRef(null)
  const gifInputRef = useRef(null)

  const [imageUrl, setImageUrl] = useState('')
  const [gifUrl, setGifUrl] = useState('')
  const [linkUrl, setLinkUrl] = useState('')
  const [showLink, setShowLink] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(false)

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        bold: {},
        italic: {},
        strike: {},
        heading: false,
        bulletList: false,
        orderedList: false,
        blockquote: false,
        code: false,
        codeBlock: false
      }),
      Underline
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'post-editor-content'
      }
    }
  })

  const uploadFile = async (file) => {
    if (!file) return null
    if (file.size > 5 * 1024 * 1024) {
      alert('El archivo no puede superar los 5 MB')
      return null
    }
    setUploading(true)
    try {
      const data = new FormData()
      data.append('file', file)
      const res = await api.post('/users/me/avatar', data)
      return res.data.avatar_url || null
    } catch (error) {
      console.error('Error uploading file:', error)
      alert('No se pudo subir el archivo')
      return null
    } finally {
      setUploading(false)
    }
  }

  const handlePhotoSelect = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    const url = await uploadFile(file)
    if (url) {
      setImageUrl(url)
      setGifUrl('')
    }
  }

  const handleGifSelect = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    const url = await uploadFile(file)
    if (url) {
      setGifUrl(url)
      setImageUrl('')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!editor) return
    const html = editor.getHTML()
    const textContent = editor.getText().replace(/\u00a0/g, ' ').trim()
    if (!textContent && !imageUrl.trim() && !gifUrl.trim() && !linkUrl.trim()) return
    setLoading(true)
    try {
      let finalThoughts = html
      if (linkUrl.trim()) {
        const cleanLink = linkUrl.trim()
        if (!finalThoughts.includes(cleanLink)) {
          finalThoughts = finalThoughts + `<p><a href="${cleanLink}" target="_blank" rel="noopener noreferrer">${cleanLink}</a></p>`
        }
      }
      const mediaUrl = (imageUrl.trim() || gifUrl.trim()) || null
      const plainTitle = textContent.slice(0, 60) || 'Publicación'
      const payload = {
        title: plainTitle,
        type: 'book',
        creator: null,
        rating: null,
        thoughts: finalThoughts || '',
        cover_url: mediaUrl
      }
      const res = await api.post('/items', payload)
      navigate(`/item/${res.data.id}`)
    } catch (error) {
      console.error('Error creating post:', error)
    } finally {
      setLoading(false)
    }
  }

  const previewUrl = imageUrl.trim() || gifUrl.trim()
  if (!editor) return null
  const hasContent = editor.getText().replace(/\u00a0/g, ' ').trim().length > 0
  const canPublish = !loading && !uploading && (hasContent || !!imageUrl.trim() || !!gifUrl.trim() || !!linkUrl.trim())

  return (
    <div className="create-post-page">
      <header className="create-post-header">
        <h1>¿Qué estás pensando hoy?</h1>
        <p>Compartí una reflexión, recomendación, foto, GIF o enlace con la comunidad</p>
      </header>
      <form onSubmit={handleSubmit} className="create-post-form">
        <div className="format-toolbar">
          <button type="button" onClick={() => editor.chain().focus().toggleBold().run()} className={`format-btn ${editor.isActive('bold') ? 'active' : ''}`} title="Negrita"><strong>B</strong></button>
          <button type="button" onClick={() => editor.chain().focus().toggleItalic().run()} className={`format-btn ${editor.isActive('italic') ? 'active' : ''}`} title="Cursiva"><em>I</em></button>
          <button type="button" onClick={() => editor.chain().focus().toggleUnderline().run()} className={`format-btn ${editor.isActive('underline') ? 'active' : ''}`} title="Subrayado"><u>U</u></button>
          <button type="button" onClick={() => editor.chain().focus().toggleStrike().run()} className={`format-btn ${editor.isActive('strike') ? 'active' : ''}`} title="Tachado"><s>S</s></button>
        </div>
        <div className="create-post-row">
          <div className="post-editor-shell">
            <EditorContent editor={editor} />
          </div>
        </div>

        {previewUrl && (
          <div className="post-media-preview">
            <img src={previewUrl} alt="Vista previa" />
            <button type="button" className="remove-media" onClick={() => { setImageUrl(''); setGifUrl('') }}>Quitar archivo</button>
          </div>
        )}

        <div className="media-buttons">
          <button type="button" className="media-action-btn" onClick={() => photoInputRef.current?.click()} disabled={uploading}>
            {uploading ? 'Subiendo...' : 'Foto'}
          </button>
          <button type="button" className="media-action-btn" onClick={() => gifInputRef.current?.click()} disabled={uploading}>
            {uploading ? 'Subiendo...' : 'GIF'}
          </button>
          <button type="button" className="media-action-btn" onClick={() => setShowLink(!showLink)}>
            Enlace
          </button>
        </div>

        <input ref={photoInputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handlePhotoSelect} hidden />
        <input ref={gifInputRef} type="file" accept="image/gif" onChange={handleGifSelect} hidden />

        {showLink && (
          <div className="create-post-row">
            <input value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://ejemplo.com" />
          </div>
        )}

        <div className="create-post-actions">
          <button type="submit" disabled={!canPublish} className="create-post-btn">
            {loading ? 'Publicando...' : 'Publicar'}
          </button>
        </div>
      </form>
    </div>
  )
}

export default CreatePost
