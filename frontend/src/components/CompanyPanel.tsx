import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import { formatCompactCurrency, formatInt } from '../lib/format'
import { Panel } from './Panel'

interface CompanyPanelProps {
  ticker: string | null
}

export function CompanyPanel({ ticker }: CompanyPanelProps) {
  const query = useQuery({
    queryKey: ['company', ticker],
    queryFn: () => api.company(ticker ?? ''),
    enabled: ticker !== null,
    retry: false,
  })

  const title = ticker ? `COMPANY PROFILE · ${ticker}` : 'COMPANY PROFILE'

  return (
    <Panel title={title}>
      {ticker === null && <p className="muted">Enter a ticker above to load a company.</p>}
      {query.isLoading && <p className="muted">Loading...</p>}
      {query.isError && <p className="error">{query.error.message}</p>}
      {query.data && (
        <>
          <dl className="kv">
            <dt>Name</dt>
            <dd>{query.data.name}</dd>
            <dt>Exchange</dt>
            <dd>{query.data.exchange ?? '—'}</dd>
            <dt>Sector</dt>
            <dd>{query.data.sector ?? '—'}</dd>
            <dt>Industry</dt>
            <dd>{query.data.industry ?? '—'}</dd>
            <dt>Country</dt>
            <dd>{query.data.country ?? '—'}</dd>
            <dt>Market cap</dt>
            <dd>{formatCompactCurrency(query.data.market_cap, query.data.currency ?? 'USD')}</dd>
            <dt>Employees</dt>
            <dd>{formatInt(query.data.employees)}</dd>
            <dt>Website</dt>
            <dd>
              {query.data.website ? (
                <a href={query.data.website} target="_blank" rel="noreferrer">
                  {query.data.website}
                </a>
              ) : (
                '—'
              )}
            </dd>
          </dl>
          {query.data.description && <p className="description">{query.data.description}</p>}
          <p className="muted source">source: {query.data.source}</p>
        </>
      )}
    </Panel>
  )
}
