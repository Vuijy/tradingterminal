/**
 * Bloomberg-style function codes for the command bar.
 *
 *   AAPL        load Apple
 *   AAPL FA     load Apple and jump to Fundamentals
 *   FA          jump to Fundamentals for the current company
 *   HELP        list the codes
 *
 * Ticker always comes first. When both tokens look like codes (e.g. "W GP", where W is
 * also Wayfair's ticker) the first one is treated as the ticker.
 */

export type PanelId =
  'chart' | 'watchlist' | 'quote' | 'fundamentals' | 'news' | 'profile' | 'supplychain' | 'macro'

export interface CommandDef {
  code: string
  aliases: string[]
  panel: PanelId
  label: string
}

export const COMMANDS: CommandDef[] = [
  { code: 'GP', aliases: ['G', 'CHART'], panel: 'chart', label: 'Price chart' },
  { code: 'Q', aliases: ['QUOTE'], panel: 'quote', label: 'Quote' },
  { code: 'DES', aliases: ['PROFILE'], panel: 'profile', label: 'Company description' },
  { code: 'FA', aliases: ['FIN'], panel: 'fundamentals', label: 'Financial analysis' },
  { code: 'CN', aliases: ['N', 'NEWS'], panel: 'news', label: 'Company news' },
  { code: 'SPLC', aliases: ['SC'], panel: 'supplychain', label: 'Supply chain' },
  { code: 'ECO', aliases: ['MACRO'], panel: 'macro', label: 'Economic data' },
  { code: 'W', aliases: ['WL', 'WATCH'], panel: 'watchlist', label: 'Watchlist' },
]

const TICKER_RE = /^[A-Z0-9.\-^=]{1,12}$/
const HELP_WORDS = new Set(['HELP', '?', 'H'])

export interface ParsedCommand {
  ticker: string | null
  panel: PanelId | null
  help: boolean
  error: string | null
}

export function findCommand(token: string): CommandDef | undefined {
  return COMMANDS.find((c) => c.code === token || c.aliases.includes(token))
}

export function parseCommand(raw: string): ParsedCommand {
  const none: ParsedCommand = { ticker: null, panel: null, help: false, error: null }
  const tokens = raw.trim().toUpperCase().split(/\s+/).filter(Boolean)
  if (tokens.length === 0) return none
  if (HELP_WORDS.has(tokens[0])) return { ...none, help: true }
  if (tokens.length > 2) {
    return { ...none, error: 'Use "TICKER", "TICKER CODE" or "CODE". Type HELP for the codes.' }
  }

  const [first, second] = tokens
  const firstCmd = findCommand(first)
  if (tokens.length === 1) {
    if (firstCmd) return { ...none, panel: firstCmd.panel }
    if (TICKER_RE.test(first)) return { ...none, ticker: first }
    return { ...none, error: `"${first}" is neither a ticker nor a function code. Type HELP.` }
  }

  const secondCmd = findCommand(second)
  if (secondCmd && TICKER_RE.test(first)) return { ...none, ticker: first, panel: secondCmd.panel }
  if (firstCmd && TICKER_RE.test(second)) return { ...none, ticker: second, panel: firstCmd.panel }
  return { ...none, error: `Unknown function "${second}". Type HELP for the list.` }
}
