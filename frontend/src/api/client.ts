import type {
  CompanyProfile,
  FilingList,
  Financials,
  Health,
  MacroSeries,
  MacroSummary,
  NewsFeed,
  PriceHistory,
  Quote,
  RelationshipGraph,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '') || '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Accept: 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const body: unknown = await res.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const d = (body as { detail: unknown }).detail
        if (typeof d === 'string') detail = d
      }
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, detail)
  }
  return (await res.json()) as T
}

const enc = encodeURIComponent

export const api = {
  health: () => request<Health>('/health'),
  company: (ticker: string) => request<CompanyProfile>(`/companies/${enc(ticker)}`),
  quote: (ticker: string) => request<Quote>(`/companies/${enc(ticker)}/quote`),
  quotes: (tickers: string[]) => request<Quote[]>(`/quotes?tickers=${enc(tickers.join(','))}`),
  history: (ticker: string, range: string, interval: string) =>
    request<PriceHistory>(
      `/companies/${enc(ticker)}/history?range=${enc(range)}&interval=${enc(interval)}`,
    ),
  news: (ticker: string, limit = 15) =>
    request<NewsFeed>(`/companies/${enc(ticker)}/news?limit=${limit}`),
  fundamentals: (ticker: string) => request<Financials>(`/companies/${enc(ticker)}/fundamentals`),
  filings: (ticker: string, forms = '10-K,10-Q,8-K', limit = 25) =>
    request<FilingList>(`/companies/${enc(ticker)}/filings?forms=${enc(forms)}&limit=${limit}`),
  relationships: (ticker: string, deep = false, refresh = false) =>
    request<RelationshipGraph>(
      `/companies/${enc(ticker)}/relationships?deep=${deep}&refresh=${refresh}`,
    ),
  macroDashboard: () => request<MacroSummary[]>('/macro/dashboard'),
  macroSeries: (seriesId: string, start?: string) =>
    request<MacroSeries>(`/macro/series/${enc(seriesId)}${start ? `?start=${enc(start)}` : ''}`),
}
