/**
 * Presentation metadata keyed by the same cover_key values the backend seed uses.
 * These are display hints only; the API response stays the source of truth.
 */

import { BookOpen, Film, FlaskConical, Music, Sparkles, Tv } from 'lucide-react'

/**
 * The single icon map for content kinds. It lives beside KINDS so the two can
 * never drift: a kind whose icon is missing would render an undefined
 * component and crash the view.
 */
export const KIND_ICON = { Sparkles, BookOpen, Film, Tv, Music, FlaskConical }

/** Resolves a kind's icon name to its component, falling back to Sparkles. */
export function kindIcon(name) {
  return KIND_ICON[name] || Sparkles
}

export const KINDS = [
  { id: 'all', label: 'All', icon: 'Sparkles' },
  { id: 'book', label: 'Books', icon: 'BookOpen' },
  { id: 'movie', label: 'Films', icon: 'Film' },
  { id: 'series', label: 'Series', icon: 'Tv' },
  { id: 'music', label: 'Music', icon: 'Music' },
  { id: 'paper', label: 'Papers', icon: 'FlaskConical' },
]

export const KIND_LABEL = {
  book: 'Book',
  movie: 'Film',
  series: 'Series',
  music: 'Music',
  paper: 'Paper',
}

export const STATUS_LABEL = {
  planned: 'Planned',
  in_progress: 'In progress',
  completed: 'Finished',
}

export const UNIT_DEFAULT = {
  book: 'pages',
  movie: 'minutes',
  series: 'episodes',
  music: 'tracks',
  paper: 'pages',
}

const COVER_STYLE = {
  'creative-act': { bg: '#f0e7d8', ink: '#8a5a3b', accent: '#253d32' },
  interstellar: { bg: '#12233a', ink: '#dbe7f3', accent: '#7fa8c9' },
  'kind-of-blue': { bg: '#17324a', ink: '#e6eef5', accent: '#5b8fb0' },
  attention: { bg: '#f4f1ea', ink: '#2c2c2c', accent: '#b06b4a' },
  severance: { bg: '#1d2b2a', ink: '#d9e6e2', accent: '#7fae9f' },
  'midnight-library': { bg: '#2a2550', ink: '#e9e6ff', accent: '#c9b6ff' },
  cosmos: { bg: '#0f1b33', ink: '#e3ecff', accent: '#8fb7ff' },
  dune: { bg: '#c98a4b', ink: '#3a2412', accent: '#7a4a1f' },
  'in-rainbows': { bg: '#59473a', ink: '#f4e6d7', accent: '#e0a267' },
  'slow-horses': { bg: '#33363a', ink: '#e4e8eb', accent: '#b06b4a' },
  default: { bg: '#e6e9e2', ink: '#253d32', accent: '#5b7f68' },
}

export function coverStyle(coverKey) {
  return COVER_STYLE[coverKey] || COVER_STYLE.default
}

export function initials(text) {
  if (!text) return '··'
  return text
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

/**
 * Read-only sample data, used ONLY when the API cannot be reached.
 * It is always labelled in the UI as preview content. Every entry carries
 * `is_demo: true` so no view can mistake sample data for real activity.
 */
export const PREVIEW_CONTENTS = [
  { id: -1, title: 'The Creative Act', creator: 'Rick Rubin', kind: 'book', year: 2023, cover_key: 'creative-act', total_units: 432, unit_label: 'pages', tags: ['creativity'], is_demo: true },
  { id: -2, title: 'Interstellar', creator: 'Christopher Nolan', kind: 'movie', year: 2014, cover_key: 'interstellar', total_units: 169, unit_label: 'minutes', tags: ['science'], is_demo: true },
  { id: -3, title: 'Kind of Blue', creator: 'Miles Davis', kind: 'music', year: 1959, cover_key: 'kind-of-blue', total_units: 5, unit_label: 'tracks', tags: ['jazz'], is_demo: true },
  { id: -4, title: 'Attention Is All You Need', creator: 'Vaswani et al.', kind: 'paper', year: 2017, cover_key: 'attention', total_units: 11, unit_label: 'pages', tags: ['machine learning'], is_demo: true },
  { id: -5, title: 'Severance', creator: 'Dan Erickson', kind: 'series', year: 2022, cover_key: 'severance', total_units: 19, unit_label: 'episodes', tags: ['mystery'], is_demo: true },
  { id: -6, title: 'The Midnight Library', creator: 'Matt Haig', kind: 'book', year: 2020, cover_key: 'midnight-library', total_units: 304, unit_label: 'pages', tags: ['fiction'], is_demo: true },
  { id: -7, title: 'Cosmos', creator: 'Carl Sagan', kind: 'book', year: 1980, cover_key: 'cosmos', total_units: 365, unit_label: 'pages', tags: ['science'], is_demo: true },
  { id: -8, title: 'Dune', creator: 'Frank Herbert', kind: 'book', year: 1965, cover_key: 'dune', total_units: 688, unit_label: 'pages', tags: ['science fiction'], is_demo: true },
  { id: -9, title: 'In Rainbows', creator: 'Radiohead', kind: 'music', year: 2007, cover_key: 'in-rainbows', total_units: 10, unit_label: 'tracks', tags: ['alternative'], is_demo: true },
  { id: -10, title: 'Slow Horses', creator: 'Will Smith', kind: 'series', year: 2022, cover_key: 'slow-horses', total_units: 24, unit_label: 'episodes', tags: ['spy'], is_demo: true },
]

export const PREVIEW_POSTS = [
  {
    id: -1,
    author: { id: -1, username: 'demo_mara', display_name: 'Mara K.', avatar_color: '#8a9e8f', bio: 'Example community member.' },
    body: 'Halfway through Cosmos and I keep underlining whole paragraphs. Sagan makes the scale of the universe feel intimate instead of frightening.',
    content: PREVIEW_CONTENTS[0],
    rating: 5,
    created_at: '2026-10-18T09:12:00+00:00',
    like_count: 12,
    comment_count: 2,
    liked: false,
    comments: [
      { id: -1, author: { id: -2, username: 'demo_jon', display_name: 'Jon Bell.', avatar_color: '#7a8fa8' }, body: 'The chapter on attention changed how I read. Worth sitting with slowly.', created_at: '2026-10-18T11:02:00+00:00', is_demo: true },
      { id: -2, author: { id: -1, username: 'demo_mara', display_name: 'Mara K.', avatar_color: '#8a9e8f' }, body: 'Adding this to my winter list.', created_at: '2026-10-18T13:25:00+00:00', is_demo: true },
    ],
    is_demo: true,
  },
  {
    id: -2,
    author: { id: -2, username: 'demo_jon', display_name: 'Jon Bell.', avatar_color: '#7a8fa8', bio: 'Example community member.' },
    body: 'Started Severance on the train and now I am suspicious of every elevator. The premise gets more uncomfortable the more ordinary it looks.',
    content: PREVIEW_CONTENTS[4],
    rating: null,
    created_at: '2026-10-17T20:40:00+00:00',
    like_count: 8,
    comment_count: 3,
    liked: false,
    comments: [
      { id: -3, author: { id: -1, username: 'demo_mara', display_name: 'Mara K.', avatar_color: '#8a9e8f' }, body: 'The elevator thing is exactly right.', created_at: '2026-10-17T21:10:00+00:00', is_demo: true },
    ],
    is_demo: true,
  },
]
