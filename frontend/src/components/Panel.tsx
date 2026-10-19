import type { ReactNode } from 'react'

interface PanelProps {
  title: string
  children: ReactNode
  /** Controls rendered on the right side of the title bar (tabs, range buttons). */
  actions?: ReactNode
  className?: string
  bodyClassName?: string
}

export function Panel({ title, children, actions, className, bodyClassName }: PanelProps) {
  return (
    <section className={`panel ${className ?? ''}`}>
      <header className="panel-head">
        <h2 className="panel-title">{title}</h2>
        {actions && <div className="panel-actions">{actions}</div>}
      </header>
      <div className={`panel-body ${bodyClassName ?? ''}`}>{children}</div>
    </section>
  )
}
