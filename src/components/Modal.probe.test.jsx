/**
 * Independent probes for the shared Modal focus trap.
 *
 * These assert the invariant directly instead of trusting the implementation's
 * own tests: every disabled, hidden, inert, negative-tabindex or non-rendered
 * control must stay out of the tab order, and focus must never escape a panel
 * even when jsdom reports `offsetParent === null` for every visible control.
 */
import { useRef, useState } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Modal from './Modal.jsx'

/** Panel with every exclusion the contract names, trailing the real focusables. */
function TrapFixture({ open = true, onClose, initialFocusRef }) {
  return (
    <Modal open={open} title="Trap" onClose={onClose} initialFocusRef={initialFocusRef}>
      <button>Alpha</button>
      <input aria-label="Notes" defaultValue="" />
      <button style={{ position: 'fixed' }}>Omega</button>
      <button disabled>Disabled</button>
      <input type="hidden" readOnly value="hidden-input" />
      <button tabIndex={-1}>Programmatic</button>
      <div hidden><button>HiddenAncestor</button></div>
      <div inert><button>InertAncestor</button></div>
      <div style={{ display: 'none' }}><button>NotDisplayed</button></div>
      <button style={{ visibility: 'hidden' }}>Invisible</button>
      <div style={{ visibility: 'collapse' }}><button>Collapsed</button></div>
      <fieldset disabled><button>DisabledGroup</button></fieldset>
    </Modal>
  )
}

function Page() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(true)}>Open editor</button>
      <input aria-label="Background field" />
      <TrapFixture open={open} onClose={() => setOpen(false)} />
      <button>Background after</button>
      <input aria-label="Background field two" />
    </div>
  )
}

const INSIDE = (dialog) => dialog.contains(document.activeElement)
const label = (el) => el.getAttribute('aria-label') || el.textContent || el.tagName
const BACKGROUND = ['Background field', 'Background field two', 'Background after', 'Open editor']

it('traps Tab inside the panel and never reaches background controls', async () => {
  const user = userEvent.setup()
  render(<Page />)
  await user.click(screen.getByRole('button', { name: 'Open editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  expect(INSIDE(dialog)).toBe(true)

  const visited = []
  for (let i = 0; i < 24; i += 1) {
    visited.push(label(document.activeElement))
    if (!INSIDE(dialog)) break
    await user.tab()
  }
  expect(INSIDE(dialog), `focus escaped to ${label(document.activeElement)}`).toBe(true)
  visited.forEach((entry) => expect(BACKGROUND).not.toContain(entry))
  const forbidden = ['Disabled', 'Programmatic', 'HiddenAncestor', 'InertAncestor',
    'NotDisplayed', 'Invisible', 'Collapsed', 'DisabledGroup', 'hidden-input']
  visited.forEach((entry) => expect(forbidden).not.toContain(entry))
  expect([...new Set(visited)].sort()).toEqual(['Alpha', 'Close dialog', 'Notes', 'Omega'].sort())
})

it('traps Shift+Tab backwards and lands on the last real control', async () => {
  const user = userEvent.setup()
  render(<Page />)
  await user.click(screen.getByRole('button', { name: 'Open editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  const close = within(dialog).getByRole('button', { name: 'Close dialog' })

  close.focus()
  await user.tab({ shift: true })
  expect(document.activeElement.textContent).toBe('Omega')
  expect(INSIDE(dialog)).toBe(true)

  await user.tab()
  expect(document.activeElement).toBe(close)
  expect(INSIDE(dialog)).toBe(true)
})

it('traps focus even though offsetParent is null for every control in a non-layout DOM', async () => {
  const user = userEvent.setup()
  render(<Page />)
  await user.click(screen.getByRole('button', { name: 'Open editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  const close = within(dialog).getByRole('button', { name: 'Close dialog' })
  const omega = within(dialog).getByRole('button', { name: 'Omega' })

  // jsdom has no layout, so offsetParent is null even for visible controls.
  expect(close.offsetParent).toBeNull()
  expect(omega.offsetParent).toBeNull()

  omega.focus()
  await user.tab()
  expect(document.activeElement).toBe(close)
})

it('keeps a Shift+Tab walk inside the panel too', async () => {
  const user = userEvent.setup()
  render(<Page />)
  await user.click(screen.getByRole('button', { name: 'Open editor' }))
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  const visited = []
  for (let i = 0; i < 20; i += 1) {
    visited.push(label(document.activeElement))
    if (!INSIDE(dialog)) break
    await user.tab({ shift: true })
  }
  expect(INSIDE(dialog), `focus escaped to ${label(document.activeElement)}`).toBe(true)
  visited.forEach((entry) => expect(BACKGROUND).not.toContain(entry))
})

it('excludes every disabled, hidden, inert, negative-tabindex and non-rendered control', async () => {
  const user = userEvent.setup()
  render(<TrapFixture onClose={() => {}} />)
  const dialog = screen.getByRole('dialog', { name: 'Trap' })

  const close = within(dialog).getByRole('button', { name: 'Close dialog' })
  close.focus()
  const order = []
  for (let i = 0; i < 12; i += 1) {
    order.push(label(document.activeElement))
    await user.tab()
  }
  expect([...new Set(order)].sort()).toEqual(['Alpha', 'Close dialog', 'Notes', 'Omega'].sort())
})

it('the DOM environment actually supports the exclusion rules the modal relies on', () => {
  const { container } = render(
    <div>
      <button disabled>Disabled</button>
      <button tabIndex={-1}>Programmatic</button>
      <div inert><button>Inert</button></div>
      <fieldset disabled><button>DisabledGroup</button></fieldset>
    </div>,
  )
  const [disabled, programmatic, inertChild, groupChild] = container.querySelectorAll('button')
  expect(disabled.matches(':disabled')).toBe(true)
  expect(programmatic.matches(':disabled')).toBe(false)
  expect(inertChild.closest('[inert]')).not.toBeNull()
  expect(groupChild.matches(':disabled')).toBe(true)
})

it('focuses initialFocusRef when provided and keeps it stable while typing', async () => {
  const user = userEvent.setup()
  function Typed() {
    const [value, setValue] = useState('')
    const ref = useRef(null)
    return (
      <Modal open title="Editor" onClose={() => {}} initialFocusRef={ref}>
        <label>Title<input ref={ref} value={value} onChange={(event) => setValue(event.target.value)} /></label>
        <button>Save</button>
      </Modal>
    )
  }
  render(<Typed />)
  const input = screen.getByLabelText('Title')
  expect(input).toHaveFocus()
  await user.type(input, 'A complete title')
  expect(input).toHaveValue('A complete title')
  expect(input).toHaveFocus()
})

it('focuses the first focusable item when no initialFocusRef is given', async () => {
  render(<TrapFixture onClose={() => {}} />)
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  expect(within(dialog).getByRole('button', { name: 'Close dialog' })).toHaveFocus()
})

it('a new inline onClose callback on every keystroke never steals the focus', async () => {
  const user = userEvent.setup()
  function Churn() {
    const [value, setValue] = useState('')
    const ref = useRef(null)
    return (
      <Modal open title="Churn" onClose={() => {}} initialFocusRef={ref}>
        <label>Body<input ref={ref} value={value} onChange={(event) => setValue(event.target.value)} /></label>
      </Modal>
    )
  }
  render(<Churn />)
  const input = screen.getByLabelText('Body')
  expect(input).toHaveFocus()
  await user.type(input, 'typing keeps focus')
  expect(input).toHaveFocus()
  expect(input).toHaveValue('typing keeps focus')
})

it('closes on Escape and returns the focus to the trigger that opened it', async () => {
  const user = userEvent.setup()
  render(<Page />)
  const trigger = screen.getByRole('button', { name: 'Open editor' })
  await user.click(trigger)
  expect(screen.getByRole('dialog', { name: 'Trap' })).toBeInTheDocument()

  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

it('closes on Escape even when the focus sits on a deep control of the panel', async () => {
  const user = userEvent.setup()
  render(<Page />)
  const trigger = screen.getByRole('button', { name: 'Open editor' })
  await user.click(trigger)
  const dialog = screen.getByRole('dialog', { name: 'Trap' })
  within(dialog).getByRole('button', { name: 'Omega' }).focus()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})

it('does not let Tab escape to the background from a panel with no focusable content', async () => {
  const user = userEvent.setup()
  render(
    <div>
      <button>Background before</button>
      <Modal open title="Empty" onClose={() => {}}>
        <p>Only text, no controls.</p>
      </Modal>
      <button>Background after</button>
    </div>,
  )
  const dialog = screen.getByRole('dialog', { name: 'Empty' })
  await user.tab()
  const active = document.activeElement
  const escaped = active !== document.body && !dialog.contains(active)
  expect(escaped, `focus escaped to ${label(active)}`).toBe(false)
})
