---
name: Efficient Workflow System
colors:
  surface: '#f6faff'
  surface-dim: '#d2dbe4'
  surface-bright: '#f6faff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#ecf5fe'
  surface-container: '#e6eff8'
  surface-container-high: '#e0e9f2'
  surface-container-highest: '#dbe4ed'
  on-surface: '#141d23'
  on-surface-variant: '#414754'
  inverse-surface: '#293138'
  inverse-on-surface: '#e9f2fb'
  outline: '#717786'
  outline-variant: '#c1c6d7'
  surface-tint: '#005bc0'
  primary: '#0059bb'
  on-primary: '#ffffff'
  primary-container: '#0070ea'
  on-primary-container: '#fefcff'
  inverse-primary: '#adc7ff'
  secondary: '#555f6b'
  on-secondary: '#ffffff'
  secondary-container: '#d9e3f1'
  on-secondary-container: '#5b6571'
  tertiary: '#9e3d00'
  on-tertiary: '#ffffff'
  tertiary-container: '#c64f00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc7ff'
  on-primary-fixed: '#001a41'
  on-primary-fixed-variant: '#004493'
  secondary-fixed: '#d9e3f1'
  secondary-fixed-dim: '#bdc7d5'
  on-secondary-fixed: '#131c26'
  on-secondary-fixed-variant: '#3e4853'
  tertiary-fixed: '#ffdbcc'
  tertiary-fixed-dim: '#ffb695'
  on-tertiary-fixed: '#351000'
  on-tertiary-fixed-variant: '#7c2e00'
  background: '#f6faff'
  on-background: '#141d23'
  surface-variant: '#dbe4ed'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-base:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Hanken Grotesk
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 24px
  gutter-grid: 16px
  card-gap: 12px
  sidebar-width: 240px
  kanban-column-width: 300px
---

## Brand & Style

This design system is engineered for high-density information environments, specifically project management and complex data tracking. The brand personality is **utilitarian, precise, and systematic**, prioritizing clarity and speed of interaction over decorative flourishes. 

The aesthetic draws from **Corporate Modernism** with a focus on data density. It utilizes a restrained color palette, subtle tonal layering, and a clear hierarchy to reduce cognitive load in complex views like Kanban boards and Gantt charts. The goal is to create an environment that feels stable, reliable, and performant.

## Colors

The palette is derived from the core blue and light gray tones seen in professional enterprise tools. 

- **Primary Blue:** Used for primary actions, active states, and focus indicators.
- **Surface Grays:** A range of cool grays (from `#F8F9FA` to `#343A40`) provides structural contrast for sidebars, headers, and container backgrounds.
- **Status & Priority:** High-saturation semantic colors are used sparingly for badges and indicators to ensure they stand out against the neutral UI.
- **Interactive States:** Use a 10% darken/lighten overlay for hover and active states on primary elements.

## Typography

This system uses **Hanken Grotesk** for its exceptional legibility and modern, sharp terminals which suit a professional SaaS environment. 

- **Scale:** Sizes are kept small (13px-14px for body) to facilitate high-density data presentation without sacrificing readability.
- **Emphasis:** Use font weight (SemiBold/Bold) rather than size increases to denote hierarchy within cards and lists.
- **Monospace:** **JetBrains Mono** is reserved for technical identifiers, IDs, and timestamps to provide a distinct visual break from prose.

## Layout & Spacing

The layout follows a **structured grid system** optimized for horizontal scanning.

- **Sidebar Navigation:** Fixed at 240px. Uses a vertical stack with 4px spacing between nav items. Active states use a left-aligned 3px primary blue border.
- **Kanban Flow:** Columns are fixed-width (300px) with a 16px gutter. Cards within columns use a 12px vertical gap.
- **Density:** Padding within cards and list items is set to a compact 12px or 16px to maximize content visibility on smaller screens.
- **Breakpoints:** 
  - Desktop: 1440px+ (full sidebar + fluid content).
  - Tablet: 1024px (collapsed sidebar to icons).
  - Mobile: 768px (bottom navigation, full-width cards).

## Elevation & Depth

Depth is used functionally to indicate interactivity and z-index priority.

- **Level 0 (Background):** `#F8F9FA` for the main canvas.
- **Level 1 (Cards/Columns):** White background with a subtle `#000000 / 0.05` 2px blur shadow. 
- **Level 2 (Hover/Drag):** When a card is picked up or hovered, the shadow increases to a 8px blur with `#000000 / 0.1` opacity to indicate elevation.
- **Level 3 (Modals/Popovers):** Deep 16px shadows with a semi-transparent backdrop blur (`blur(4px)`) to focus the user's attention.
- **Outlines:** High-density inputs and secondary buttons use a 1px solid border (`#DEE2E6`) instead of shadows to remain "flat" and clean.

## Shapes

The design system utilizes **Soft (0.25rem)** roundedness to maintain a professional, organized look that feels modern but not overly casual.

- **Standard Elements:** 4px radius for buttons, input fields, and cards.
- **Status Badges:** 4px radius (square-ish) to differentiate from "pill-style" tags which may represent users or categories.
- **Selection Indicators:** Full-height rounded pill shapes are only used for global search bars or specific "New Project" call-to-action buttons.

## Components

### Kanban Cards
- **Structure:** 1px border (`#E9ECEF`), white fill, 12px internal padding.
- **Header:** Title in `body-base` (Bold), Priority badge in top-right.
- **Footer:** User avatar (24px) and date stamp in `data-mono`.

### Status Badges
- **Style:** Subtle background tints (10% opacity of the semantic color) with high-contrast text.
- **Success:** `#D4EDDA` background, `#155724` text.
- **Error:** `#F8D7DA` background, `#721C24` text.

### Buttons
- **Primary:** Solid `#007BFF`, white text, 4px radius.
- **Secondary:** Transparent background, `#007BFF` border and text.
- **Ghost:** No border/background until hover, used for utility actions in headers.

### Navigation Sidebar
- **Inactive:** `#6C757D` text and icons.
- **Active:** `#007BFF` text and icons, light blue background tint (`#E7F1FF`), and a leading 3px vertical bar on the left edge.

### Input Fields
- **Default:** White fill, 1px `#CED4DA` border.
- **Focus:** 1px `#007BFF` border with a 3px soft blue outer glow.