---
# Frontend standards — FinAlly Next.js

## Build
- Static export only: next build → out/ directory
- Served by FastAPI at root — no Next.js server at runtime
- No SSR, no Next.js API routes — all data from FastAPI /api/*
- TypeScript strict mode — no implicit any

## Visual aesthetic (Bloomberg terminal)
- Dark background: bg-black or bg-zinc-900
- Price colors: text-green-400 (up), text-red-400 (down)
- Monospace for all numbers: font-mono
- Data-dense layout — minimize whitespace, maximize info density
- Price flash animation: green flash on uptick, red flash on downtick

## Component patterns
- Functional components + hooks only
- Props typed with TypeScript interfaces
- SSE hook: useSSE(endpoint) managing EventSource lifecycle
- No prop drilling — use React context or Zustand for portfolio state

## Key components
- PriceCell — price with flash animation on change
- PortfolioHeatmap — treemap (recharts Treemap)
- PnLChart — area chart of portfolio value (recharts AreaChart)
- PositionsTable — sortable holdings table
- AIChat — streaming chat consuming SSE from /api/chat/stream
- Watchlist — live prices, add/remove via AI or manual

## API rules
- Always relative paths (/api/...) — never hardcode localhost
- SSE: EventSource('/api/market/stream')
- Fetch: standard fetch() + async/await — no axios
- TypeScript interfaces matching FastAPI Pydantic schemas

## Testing
- E2E: Playwright in test/
- Critical flows: buy/sell, AI trade execution, price streaming