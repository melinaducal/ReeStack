import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { book, entry, mockApi } from './test/fixtures';

async function start(options) {
  const mock = mockApi(options);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('A creative life begins with noticing.');
  return { ...mock, user };
}

describe('catalog, search and honest unavailable states', () => {
  it.each(['book', 'movie', 'series', 'music', 'paper'])('manually creates and saves %s content', async kind => {
    const { user, calls } = await start({ signedIn: true, handlers: {
      'POST /contents': ({ body }) => Response.json({ ...book, ...body, id: 30, cover_key: '' }, { status: 201 }),
    } });
    await user.click(screen.getByRole('button', { name: 'Add content' }));
    const dialog = screen.getByRole('dialog', { name: 'Add something worth discovering' });
    await user.type(within(dialog).getByLabelText('Title'), 'A new discovery');
    await user.type(within(dialog).getByLabelText('Creator'), 'A. Author');
    await user.selectOptions(within(dialog).getByLabelText('Type'), kind);
    await user.click(within(dialog).getByRole('button', { name: 'Add to catalog' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(calls.find(call => call.key === 'POST /contents').body).toMatchObject({ title: 'A new discovery', creator: 'A. Author', kind });
    expect(calls).toContainEqual({ key: 'POST /collection', body: { content_id: 30, status: 'planned' }, search: '' });
  });

  it('retries saving a newly created work without creating it twice', async () => {
    const { user, calls } = await start({ signedIn: true, handlers: {
      'POST /contents': () => Response.json({ ...book, id: 30 }, { status: 201 }),
    }, fail: { 'POST /collection': 'Save is temporarily unavailable.' } });
    await user.click(screen.getByRole('button', { name: 'Add content' }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Title'), 'A new discovery');
    await user.type(within(dialog).getByLabelText('Creator'), 'A. Author');
    await user.click(within(dialog).getByRole('button', { name: 'Add to catalog' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Save is temporarily unavailable.');
    expect(within(dialog).getByText(/already in the public catalog/)).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Retry saving' }));
    await waitFor(() => expect(calls.filter(call => call.key === 'POST /collection')).toHaveLength(2));
    expect(calls.filter(call => call.key === 'POST /contents')).toHaveLength(1);
  });

  it('uses global search for discovery and clears empty results', async () => {
    const { user, calls } = await start();
    const search = screen.getByRole('searchbox', { name: 'Search the catalog' });
    await user.type(search, 'nonexistent title{Enter}');
    expect(await screen.findByText('Nothing here just yet.')).toBeVisible();
    expect(calls.some(call => call.key === 'GET /contents' && call.search.includes('q=nonexistent+title'))).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));
    expect(await screen.findByRole('button', { name: 'View The Creative Act' })).toBeVisible();
    expect(search).toHaveValue('');
  });

  it('shows labeled read-only preview on public API failure and never sends writes', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    expect(await screen.findByText('Preview mode · Start the API to save your activity')).toBeVisible();
    expect(screen.getAllByText('Sample reflection').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Write a reflection' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Save The Creative Act', exact: true })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reconnect' })).toBeEnabled();
    expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  });

  it('does not substitute samples for a failed private library request', async () => {
    const { user } = await start({ signedIn: true, fail: { 'GET /collection': 'Your library could not be loaded.' } });
    await user.click(screen.getByRole('button', { name: 'My library', exact: true }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Your library could not be loaded.');
    expect(screen.getByRole('button', { name: 'Retry library' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Edit The Creative Act' })).not.toBeInTheDocument();
  });

  it('reports insights only from the signed-in collection', async () => {
    const { user } = await start({ signedIn: true, entries: [{ ...entry, rating: 4 }] });
    await user.click(screen.getByRole('button', { name: 'Insights', exact: true }));
    expect(await screen.findByLabelText('Saved works')).toHaveTextContent('1');
    expect(screen.getByLabelText('In progress')).toHaveTextContent('1');
    expect(screen.getByLabelText('Completed works')).toHaveTextContent('0');
    expect(screen.getByLabelText('Average rating')).toHaveTextContent('4.0');
    expect(screen.getByText('Books · 1')).toBeVisible();
    expect(screen.getByText('Films · 0')).toBeVisible();
  });
});

describe('assistant and form failure boundaries', () => {
  it('shows a real assistant failure, retries the exact message and erases chat on logout', async () => {
    let unavailable = true;
    const { user, calls } = await start({ signedIn: true, handlers: {
      'GET /assistant/status': () => Response.json({ configured: true, model: 'configured-model' }),
      'POST /assistant/chat': () => unavailable
        ? Response.json({ detail: 'The assistant is unavailable. Please try again.' }, { status: 503 })
        : Response.json({ reply: 'Your saved works include The Creative Act.' }),
    } });
    await user.click(screen.getByRole('button', { name: 'Assistant', exact: true }));
    let dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText(/collection and posts.*configured LLM/)).toBeVisible();
    await user.type(await within(dialog).findByLabelText('Message the assistant'), 'What am I reading?');
    await user.click(within(dialog).getByRole('button', { name: 'Send message' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('The assistant is unavailable.');
    expect(within(dialog).queryByText('Your saved works include The Creative Act.')).not.toBeInTheDocument();
    unavailable = false;
    await user.click(within(dialog).getByRole('button', { name: 'Retry message' }));
    expect(await within(dialog).findByText('Your saved works include The Creative Act.')).toBeVisible();
    expect(calls.filter(call => call.key === 'POST /assistant/chat').map(call => call.body)).toEqual([{ message: 'What am I reading?' }, { message: 'What am I reading?' }]);
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'Sign out', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Assistant', exact: true }));
    dialog = screen.getByRole('dialog');
    expect(within(dialog).queryByText('Your saved works include The Creative Act.')).not.toBeInTheDocument();
    expect(within(dialog).queryByText('What am I reading?')).not.toBeInTheDocument();
  });

  it('shows auth errors, rejects blank input and traps keyboard focus', async () => {
    const { user, calls } = await start({ fail: { 'POST /auth/login': 'Invalid username or password.' } });
    await user.click(screen.getByRole('button', { name: 'Sign in', exact: true }));
    const dialog = screen.getByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Sign in', exact: true }));
    expect(calls.some(call => call.key === 'POST /auth/login')).toBe(false);
    await user.type(within(dialog).getByLabelText('Username'), 'alex');
    await user.type(within(dialog).getByLabelText('Password'), 'incorrect-password');
    await user.click(within(dialog).getByRole('button', { name: 'Sign in', exact: true }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Invalid username or password.');
    const close = within(dialog).getByRole('button', { name: 'Close dialog' });
    close.focus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('keeps like and comment counters unchanged when writes are rejected', async () => {
    const { user, calls } = await start({ signedIn: true, fail: {
      'PUT /posts/9/like': 'The like could not be saved.',
      'POST /posts/9/comments': 'The comment could not be published.',
    } });
    const card = screen.getByText('A creative life begins with noticing.').closest('article');
    await user.click(within(card).getByRole('button', { name: 'Like reflection · 2 likes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The like could not be saved.');
    expect(within(card).getByRole('button', { name: 'Like reflection · 2 likes' })).toHaveAttribute('aria-pressed', 'false');
    await user.click(within(card).getByRole('button', { name: 'Comments · 0 comments' }));
    await user.type(await within(card).findByLabelText('Your comment'), 'An unsaved comment.');
    await user.click(within(card).getByRole('button', { name: 'Post comment' }));
    expect(await within(card).findByRole('alert')).toHaveTextContent('The comment could not be published.');
    expect(within(card).getByRole('button', { name: 'Comments · 0 comments' })).toBeVisible();
    expect(within(card).getByLabelText('Your comment')).toHaveValue('An unsaved comment.');
    expect(calls.filter(call => call.key === 'POST /posts/9/comments')).toHaveLength(1);
  });
});
