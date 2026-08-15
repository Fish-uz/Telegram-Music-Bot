---
name: Sonic Interface
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#ccc3d8'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#958da1'
  outline-variant: '#4a4455'
  surface-tint: '#d2bbff'
  primary: '#d2bbff'
  on-primary: '#3f008e'
  primary-container: '#7c3aed'
  on-primary-container: '#ede0ff'
  inverse-primary: '#732ee4'
  secondary: '#89ceff'
  on-secondary: '#00344d'
  secondary-container: '#00a2e6'
  on-secondary-container: '#00344e'
  tertiary: '#4edea3'
  on-tertiary: '#003824'
  tertiary-container: '#007650'
  on-tertiary-container: '#76ffc2'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#eaddff'
  primary-fixed-dim: '#d2bbff'
  on-primary-fixed: '#25005a'
  on-primary-fixed-variant: '#5a00c6'
  secondary-fixed: '#c9e6ff'
  secondary-fixed-dim: '#89ceff'
  on-secondary-fixed: '#001e2f'
  on-secondary-fixed-variant: '#004c6e'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-table:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-metrics:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 48px
  sidebar-width: 260px
  sidebar-collapsed: 72px
---

## Brand & Style
The design system is engineered for a high-performance Telegram bot management environment. The brand personality is "Technological Precision"—focused on speed, data integrity, and musical energy.

The aesthetic combines **Minimalism** with **Glassmorphism** accents. Most of the interface remains utilitarian and clean to prioritize data legibility, while interactive nodes and high-level metrics utilize subtle translucent layers and vibrant glows to evoke a "music-tech" atmosphere. The emotional response should be one of total control and professional efficiency.

## Colors
The palette is rooted in a "Deep Space" dark mode.

- **Primary (Neon Violet):** Used for primary actions, active navigation states, and key data trend lines.
- **Secondary (Electric Blue):** Used for informational accents, secondary buttons, and link states.
- **Success (Emerald):** Reserved for bot "Online" statuses and positive growth metrics.
- **Neutrals:** A range of Slate and Charcoal (ranging from `#020617` to `#334155`) provides the structural backbone, ensuring the vibrant accents pop without causing eye strain.

Backgrounds use a layered approach: the base level is the darkest, with containers becoming slightly lighter to indicate elevation.

## Typography
This design system employs a three-tier type system:
1. **Hanken Grotesk** for headlines to provide a modern, sharp startup feel.
2. **Inter** for all body copy and UI controls, ensuring maximum legibility across dense data tables.
3. **JetBrains Mono** for specialized metrics (like user IDs, timestamps, or bitrates) to reinforce the technical nature of the bot backend.

On mobile devices, `display-lg` should scale down to `32px` to prevent layout overflow. All data-heavy views should stick to `body-md` or `data-table` sizing to maximize information density while maintaining whitespace.

## Layout & Spacing
The layout follows a **Fluid Grid** model with fixed-width sidebars.

- **Desktop:** A 12-column grid with `24px` gutters. The sidebar is docked to the left.
- **Tablet:** A 6-column grid with `16px` gutters. The sidebar collapses into an icon-only rail or a hamburger menu.
- **Mobile:** A 4-column grid with `16px` margins. Layouts stack vertically.

Spacing is generous around "Metric Cards" to prevent cognitive overload. Tables use a strict "Compact" or "Standard" toggle: Standard uses `16px` vertical cell padding, while Compact uses `8px`.

## Elevation & Depth
Depth is created primarily through **Tonal Layering** and **Glassmorphism**, rather than traditional heavy shadows.

1. **Floor:** The main application background (`#020617`).
2. **Surface:** Cards and sidebar containers use a slightly lighter slate (`#0F172A`).
3. **Overlay:** Modals and dropdowns use a semi-transparent blur (Backdrop-filter: blur(12px)) with a subtle `1px` border of `white/10%` to simulate glass.
4. **Interactive Shadow:** Only primary buttons use a shadow, which is a soft, diffused glow colored like the button itself (e.g., a violet glow for a violet button) at 20% opacity.

## Shapes
The design system utilizes a **Soft (0.25rem)** base roundedness to maintain a professional, architectural feel.

- **Cards & Content Blocks:** Use `rounded-lg` (0.5rem) to differentiate from small UI controls.
- **Buttons & Inputs:** Use the base `rounded` (0.25rem) for a precise, "tooled" look.
- **Status Indicators:** Use `rounded-full` (pill) for status chips (e.g., "Active", "Processing") to distinguish them from interactive buttons.

## Components
- **Buttons:** Primary buttons use a solid Neon Violet fill with white text. Secondary buttons use a ghost style (border only) until hover.
- **Data Tables:** Headers are `label-caps` with a subtle bottom border. Rows feature a `white/5%` background hover state. No vertical lines; only horizontal separators for a clean horizontal flow.
- **Metric Cards:** Large numbers in `mono-metrics` font. A small sparkline (mini-graph) is often embedded at the bottom of the card using the Primary color.
- **Navigation:** Collapsible sidebar with active states marked by a thick `3px` left-border in Primary color and a subtle `white/5%` background highlight.
- **Status Chips:** Small, high-contrast badges with a `2px` dot indicating "Live" status (pulsing for active bot threads).
- **Input Fields:** Darker than the surface color with a `1px` border that transitions to Electric Blue on focus.
