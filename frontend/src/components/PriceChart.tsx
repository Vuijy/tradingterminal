import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import type { Candle } from '../api/types'
import { formatCompactNumber, formatNumber, formatSigned, signClass } from '../lib/format'
import { Panel } from './Panel'

interface RangePreset {
  label: string
  range: string
  interval: string
}

// Range -> bar size pairs, the way TradingView's range selector works.
const RANGES: RangePreset[] = [
  { label: '1D', range: '1d', interval: '5m' },
  { label: '5D', range: '5d', interval: '15m' },
  { label: '1M', range: '1mo', interval: '1h' },
  { label: '3M', range: '3mo', interval: '1d' },
  { label: '6M', range: '6mo', interval: '1d' },
  { label: 'YTD', range: 'ytd', interval: '1d' },
  { label: '1Y', range: '1y', interval: '1d' },
  { label: '5Y', range: '5y', interval: '1wk' },
  { label: 'MAX', range: 'max', interval: '1mo' },
]
const DEFAULT_RANGE = RANGES[4]
const INTRADAY = new Set(['1m', '2m', '5m', '15m', '30m', '1h'])

const UP = '#2ecc71'
const DOWN = '#ff4d4f'
const UP_SOFT = 'rgba(46, 204, 113, 0.35)'
const DOWN_SOFT = 'rgba(255, 77, 79, 0.35)'

interface Bar extends Candle {
  prevClose: number | null
}

interface PriceChartProps {
  ticker: string | null
  className?: string
}

export function PriceChart({ ticker, className }: PriceChartProps) {
  const [preset, setPreset] = useState<RangePreset>(DEFAULT_RANGE)
  const [hover, setHover] = useState<Bar | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const barsRef = useRef<Map<number, Bar>>(new Map())

  const intraday = INTRADAY.has(preset.interval)

  /** Back to the original view: all bars visible, price axis auto-scaled. */
  function resetView() {
    const chart = chartRef.current
    if (!chart) return
    chart.priceScale('right').applyOptions({ autoScale: true })
    chart.priceScale('volume').applyOptions({ autoScale: true })
    chart.timeScale().resetTimeScale()
    chart.timeScale().fitContent()
  }

  const query = useQuery({
    queryKey: ['history', ticker, preset.range, preset.interval],
    queryFn: () => api.history(ticker ?? '', preset.range, preset.interval),
    enabled: ticker !== null,
    retry: false,
    placeholderData: keepPreviousData,
    refetchInterval: intraday ? 60_000 : false,
  })

  // Create the chart once; it lives in refs and survives re-renders.
  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      width: el.clientWidth,
      height: el.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#7d8a9a',
        fontSize: 11,
        fontFamily: "ui-monospace, 'Cascadia Mono', Consolas, Menlo, monospace",
      },
      grid: {
        vertLines: { color: '#151c26' },
        horzLines: { color: '#151c26' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(255, 176, 0, 0.5)', labelBackgroundColor: '#ffb000' },
        horzLine: { color: 'rgba(255, 176, 0, 0.5)', labelBackgroundColor: '#ffb000' },
      },
      rightPriceScale: { borderColor: '#1f2a37' },
      timeScale: { borderColor: '#1f2a37', rightOffset: 3, secondsVisible: false },
    })

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      borderVisible: false,
      wickUpColor: UP,
      wickDownColor: DOWN,
    })
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.25 } })

    const onMove = (param: MouseEventParams) => {
      if (param.time === undefined) {
        setHover(null)
        return
      }
      setHover(barsRef.current.get(param.time as number) ?? null)
    }
    chart.subscribeCrosshairMove(onMove)

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight })
    })
    observer.observe(el)

    chartRef.current = chart
    candleRef.current = candle
    volumeRef.current = volume

    return () => {
      observer.disconnect()
      chart.unsubscribeCrosshairMove(onMove)
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      volumeRef.current = null
    }
  }, [])

  // Push data into the chart whenever it changes.
  useEffect(() => {
    const chart = chartRef.current
    const candle = candleRef.current
    const volume = volumeRef.current
    if (!chart || !candle || !volume) return

    const candles = query.data?.candles ?? []
    // The library renders times in UTC. For intraday bars shift them so the axis reads
    // in the viewer's local time, the usual workaround recommended by TradingView.
    const offset = intraday ? -new Date().getTimezoneOffset() * 60 : 0
    const bars = new Map<number, Bar>()
    let prevClose: number | null = null
    const candleData = candles.map((c) => {
      const time = c.time + offset
      bars.set(time, { ...c, time, prevClose })
      prevClose = c.close
      return { time: time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close }
    })
    const volumeData = candles.map((c) => ({
      time: (c.time + offset) as UTCTimestamp,
      value: c.volume ?? 0,
      color: c.close >= c.open ? UP_SOFT : DOWN_SOFT,
    }))

    barsRef.current = bars
    candle.setData(candleData)
    volume.setData(volumeData)
    chart.applyOptions({ timeScale: { timeVisible: intraday } })
    chart.timeScale().fitContent()
    setHover(null)
  }, [query.data, intraday])

  const candles = query.data?.candles ?? []
  const last = candles.at(-1)
  const lastBar: Bar | null = last ? { ...last, prevClose: candles.at(-2)?.close ?? null } : null
  const shown = hover ?? lastBar
  const change = shown && shown.prevClose != null ? shown.close - shown.prevClose : null
  const changePct = change != null && shown?.prevClose ? (change / shown.prevClose) * 100 : null

  const first = candles[0]
  const rangeChange = first && last ? last.close - first.open : null
  const rangeChangePct =
    rangeChange != null && first?.open ? (rangeChange / first.open) * 100 : null

  const title = ticker ? `PRICE · ${ticker}` : 'PRICE'
  const showingStale = query.data && query.data.ticker !== ticker

  return (
    <Panel
      title={title}
      className={className}
      bodyClassName="chart-body"
      actions={
        <div className="range-bar" role="tablist" aria-label="Chart range">
          <button
            type="button"
            onClick={resetView}
            title="Reset zoom and position (or right-click the chart)"
            aria-label="Reset chart view"
          >
            {'↺'}
          </button>
          {RANGES.map((r) => (
            <button
              key={r.label}
              type="button"
              className={r.label === preset.label ? 'active' : ''}
              onClick={() => setPreset(r)}
            >
              {r.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="chart-legend">
        {shown && !showingStale ? (
          <>
            <span className="legend-key">
              {query.data?.ticker} · {preset.interval}
              {query.data?.currency ? ` · ${query.data.currency}` : ''}
            </span>
            <span>
              O <b>{formatNumber(shown.open)}</b>
            </span>
            <span>
              H <b>{formatNumber(shown.high)}</b>
            </span>
            <span>
              L <b>{formatNumber(shown.low)}</b>
            </span>
            <span>
              C <b>{formatNumber(shown.close)}</b>
            </span>
            <span className={signClass(change)}>
              {formatSigned(change)} ({formatSigned(changePct, 2, '%')})
            </span>
            <span>
              Vol <b>{formatCompactNumber(shown.volume)}</b>
            </span>
            <span className={`legend-range ${signClass(rangeChange)}`}>
              {preset.label}: {formatSigned(rangeChangePct, 2, '%')}
            </span>
          </>
        ) : null}
      </div>
      <div
        ref={containerRef}
        className="chart-container"
        title="Right-click to reset the view"
        onContextMenu={(e) => {
          e.preventDefault()
          resetView()
        }}
      />
      {ticker === null && (
        <div className="chart-overlay muted">Enter a ticker above to load a chart.</div>
      )}
      {ticker !== null && query.isFetching && (!query.data || showingStale) && (
        <div className="chart-overlay muted">Loading {ticker}...</div>
      )}
      {query.isError && <div className="chart-overlay error">{query.error.message}</div>}
    </Panel>
  )
}
