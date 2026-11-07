import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clampRating,
  ratingFromKey,
  ratingFromPointer
} from './starRating.js'

const PAGE = { min: 1, max: 5, step: 0.5 }

test('clampRating snaps to half steps inside the 1-5 page range', () => {
  assert.equal(clampRating(0, PAGE), 1)
  assert.equal(clampRating(0.49, PAGE), 1)
  assert.equal(clampRating(1, PAGE), 1)
  assert.equal(clampRating(1.24, PAGE), 1)
  assert.equal(clampRating(1.25, PAGE), 1.5)
  assert.equal(clampRating(2.5, PAGE), 2.5)
  assert.equal(clampRating(4.5, PAGE), 4.5)
  assert.equal(clampRating(4.74, PAGE), 4.5)
  assert.equal(clampRating(4.75, PAGE), 5)
  assert.equal(clampRating(5, PAGE), 5)
  assert.equal(clampRating(9, PAGE), 5)
})

test('clampRating supports a 0.5 minimum for reusable use', () => {
  assert.equal(clampRating(0, { min: 0.5, max: 5, step: 0.5 }), 0.5)
  assert.equal(clampRating(0.3, { min: 0.5, max: 5, step: 0.5 }), 0.5)
  assert.equal(clampRating(0.75, { min: 0.5, max: 5, step: 0.5 }), 1)
  assert.equal(clampRating(5, { min: 0.5, max: 5, step: 0.5 }), 5)
})

test('ratingFromPointer maps star halves to values', () => {
  const rect = { left: 0, width: 100 }

  assert.equal(ratingFromPointer(0, rect, PAGE), 1)
  assert.equal(ratingFromPointer(10, rect, PAGE), 1)
  assert.equal(ratingFromPointer(30, rect, PAGE), 1.5)
  assert.equal(ratingFromPointer(50, rect, PAGE), 2.5)
  assert.equal(ratingFromPointer(70, rect, PAGE), 3.5)
  assert.equal(ratingFromPointer(90, rect, PAGE), 4.5)
  assert.equal(ratingFromPointer(100, rect, PAGE), 5)
  assert.equal(ratingFromPointer(50, null, PAGE), null)
  assert.equal(ratingFromPointer(50, { left: 0, width: 0 }, PAGE), null)
})

test('ratingFromPointer ignores the row offset', () => {
  const rect = { left: 200, width: 200 }
  assert.equal(ratingFromPointer(200, rect, PAGE), 1)
  assert.equal(ratingFromPointer(300, rect, PAGE), 2.5)
  assert.equal(ratingFromPointer(400, rect, PAGE), 5)
})

test('keyboard increases and decreases by half a star', () => {
  assert.equal(ratingFromKey('ArrowRight', null, PAGE), 1)
  assert.equal(ratingFromKey('ArrowRight', 1, PAGE), 1.5)
  assert.equal(ratingFromKey('ArrowRight', 4.5, PAGE), 5)
  assert.equal(ratingFromKey('ArrowUp', 2.5, PAGE), 3)
  assert.equal(ratingFromKey('ArrowLeft', 1.5, PAGE), 1)
  assert.equal(ratingFromKey('ArrowLeft', 1, PAGE), 1)
  assert.equal(ratingFromKey('ArrowDown', 3, PAGE), 2.5)
})

test('keyboard supports Home, End and clearing', () => {
  assert.equal(ratingFromKey('Home', 4, PAGE), 1)
  assert.equal(ratingFromKey('End', 2, PAGE), 5)
  assert.equal(ratingFromKey('Delete', 3, PAGE), null)
  assert.equal(ratingFromKey('Backspace', 3, PAGE), null)
  assert.equal(ratingFromKey('0', 3, PAGE), null)
  assert.equal(ratingFromKey('Delete', 3, { ...PAGE, allowClear: false }), 3)
  assert.equal(ratingFromKey('Enter', 3, PAGE), undefined)
})

test('required selections are representable', () => {
  const rect = { left: 0, width: 200 }
  // 0.5 stars only exists in the reusable 0.5 minimum mode.
  assert.equal(ratingFromPointer(10, rect, { min: 0.5, max: 5, step: 0.5 }), 0.5)
  assert.equal(ratingFromPointer(100, rect, PAGE), 2.5)
  assert.equal(ratingFromPointer(180, rect, PAGE), 4.5)
  assert.equal(ratingFromPointer(200, rect, PAGE), 5)
})
