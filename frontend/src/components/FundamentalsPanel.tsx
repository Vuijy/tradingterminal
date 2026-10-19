import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import type { ConceptMeta, FinancialPeriod, Financials } from '../api/types'
import {
  DASH,
  formatCompactNumber,
  formatDate,
  formatNumber,
  formatPct,
  formatSigned,
  signClass,
} from '../lib/format'
import { Panel } from './Panel'

type Tab = 'annual' | 'quarterly' | 'filings'

const TABS: { id: Tab; label: string }[] = [
  { id: 'annual', label: 'Annual' },
  { id: 'quarterly', label: 'Quarterly' },
  { id: 'filings', label: 'Filings' },
]

const SIX_HOURS = 6 * 60 * 60 * 1000

interface FundamentalsPanelProps {
  ticker: string | null
  className?: string
}

export function FundamentalsPanel({ ticker, className }: FundamentalsPanelProps) {
  const [tab, setTab] = useState<Tab>('annual')

  const financials = useQuery({
    queryKey: ['fundamentals', ticker],
    queryFn: () => api.fundamentals(ticker ?? ''),
    enabled: ticker !== null,
    retry: false,
    staleTime: SIX_HOURS,
  })
  const filings = useQuery({
    queryKey: ['filings', ticker],
    queryFn: () => api.filings(ticker ?? ''),
    enabled: ticker !== null && tab === 'filings',
    retry: false,
    staleTime: SIX_HOURS,
  })

  const title = ticker ? `FUNDAMENTALS · ${ticker}` : 'FUNDAMENTALS'

  return (
    <Panel
      title={title}
      className={className}
      actions={
        <div className="tab-bar" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={tab === t.id ? 'active' : ''}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      }
    >
      {ticker === null && (
        <p className="muted">Financial statements from SEC EDGAR appear here (US filers only).</p>
      )}
      {ticker !== null && tab !== 'filings' && (
        <>
          {financials.isLoading && <p className="muted">Loading EDGAR data...</p>}
          {financials.isError && <p className="error">{financials.error.message}</p>}
          {financials.data && <StatementTable data={financials.data} mode={tab} />}
        </>
      )}
      {ticker !== null && tab === 'filings' && (
        <>
          {filings.isLoading && <p className="muted">Loading filings...</p>}
          {filings.isError && <p className="error">{filings.error.message}</p>}
          {filings.data && (
            <>
              <ul className="filing-list">
                {filings.data.filings.map((f) => (
                  <li key={f.accession}>
                    <a href={f.url} target="_blank" rel="noreferrer">
                      <span className="badge">{f.form}</span>
                      <span>{formatDate(f.filed)}</span>
                      <span className="muted">
                        {f.report_date ? ` period ${formatDate(f.report_date)}` : ''}
                        {f.description ? ` · ${f.description}` : ''}
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
              {filings.data.filings.length === 0 && <p className="muted">No filings found.</p>}
              <p className="muted source">source: {filings.data.source}</p>
            </>
          )}
        </>
      )}
    </Panel>
  )
}

function StatementTable({ data, mode }: { data: Financials; mode: 'annual' | 'quarterly' }) {
  const all = mode === 'annual' ? data.annual : data.quarterly
  const periods = all.slice(0, mode === 'annual' ? 6 : 8).reverse()
  if (periods.length === 0) {
    return <p className="muted">No {mode} statements found in EDGAR for this company.</p>
  }
  const concepts = data.concepts.filter((c) => c.key !== 'cost_of_revenue')
  const income = concepts.filter((c) => c.kind === 'duration')
  const balance = concepts.filter((c) => c.kind === 'instant')

  return (
    <>
      <div className="table-scroll">
        <table className="fin-table">
          <thead>
            <tr>
              <th>{data.currency}</th>
              {periods.map((p) => (
                <th key={p.period} title={periodTooltip(p)}>
                  {p.period}
                  {p.derived ? '*' : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <SectionRow label="Income & cash flow" span={periods.length + 1} />
            {income.map((c) => (
              <ValueRow key={c.key} concept={c} periods={periods} />
            ))}
            <SectionRow label="Balance sheet" span={periods.length + 1} />
            {balance.map((c) => (
              <ValueRow key={c.key} concept={c} periods={periods} />
            ))}
            <SectionRow label="Ratios" span={periods.length + 1} />
            <RatioRow label="Gross margin" periods={periods} num="gross_profit" den="revenue" />
            <RatioRow
              label="Operating margin"
              periods={periods}
              num="operating_income"
              den="revenue"
            />
            <RatioRow label="Net margin" periods={periods} num="net_income" den="revenue" />
            <tr>
              <td>Revenue growth YoY</td>
              {periods.map((p) => {
                const g = yoyGrowth(p, all, 'revenue')
                return (
                  <td key={p.period} className={`num ${signClass(g)}`}>
                    {formatSigned(g, 1, '%')}
                  </td>
                )
              })}
            </tr>
          </tbody>
        </table>
      </div>
      {periods.some((p) => p.derived) && (
        <p className="muted small">
          * Q4 derived as fiscal year minus Q1-Q3; companies do not report Q4 on its own.
        </p>
      )}
      <p className="muted source">
        source: {data.source} · {data.entity_name} · CIK {data.cik}
      </p>
    </>
  )
}

function SectionRow({ label, span }: { label: string; span: number }) {
  return (
    <tr className="section">
      <td colSpan={span}>{label}</td>
    </tr>
  )
}

function ValueRow({ concept, periods }: { concept: ConceptMeta; periods: FinancialPeriod[] }) {
  return (
    <tr>
      <td>{concept.label}</td>
      {periods.map((p) => {
        const v = p.values[concept.key]
        return (
          <td key={p.period} className={`num ${v != null && v < 0 ? 'down' : ''}`}>
            {formatValue(v, concept.unit)}
          </td>
        )
      })}
    </tr>
  )
}

function RatioRow({
  label,
  periods,
  num,
  den,
}: {
  label: string
  periods: FinancialPeriod[]
  num: string
  den: string
}) {
  return (
    <tr>
      <td>{label}</td>
      {periods.map((p) => {
        const n = p.values[num]
        const d = p.values[den]
        const ratio = n != null && d ? (n / d) * 100 : null
        return (
          <td key={p.period} className="num">
            {formatPct(ratio)}
          </td>
        )
      })}
    </tr>
  )
}

function formatValue(value: number | null, unit: string): string {
  if (value == null) return DASH
  if (unit === 'USD/shares') return formatNumber(value, 2)
  return formatCompactNumber(value, 2)
}

function yoyGrowth(p: FinancialPeriod, all: FinancialPeriod[], key: string): number | null {
  const base = all.find(
    (q) => q.fiscal_year === p.fiscal_year - 1 && q.fiscal_period === p.fiscal_period,
  )
  const cur = p.values[key]
  const prev = base?.values[key]
  if (cur == null || prev == null || prev <= 0) return null
  return (cur / prev - 1) * 100
}

function periodTooltip(p: FinancialPeriod): string {
  const parts = [`${p.start ?? '?'} to ${p.end}`]
  if (p.form) parts.push(p.form)
  if (p.filed) parts.push(`filed ${p.filed}`)
  if (p.derived) parts.push('derived')
  return parts.join(' · ')
}
