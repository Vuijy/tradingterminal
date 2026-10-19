# Product direction (decision log)

Last updated 2026-10-19. Status: **paused after the supply-chain milestone; niche not yet
final.** The owner decided to stop adding features broadly ("competing with Bloomberg will
fail") and pick a specific type of user. Nothing below is implemented yet.

## Where the product stands

Working, tested, verified live: price chart (TradingView lightweight-charts) with reset,
watchlist, quote with ranges, SEC fundamentals + filings, Yahoo news with filter, FRED macro
dashboard, Bloomberg-style command codes, back navigation, and the supply-chain graph mined
from 10-K text plus EDGAR full-text search, with fullscreen mode. All data is free.
Not built: comparison overlay, drawing tools, multi-chart, XBRL segments, valuation ratios,
20-F/IFRS, recession shading, release calendar, yield curve, market-wide news, saved
layouts, OpenAPI type generation, production nginx build (see ROADMAP.md).

## Niche candidates discussed

1. **Supply-chain / second-order trader** ("Apple guides down, who is exposed?"). Best fit
   for what exists; the graph with revenue shares is the whole product. Paid incumbent:
   Bloomberg SPLC.
2. Earnings-season trader: calendar, past reactions, guidance diffs, supplier tells.
3. "Read the 10-K for me" long-horizon investor: year-over-year risk-factor and
   concentration diffs, every claim linked to its sentence. Deepest moat, slowest growth.
4. Insider / smart-money follower: Form 4, 13F, 13D from EDGAR.
5. Macro-aware swing trader around FRED releases. Least differentiated.
6. **Small-cap / micro-cap specialist.** Owner liked this. Data check on SCKT ($4M),
   GUER, KOPN, CLFD: prices, 10 years of statements, filings and concentration
   disclosures all present (EDGAR covers small filers as well as Apple). Gaps found:
   regex extraction produced junk on sloppier small-cap prose ("Accounts", "Singapore"),
   XBRL revenue tags drift (Kopin revenue misread, Guerrilla RF revenue missing), news is
   thin, reverse search is thin because few filers name a $45M company. Needed first:
   recalibrate extraction on 20-30 micro-cap 10-Ks (LLM backstop likely), widen tag
   handling; then Form 4 insider buys, S-1/S-3 dilution history, 8-K going-concern and
   auditor-change items, FINRA short interest.
7. Thematic basket builder from filing relationships (extension of 1).

## Positions taken (Claude's assessment, owner has not overruled)

- **Portfolio-allocation-by-risk-tolerance tool: advised against.** Commoditised and
  free elsewhere (robo-advisors, Portfolio Visualizer), uses none of the filing moat,
  low-engagement, optimiser outputs are fragile, and individualised weights edge toward
  investment advice. The defensible variant: "know what you own" for long-term holders:
  look-through exposure via the supply-chain graph, simple capped sizing with the maths
  shown, thesis tracking that flags when filing facts change, a yearly 10-K check-in.
- **Long-term / low-frequency vs high-frequency scalpers: long-term, clearly.** Scalping
  needs real-time quotes, level 2 and broker execution; free data is 15-minute delayed
  and polled; nothing built here helps a scalper. Long-horizon users consume exactly the
  slow, free data the terminal is good at. Swing traders (days to weeks) are the furthest
  reasonable stretch toward activity.

## Likely next step when work resumes

Pick between niche 6 (small-cap specialist) and the "know what you own" long-term
researcher, or combine them (small-cap, filing-driven, low frequency). Either way the
first engineering task is the same: a calibration pass of the extraction rules on
small-cap filings and sturdier XBRL tag selection.
