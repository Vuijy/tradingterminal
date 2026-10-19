import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import type { MacroSummary } from '../api/types'
import {
  formatCompactNumber,
  formatNumber,
  formatSigned,
  isoDaysAgo,
  signClass,
} from '../lib/format'
import { LineChart } from './LineChart'
import { Panel } from './Panel'

interface Span {
  label: string
  days: number | null
}

const SPANS: Span[] = [
  { label: '1Y', days: 365 },
  { label: '5Y', days: 5 * 365 },
  { label: 'MAX', days: null },
]
const FIFTEEN_MIN = 15 * 60_000
const ONE_HOUR = 60 * 60_000

interface MacroPanelProps {
  className?: string
}

export function MacroPanel({ className }: MacroPanelProps) {
  const [selected, setSelected] = useState('DGS10')
  const [span, setSpan] = useState<Span>(SPANS[1])

  const dashboard = useQuery({
    queryKey: ['macro', 'dashboard'],
    queryFn: api.macroDashboard,
    staleTime: FIFTEEN_MIN,
    refetchInterval: FIFTEEN_MIN,
    retry: false,
  })

  const start = span.days ? isoDaysAgo(span.days) : undefined
  const series = useQuery({
    queryKey: ['macro', 'series', selected, start ?? 'all'],
    queryFn: () => api.macroSeries(selected, start),
    staleTime: ONE_HOUR,
    retry: false,
  })

  const selectedMeta = dashboard.data?.find((s) => s.series_id === selected)
  const points = series.data?.observations.map((o) => ({ time: o.date, value: o.value })) ?? []
  const latest = points.at(-1)

  return (
    <Panel
      title="MACRO"
      className={className}
      actions={
        <div className="range-bar" role="tablist" aria-label="Macro chart span">
          {SPANS.map((s) => (
            <button
              key={s.label}
              type="button"
              className={s.label === span.label ? 'active' : ''}
              onClick={() => setSpan(s)}
            >
              {s.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="macro-chart-head">
        <span className="legend-key">
          {selectedMeta?.title ?? selected}
          {selectedMeta?.unit ? ` (${selectedMeta.unit})` : ''}
        </span>
        <span className="muted small">
          {series.isFetching
            ? 'updating...'
            : latest
              ? `${formatNumber(latest.value, precisionFor(selectedMeta))} on ${latest.time}`
              : selected}
        </span>
      </div>
      {series.isError && <p className="error">{series.error.message}</p>}
      <LineChart data={points} height={170} precision={precisionFor(selectedMeta)} />

      {dashboard.isLoading && <p className="muted">Loading FRED series...</p>}
      {dashboard.isError && <p className="error">{dashboard.error.message}</p>}
      {dashboard.data && (
        <div className="tile-grid">
          {dashboard.data.map((s) => (
            <Tile
              key={s.series_id}
              s={s}
              active={s.series_id === selected}
              onClick={() => setSelected(s.series_id)}
            />
          ))}
        </div>
      )}
      <p className="muted source">source: FRED (St. Louis Fed)</p>
    </Panel>
  )
}

function Tile({ s, active, onClick }: { s: MacroSummary; active: boolean; onClick: () => void }) {
  const digits = precisionFor(s)
  const compact = s.latest_value != null && Math.abs(s.latest_value) >= 10_000
  const value =
    s.latest_value == null
      ? '—'
      : compact
        ? formatCompactNumber(s.latest_value, 1)
        : formatNumber(s.latest_value, digits)
  return (
    <button type="button" className={`tile ${active ? 'active' : ''}`} onClick={onClick}>
      <div className="tile-title">{s.title}</div>
      <div className="tile-value">
        {value}
        {s.unit === '%' ? <span className="tile-unit">%</span> : null}
      </div>
      <div className="tile-meta">
        <span className={signClass(s.change)} title="Change vs previous observation">
          {compact ? formatSigned(s.change_pct, 2, '%') : formatSigned(s.change, digits)}
        </span>
        {s.yoy_pct != null && s.unit !== '%' && (
          <span className={signClass(s.yoy_pct)} title="Year over year">
            YoY {formatSigned(s.yoy_pct, 1, '%')}
          </span>
        )}
      </div>
      <div className="tile-date muted">{s.latest_date ?? ''}</div>
    </button>
  )
}

function precisionFor(s: MacroSummary | undefined): number {
  if (!s || s.latest_value == null) return 2
  if (Math.abs(s.latest_value) >= 1000) return 0
  return 2
}
