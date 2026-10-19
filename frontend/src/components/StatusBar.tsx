import type { Health } from '../api/types'

interface StatusBarProps {
  health: Health | undefined
  isError: boolean
  isLoading: boolean
}

export function StatusBar({ health, isError, isLoading }: StatusBarProps) {
  const state = isLoading ? 'unknown' : isError || !health ? 'bad' : 'ok'
  const label = state === 'ok' ? 'API ONLINE' : state === 'bad' ? 'API OFFLINE' : 'API ...'

  return (
    <footer className="statusbar">
      <span>
        <span className={`dot ${state}`} />
        {label}
      </span>
      {health && (
        <>
          <span>v{health.version}</span>
          <span>env: {health.env}</span>
          <span>provider: {health.provider}</span>
        </>
      )}
      {isError && <span className="error">Start the backend: uvicorn app.main:app --reload</span>}
    </footer>
  )
}
