import { useMemo } from 'react'

import { KINDS, STATUS_LABEL } from '../lib/catalog.js'

export default function InsightsView({ app }) {
  const stats = useMemo(() => {
    const collection = app.collection
    const rated = collection.filter((entry) => entry.rating)
    const average = rated.length
      ? (rated.reduce((sum, entry) => sum + entry.rating, 0) / rated.length).toFixed(1)
      : null
    const countKind = (kind) => collection.filter((entry) => entry.content.kind === kind).length
    const countStatus = (status) => collection.filter((entry) => entry.status === status).length
    return {
      total: collection.length,
      average,
      byKind: KINDS.filter((item) => item.id !== 'all').map((item) => ({
        id: item.id,
        // KINDS carries the display label ("Books"); KIND_LABEL is the singular
        // used next to a single work. Insights counts works, so it reads plural.
        label: item.label,
        count: countKind(item.id),
      })),
      byStatus: Object.entries(STATUS_LABEL).map(([value, label]) => ({
        value,
        label,
        count: countStatus(value),
      })),
    }
  }, [app.collection])

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <span className="eyebrow">Insights</span>
          <h1>Your record, at a glance</h1>
          <p className="muted">Every number here comes from your own collection. Nothing is estimated.</p>
        </div>
      </header>

      <ul className="stat-grid">
        <li className="card stat" aria-label="Saved works">
          <span className="stat__value" aria-hidden="true">
            {stats.total}
          </span>
          <span className="muted small" aria-hidden="true">
            saved works
          </span>
        </li>
        <li className="card stat" aria-label="In progress">
          <span className="stat__value" aria-hidden="true">
            {stats.byStatus.find((item) => item.value === 'in_progress')?.count ?? 0}
          </span>
          <span className="muted small" aria-hidden="true">
            in progress
          </span>
        </li>
        <li className="card stat" aria-label="Completed works">
          <span className="stat__value" aria-hidden="true">
            {stats.byStatus.find((item) => item.value === 'completed')?.count ?? 0}
          </span>
          <span className="muted small" aria-hidden="true">
            completed works
          </span>
        </li>
        <li className="card stat" aria-label="Average rating">
          <span className="stat__value" aria-hidden="true">
            {stats.average ?? '—'}
          </span>
          <span className="muted small" aria-hidden="true">
            average rating
          </span>
        </li>
      </ul>

      <section className="card">
        <h2 className="rail-card__title">By type</h2>
        <ul className="bars">
          {stats.byKind.map((item) => (
            <li key={item.id}>
              <span className="bars__label">{`${item.label} · ${item.count}`}</span>
              <span className="bars__track">
                <span
                  className="bars__fill"
                  style={{ width: `${stats.total ? (item.count / stats.total) * 100 : 0}%` }}
                />
              </span>
              <span className="bars__value">{item.count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h2 className="rail-card__title">By status</h2>
        <ul className="bars">
          {stats.byStatus.map((item) => (
            <li key={item.value}>
              <span className="bars__label">{`${item.label} · ${item.count}`}</span>
              <span className="bars__track">
                <span
                  className="bars__fill"
                  style={{ width: `${stats.total ? (item.count / stats.total) * 100 : 0}%` }}
                />
              </span>
              <span className="bars__value">{item.count}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
