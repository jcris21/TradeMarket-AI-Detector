---
name: Quant-Logic Terminal
colors:
  surface: '#10141a'
  surface-dim: '#10141a'
  surface-bright: '#353940'
  surface-container-lowest: '#0a0e14'
  surface-container-low: '#181c22'
  surface-container: '#1c2026'
  surface-container-high: '#262a31'
  surface-container-highest: '#31353c'
  on-surface: '#dfe2eb'
  on-surface-variant: '#bec8d1'
  inverse-surface: '#dfe2eb'
  inverse-on-surface: '#2d3137'
  outline: '#88929a'
  outline-variant: '#3e484f'
  surface-tint: '#84cfff'
  primary: '#84cfff'
  on-primary: '#00344c'
  primary-container: '#209dd7'
  on-primary-container: '#003046'
  inverse-primary: '#00658e'
  secondary: '#eab2ff'
  on-secondary: '#4e0e6a'
  secondary-container: '#672b83'
  on-secondary-container: '#df9bfb'
  tertiary: '#fdbc23'
  on-tertiary: '#412d00'
  tertiary-container: '#bf8b00'
  on-tertiary-container: '#3c2900'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#c7e7ff'
  primary-fixed-dim: '#84cfff'
  on-primary-fixed: '#001e2e'
  on-primary-fixed-variant: '#004c6c'
  secondary-fixed: '#f7d8ff'
  secondary-fixed-dim: '#eab2ff'
  on-secondary-fixed: '#310048'
  on-secondary-fixed-variant: '#672b83'
  tertiary-fixed: '#ffdea5'
  tertiary-fixed-dim: '#fdbc23'
  on-tertiary-fixed: '#261900'
  on-tertiary-fixed-variant: '#5d4200'
  background: '#10141a'
  on-background: '#dfe2eb'
  surface-variant: '#31353c'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  data-tabular:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: '0'
  body-base:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: '0'
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.08em
  data-tabular-mobile:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-margin: 24px
  panel-gutter: 12px
  cell-padding-x: 12px
  cell-padding-y: 6px
  stack-compact: 8px
  stack-loose: 16px
---

## Brand & Style
The brand personality is authoritative, analytical, and uncompromisingly technical. It is designed for financial analysts and quantitative traders who require high-density information without cognitive fatigue. The design style is a hybrid of **Corporate Modern** and **Technical Brutalism**, prioritizing utility, precision, and the "Terminal" aesthetic.

The UI should evoke a sense of deep-space focus—quiet, stable, and reactive. By using a dark-mode foundation with surgical neon accents, the design system communicates that it is an advanced tool for detecting patterns invisible to the human eye. 

**Key Stylistic Pillars:**
- **Information Density:** High-density grids where every pixel serves a data-driven purpose.
- **Instrument Precision:** Hairline borders and monospaced typography to reflect the accuracy of financial calculations.
- **Reactive Lighting:** Using neon glows (cyan and purple) sparingly to highlight AI-driven insights against a muted, professional backdrop.

## Colors
The palette is rooted in a "Deep Space" hierarchy. The background uses a layered dark strategy to reduce eye strain during long trading sessions.

- **Primary (Cyber-Cyan):** Reserved for technical coordinates, active data focus, and primary navigational paths.
- **Secondary (Amethyst Tech-Purple):** Dedicated exclusively to AI-driven interactions, agentic behaviors, and "machine intelligence" status.
- **Tertiary (Amber Gold):** Used for alerts, high-priority opportunities, and critical system state changes.
- **Neutral (Obsidian Slate):** The structural foundation. We use varying levels of slate to define depth rather than shadows.
- **Market Semantics:** Standardized Bullish Green and Bearish Red are used strictly for price action and execution status, ensuring they remain distinct from the UI's functional accents.

## Typography
Typography is the primary vehicle for data clarity. We employ a dual-font strategy:
- **Geist Sans:** Used for headlines and structural UI elements to provide a modern, clean professional feel.
- **JetBrains Mono:** Used for all data points, tickers, and AI chat logs. This ensures that numerical values align perfectly in tables (tabular numbers) and emphasizes the technical nature of the tool.

**Rules:**
- Use `label-caps` for all table headers and panel titles to create a clear visual break from data.
- Enforce `tabular-nums` for all price and percentage fields to prevent horizontal jitter during real-time updates.
- On mobile, font sizes drop slightly, but monospaced formatting is maintained to preserve the density of financial information.

## Layout & Spacing
The layout follows a **Fixed-Grid Terminal** model. The application should feel like a single-screen workstation where the user's eye can travel across quadrants without scrolling.

**Grid Strategy:**
- **Desktop:** A three-column dashboard. Left (Watchlist: 320px), Center (Charts/Main: Flex), Right (AI Assistant: 360px).
- **Gutter:** A consistent 12px gutter between panels creates a "windowed" effect.
- **Alignment:** Financial values are always right-aligned to allow for decimal point scanning. Labels and descriptors are left-aligned.

**Reflow:** On mobile, the three columns stack into a tabbed view (Market, Analysis, AI) to maintain readability of the dense data tables.

## Elevation & Depth
This design system rejects heavy shadows in favor of **Tonal Layering** and **Hairline Outlines**.

- **Level 0 (Canvas):** The deepest layer (`#0d1117`). Used for the main application background.
- **Level 1 (Panels):** Raised slightly using a flat fill (`#161b22`) and a 1px solid border (`#30363d`).
- **Level 2 (Interactive/Hover):** When a row or card is hovered, the background shifts to `#21262d`.
- **Focus State:** Interactive elements (inputs, active buttons) use a 1px neon border (`#209dd7`) with no outer glow, maintaining the sharp, engineered aesthetic.

## Shapes
Shapes are disciplined and "Soft-Sharp." We use a very tight corner radius (4px) to suggest a robust, industrial feel. 

- **Containers & Inputs:** 4px (Soft) to maintain a professional look.
- **Buttons:** 4px. Avoid pill shapes unless used for specific status tags or badges.
- **Market Flashers:** Real-time price updates use a square background flash with 0px radius to emphasize the "grid" nature of the data.

## Components

### Buttons
- **Action Buttons:** Compact height (32px). Primary actions (AI Execute) use the Amethyst Purple. Technical actions use Cyber-Cyan.
- **Market Triggers:** "Buy" and "Sell" buttons use the semantic Green/Red but are constrained to the 4px corner radius.

### Input Fields
- Flat backgrounds (`#0d1117`) with 1px borders. Text is always monospaced. The cursor is a non-blinking block or a thin cyan line to mimic a command-line interface.

### Data Tables
- Row height is locked to 32px or 36px. Borders are used only between columns or at the bottom of rows (1px solid `#30363d`).
- **Price Flashes:** When a price updates, the background of the cell flashes green or red at 20% opacity, fading out over 500ms.

### AI Assistant Chat
- Message bubbles do not use heavy rounding. They are rectangular panels with a slight indent. 
- User messages: Bordered with Purple. 
- AI messages: Bordered with Cyan.

### Status Indicators
- Use small, glowing LEDs (8px circles) in the header to indicate "Live" connectivity. A slow pulse effect is used for the "AI Analyzing" state.

### UX Improvements
1. **Confidence Heat-Bar:** For every AI detection, include a small horizontal gradient bar (Purple to Cyan) showing the "Certainty Score."
2. **Standardized Glossary:** Ensure all terminology is technical and consistent (e.g., "Execution" instead of "Buying").
3. **Keyboard Shortcuts:** Visual tooltips should appear on hover showing shortcuts (e.g., `[B]` for Buy).