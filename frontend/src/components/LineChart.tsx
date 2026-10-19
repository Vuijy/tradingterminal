import {
  AreaSeries,
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'

export interface LinePoint {
  /** ISO date, YYYY-MM-DD. */
  time: string
  value: number
}

interface LineChartProps {
  data: LinePoint[]
  height?: number
  color?: string
  precision?: number
}

/** Small area chart for a single time series (macro panel). */
export function LineChart({
  data,
  height = 200,
  color = '#ffb000',
  precision = 2,
}: LineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#7d8a9a',
        fontSize: 11,
        fontFamily: "ui-monospace, 'Cascadia Mono', Consolas, Menlo, monospace",
      },
      grid: { vertLines: { color: '#151c26' }, horzLines: { color: '#151c26' } },
      rightPriceScale: { borderColor: '#1f2a37' },
      timeScale: { borderColor: '#1f2a37' },
      handleScroll: false,
      handleScale: false,
    })
    const series = chart.addSeries(AreaSeries, {
      lineColor: color,
      topColor: 'rgba(255, 176, 0, 0.35)',
      bottomColor: 'rgba(255, 176, 0, 0.02)',
      lineWidth: 2,
      priceLineVisible: false,
      priceFormat: { type: 'price', precision, minMove: 10 ** -precision },
    })
    const observer = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }))
    observer.observe(el)
    chartRef.current = chart
    seriesRef.current = series
    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [height, color, precision])

  useEffect(() => {
    const series = seriesRef.current
    const chart = chartRef.current
    if (!series || !chart) return
    series.setData(data.map((p) => ({ time: p.time as Time, value: p.value })))
    chart.timeScale().fitContent()
  }, [data])

  return <div ref={containerRef} className="line-chart" style={{ height }} />
}
