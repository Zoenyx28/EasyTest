---
name: Claymorphism QA System
colors:
  surface: '#f9f9ff'
  surface-dim: '#d0daf0'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d9e3f9'
  on-surface: '#121c2c'
  on-surface-variant: '#514442'
  inverse-surface: '#273141'
  inverse-on-surface: '#ebf1ff'
  outline: '#2D3748'
  outline-variant: '#d6c2bf'
  surface-tint: '#83514b'
  primary: '#83514b'
  on-primary: '#ffffff'
  primary-container: '#fdbcb4'
  on-primary-container: '#794943'
  inverse-primary: '#f7b7af'
  secondary: '#3a6470'
  on-secondary: '#ffffff'
  secondary-container: '#beeaf8'
  on-secondary-container: '#416a77'
  tertiary: '#006e2f'
  on-tertiary: '#ffffff'
  tertiary-container: '#51e77b'
  on-tertiary-container: '#00642a'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad5'
  primary-fixed-dim: '#f7b7af'
  on-primary-fixed: '#33100d'
  on-primary-fixed-variant: '#683a35'
  secondary-fixed: '#beeaf8'
  secondary-fixed-dim: '#a3cddb'
  on-secondary-fixed: '#001f27'
  on-secondary-fixed-variant: '#214c58'
  tertiary-fixed: '#6bff8f'
  tertiary-fixed-dim: '#4ae176'
  on-tertiary-fixed: '#002109'
  on-tertiary-fixed-variant: '#005321'
  background: '#f9f9ff'
  on-background: '#121c2c'
  surface-variant: '#d9e3f9'
  cta: '#22C55E'
  cta-dark: '#16A34A'
  lavender: '#E6E6FA'
  mint: '#98FF98'
  accent-orange: '#EA580C'
  bg-window: '#FFF9F5'
  bg-input: '#FFF0E9'
  broken: '#7C3AED'
typography:
  display-lg:
    fontFamily: Fredoka
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Fredoka
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  headline-sm:
    fontFamily: Fredoka
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
  body-md:
    fontFamily: Nunito
    fontSize: 12.5px
    fontWeight: '400'
    lineHeight: 17.5px
  body-semibold:
    fontFamily: Nunito
    fontSize: 12.5px
    fontWeight: '600'
    lineHeight: 17.5px
  label-md:
    fontFamily: Nunito
    fontSize: 11.5px
    fontWeight: '600'
    lineHeight: 16px
  label-sm:
    fontFamily: Nunito
    fontSize: 10.5px
    fontWeight: '600'
    lineHeight: 14px
  code:
    fontFamily: jetbrainsMono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 19px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  micro: 2px
  xs: 6px
  sm: 8px
  md: 12px
  lg: 20px
  xl: 24px
  header-height: 56px
  sidebar-width: 260px
---

## Brand & Style

The design system is built on the **Claymorphism** aesthetic, designed to transform a complex technical AI QA platform into a tactile, approachable, and highly legible workspace. It prioritizes clarity through physical metaphors: elements appear "pressed" into the surface or "floating" above it.

### Design Movement: Claymorphism
- **Tactile UI:** Every interactive element should feel like a physical object.
- **Bold Definition:** Strong, consistent outlines define boundaries, ensuring accessibility and a playful "sticker-like" quality.
- **Micro-interactions:** Navigation and actions rely on "sinking" and "lifting" animations rather than simple color shifts.
- **Warmth:** A departure from cold enterprise blues, utilizing warm whites and peach highlights to reduce cognitive fatigue during complex QA workflows.

**Target Audience:** QA Engineers, Product Managers, and DevOps Professionals who require a high-density information environment that remains visually stimulating and logically organized.

## Colors

The palette is divided into functional roles to guide the user through the AI-driven workflow.

- **Primary (Peach - #FDBCB4):** Used exclusively for focus, selection, and decorative accents. It indicates "AI Attention." Never used for destructive actions or primary CTAs.
- **CTA (Green - #22C55E):** The engine of the UI. All progress-related actions (Confirm, Generate, Run) use this color.
- **Secondary (Light Blue - #ADD8E6):** Used for supporting elements and secondary actions that don't drive the main workflow forward.
- **Neutral (Dark Slate - #2D3748):** Used for the core `--outline` token and primary text. In dark mode, this transitions to a soft off-white.
- **Decorative "Candy" Colors:** Lavender and Mint are reserved for low-priority background icons or categorization within the AI Chat Panel.

## Typography

The typography system balances the friendly, rounded nature of **Fredoka** for headings with the high legibility of **Nunito** for data-heavy正文 (body text).

- **Headings:** Use Fredoka with a semibold weight (600). It should feel soft but authoritative.
- **Body:** Use Nunito for all interface labels, buttons, and descriptions. For buttons, always use the semibold variant.
- **Data Density:** To accommodate the complex multi-step QA workflow, the base font size is set to a precise 12.5px. This allows for high information density without sacrificing readability.
- **Code:** Log outputs and test scripts must use JetBrains Mono for clear character differentiation (e.g., 0 vs O).

## Layout & Spacing

The layout uses a **fixed-fluid hybrid model** optimized for three-column AI collaboration.

- **The Three-Column Workflow:** 
    1. **Left (Fixed 260px):** Navigation and step tracking.
    2. **Center (Fluid):** Main workspace for Requirement/Story/Test editing.
    3. **Right (Fixed 320px - 400px):** AI Assistant and Quality Gate results.
- **Rhythm:** A 4px baseline grid ensures consistent vertical rhythm. Standard padding for cards is `12px` (md), while page-level gutters are `24px` (xl).
- **Header:** A fixed 56px height with a 3px bottom `--outline`.

## Elevation & Depth

This system rejects traditional blur-based elevation in favor of **Hard-Offset Shadows** and **Tonal Layering**.

- **Hard Shadows:** Interactive elements use `Npx Npx 0` shadows. This creates a "3D sticker" effect. 
    - Floating: Higher offset (6px).
    - Resting: Standard offset (4px).
    - Pressed: Minimal offset (1-2px) combined with a `translate(x, y)` transform to simulate physical pressure.
- **Tonal Layers:** The background uses a warm white (`--bg-window`), while active containers (Cards/Panels) use pure white (`--bg-card`) to pop forward.
- **Glassmorphism:** Reserved exclusively for the Header and Sidebar (`backdrop-filter: blur(20px)`) to provide a sense of transparency and modern stack depth without cluttering the workspace.

## Shapes

The shape language is "Bulky-Soft." High corner radii are used to reinforce the Claymorphism theme.

- **Radius-LG (24px):** Main modal panels and large content containers.
- **Radius-MD (16px):** Primary cards, buttons, and dropdown menus.
- **Radius-SM (12px):** Input fields and small utility buttons.
- **Full (999px):** Status tags, priority pills, and avatars.

**Outlines:** Every shape must be bound by a 2px or 3px `--outline`. This is the most critical visual rule for the design system.

## Components

### AI-Specific Components
- **AIReviewCard:** Uses the `Radius-MD` with a 2px `--outline`. It features a "Quality Score" in the top right using a colored pill. If the status is `WARNING`, the outline may shift to `--accent-orange`.
- **QualityGateCard:** A specialized card with a 3px left-border accent color corresponding to the score. It includes two primary actions: [Fix] (Secondary) and [Continue] (CTA Green).
- **ScoreRadar:** A simplified radar chart inside a `Radius-LG` container, using `--color-primary-soft` for the fill area and `--cta` for the data line.
- **AIChatPanel:** A fixed sidebar element. Messages use different background tones: AI responses in `--bg-soft` with a subtle `--lavender` icon; user inputs in `--bg-card` with an `--outline`.

### Collaboration Patterns
- **Versioning Indicators:** Small `11px` labels (e.g., "v3") placed in the top right of Story cards, using a `Radius-SM` and a light peach background to indicate AI optimization.
- **Review States:** Elements awaiting human confirmation must feature a "Wait Human" banner with a dashed `--outline` variant to signify incomplete state.

### Standard UI
- **Buttons:** 600 weight text, 3px `--outline`, and `--shadow-hard-md`. On hover, they translate 2px down/right.
- **Inputs:** Use `--bg-input` with an inset `shadow-hard-sm-pressed` to look "carved" into the clay surface.
- **BaseTag:** Capsule shaped with a 5px status dot and 1.5px outline.