import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import App from './App.jsx'
import { book, entry, mockApi } from './test/fixtures.js'

function start(hash = '', options) {
  window.history.replaceState(null, '', hash || window.location.pathname)
  const mock = mockApi(options)
  const user = userEvent.setup()
  render(<App />)
  return { ...mock, user }
}

function changeHash(hash) {
  act(() => {
    window.history.replaceState(null, '', hash)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
}

function expectTitle(label) {
  const topbar = screen.getByRole('button', { name: 'Toggle navigation' }).closest('header')
  expect(within(topbar).getByText(label, { exact: true })).toBeVisible()
}

function expectRoute(label) {
  expectTitle(label)
  expect(screen.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-current', 'page')
}

describe('Discover routing', () => {
  it('opens Discover from navigation and uses the existing search and save contract', async () => {
    const { user, calls } = start('', { signedIn: true })
    await screen.findByText('A creative life begins with noticing.')
    await user.click(screen.getByRole('button', { name: 'Discover', exact: true }))

    expect(window.location.hash).toBe('#/discover')
    expectRoute('Discover')
    const catalog = within(screen.getByRole('region', { name: 'Catalog' }))
    await user.type(catalog.getByRole('searchbox', { name: 'Search the catalog' }), 'Creative Act')
    await waitFor(() => expect(calls).toContainEqual({
      key: 'GET /contents', body: undefined, search: 'q=Creative+Act',
    }))
    await waitFor(() => expect(catalog.queryByText('Interstellar')).not.toBeInTheDocument())
    await user.click(catalog.getByRole('button', { name: 'Save for later: The Creative Act' }))
    expect(await catalog.findByRole('button', { name: 'Saved for later: The Creative Act' })).toBeDisabled()
    expect(calls.filter(call => call.key === 'POST /collection')).toEqual([
      { key: 'POST /collection', body: { content_id: book.id, status: 'planned' }, search: '' },
    ])
  })

  it.each(['#/discover', '#discover'])('loads the catalog directly at %s', async hash => {
    const { calls } = start(hash)
    expect(await screen.findByRole('button', { name: 'View The Creative Act' })).toBeVisible()
    expect(within(screen.getByRole('main')).getByRole('heading', { name: 'Browse the catalog' })).toBeVisible()
    expectRoute('Discover')
    expect(window.location.hash).toBe(hash)
    expect(calls.filter(call => call.key === 'GET /contents')).toEqual([
      { key: 'GET /contents', body: undefined, search: '' },
    ])
    expect(calls.every(call => call.key.startsWith('GET '))).toBe(true)
  })

  it('keeps community inline search and filters when switching to Discover and back', async () => {
    const { user, calls } = start()
    await screen.findByText('A creative life begins with noticing.')
    await user.click(screen.getByRole('button', { name: 'Books', exact: true }))
    const search = screen.getByRole('searchbox', { name: 'Search the catalog' })
    await user.type(search, 'nonexistent title')
    expect(await screen.findByText('Nothing here just yet.')).toBeVisible()
    expect(calls).toContainEqual({
      key: 'GET /contents', body: undefined, search: 'q=nonexistent+title&kind=book',
    })
    expect(calls).toContainEqual({ key: 'GET /posts', body: undefined, search: 'kind=book&sort=latest' })

    await user.click(screen.getByRole('button', { name: 'Discover', exact: true }))
    expect(screen.getByRole('searchbox', { name: 'Search the catalog' })).toHaveValue('nonexistent title')
    expect(screen.getByRole('button', { name: 'Books', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Community', exact: true }))
    expectRoute('Community')
    expect(screen.getByRole('searchbox', { name: 'Search the catalog' })).toHaveValue('nonexistent title')
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(await screen.findByRole('button', { name: 'View Interstellar' })).toBeVisible()
    expect(screen.getByRole('searchbox', { name: 'Search the catalog' })).toHaveValue('')
    expect(screen.getByRole('button', { name: 'All', exact: true })).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('Assistant hash and modal lifecycle', () => {
  it.each(['#/assistant', '#assistant'])('opens the existing dialog over a useful main view at %s', async hash => {
    const { user, calls } = start(hash)
    const dialog = await screen.findByRole('dialog', { name: 'Assistant' })
    expectTitle('Assistant')
    expect(within(dialog).getByLabelText('Message the assistant')).toBeDisabled()
    expect(within(dialog).getByText(/not configured in this server environment/)).toBeVisible()
    expect(within(dialog).getByRole('button', { name: 'Close dialog' })).toHaveFocus()
    expect(await within(screen.getByRole('main')).findByText('A creative life begins with noticing.')).toBeVisible()
    expect(window.location.hash).toBe(hash)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(window.location.hash).toBe('#/community')
    expectRoute('Community')
    expect(calls.every(call => call.key.startsWith('GET '))).toBe(true)
  })

  it('responds to hash changes without stranding an open dialog or empty main', async () => {
    start()
    await screen.findByText('A creative life begins with noticing.')
    changeHash('#/assistant')
    expect(screen.getByRole('dialog', { name: 'Assistant' })).toBeVisible()
    changeHash('#/discover')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expectRoute('Discover')
    expect(screen.getByRole('heading', { name: 'Browse the catalog' })).toBeVisible()
  })

  it('keeps sidebar Assistant modal-only, retains chat on close, and clears it on logout', async () => {
    const { user, calls } = start('#/library', { signedIn: true, entries: [entry], handlers: {
      'GET /assistant/status': () => Response.json({ configured: true, model: 'configured-model' }),
      'POST /assistant/chat': () => Response.json({ reply: 'Your private reading suggestion.' }),
    } })
    await screen.findByRole('button', { name: 'Edit The Creative Act' })
    const trigger = screen.getByRole('button', { name: 'Assistant', exact: true })
    await user.click(trigger)
    let dialog = screen.getByRole('dialog', { name: 'Assistant' })
    await user.type(within(dialog).getByLabelText('Message the assistant'), 'What should I revisit?')
    await user.click(within(dialog).getByRole('button', { name: 'Send message' }))
    expect(await within(dialog).findByText('Your private reading suggestion.')).toBeVisible()
    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
    expect(window.location.hash).toBe('#/library')
    expectRoute('My library')

    await user.click(trigger)
    dialog = screen.getByRole('dialog', { name: 'Assistant' })
    expect(within(dialog).getByText('What should I revisit?')).toBeVisible()
    expect(within(dialog).getByText('Your private reading suggestion.')).toBeVisible()
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument())
    expect(await screen.findByText('A little space of your own.')).toBeVisible()
    changeHash('#/assistant')
    dialog = screen.getByRole('dialog', { name: 'Assistant' })
    expect(within(dialog).queryByText('What should I revisit?')).not.toBeInTheDocument()
    expect(within(dialog).queryByText('Your private reading suggestion.')).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText('Message the assistant')).toBeDisabled()
    expect(calls.filter(call => call.key === 'POST /assistant/chat')).toEqual([
      { key: 'POST /assistant/chat', body: { message: 'What should I revisit?' }, search: '' },
    ])
  })
})

describe('existing routes and hash parsing', () => {
  it.each(['', '#/unknown', '#community'])('keeps the Community default at %s', async hash => {
    const { calls } = start(hash)
    expect(await screen.findByText('A creative life begins with noticing.')).toBeVisible()
    expectRoute('Community')
    expect(screen.getByRole('searchbox', { name: 'Search the catalog' })).toBeVisible()
    expect(window.location.hash).toBe(hash)
    expect(calls).toContainEqual({ key: 'GET /posts', body: undefined, search: 'sort=latest' })
    expect(calls.every(call => call.key.startsWith('GET '))).toBe(true)
  })

  it('still navigates to the private library and collection-derived Insights', async () => {
    const { user, calls } = start('', { signedIn: true, entries: [entry] })
    await screen.findByText('A creative life begins with noticing.')
    await user.click(screen.getByRole('button', { name: 'My library', exact: true }))
    expect(await screen.findByRole('button', { name: 'Edit The Creative Act' })).toBeVisible()
    expect(screen.getByText('42 / 432 pages')).toBeVisible()
    expectRoute('My library')
    expect(window.location.hash).toBe('#/library')
    await user.click(screen.getByRole('button', { name: 'Insights', exact: true }))
    expectRoute('Insights')
    expect(window.location.hash).toBe('#/insights')
    expect(screen.getByLabelText('Saved works')).toHaveTextContent('1')
    expect(screen.getByLabelText('In progress')).toHaveTextContent('1')
    expect(calls.every(call => call.key.startsWith('GET '))).toBe(true)
  })
})
