// Mirrors the Pydantic schemas in backend/app/models. Keep in sync by hand for now;
// generate from /api/v1/openapi.json once the API stabilises.

export interface Health {
  status: string
  app: string
  version: string
  env: string
  provider: string
  time: string
}

export interface CompanyProfile {
  ticker: string
  name: string
  exchange: string | null
  currency: string | null
  sector: string | null
  industry: string | null
  country: string | null
  website: string | null
  market_cap: number | null
  employees: number | null
  description: string | null
  source: string
}

export interface Quote {
  ticker: string
  price: number | null
  previous_close: number | null
  change: number | null
  change_pct: number | null
  currency: string | null
  as_of: string | null
  day_high: number | null
  day_low: number | null
  year_high: number | null
  year_low: number | null
  volume: number | null
  market_cap: number | null
  source: string
}

export interface Candle {
  /** Bar open time, Unix seconds UTC. */
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number | null
}

export interface PriceHistory {
  ticker: string
  range: string
  interval: string
  currency: string | null
  timezone: string | null
  candles: Candle[]
  source: string
}

export interface NewsItem {
  id: string
  title: string
  publisher: string | null
  url: string
  published_at: string | null
  thumbnail_url: string | null
  related_tickers: string[]
}

export interface NewsFeed {
  ticker: string
  items: NewsItem[]
  source: string
}

export interface ConceptMeta {
  key: string
  label: string
  kind: 'duration' | 'instant'
  unit: string
}

export interface FinancialPeriod {
  period: string
  fiscal_year: number
  fiscal_period: string
  start: string | null
  end: string
  filed: string | null
  form: string | null
  derived: boolean
  values: Record<string, number | null>
}

export interface Financials {
  ticker: string
  cik: number
  entity_name: string
  currency: string
  concepts: ConceptMeta[]
  annual: FinancialPeriod[]
  quarterly: FinancialPeriod[]
  source: string
}

export interface Filing {
  accession: string
  form: string
  filed: string
  report_date: string | null
  description: string | null
  url: string
}

export interface FilingList {
  ticker: string
  cik: number
  entity_name: string | null
  filings: Filing[]
  source: string
}

export type Relation = 'supplier' | 'customer' | 'competitor' | 'partner'

export interface RelationshipEvidence {
  source_cik: number
  source_name: string
  source_ticker: string | null
  form: string
  filed: string | null
  accession: string
  url: string
  section: string | null
  snippet: string
  /** Share of the speaking filer's revenue from the counterparty, when stated. */
  percent: number | null
  method: 'own_filing' | 'full_text_search' | 'stored'
  pattern: string | null
}

export interface RelatedCompany {
  name: string
  ticker: string | null
  cik: number | null
  relation: Relation
  confidence: number
  revenue_share_pct: number | null
  evidence: RelationshipEvidence[]
}

export interface AnonymousCustomer {
  label: string
  percent: number | null
  evidence: RelationshipEvidence
}

export interface RelationshipGraph {
  ticker: string
  cik: number
  name: string
  suppliers: RelatedCompany[]
  customers: RelatedCompany[]
  competitors: RelatedCompany[]
  partners: RelatedCompany[]
  anonymous_customers: AnonymousCustomer[]
  analyzed_filings: string[]
  status: 'own_filing_only' | 'complete'
  generated_at: string
  source: string
}

export interface MacroObservation {
  date: string
  value: number
}

export interface MacroSeries {
  series_id: string
  title: string
  unit: string | null
  frequency: string | null
  observations: MacroObservation[]
  source: string
}

export interface MacroSummary {
  series_id: string
  title: string
  unit: string | null
  frequency: string | null
  group: string
  latest_value: number | null
  latest_date: string | null
  previous_value: number | null
  previous_date: string | null
  change: number | null
  change_pct: number | null
  yoy_pct: number | null
}
