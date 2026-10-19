import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import { timeAgo } from '../lib/format'
import { Panel } from './Panel'

interface NewsPanelProps {
  ticker: string | null
  onSelectTicker: (ticker: string) => void
  className?: string
}

export function NewsPanel({ ticker, onSelectTicker, className }: NewsPanelProps) {
  const [filter, setFilter] = useState('')
  const query = useQuery({
    queryKey: ['news', ticker],
    queryFn: () => api.news(ticker ?? '', 15),
    enabled: ticker !== null,
    retry: false,
    refetchInterval: 5 * 60_000,
  })

  const title = ticker ? `NEWS · ${ticker}` : 'NEWS'
  const needle = filter.trim().toLowerCase()
  const items = query.data?.items ?? []
  const shown = needle
    ? items.filter((n) => `${n.title} ${n.publisher ?? ''}`.toLowerCase().includes(needle))
    : items

  return (
    <Panel
      title={title}
      className={className}
      actions={
        <input
          className="filter-input"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="filter"
          aria-label="Filter headlines by keyword"
          spellCheck={false}
        />
      }
    >
      {ticker === null && <p className="muted">Headlines from Yahoo Finance appear here.</p>}
      {query.isLoading && <p className="muted">Loading headlines...</p>}
      {query.isError && <p className="error">{query.error.message}</p>}
      {query.data && items.length === 0 && (
        <p className="muted">No recent headlines for {ticker}.</p>
      )}
      {query.data && items.length > 0 && shown.length === 0 && (
        <p className="muted">No headlines match &quot;{filter.trim()}&quot;.</p>
      )}
      {shown.length > 0 && (
        <ul className="news-list">
          {shown.map((n) => (
            <li key={n.id}>
              <a href={n.url} target="_blank" rel="noreferrer">
                {n.title}
              </a>
              <div className="news-meta muted">
                {n.publisher ?? 'Yahoo Finance'}
                {n.published_at ? ` · ${timeAgo(n.published_at)}` : ''}
                {n.related_tickers
                  .filter((t) => t !== ticker)
                  .slice(0, 4)
                  .map((t) => (
                    <button
                      key={t}
                      type="button"
                      className="chip"
                      onClick={() => onSelectTicker(t)}
                      title={`Open ${t}`}
                    >
                      {t}
                    </button>
                  ))}
              </div>
            </li>
          ))}
        </ul>
      )}
      {query.data && (
        <p className="muted source">
          source: {query.data.source}
          {needle ? ` · ${shown.length} of ${items.length} shown` : ''}
        </p>
      )}
    </Panel>
  )
}
