export const DASH = '—'

export function formatCompactCurrency(value: number | null | undefined, currency = 'USD'): string {
  if (value == null) return DASH
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      notation: 'compact',
      maximumFractionDigits: 2,
    }).format(value)
  } catch {
    return value.toLocaleString('en-US')
  }
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value == null) return DASH
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatSigned(value: number | null | undefined, digits = 2, suffix = ''): string {
  if (value == null) return DASH
  const sign = value > 0 ? '+' : ''
  return `${sign}${formatNumber(value, digits)}${suffix}`
}

export function formatInt(value: number | null | undefined): string {
  if (value == null) return DASH
  return value.toLocaleString('en-US')
}

/** 1234567890 -> "1.23B"; keeps the sign, no currency symbol. */
export function formatCompactNumber(value: number | null | undefined, digits = 2): string {
  if (value == null) return DASH
  const abs = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (abs >= 1e12) return `${sign}${(abs / 1e12).toFixed(digits)}T`
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(digits)}B`
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(digits)}M`
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(digits)}K`
  return `${sign}${abs.toFixed(digits)}`
}

/** Percent with a fixed number of decimals; input is already in percent units. */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return DASH
  return `${value.toFixed(digits)}%`
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return DASH
  return iso.slice(0, 10)
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60_000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toISOString().slice(0, 10)
}

export function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setUTCDate(d.getUTCDate() - days)
  return d.toISOString().slice(0, 10)
}

export function signClass(value: number | null | undefined): string {
  if (value == null || value === 0) return ''
  return value > 0 ? 'up' : 'down'
}
