import { describe, expect, it } from 'vitest'
import { KINDS, KIND_LABEL, PREVIEW_CONTENTS, PREVIEW_POSTS } from '../lib/catalog.js'

describe('catalog metadata', () => {
  it('exposes every supported kind, including the all filter', () => {
    const ids = KINDS.map((kind) => kind.id)
    expect(ids).toEqual(['all', 'book', 'movie', 'series', 'music', 'paper'])
  })

  it('labels every kind that the API can return', () => {
    for (const kind of ['book', 'movie', 'series', 'music', 'paper']) {
      expect(KIND_LABEL[kind]).toBeTruthy()
    }
  })

  it('gives every kind an icon name that exists in the shared icon map', () => {
    const icons = ['Sparkles', 'BookOpen', 'Film', 'Tv', 'Music', 'FlaskConical']
    for (const kind of KINDS) {
      expect(icons).toContain(kind.icon)
    }
  })

  it('marks preview content as demo so it is never mistaken for real activity', () => {
    expect(PREVIEW_CONTENTS.length).toBeGreaterThan(0)
    for (const content of PREVIEW_CONTENTS) {
      expect(content.is_demo).toBe(true)
      expect(content.title).toBeTruthy()
    }
  })

  it('marks preview posts as demo and gives them coherent author and content shapes', () => {
    expect(PREVIEW_POSTS.length).toBeGreaterThan(0)
    for (const post of PREVIEW_POSTS) {
      expect(post.is_demo).toBe(true)
      expect(post.author?.display_name).toBeTruthy()
      expect(typeof post.body).toBe('string')
      expect(Array.isArray(post.comments)).toBe(true)
    }
  })

  it('gives preview content unique ids so React keys stay stable', () => {
    const ids = PREVIEW_CONTENTS.map((content) => content.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
