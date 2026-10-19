import { useEffect, useRef, useState, type FormEvent } from 'react'

interface CommandBarProps {
  onSubmit: (raw: string) => void
  defaultValue?: string
  error: string | null
  /** Previous ticker in the navigation history, if any. */
  backTo?: string | null
  onBack?: () => void
}

export function CommandBar({
  onSubmit,
  defaultValue = '',
  error,
  backTo = null,
  onBack,
}: CommandBarProps) {
  const [value, setValue] = useState(defaultValue)
  const inputRef = useRef<HTMLInputElement>(null)

  // "/" focuses the command bar from anywhere; Escape leaves it.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      const typing =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable
      if (e.key === '/' && !typing) {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      } else if (e.key === 'Escape' && target === inputRef.current) {
        inputRef.current?.blur()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (value.trim()) onSubmit(value)
  }

  return (
    <div className="command-wrap">
      <form className="command-bar" onSubmit={handleSubmit}>
        {backTo && onBack && (
          <button
            type="button"
            className="back-btn"
            onClick={onBack}
            title={`Back to ${backTo}`}
            aria-label={`Back to ${backTo}`}
          >
            {'←'} {backTo}
          </button>
        )}
        <input
          ref={inputRef}
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="TICKER  or  TICKER CODE  (AAPL FA)  or  HELP"
          spellCheck={false}
          aria-label="Command"
          aria-invalid={error ? true : undefined}
        />
        <button type="submit">GO</button>
      </form>
      <div className={`command-hint ${error ? 'error' : 'muted'}`}>
        {error ??
          'Codes: GP chart · Q quote · DES profile · FA fundamentals · CN news · SPLC supply chain · ECO macro · W watchlist · press / to focus'}
      </div>
    </div>
  )
}
