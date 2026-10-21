import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import { book, entry, mockApi, user as account } from './test/fixtures';

const start = async options => {
  const mock = mockApi(options);
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText('A creative life begins with noticing.');
  return { ...mock, user };
};
const go = async (user, name) => user.click(screen.getByRole('button', { name, exact: true }));

describe('Reesatck public discovery and authentication', () => {
  it('filters the community by category and restores all posts', async () => {
    const { user, calls } = await start();
    await go(user, 'Films');
    await waitFor(() => expect(screen.queryByText('A creative life begins with noticing.')).not.toBeInTheDocument());
    expect(screen.getByText('Looking beyond the horizon.')).toBeVisible();
    expect(calls).toContainEqual({ key: 'GET /posts', body: undefined, search: 'kind=movie&sort=latest' });
    await go(user, 'All');
    expect(await screen.findByText('A creative life begins with noticing.')).toBeVisible();
  });

  it('requires authentication before saving and restores keyboard focus on Escape', async () => {
    const { user, calls } = await start();
    const save = screen.getByRole('button', { name: 'Save The Creative Act', exact: true });
    await user.click(save);
    const dialog = screen.getByRole('dialog', { name: 'Welcome back' });
    expect(within(dialog).getByLabelText('Username')).toHaveFocus();
    expect(calls.some(call => call.key === 'POST /collection')).toBe(false);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(save).toHaveFocus();
  });

  it('signs in with the real contract and saves only after an explicit authenticated action', async () => {
    const { user, calls } = await start();
    await user.click(screen.getByRole('button', { name: 'Save The Creative Act', exact: true }));
    const dialog = screen.getByRole('dialog');
    await user.type(within(dialog).getByLabelText('Username'), 'alex');
    await user.type(within(dialog).getByLabelText('Password'), 'a-secure-password');
    await user.click(within(dialog).getByRole('button', { name: 'Sign in', exact: true }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(calls).toContainEqual({ key: 'POST /auth/login', body: { username: 'alex', password: 'a-secure-password' }, search: '' });
    await user.click(await screen.findByRole('button', { name: 'Save The Creative Act', exact: true }));
    expect(await screen.findByRole('button', { name: 'Saved The Creative Act', exact: true })).toBeDisabled();
    expect(calls).toContainEqual({ key: 'POST /collection', body: { content_id: book.id, status: 'planned' }, search: '' });
  });

  it('keeps failed writes visible and never marks failed saves as saved', async () => {
    const { user, calls } = await start({ signedIn: true, fail: { 'POST /collection': 'This item could not be saved.' } });
    await user.click(screen.getByRole('button', { name: 'Save The Creative Act', exact: true }));
    expect(await screen.findByRole('alert')).toHaveTextContent('This item could not be saved.');
    expect(screen.getByRole('button', { name: 'Save The Creative Act', exact: true })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Saved The Creative Act', exact: true })).not.toBeInTheDocument();
    expect(calls.filter(call => call.key === 'POST /collection')).toHaveLength(1);
  });
});

describe('reflections and conversations', () => {
  it('publishes a linked reflection without completing or even saving the content', async () => {
    const { user, calls } = await start({ signedIn: true });
    await go(user, 'Write a reflection');
    const dialog = screen.getByRole('dialog', { name: 'A thought worth sharing' });
    await user.type(within(dialog).getByLabelText('Your reflection'), 'Only a few pages in, and already seeing things differently.');
    await user.selectOptions(within(dialog).getByLabelText('Link a work (optional)'), '1');
    expect(within(dialog).getByText(/Public ·/)).toBeVisible();
    await user.click(within(dialog).getByRole('button', { name: 'Publish reflection' }));
    expect(await screen.findByText('Only a few pages in, and already seeing things differently.')).toBeVisible();
    expect(calls).toContainEqual({ key: 'POST /posts', body: { body: 'Only a few pages in, and already seeing things differently.', content_id: 1 }, search: '' });
    expect(calls.some(call => call.key.startsWith('PATCH /collection') || call.key === 'POST /collection')).toBe(false);
  });

  it('uses server like counts, toggles likes and submits public comments', async () => {
    const { user, calls } = await start({ signedIn: true });
    const card = screen.getByText('A creative life begins with noticing.').closest('article');
    await user.click(within(card).getByRole('button', { name: 'Like reflection · 2 likes' }));
    await waitFor(() => expect(within(card).getByRole('button', { name: 'Unlike reflection · 3 likes' })).toHaveAttribute('aria-pressed', 'true'));
    await user.click(within(card).getByRole('button', { name: 'Unlike reflection · 3 likes' }));
    await waitFor(() => expect(within(card).getByRole('button', { name: 'Like reflection · 2 likes' })).toHaveAttribute('aria-pressed', 'false'));
    await user.click(within(card).getByRole('button', { name: 'Comments · 0 comments' }));
    await user.type(await within(card).findByLabelText('Your comment'), 'A lovely way to look at it.');
    await user.click(within(card).getByRole('button', { name: 'Post comment' }));
    expect(await within(card).findByText('A lovely way to look at it.')).toBeVisible();
    expect(calls.map(call => call.key)).toEqual(expect.arrayContaining(['PUT /posts/9/like', 'DELETE /posts/9/like']));
    expect(calls).toContainEqual({ key: 'POST /posts/9/comments', body: { body: 'A lovely way to look at it.' }, search: '' });
  });
});

describe('private library and session boundaries', () => {
  it('edits bounded progress, rating and private review, then clears the rating', async () => {
    const { user, calls } = await start({ signedIn: true, entries: [entry] });
    await go(user, 'My library');
    await user.click(await screen.findByRole('button', { name: 'Edit The Creative Act' }));
    let dialog = screen.getByRole('dialog');
    const progress = within(dialog).getByLabelText('Progress (pages)');
    expect(progress).toHaveAttribute('max', '432');
    fireEvent.change(progress, { target: { value: '433' } });
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(calls.some(call => call.key === 'PATCH /collection/8')).toBe(false);
    fireEvent.change(progress, { target: { value: '84' } });
    await user.selectOptions(within(dialog).getByLabelText('Rating'), '4');
    await user.type(within(dialog).getByLabelText('Private review'), 'Worth returning to.');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(calls).toContainEqual({ key: 'PATCH /collection/8', body: { status: 'in_progress', progress: 84, rating: 4, review: 'Worth returning to.' }, search: '' });
    expect(screen.getByText('84 / 432 pages')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Edit The Creative Act' }));
    dialog = screen.getByRole('dialog');
    await user.selectOptions(within(dialog).getByLabelText('Rating'), '');
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    await waitFor(() => expect(calls.filter(call => call.key === 'PATCH /collection/8')).toHaveLength(2));
    expect(calls.filter(call => call.key === 'PATCH /collection/8')[1].body.rating).toBeNull();
  });

  it('does not lose stored progress or review when an update is rejected', async () => {
    const { user } = await start({ signedIn: true, entries: [entry], fail: { 'PATCH /collection/8': 'Progress exceeds the total.' } });
    await go(user, 'My library');
    await user.click(await screen.findByRole('button', { name: 'Edit The Creative Act' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('Progress (pages)'), { target: { value: '99' } });
    await user.click(within(dialog).getByRole('button', { name: 'Save changes' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Progress exceeds the total.');
    expect(screen.getByText('42 / 432 pages')).toBeVisible();
    expect(within(dialog).getByRole('button', { name: 'Save changes' })).toBeEnabled();
  });

  it('requires confirmation before removing an entry', async () => {
    const { user, calls } = await start({ signedIn: true, entries: [entry] });
    await go(user, 'My library');
    await user.click(await screen.findByRole('button', { name: 'Edit The Creative Act' }));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove from library' }));
    expect(calls.some(call => call.key === 'DELETE /collection/8')).toBe(false);
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Remove permanently' }));
    expect(await screen.findByText('Your next discovery belongs here.')).toBeVisible();
    expect(calls.filter(call => call.key === 'DELETE /collection/8')).toHaveLength(1);
  });

  it('discards delayed private responses and chat state on logout', async () => {
    let resolveCollection;
    const delayed = new Promise(resolve => { resolveCollection = resolve; });
    const { user } = await start({ signedIn: true, handlers: { 'GET /collection': () => delayed } });
    await go(user, 'Assistant');
    expect(await screen.findByText(/server environment/)).toBeVisible();
    await user.keyboard('{Escape}');
    await go(user, 'Sign out');
    resolveCollection(Response.json([{ ...entry, review: 'A private note that must never return.' }]));
    await go(user, 'My library');
    expect(await screen.findByText('A little space of your own.')).toBeVisible();
    expect(screen.queryByText('A private note that must never return.')).not.toBeInTheDocument();
    expect(screen.queryByText(account.display_name, { exact: true })).not.toBeInTheDocument();
  });
});
