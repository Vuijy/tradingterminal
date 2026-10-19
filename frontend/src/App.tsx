import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from './api/client'
import { Clock } from './components/Clock'
import { CommandBar } from './components/CommandBar'
import { CompanyPanel } from './components/CompanyPanel'
import { FundamentalsPanel } from './components/FundamentalsPanel'
import { HelpOverlay } from './components/HelpOverlay'
import { MacroPanel } from './components/MacroPanel'
import { NewsPanel } from './components/NewsPanel'
import { PriceChart } from './components/PriceChart'
import { QuotePanel } from './components/QuotePanel'
import { StatusBar } from './components/StatusBar'
import { SupplyChainPanel } from './components/SupplyChainPanel'
import { WatchlistPanel } from './components/WatchlistPanel'
import { parseCommand, type PanelId } from './lib/commands'

/** `?t=AAPL` preloads a ticker so views are linkable. */
function tickerFromUrl(): string | null {
  try {
    const t = new URLSearchParams(window.location.search).get('t')
    return t ? t.trim().toUpperCase() : null
  } catch {
    return null
  }
}

interface PanelFocus {
  panel: PanelId
  nonce: number
}

export default function App() {
  const [ticker, setTicker] = useState<string | null>(tickerFromUrl)
  const [history, setHistory] = useState<string[]>([])
  const tickerRef = useRef<string | null>(ticker)
  tickerRef.current = ticker
  const [commandError, setCommandError] = useState<string | null>(null)
  const [helpOpen, setHelpOpen] = useState(false)
  const [focus, setFocus] = useState<PanelFocus | null>(null)

  const health = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 15_000,
    retry: false,
  })

  const applyTicker = useCallback((t: string) => {
    setTicker(t)
    try {
      const url = new URL(window.location.href)
      url.searchParams.set('t', t)
      window.history.replaceState(null, '', url)
    } catch {
      // URL updates are a convenience only
    }
  }, [])

  const selectTicker = useCallback(
    (next: string) => {
      const t = next.trim().toUpperCase()
      if (!t) return
      const current = tickerRef.current
      if (current && current !== t) setHistory((h) => [...h, current].slice(-30))
      if (current !== t) applyTicker(t)
    },
    [applyTicker],
  )

  const goBack = useCallback(() => {
    setHistory((h) => {
      const previous = h[h.length - 1]
      if (previous) applyTicker(previous)
      return h.slice(0, -1)
    })
  }, [applyTicker])

  const backTo = history[history.length - 1] ?? null

  const jumpTo = useCallback((panel: PanelId) => {
    setFocus((prev) => ({ panel, nonce: (prev?.nonce ?? 0) + 1 }))
  }, [])

  const runCommand = useCallback(
    (raw: string) => {
      const parsed = parseCommand(raw)
      if (parsed.error) {
        setCommandError(parsed.error)
        return
      }
      setCommandError(null)
      if (parsed.help) {
        setHelpOpen(true)
        return
      }
      if (parsed.ticker) selectTicker(parsed.ticker)
      if (parsed.panel) jumpTo(parsed.panel)
    },
    [selectTicker, jumpTo],
  )

  // Scroll the requested panel into view and flash its border.
  useEffect(() => {
    if (!focus) return
    const slot = document.getElementById(`panel-${focus.panel}`)
    const el = slot?.firstElementChild as HTMLElement | null
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    el.classList.add('panel-focus')
    const timer = setTimeout(() => el.classList.remove('panel-focus'), 1600)
    return () => clearTimeout(timer)
  }, [focus])

  return (
    <div className="terminal">
      <header className="topbar">
        <span className="brand">TRADING TERMINAL</span>
        <span className="topbar-right">
          <button
            type="button"
            className="mini-btn"
            onClick={() => setHelpOpen(true)}
            aria-label="Show command help"
          >
            HELP
          </button>
          <Clock />
        </span>
      </header>

      <CommandBar
        onSubmit={runCommand}
        defaultValue={ticker ?? ''}
        error={commandError}
        backTo={backTo}
        onBack={goBack}
      />

      <main className="workspace">
        <div id="panel-chart" className="slot">
          <PriceChart ticker={ticker} className="span-2 panel-chart" />
        </div>
        <div id="panel-watchlist" className="slot">
          <WatchlistPanel current={ticker} onSelectTicker={selectTicker} />
        </div>
        <div id="panel-quote" className="slot">
          <QuotePanel ticker={ticker} />
        </div>

        <div id="panel-fundamentals" className="slot">
          <FundamentalsPanel ticker={ticker} className="span-2" />
        </div>
        <div id="panel-news" className="slot">
          <NewsPanel ticker={ticker} onSelectTicker={selectTicker} />
        </div>
        <div id="panel-profile" className="slot">
          <CompanyPanel ticker={ticker} />
        </div>

        <div id="panel-supplychain" className="slot">
          <SupplyChainPanel
            ticker={ticker}
            onSelectTicker={selectTicker}
            backTo={backTo}
            onBack={goBack}
            className="span-2"
          />
        </div>
        <div id="panel-macro" className="slot">
          <MacroPanel className="span-2" />
        </div>
      </main>

      <StatusBar health={health.data} isError={health.isError} isLoading={health.isLoading} />
      {helpOpen && <HelpOverlay onClose={() => setHelpOpen(false)} />}
    </div>
  )
}
