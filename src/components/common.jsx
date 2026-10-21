import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Bookmark, Check, LoaderCircle, SearchX, X } from 'lucide-react';
import { kindInfo, kinds } from '../domain';
import { useAction } from '../hooks';

export function Modal({ title, subtitle, children, onClose, wide = false }) {
  const titleId = useId();
  const ref = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement;
    const panel = ref.current;
    const overflow = document.body.style.overflow;
    const app = document.getElementById('app-shell');
    if (app) app.inert = true;
    document.body.style.overflow = 'hidden';
    const controls = () => [...panel.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href], [tabindex="0"]')];
    (panel.querySelector('[data-autofocus]') || controls()[0] || panel).focus();
    const onKey = event => {
      if (event.key === 'Escape') { event.preventDefault(); close.current(); }
      if (event.key !== 'Tab') return;
      const items = controls();
      const first = items[0];
      const last = items.at(-1);
      if (!items.length) { event.preventDefault(); panel.focus(); }
      else if (event.shiftKey && (document.activeElement === first || !panel.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !panel.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      if (app) app.inert = false;
      if (previous?.isConnected) previous.focus();
      else document.getElementById('main-content')?.focus();
    };
  }, []);
  return createPortal(<div className="modal-backdrop" onClick={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={ref} className={`modal ${wide ? 'modal--wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
      <header className="modal-header">
        <div><span className="eyebrow">A LITTLE MORE CURIOUS</span><h2 id={titleId}>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>
        <button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20} /></button>
      </header>
      {children}
    </section>
  </div>, document.body);
}

export function ErrorMessage({ message }) {
  return message ? <p role="alert" className="inline-error"><AlertCircle size={17} aria-hidden="true" /><span>{message}</span></p> : null;
}

export function ErrorPanel({ message, onRetry, label = 'Try again' }) {
  return <div className="error-panel"><ErrorMessage message={message} /><button className="button secondary" onClick={onRetry}>{label}</button></div>;
}

export function Loading({ label = 'Loading your next discovery…' }) {
  return <div role="status" className="loading-state"><span className="sr-only">{label}</span>
    {[1, 2, 3].map(item => <div className="skeleton-card" key={item} aria-hidden="true"><i /><div><i /><i /><i /></div></div>)}
  </div>;
}

export function EmptyState({ title = 'Nothing here just yet.', children, action, onAction }) {
  return <div className="empty-state"><span className="empty-icon"><SearchX size={28} /></span><h2>{title}</h2><p>{children}</p>{action && <button className="button secondary" onClick={onAction}>{action}</button>}</div>;
}

export function KindChips({ value, onChange }) {
  return <div className="kind-chips" aria-label="Filter by content type" role="group">
    {kinds.map(({ value: kind, label, icon: Icon }) => <button key={kind} className={`chip ${value === kind ? 'active' : ''}`} aria-pressed={value === kind} onClick={() => onChange(kind)}><Icon size={16} aria-hidden="true" />{label}</button>)}
  </div>;
}

export function KindLabel({ kind }) {
  const { icon: Icon, singular } = kindInfo(kind);
  return <span className={`kind-label kind-label--${kind}`}><Icon size={13} aria-hidden="true" />{singular}</span>;
}

export function Avatar({ user, small = false }) {
  const initials = (user?.display_name || user?.username || 'You').split(/\s+/).slice(0, 2).map(name => name[0]).join('').toUpperCase();
  const color = /^#[0-9a-f]{6}$/i.test(user?.avatar_color) ? user.avatar_color : '#6e816a';
  return <span className={`avatar ${small ? 'avatar--small' : ''}`} style={{ backgroundColor: color }} aria-hidden="true">{initials}</span>;
}

export function SaveButton({ content, collection, authorize, preview, notify, compact = false }) {
  const action = useAction();
  const saved = collection.entries.some(entry => entry.content.id === content.id);
  const save = () => {
    if (!authorize()) return;
    action.run(async () => {
      await collection.save(content);
      notify(`${content.title} saved to your private library.`);
    }, message => notify(message, 'error'));
  };
  const Icon = action.pending ? LoaderCircle : saved ? Check : Bookmark;
  return <button className={`save-button ${compact ? 'save-button--compact' : ''}`} onClick={save} disabled={preview || saved || action.pending}
    aria-label={`${saved ? 'Saved' : 'Save'} ${content.title}`} title={preview ? 'Read-only preview. Start the API to save.' : undefined}>
    <Icon size={17} className={action.pending ? 'spinning' : ''} aria-hidden="true" /><span>{action.pending ? 'Saving…' : saved ? 'Saved' : 'Save'}</span>
  </button>;
}
