import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { RelatedCompany, Relation, RelationshipEvidence } from '../api/types'
import { formatDate, formatPct } from '../lib/format'
import { Panel } from './Panel'

const SIX_HOURS = 6 * 60 * 60 * 1000
const NODE_W = 210
const NODE_H = 40
const ROW = 48
const WIDTH = 900
const MAX_COLUMN = 10
const MAX_ROW = 8

const COLORS: Record<Relation, string> = {
  supplier: '#ffb000',
  customer: '#2ecc71',
  competitor: '#ff4d4f',
  partner: '#4da3ff',
}

interface SupplyChainPanelProps {
  ticker: string | null
  onSelectTicker: (ticker: string) => void
  backTo?: string | null
  onBack?: () => void
  className?: string
}

export function SupplyChainPanel({
  ticker,
  onSelectTicker,
  backTo = null,
  onBack,
  className,
}: SupplyChainPanelProps) {
  const [selected, setSelected] = useState<string | null>(null)
  const [rescan, setRescan] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)

  // Escape leaves fullscreen; lock page scroll while it is open.
  useEffect(() => {
    if (!fullscreen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setFullscreen(false)
    }
    window.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [fullscreen])

  const quick = useQuery({
    queryKey: ['relationships', ticker, 'quick'],
    queryFn: () => api.relationships(ticker ?? '', false),
    enabled: ticker !== null,
    retry: false,
    staleTime: SIX_HOURS,
  })
  const needsDeep = quick.isSuccess && quick.data.status !== 'complete'
  const deep = useQuery({
    queryKey: ['relationships', ticker, 'deep', rescan],
    queryFn: () => api.relationships(ticker ?? '', true, rescan > 0),
    enabled: ticker !== null && (needsDeep || rescan > 0),
    retry: false,
    staleTime: SIX_HOURS,
  })

  const graph = deep.data ?? quick.data
  const title = ticker ? `SUPPLY CHAIN · ${ticker}` : 'SUPPLY CHAIN'
  const nodes = graph
    ? [...graph.suppliers, ...graph.customers, ...graph.competitors, ...graph.partners]
    : []
  const selectedNode = nodes.find((n) => nodeKey(n) === selected) ?? null

  return (
    <Panel
      title={title}
      className={`${className ?? ''} ${fullscreen ? 'panel-fullscreen' : ''}`}
      actions={
        <>
          {backTo && onBack && (
            <button
              type="button"
              className="back-btn"
              onClick={onBack}
              title={`Back to ${backTo}`}
              aria-label={`Back to ${backTo}`}
            >
              {'←'} Back to {backTo}
            </button>
          )}
          {graph && (
            <button
              type="button"
              className="mini-btn"
              onClick={() => setRescan((n) => n + 1)}
              disabled={deep.isFetching}
              title="Rebuild from the latest filings"
            >
              {deep.isFetching ? 'scanning...' : 'Rescan'}
            </button>
          )}
          <button
            type="button"
            className="mini-btn"
            onClick={() => setFullscreen((f) => !f)}
            title={fullscreen ? 'Exit fullscreen (Esc)' : 'Fullscreen'}
            aria-label={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {fullscreen ? '✖ Exit' : '⛶ Fullscreen'}
          </button>
        </>
      }
    >
      {ticker === null && (
        <p className="muted">
          Suppliers, customers and competitors mined from SEC 10-K filings appear here.
        </p>
      )}
      {quick.isLoading && <p className="muted">Reading the latest 10-K...</p>}
      {quick.isError && <p className="error">{quick.error.message}</p>}
      {graph && (
        <>
          {deep.isFetching && (
            <p className="muted small sc-progress">
              Searching EDGAR for filers that mention {graph.name} and reading their filings. The
              first scan of a company takes up to a minute.
            </p>
          )}
          {deep.isError && <p className="error small">{deep.error.message}</p>}
          <Graph
            graph={graph}
            selected={selected}
            onSelect={(key) => setSelected(key === selected ? null : key)}
            onOpen={onSelectTicker}
          />
          <div className="sc-legend muted small">
            <span>
              <i style={{ background: COLORS.supplier }} /> supplier
            </span>
            <span>
              <i style={{ background: COLORS.customer }} /> customer
            </span>
            <span>
              <i style={{ background: COLORS.competitor }} /> competitor
            </span>
            <span>
              <i style={{ background: COLORS.partner }} /> partner
            </span>
            <span>click a node for evidence, click a ticker to open it</span>
          </div>
          {selectedNode ? (
            <Evidence node={selectedNode} centre={graph.name} />
          ) : (
            <Summary graph={graph} />
          )}
          <p className="muted source">
            source: {graph.source} · {graph.analyzed_filings.length} filings analysed ·{' '}
            {graph.status === 'complete' ? 'own filing + full-text search' : 'own filing only'} ·
            generated {formatDate(graph.generated_at)}
          </p>
        </>
      )}
    </Panel>
  )
}

function nodeKey(n: RelatedCompany): string {
  return `${n.relation}:${n.cik ?? n.name}`
}

function trim(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

interface GraphProps {
  graph: import('../api/types').RelationshipGraph
  selected: string | null
  onSelect: (key: string) => void
  onOpen: (ticker: string) => void
}

function Graph({ graph, selected, onSelect, onOpen }: GraphProps) {
  const suppliers = graph.suppliers.slice(0, MAX_COLUMN)
  const customers = graph.customers.slice(0, MAX_COLUMN)
  const competitors = graph.competitors.slice(0, MAX_ROW)
  const partners = graph.partners.slice(0, 4)

  const rows = Math.max(suppliers.length, customers.length, 1)
  const topPad = partners.length > 0 ? ROW + 50 : 24
  const columnsHeight = rows * ROW
  const centreY = topPad + columnsHeight / 2 - NODE_H / 2
  const compRows = Math.ceil(competitors.length / 4)
  const compTop = topPad + columnsHeight + 36
  const height = compTop + (compRows > 0 ? compRows * ROW + 10 : 0) + 10

  const leftX = 10
  const centreX = WIDTH / 2 - NODE_W / 2
  const rightX = WIDTH - NODE_W - 10

  const edges: string[] = []
  const nodes: { node: RelatedCompany; x: number; y: number }[] = []
  suppliers.forEach((n, i) => {
    const y = topPad + i * ROW
    nodes.push({ node: n, x: leftX, y })
    edges.push(curve(leftX + NODE_W, y + NODE_H / 2, centreX, centreY + NODE_H / 2))
  })
  customers.forEach((n, i) => {
    const y = topPad + i * ROW
    nodes.push({ node: n, x: rightX, y })
    edges.push(curve(centreX + NODE_W, centreY + NODE_H / 2, rightX, y + NODE_H / 2))
  })
  const compEdges: string[] = []
  competitors.forEach((n, i) => {
    const col = i % 4
    const row = Math.floor(i / 4)
    const x = 10 + col * (NODE_W + 16)
    const y = compTop + row * ROW
    nodes.push({ node: n, x, y })
    compEdges.push(curveV(centreX + NODE_W / 2, centreY + NODE_H, x + NODE_W / 2, y))
  })
  partners.forEach((n, i) => {
    const x = 10 + i * (NODE_W + 16)
    nodes.push({ node: n, x, y: 24 })
  })

  const empty = nodes.length === 0

  return (
    <div className="sc-wrap">
      <svg
        className="sc-svg"
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="img"
        aria-label={`Supply chain graph for ${graph.name}`}
      >
        <text x={leftX} y={topPad - 8} className="sc-col-title">
          SUPPLIERS ({graph.suppliers.length})
        </text>
        <text x={rightX} y={topPad - 8} className="sc-col-title">
          CUSTOMERS ({graph.customers.length})
        </text>
        {competitors.length > 0 && (
          <text x={10} y={compTop - 10} className="sc-col-title">
            COMPETITORS ({graph.competitors.length})
          </text>
        )}
        {partners.length > 0 && (
          <text x={10} y={14} className="sc-col-title">
            PARTNERS ({graph.partners.length})
          </text>
        )}
        {edges.map((d, i) => (
          <path key={`e${i}`} d={d} className="sc-edge" />
        ))}
        {compEdges.map((d, i) => (
          <path key={`c${i}`} d={d} className="sc-edge competitor" />
        ))}
        <g className="sc-centre">
          <rect x={centreX} y={centreY} width={NODE_W} height={NODE_H} rx={3} />
          <text x={centreX + NODE_W / 2} y={centreY + 17} textAnchor="middle" className="sc-name">
            {trim(graph.name, 24)}
          </text>
          <text x={centreX + NODE_W / 2} y={centreY + 31} textAnchor="middle" className="sc-sub">
            {graph.ticker} · CIK {graph.cik}
          </text>
        </g>
        {nodes.map(({ node, x, y }) => {
          const key = nodeKey(node)
          const colour = COLORS[node.relation]
          const sub = [
            node.ticker ?? 'not SEC-listed',
            node.revenue_share_pct != null
              ? `${formatPct(node.revenue_share_pct, 0)} of rev`
              : null,
            `${Math.round(node.confidence * 100)}%`,
          ]
            .filter(Boolean)
            .join(' · ')
          return (
            <g
              key={key}
              className={`sc-node ${selected === key ? 'selected' : ''}`}
              onClick={() => onSelect(key)}
              style={{ ['--node' as string]: colour }}
            >
              <title>{node.evidence[0]?.snippet ?? node.name}</title>
              <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={3} stroke={colour} />
              <text x={x + 8} y={y + 16} className="sc-name">
                {trim(node.name, 30)}
              </text>
              <text x={x + 8} y={y + 30} className="sc-sub">
                {trim(sub, node.ticker ? 24 : 32)}
              </text>
              {node.ticker && (
                <text
                  x={x + NODE_W - 8}
                  y={y + 30}
                  textAnchor="end"
                  className="sc-open"
                  onClick={(e) => {
                    e.stopPropagation()
                    onOpen(node.ticker as string)
                  }}
                >
                  open →
                </text>
              )}
            </g>
          )
        })}
        {empty && (
          <text x={WIDTH / 2} y={height - 14} textAnchor="middle" className="sc-sub">
            No named counterparties found in the filings analysed so far.
          </text>
        )}
      </svg>
    </div>
  )
}

function curve(x1: number, y1: number, x2: number, y2: number): string {
  const mx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
}

function curveV(x1: number, y1: number, x2: number, y2: number): string {
  const my = (y1 + y2) / 2
  return `M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`
}

function Evidence({ node, centre }: { node: RelatedCompany; centre: string }) {
  const verb: Record<Relation, string> = {
    supplier: `supplies ${centre}`,
    customer: `buys from ${centre}`,
    competitor: `competes with ${centre}`,
    partner: `partners with ${centre}`,
  }
  return (
    <div className="sc-evidence">
      <div className="sc-evidence-head">
        <span className="legend-key">{node.name}</span>
        <span className="muted">
          {' '}
          {verb[node.relation]}
          {node.revenue_share_pct != null
            ? node.relation === 'supplier'
              ? ` · ${centre} is ${formatPct(node.revenue_share_pct, 1)} of its revenue`
              : ` · ${formatPct(node.revenue_share_pct, 1)} of ${centre}'s revenue`
            : ''}
          {' · confidence '}
          {Math.round(node.confidence * 100)}%
        </span>
      </div>
      <ul className="evidence-list">
        {node.evidence.map((e, i) => (
          <li key={`${e.accession}-${i}`}>
            <EvidenceLine e={e} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function EvidenceLine({ e }: { e: RelationshipEvidence }) {
  return (
    <>
      <div className="evidence-meta muted small">
        <a href={e.url} target="_blank" rel="noreferrer">
          {e.source_name}
          {e.source_ticker ? ` (${e.source_ticker})` : ''} {e.form} {formatDate(e.filed)}
        </a>
        {e.section ? ` · ${e.section}` : ''}
        {e.percent != null ? ` · ${formatPct(e.percent, 1)} of revenue` : ''}
        {` · ${e.method === 'own_filing' ? 'own filing' : 'full-text search'}`}
      </div>
      <div className="evidence-snippet">{e.snippet}</div>
    </>
  )
}

function Summary({ graph }: { graph: import('../api/types').RelationshipGraph }) {
  return (
    <div className="sc-summary small">
      {graph.anonymous_customers.length > 0 && (
        <p className="muted">
          Unnamed major customers disclosed by {graph.name}:{' '}
          {graph.anonymous_customers
            .map(
              (a) =>
                `${a.label}${a.percent != null ? ` (${formatPct(a.percent, 0)} of revenue)` : ''}`,
            )
            .join(', ')}
          .
        </p>
      )}
      {graph.status !== 'complete' && (
        <p className="muted">
          Only {graph.name}'s own filing has been read so far; the full-text search adds the
          companies that name {graph.name} in their reports.
        </p>
      )}
    </div>
  )
}
