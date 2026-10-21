import { BookOpen, Clapperboard, Tv, Disc3, FileText, LayoutGrid } from 'lucide-react';

export const kinds = [
  { value: '', label: 'All', singular: 'Work', icon: LayoutGrid },
  { value: 'book', label: 'Books', singular: 'Book', icon: BookOpen, unit: 'pages' },
  { value: 'movie', label: 'Films', singular: 'Film', icon: Clapperboard, unit: 'minutes' },
  { value: 'series', label: 'Series', singular: 'Series', icon: Tv, unit: 'episodes' },
  { value: 'music', label: 'Music', singular: 'Music', icon: Disc3, unit: 'tracks' },
  { value: 'paper', label: 'Papers', singular: 'Paper', icon: FileText, unit: 'pages' },
];
export const statuses = [
  { value: 'planned', label: 'For later' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
];
export const kindInfo = value => kinds.find(kind => kind.value === value) || kinds[0];
export const statusLabel = value => statuses.find(status => status.value === value)?.label || value;
export const progressLabel = entry => `${entry.progress}${entry.content.total_units ? ` / ${entry.content.total_units}` : ''} ${entry.content.unit_label || 'units'}`;
export const matches = (content, kind, text = '') => (!kind || content?.kind === kind)
  && (!text || `${content?.title || ''} ${content?.creator || ''} ${content?.description || ''}`.toLowerCase().includes(text.toLowerCase()));

export function entryPayload(form) {
  return {
    status: form.status, progress: Number(form.progress),
    rating: form.rating === '' ? null : Number(form.rating), review: form.review.trim(),
  };
}

export function contentPayload(form) {
  return {
    title: form.title.trim(), creator: form.creator.trim(), kind: form.kind,
    description: form.description.trim(),
    year: form.year === '' ? null : Number(form.year),
    total_units: form.total_units === '' ? null : Number(form.total_units),
    unit_label: form.unit_label.trim() || kindInfo(form.kind).unit,
    tags: [...new Set(form.tags.split(',').map(tag => tag.trim()).filter(Boolean))],
  };
}

export function displayDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(date);
}
