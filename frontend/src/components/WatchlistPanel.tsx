import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api } from '../api/client'
import { formatNumber, formatSigned, signClass } from '../lib/format'
import { useStoredState } from '../lib/storage'
import { Panel } from './Panel'

const STORAGE_KEY = 'tt.watchlist.v1'
const DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META', 'TSLA', 'JPM']
const MAX_SYMBOLS = 30
const TICKER_RE = /^[A-Z0-9.\-^=]{1,12}$/

interface WatchlistPanelProps {
  current: string | null
  onSelectTicker: (ticker: string) => void
  className?: string
}

export function WatchlistPanel({ current, onSelectTicker, className }: WatchlistPanelProps) {
  const [tickers, setTickers] = useStoredState<string[]>(STORAGE_KEY, DEFAULT_WATCHLIST)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  const quotes = useQuery({
    queryKey: ['quotes', tickers],
    queryFn: () => api.quotes(tickers),
    enabled: tickers.length > 0,
    refetchInterval: 30_000,
    placeholderData: keepPreviousData,
    retry: false,
  })
  const byTicker = new Map((quotes.data ?? []).map((q) => [q.ticker, q]))

  function add(symbol: string) {
    const t = symbol.trim().toUpperCase()
    if (!t) return
    if (!TICKER_RE.test(t)) {
      setError(`"${t}" is not a valid symbol`)
      return
    }
    if (tickers.includes(t)) {
      setError(`${t} is already on the list`)
      return
    }
    if (tickers.length >= MAX_SYMBOLS) {
      setError(`Watchlist is limited to ${MAX_SYMBOLS} symbols`)
      return
    }
    setError(null)
    setTickers([...tickers, t])
  }

  function remove(symbol: string) {
    setTickers(tickers.filter((t) => t !== symbol))
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    add(draft)
    setDraft('')
  }

  const canAddCurrent = current !== null && !tickers.includes(current)

  return (
    <Panel
      title="WATCHLIST"
      className={className}
      actions={
        canAddCurrent ? (
          <button type="button" className="mini-btn" onClick={() => add(current)}>
            + {current}
          </button>
        ) : undefined
      }
    >
      {tickers.length > 0 && (
        <table className="watch-table">
          <tbody>
            {tickers.map((t) => {
              const q = byTicker.get(t)
              const missing = !q && quotes.isSuccess
              return (
                <tr key={t} className={t === current ? 'active' : ''}>
                  <td className="sym">
                    <button type="button" className="link-btn" onClick={() => onSelectTicker(t)}>
                      {t}
                    </button>
                  </td>
                  <td className="num">
                    {q ? formatNumber(q.price) : missing ? 'n/a' : quotes.isLoading ? '...' : ''}
                  </td>
                  <td className={`num ${signClass(q?.change_pct)}`}>
                    {q ? formatSigned(q.change_pct, 2, '%') : ''}
                  </td>
                  <td className="rm">
                    <button
                      type="button"
                      className="icon-btn"
                      aria-label={`Remove ${t} from watchlist`}
                      title="Remove"
                      onClick={() => remove(t)}
                    >
                      {'×'}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {tickers.length === 0 && <p className="muted">Watchlist is empty. Add a symbol below.</p>}
      <form className="watch-add" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add symbol"
          aria-label="Add symbol to watchlist"
          spellCheck={false}
        />
        <button type="submit">Add</button>
      </form>
      {error && <p className="error small">{error}</p>}
      {quotes.isError && <p className="error small">{quotes.error.message}</p>}
      <p className="muted source">refreshes every 30s</p>
    </Panel>
  )
}
