export const TYPE_LABELS = {
  book: 'Libro',
  movie: 'Película',
  series: 'Serie',
  music: 'Música',
  paper: 'Paper',
  post: 'Publicación'
}

export function getInitials(name) {
  if (!name) return 'U'
  return name
    .split(' ')
    .map(part => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}
