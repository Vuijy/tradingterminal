import { useEffect } from 'react'

import { COMMANDS } from '../lib/commands'

interface HelpOverlayProps {
  onClose: () => void
}

export function HelpOverlay({ onClose }: HelpOverlayProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="help-backdrop" onClick={onClose} role="presentation">
      <div
        className="help-box"
        role="dialog"
        aria-modal="true"
        aria-label="Command help"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="help-head">
          <span className="legend-key">COMMAND BAR</span>
          <button type="button" className="icon-btn" aria-label="Close help" onClick={onClose}>
            {'×'}
          </button>
        </div>
        <p className="muted small">
          Type a ticker to load a company. Add a function code to jump straight to a panel, e.g.{' '}
          <b>AAPL FA</b>. A code on its own applies to the current company. Press <b>/</b> anywhere
          to focus the bar, <b>Esc</b> to leave it.
        </p>
        <table className="help-table">
          <tbody>
            {COMMANDS.map((c) => (
              <tr key={c.code}>
                <td className="legend-key">{c.code}</td>
                <td className="muted">{c.aliases.join(', ')}</td>
                <td>{c.label}</td>
              </tr>
            ))}
            <tr>
              <td className="legend-key">HELP</td>
              <td className="muted">?</td>
              <td>This list</td>
            </tr>
          </tbody>
        </table>
        <p className="muted small">
          Views are linkable: <b>?t=NVDA</b> in the URL preloads a ticker.
        </p>
      </div>
    </div>
  )
}
