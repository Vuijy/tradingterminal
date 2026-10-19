import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import { formatCompactNumber, formatNumber, formatSigned } from '../lib/format'
import { Panel } from './Panel'

interface QuotePanelProps {
  ticker: string | null
}

export function QuotePanel({ ticker }: QuotePanelProps) {
  const query = useQuery({
    queryKey: ['quote', ticker],
    queryFn: () => api.quote(ticker ?? ''),
    enabled: ticker !== null,
    retry: false,
    refetchInterval: 60_000,
  })

  const title = ticker ? `QUOTE · ${ticker}` : 'QUOTE'
  const change = query.data?.change ?? 0
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : ''
  const q = query.data

  return (
    <Panel title={title}>
      {ticker === null && <p className="muted">No instrument selected.</p>}
      {query.isLoading && <p className="muted">Loading...</p>}
      {query.isError && <p className="error">{query.error.message}</p>}
      {q && (
        <>
          <div className={`price ${direction}`}>
            {formatNumber(q.price)} <span className="muted currency">{q.currency ?? ''}</span>
          </div>
          <div className={direction}>
            {formatSigned(q.change)} ({formatSigned(q.change_pct, 2, '%')})
          </div>
          <dl className="kv">
            <dt>Prev close</dt>
            <dd>{formatNumber(q.previous_close)}</dd>
            <dt>Volume</dt>
            <dd>{formatCompactNumber(q.volume, 2)}</dd>
            <dt>Market cap</dt>
            <dd>{formatCompactNumber(q.market_cap, 2)}</dd>
            <dt>As of</dt>
            <dd>{q.as_of ? new Date(q.as_of).toLocaleString() : '—'}</dd>
          </dl>
          <RangeBar label="Day" low={q.day_low} high={q.day_high} value={q.price} />
          <RangeBar label="52 week" low={q.year_low} high={q.year_high} value={q.price} />
          <p className="muted source">source: {q.source}</p>
        </>
      )}
    </Panel>
  )
}

function RangeBar({
  label,
  low,
  high,
  value,
}: {
  label: string
  low: number | null
  high: number | null
  value: number | null
}) {
  if (low == null || high == null || value == null || high <= low) return null
  const pct = Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100))
  return (
    <div className="rng">
      <div className="rng-head">
        <span className="muted">{label}</span>
        <span>
          {formatNumber(low)} <span className="muted">to</span> {formatNumber(high)}
        </span>
      </div>
      <div className="rng-track" title={`${pct.toFixed(0)}% of the ${label.toLowerCase()} range`}>
        <div className="rng-dot" style={{ left: `${pct}%` }} />
      </div>
    </div>
  )
}
