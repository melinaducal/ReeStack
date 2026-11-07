import { useEffect } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import { TextStyle } from '@tiptap/extension-text-style'
import { FontFamily } from '@tiptap/extension-font-family'
import './RichTextEditor.css'

const FontSize = TextStyle.extend({
  addAttributes() {
    return {
      fontSize: {
        default: null,
        parseHTML: element => element.style.fontSize || null,
        renderHTML: attributes => {
          if (!attributes.fontSize) return {}
          return { style: `font-size: ${attributes.fontSize}` }
        }
      }
    }
  },
  addCommands() {
    return {
      setFontSize: (fontSize) => ({ chain }) => {
        return chain().setMark('textStyle', { fontSize }).run()
      },
      unsetFontSize: () => ({ chain }) => {
        return chain().setMark('textStyle', { fontSize: null }).removeEmptyTextStyle().run()
      }
    }
  }
})

const SIZE_OPTIONS = ['12px', '14px', '16px', '18px', '20px', '24px', '28px', '32px']

function RichTextEditor({ value = '', onChange }) {
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
      Underline,
      TextStyle,
      FontFamily,
      FontSize
    ],
    content: value,
    onUpdate: ({ editor: current }) => {
      if (onChange) onChange(current.getHTML())
    },
    editorProps: {
      attributes: {
        class: 'rich-editor-content'
      }
    }
  })

  useEffect(() => {
    if (!editor) return
    if (value !== editor.getHTML()) {
      editor.commands.setContent(value || '', { emitUpdate: false })
    }
  }, [editor, value])

  if (!editor) return null

  return (
    <div className="rich-editor">
      <div className="rich-editor-toolbar">
        <select
          className="rich-editor-select"
          defaultValue=""
          onChange={(e) => {
            if (!e.target.value) return
            editor.chain().focus().setFontSize(e.target.value).run()
            e.target.value = ''
          }}
          aria-label="Tamaño de letra"
        >
          <option value="">Tamaño</option>
          {SIZE_OPTIONS.map(size => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
        <button type="button" onClick={() => editor.chain().focus().toggleBold().run()} className={`rich-editor-btn ${editor.isActive('bold') ? 'active' : ''}`} title="Negrita"><strong>B</strong></button>
        <button type="button" onClick={() => editor.chain().focus().toggleItalic().run()} className={`rich-editor-btn ${editor.isActive('italic') ? 'active' : ''}`} title="Cursiva"><em>I</em></button>
        <button type="button" onClick={() => editor.chain().focus().toggleUnderline().run()} className={`rich-editor-btn ${editor.isActive('underline') ? 'active' : ''}`} title="Subrayado"><u>U</u></button>
        <button type="button" onClick={() => editor.chain().focus().toggleStrike().run()} className={`rich-editor-btn ${editor.isActive('strike') ? 'active' : ''}`} title="Tachado"><s>S</s></button>
      </div>
      <EditorContent editor={editor} className="rich-editor-shell" />
    </div>
  )
}

export default RichTextEditor
