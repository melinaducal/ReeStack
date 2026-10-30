const MESSAGE_TRANSLATIONS = [
  [/String should have at most (\d+) characters/i, (m) => `Máximo ${m[1]} caracteres`],
  [/String should have at least (\d+) characters/i, (m) => `Mínimo ${m[1]} caracteres`],
  [/valid email address/i, () => 'Correo electrónico inválido'],
  [/valid date/i, () => 'Fecha inválida'],
  [/should be a valid date/i, () => 'Fecha inválida'],
  [/Field required/i, () => 'Campo obligatorio'],
]

function translate(message) {
  for (const [pattern, build] of MESSAGE_TRANSLATIONS) {
    const match = message.match(pattern)
    if (match) return build(match)
  }
  return message
}

export function getErrorMessage(error, fallback = 'Ocurrió un error inesperado') {
  const detail = error?.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item
        if (item && typeof item.msg === 'string') {
          const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null
          const text = translate(item.msg)
          return field ? `${field}: ${text}` : text
        }
        return null
      })
      .filter(Boolean)

    if (messages.length > 0) return messages.join('. ')
  }

  if (detail && typeof detail === 'object' && typeof detail.msg === 'string') {
    return detail.msg
  }

  return fallback
}
