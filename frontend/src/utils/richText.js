import DOMPurify from 'dompurify'

export const POST_TYPE = 'post'

// Rich text is only interpreted for social posts. The type is explicit in the
// data model; it is never inferred from the text or the HTML.
const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'del',
  'a', 'span', 'ul', 'ol', 'li', 'blockquote'
]
const ALLOWED_ATTR = ['href', 'target', 'rel', 'style']

export function isPost(item) {
  return item?.type === POST_TYPE
}

export function sanitizeRichText(value) {
  if (!value) return ''
  return DOMPurify.sanitize(value, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false
  })
}
