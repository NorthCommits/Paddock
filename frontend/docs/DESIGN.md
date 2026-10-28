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

Colour follows the 60-30-10 rule, chosen for a bold, professional look:

- **60% neutral.** Paper (light) or ink (dark): backgrounds, cards, body text.
- **30% indigo.** Structure: the app sidebar, bands on the landing page, links, selection, focus rings, badges.
- **10% ember.** The one thing to press or watch: main buttons, live signals, the logo square. Ember is never used as text on paper (2.5:1); it is a fill with ink text on it (6.7:1), or text on ink and indigo.

Token names follow shadcn semantics, plus `signal` (ember), `band` (indigo section), `ink` (always-dark section) and `input-border`.

| Token | Light | Dark | Use |
|---|---|---|---|
| background | #F5F3EE | #0F1115 | Main surfaces |
| muted | #ECE9E1 | #0B0D10 | Grouped background, chips, code wells |
| card | #FFFFFF | #181B22 | Cards, sheets, popovers |
| foreground | #0F1115 | #F5F3EE | Primary text |
| muted-foreground | #565A66 | #A3A7B3 | Supporting text |
| subtle | #5F6370 | #8E93A0 | Placeholders, captions |
| border | rgba(15,17,21,0.14) | rgba(245,243,238,0.14) | Hairlines |
| input-border | #7C808C | #7C808C | Form field outlines (3:1 or better) |
| primary (indigo) | #3B33C9 | #A79BFF | Links, selection, focus, brand text |
| primary-foreground | #FFFFFF | #0F1115 | Text on primary |
| primary-soft | #E6E4FA | #25225F | Tinted panels, avatars, badges |
| signal (ember) | #FF6B4A | #FF6B4A | Main buttons, live signals |
| signal-foreground | #0F1115 | #0F1115 | Text on ember |
| band | #1E1B5E | #2D2A8C | Sidebar, landing bands |
| ink | #0F1115 | #0F1115 | Landing sections that stay dark in both themes |
| destructive | #C4122F | #FF7A85 | Destructive actions and errors |
| warning | #8A4B00 | #FFB347 | Warnings |

Every text and control pair is checked by `npm run check:contrast` (65 checks, WCAG AA, light and dark). It fails if a token change breaks a ratio. Run it after editing `globals.css`.

Type: Sora for display headings on the landing page and the logo word, an italic Instrument Serif for one emphasised word per heading, JetBrains Mono for small labels and code, and the system font inside the app.

Rules: one hot colour (ember) per screen. No colour as the only signal (status always has words or a shape). Text contrast at least 4.5:1, large text and icons at least 3:1. The theme follows the system setting. Motion stops or simplifies when the system asks for reduced motion, and anything that moves by itself has a pause button.

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
| Connect an agent | Get an agent publishing and answering requests | Four steps: token, environment variable, check, request loop (list, claim, complete) with copyable commands. |
| Comments panel | Discuss a page and ask the agent for changes | Side panel in the viewer, opened from the toolbar. Filter Open, Resolved, All. Threads with replies, edit, delete, resolve. @agent is highlighted and shows a status chip: Waiting for agent, Agent working, Done in vN, Dismissed. Editors can dismiss a request. Viewers can read only. Updates live from the page stream, with a refetch after any reconnect. |
| Tokens | Manage agent tokens | List with status, create sheet with scopes, show-once secret, revoke confirmation. |
| Account | See account details, sign out | |
| Webhooks | Send events to your own server | Settings tab. List with On or Off, filter summary, Send test (result shown inline), Turn off, History (recent deliveries with status and tries), Delete. New webhook sheet with every event or a grouped checklist. The signing secret is shown once with copy. |
| Command palette | Go anywhere, create a token, sign out | Cmd K or Ctrl K. |

Live updates of comments and requests follow with the real-time milestone.

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

1. **Accent colour.** Indigo and ember, 60-30-10, values in section 4. (Changed from warm green in the October 2026 revamp.)
2. **Landing page.** Built in the first release.
3. **Mark and wordmark.** An original geometric "P" whose bowl has an open gate (a space people and agents can enter), designed with the logo-design process (concepts in `brand/concepts`, chosen: Gate P). Wordmark is the symbol plus the word "Paddock" set live in the system font at semibold. The app icon is the ink mark on an ember rounded square. Assets: `brand/` (sources) and `public/brand/` (exports). It can be swapped by replacing those files.
4. **API access.** Same-origin proxy: Next rewrites `/api/:path*` to the backend, which keeps the login cookie simple in development and production.
