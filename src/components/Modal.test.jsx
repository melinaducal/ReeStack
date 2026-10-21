import { useRef, useState } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Modal from './Modal.jsx'

function Example() {
  const [open, setOpen] = useState(false)
  const [value, setValue] = useState('')
  const inputRef = useRef(null)
  return (
    <>
      <button onClick={() => setOpen(true)}>Open editor</button>
      <Modal open={open} title="Editor" onClose={() => setOpen(false)} initialFocusRef={inputRef}>
        <label>Title<input ref={inputRef} value={value} onChange={(event) => setValue(event.target.value)} /></label>
        <button style={{ position: 'fixed' }}>Save</button>
        <button disabled>Unavailable</button>
        <button tabIndex={-1}>Programmatic only</button>
        <div hidden><button>Hidden ancestor</button></div>
        <div style={{ display: 'none' }}><button>Not displayed</button></div>
        <button style={{ visibility: 'hidden' }}>Invisible</button>
        <fieldset disabled><button>Disabled group</button></fieldset>
        <input type="hidden" />
      </Modal>
    </>
  )
}

it('wraps keyboard focus in both directions, skipping unavailable controls without relying on layout', async () => {
  const user = userEvent.setup()
  render(<Example />)
  await user.click(screen.getByRole('button', { name: 'Open editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Editor' })
  const close = within(dialog).getByRole('button', { name: 'Close dialog' })
  const save = within(dialog).getByRole('button', { name: 'Save' })

  close.focus()
  await user.tab({ shift: true })
  expect(save).toHaveFocus()
  await user.tab()
  expect(close).toHaveFocus()
  await user.tab()
  expect(within(dialog).getByLabelText('Title')).toHaveFocus()
})

it('keeps initial focus stable while typing and restores the trigger after Escape', async () => {
  const user = userEvent.setup()
  render(<Example />)
  const trigger = screen.getByRole('button', { name: 'Open editor' })
  await user.click(trigger)
  const input = screen.getByLabelText('Title')
  expect(input).toHaveFocus()
  await user.type(input, 'A complete title')
  expect(input).toHaveValue('A complete title')
  expect(input).toHaveFocus()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
