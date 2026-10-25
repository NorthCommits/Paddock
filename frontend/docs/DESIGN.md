# Paddock: Frontend design contract (v1)

Status: Accepted. First release built (see section 7).
Stack: Next.js (App Router), TypeScript, Tailwind CSS v4, Radix UI primitives, Lucide icons
Backend: see ../../backend/docs/SDD.md

This contract fixes the visual and interaction decisions before any screen is built, so every screen follows the same rules. A reviewer should be able to check any screen against this page.

## 1. What this product should feel like

Paddock is a quiet tool for reading, discussing and improving pages that agents publish. It should feel like a well-made Mac app that happens to run in a browser: calm, dense enough to be useful, precise, and keyboard friendly. The content (the published page) is the hero. The interface stays out of its way.

References for the feel, not for copying: Apple's own apps (Notes, Mail, Finder), Linear, Things 3, Raycast. Nothing is copied from Spacesheep or any other product: the name, words, layout and drawings are our own.

## 2. Sources used

- Apple Human Interface Guidelines principles, through the installed `macos-app-design` and `the-final-5-percent` skills. These are written for SwiftUI, so only the principles and measurements are used (hierarchy, spacing rhythm, motion, restraint, microcopy, accessibility). None of the Swift code is used.
- `frontend-ui-engineering`: the list of habits that make a UI look machine-made, plus states and accessibility rules.
- `apple-design` (dickwu/apple-design-skill, installed in `.claude/skills/apple-design`): the HIG reference with 123 pages. It is the review lens for every screen: each screen is checked against its pages on layout, typography, color, motion, accessibility and components before it is called done. Where it describes native controls, we apply the principle to the web equivalent.
- `logo-design` (kaankiziltug/logo-design-skill, installed in `.claude/skills/logo-design`): the process for the mark (brief, concepts, audit, small-size checks, export kit). Its reference library is third-party trademarks and is never traced.
- `shadcn` (shadcn-ui/ui skill): component conventions. Components live in `src/components/ui`, use `cva` variants, `cn()`, semantic tokens and `data-slot`. The shadcn CLI registry is not reachable from our build machine, so components are written by hand in the same style.
- `motion-framer` (freshtechbro/claudedesignskills): animation with the `motion` package (`motion/react`). Rules in section 4.
- `locomotive-scroll` (freshtechbro/claudedesignskills): smooth scrolling. The skill documents v4, which hijacks scrolling with transforms. We use v5 (built on Lenis) instead because it keeps the native scrollbar, sticky headers and in-view reveals working. Used on the landing page only, off for reduced motion, native momentum on touch.
- `ui-ux-pro-max`: its pre-delivery checklist and process only. Its generated palette (indigo with a serif and sans pairing) is rejected, because indigo and purple are exactly the look we are avoiding.

## 3. Principles

1. **Content first.** Chrome is neutral and thin. Colour is used for one thing: the action the person can take.
2. **One opinion per decision.** One accent colour, three corner radii, one spacing grid, one type scale. No one-off values.
3. **Mac conventions on the web.** Translucent sidebar, unified toolbar, hover states on everything clickable, right-click and menu actions, a command palette on Cmd+K (Ctrl+K elsewhere), and a shortcut hint wherever a shortcut exists.
4. **Gradual revelation.** Show what matters now. Details open in place, in sheets and popovers, not on new pages.
5. **Restraint in motion.** Motion explains where something came from or went. Frequent actions get subtle motion; rare milestones may get a moment.
6. **Every state is designed.** Loading, empty, error, success and no-permission states get the same care as the main view.

## 4. Design tokens

All values live as CSS variables and Tailwind theme entries. Raw colours and pixel values are not used in components.

### Colour (light / dark)

Token names follow shadcn semantics (`background`, `foreground`, `card`, `muted`, `primary`, ...). The neutrals are warm, like paper, so the green feels at home.

| Token | Light | Dark | Use |
|---|---|---|---|
| background | #FBFAF6 | #161715 | Main surfaces |
| muted | #F1EFE8 | #0F100E | Grouped background, chips, code wells |
| card | #FFFFFF | #222421 | Cards, sheets, popovers |
| foreground | #1D1D1B | #F3F2EC | Primary text |
| muted-foreground | #66655E | #A6A59C | Supporting text |
| subtle | #6C6B63 | #939289 | Placeholders, captions |
| border | rgba(40,36,20,0.12) | rgba(255,255,240,0.13) | Hairlines |
| primary | #2B7A4B | #5FBF85 | Buttons, links, selection |
| primary-foreground | #FFFFFF | #0B2415 | Text on primary |
| primary-soft | #E4F0E8 | #1E3326 | Tinted panels, avatars, badges |
| destructive | #D70015 | #FF453A | Destructive actions and errors |

Measured contrast (WCAG): foreground on background 16.2 and 16.0; muted-foreground on background 5.6 and 7.3, on muted 5.1 and 7.7; primary on background 5.0 and 8.0; white on primary 5.3; dark text on dark-mode primary 7.3; primary on primary-soft 4.5 and 6.0. Every new pair is checked by script before use.

Rules: one accent only. No gradients. No colour as the only signal. Text contrast at least 4.5:1, large text and icons at least 3:1. The theme follows the system setting.

### Typography

- Font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, "Segoe UI", Roboto, sans-serif`. On Apple devices this is SF Pro, with the correct optical sizes chosen by the system. No web font is downloaded and Apple's fonts are not bundled. On other systems the platform font is used.
- Mono: `ui-monospace, "SF Mono", Menlo, Consolas, monospace` for tokens, code and shortcuts.
- Letter spacing is left at the font's default, except large display text (negative) and all-caps labels (positive).
- Numbers that change use tabular figures.

| Role | Size / line | Weight |
|---|---|---|
| Display (marketing hero) | 56 / 60 | 600, tracking -0.03em |
| Title (page title) | 22 / 28 | 600 |
| Headline (section, card title) | 15 / 20 | 600 |
| Body (app) | 13 / 18 | 400 |
| Reading (long text, marketing body) | 17 / 26 | 400 |
| Secondary | 12 / 16 | 400, text-secondary |
| Caption | 11 / 14 | 400 |

Body text is left aligned everywhere. Only display titles and single call-to-action blocks are centred. Light weights are not used below 20px.

### Spacing, size and shape

- 4px grid: 4, 8, 12, 16, 20, 24, 32, 48, 64.
- Corner radii, three only: 6 (small controls, keyboard keys), 10 (buttons, inputs, cards), 14 (popovers, sheets, windows). Pills only for tags.
- Control heights: 28 (toolbar), 32 (default), 40 (forms and marketing). On touch screens controls are at least 44.
- Layout widths: sidebar 240, forms 360 to 440, settings content 640, lists 960.
- Borders are hairlines. Shadows only on floating layers (popovers, sheets, command palette), soft and low opacity, never pure black at full strength.

### Motion

Tools: the `motion` package for entrances, scroll reveals, shared-layout indicators (`layoutId`) and exits; CSS keyframes (`tw-animate-css`) for dialogs. Patterns in use: word-by-word headline rise, looping product illustration, scroll reveal with stagger, fence posts that grow in, an agent dot passing through the gate, spring-moving nav and tab indicators, page-to-page fade, list items entering in sequence. The landing page also has a scroll progress bar, a pinned three-step section, and interactive demos (a hero where you mention the agent and get a new version, click-to-comment lines, tabs of what agents can publish). Demos are labelled as simulations. Everything respects reduced motion (`useReducedMotion` and a global media query).


- Durations: 120ms (hover, press), 200ms (small reveals), 320ms (sheets and larger moves).
- Curves: enter `cubic-bezier(0.2, 0, 0, 1)`; sheets `cubic-bezier(0.32, 0.72, 0, 1)`; exits are faster than enters.
- Only transform and opacity are animated. Animations can be interrupted. Nothing bounces except a rare celebration.
- With reduced motion on, movement is replaced by a simple fade.
- No spinner for anything under 500ms. Loading content uses skeletons that match the final layout, so nothing jumps.

## 5. Layout and navigation

**App shell.** A left sidebar (collapsible), a thin toolbar on top of the content with the page title and actions, then the content. The sidebar and toolbar use the translucent material over the content. On narrow screens the sidebar becomes a slide-over sheet.

**Sidebar sections.** Pages, Requests (later), Connect an agent, Settings. The signed-in person sits at the bottom.

**Command palette (Cmd+K).** Go to any screen, create a token, switch theme, sign out. Later: search pages, jump to a version.

**Keyboard.** Every list supports arrow keys and type-to-select. Visible focus ring on every control (accent, 2px, offset 2px). Shortcut hints appear in menus and tooltips.

## 6. Components (built once, reused)

Button (default, secondary, ghost, link, destructive; sizes 28/32/40), TextField, PasswordField (show or hide toggle, strength meter on sign up), Checkbox, Segmented control, Badge, Tooltip, Menu and context menu, Sheet (modal), Popover, Command palette, Toast (only for passive confirmations, never for important results), Skeleton, EmptyState, Sidebar, Toolbar, CopyField (for tokens and snippets).

All interactive pieces come from Radix primitives for correct keyboard and screen reader behaviour, styled with our tokens.

## 7. Screens for the first release (built)

| Screen | Job | Notes |
|---|---|---|
| Landing | Explain Paddock and let people try the loop | Interactive hero (mention the agent, get a new version, switch versions), why Paddock, pinned three-step section, what agents can publish, click-to-comment demo, live and versioned feature cards, bring your own agent, safety, FAQ, closing call to action. Demos are labelled as simulations. Items not built yet are described as "on the way". |
| Sign up | Create an account | Password strength meter and show or hide toggle. Field errors from the API are shown in place. |
| Log in | Return to the workspace | Show or hide toggle. |
| Pages (home) | Show published pages | Empty state with an example preview. Pages arrive with the backend pages milestone. |
| Connect an agent | Get an agent publishing | Three steps with copyable snippets in curl, Python and Node. |
| Tokens | Manage agent tokens | List with status, create sheet with scopes, show-once secret, revoke confirmation. |
| Account | See account details, sign out | |
| Command palette | Go anywhere, create a token, sign out | Cmd K or Ctrl K. |

Screens for pages, versions, comments, requests and sharing follow as their backend milestones are finished.

## 8. Voice and microcopy

- Sentence case everywhere. Buttons name the action: "Create account", "Create token", not "Submit".
- Short, specific and warm. Say what happened and what to do next. No exclamation marks, no emoji, no jokes in errors.
- Errors: what went wrong, then how to fix it. Example: "That email is already registered. Try logging in."
- Destructive confirmations name the object: "Revoke 'my claude code'? Agents using it will stop working."
- Empty states explain the next step, never just "Nothing here".

## 9. Accessibility

WCAG 2.1 AA: contrast, keyboard access for everything, visible focus, labelled controls, error text next to the field and announced to screen readers, reduced motion, 44px touch targets on touch screens, no information by colour alone, correct heading order, and readable at 200 percent zoom.

## 10. Things this UI must not do

Indigo, purple or pink gradients; glow orbs and blurred blobs; the Inter font; large rounded corners on everything; stacked shadows; emoji as icons; uniform card grids and template hero sections; centred paragraphs; placeholder-only labels; "Submit" buttons; toasts for important results; guided tours; spinners for fast loads; lorem ipsum.

## 11. How the work is checked

1. Build and type check pass; lint passes.
2. Unit tests for the API client and logic; end-to-end tests for sign up, log in and token creation against a test backend.
3. Screenshots of every screen in light and dark at 375, 768, 1024 and 1440 widths (done by hand for the first release), reviewed against this page.
4. Contrast values checked by script.
5. Keyboard-only walk through each flow.
6. Final review with the accessibility and design critique skills.

## 12. Decisions made

1. **Accent colour.** Warm green, values in section 4.
2. **Landing page.** Built in the first release.
3. **Mark and wordmark.** An original geometric "P" whose bowl has an open gate (a space people and agents can enter), designed with the logo-design process (concepts in `brand/concepts`, chosen: Gate P). Wordmark is the symbol plus the word "Paddock" set live in the system font at semibold. The app icon is the white mark on an accent rounded square. Assets: `brand/` (sources) and `public/brand/` (exports). It can be swapped by replacing those files.
4. **API access.** Same-origin proxy: Next rewrites `/api/:path*` to the backend, which keeps the login cookie simple in development and production.
