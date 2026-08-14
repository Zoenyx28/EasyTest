---
name: Precision Logic
colors:
  surface: '#faf9ff'
  surface-dim: '#ccdaff'
  surface-bright: '#faf9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f3ff'
  surface-container: '#e9edff'
  surface-container-high: '#e1e8ff'
  surface-container-highest: '#d8e2ff'
  on-surface: '#051a3e'
  on-surface-variant: '#434654'
  inverse-surface: '#1d3054'
  inverse-on-surface: '#edf0ff'
  outline: '#737685'
  outline-variant: '#c3c6d6'
  surface-tint: '#0c56d0'
  primary: '#003d9b'
  on-primary: '#ffffff'
  primary-container: '#0052cc'
  on-primary-container: '#c4d2ff'
  inverse-primary: '#b2c5ff'
  secondary: '#535f73'
  on-secondary: '#ffffff'
  secondary-container: '#d4e0f8'
  on-secondary-container: '#576377'
  tertiary: '#7b2600'
  on-tertiary: '#ffffff'
  tertiary-container: '#a33500'
  on-tertiary-container: '#ffc6b2'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2ff'
  primary-fixed-dim: '#b2c5ff'
  on-primary-fixed: '#001848'
  on-primary-fixed-variant: '#0040a2'
  secondary-fixed: '#d7e3fb'
  secondary-fixed-dim: '#bbc7de'
  on-secondary-fixed: '#101c2d'
  on-secondary-fixed-variant: '#3b475b'
  tertiary-fixed: '#ffdbcf'
  tertiary-fixed-dim: '#ffb59b'
  on-tertiary-fixed: '#380d00'
  on-tertiary-fixed-variant: '#812800'
  background: '#faf9ff'
  on-background: '#051a3e'
  surface-variant: '#d8e2ff'
typography:
  display:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  h2:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  h3:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
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
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  code:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin: 24px
---

## Brand & Style

This design system is engineered for high-stakes B2B environments where precision and data density are paramount. The visual language follows a **Corporate / Modern** aesthetic with a strong emphasis on **Minimalism** to reduce cognitive load during complex requirement analysis. 

The system prioritizes clarity over decoration, using ample whitespace within components while maintaining high information density across the layout. The goal is to evoke a sense of "Quiet Intelligence"—a tool that stays out of the way until needed, providing a reliable and professional workspace for engineers, analysts, and project managers.

## Colors

The palette is anchored by "Trust Blue" (#0052CC), a high-contrast primary color that signals stability and action. 

- **Primary:** Used for primary actions, active navigation states, and progress indicators.
- **Neutral Stack:** A range of grays from `#091E42` (Deep Navy for text) to `#F4F5F7` (Light Gray for backgrounds and code blocks).
- **Semantic Logic:**
  - **Pending (待确定):** Amber (#FFAB00) to denote items requiring attention but not yet critical.
  - **Confirmed (已确定):** Emerald Green (#36B37E) for validated requirements and passed tests.
  - **Issue/Gap (已修复/有差异):** Sunset Red (#FF5630) for failed tests or requirement conflicts.
- **AI Accents:** Use a subtle gradient or a shift toward a softer violet-blue to distinguish AI-generated insights from manual entries.

## Typography

The typography system uses **Inter** for all UI elements to ensure maximum legibility across small font sizes in data tables. **JetBrains Mono** is introduced for requirement excerpts and technical documentation snippets to provide a clear visual distinction from standard interface text.

For technical documentation:
- Use `body-md` as the standard reading size.
- Use `code` for any technical requirement IDs or logic snippets.
- `label-md` should be used for status badges and table headers to provide clear structural hierarchy.

## Layout & Spacing

The layout follows a **Fluid Grid** model with a sidebar-heavy navigation structure. 

- **Density:** High-density spacing is used (4px base unit). In data tables, vertical padding is minimized to 8px to maximize the number of visible rows.
- **Breakpoints:** 
  - **Desktop (1440px+):** 12-column grid, 240px fixed sidebar.
  - **Tablet (768px-1439px):** 8-column grid, collapsed icon-only sidebar.
  - **Mobile:** Not prioritized for this system, but falls back to a single column with 16px margins.
- **Functional Grouping:** Use `spacing.md` (16px) to separate logical groups and `spacing.xl` (32px) to separate major sections of a workflow.

## Elevation & Depth

To maintain a clean, professional look, this design system uses **Tonal Layers** and **Low-contrast Outlines** instead of heavy shadows.

- **Level 0 (Background):** Primary background uses `#F4F5F7`.
- **Level 1 (Cards/Surface):** Pure white `#FFFFFF` with a 1px border of `#DFE1E6`. No shadow.
- **Level 2 (Modals/Popovers):** Pure white with a very soft ambient shadow: `0px 8px 12px rgba(9, 30, 66, 0.15)`.
- **Active State:** Elements being dragged or interacted with use a 2px Primary Blue border rather than a shadow to indicate focus.

## Shapes

The shape language is **Soft** (0.25rem), reflecting a precise, engineering-focused tool. 

- **Standard Elements:** Inputs, buttons, and status badges use `0.25rem` (4px) corner radius.
- **Cards & Containers:** Use `0.5rem` (8px) for larger structural components to provide a subtle visual softening of the complex interface.
- **AI Bubbles:** Use a slightly higher roundedness (12px) to differentiate "assisted" content from "structured" system content.

## Components

### Status Badges
- **待确定 (Pending):** Background `#FFFAE6`, Text `#FF8B00`, Left-aligned 8px dot in `#FFAB00`.
- **已确定 (Confirmed):** Background `#E3FCEF`, Text `#006644`.
- **已修复 (Fixed):** Background `#DEEBFF`, Text `#0747A6`.

### Data Tables
- Header background: `#F4F5F7`.
- Row height: 40px (Standard) or 32px (Compact).
- Vertical alignment: Top-aligned for long requirement text.

### AI Chat Bubbles
- AI-generated insights appear in a pale blue container (`#E6EFFC`) with a subtle `1px` border in `#B3D4FF`.
- Typography within AI bubbles uses `body-sm` with slightly increased line height (1.5) for readability.

### Requirement Excerpts
- Highlighted text logic: Use a background of `#F4F5F7` with a monospace font. 
- Example: `[REQ-001]` should always be wrapped in a code-style highlight.

### Buttons
- **Primary:** Solid Blue, white text.
- **Secondary:** Transparent background, Blue text, Blue border.
- **Ghost:** Transparent background, Grey text, no border (used for table row actions).