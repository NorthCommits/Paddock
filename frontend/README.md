# Paddock frontend

The Paddock web app. Next.js (App Router), TypeScript, Tailwind CSS v4, Radix UI primitives, Motion for animation, Lucide icons and cmdk for the command palette.

The design contract is in [`docs/DESIGN.md`](docs/DESIGN.md). Read it before changing any screen.

## Run it

You need Node 20 or newer and the backend running (see [`../backend/README.md`](../backend/README.md)).

```
cd frontend
cp .env.example .env.local    # optional, only if the backend is not on port 8000
npm install
npm run dev
```

Open http://localhost:3000.

| Variable | Purpose | Default |
|---|---|---|
| `BACKEND_URL` | Where Next forwards `/api` requests | `http://localhost:8000` |

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Development server |
| `npm run build` | Production build (also type checks) |
| `npm run start` | Serve the production build |
| `npm run lint` | Type check only (`tsc --noEmit`) |

## Structure

```
src/
  app/                 routes: landing, login, signup, and the signed-in app in (app)/
  components/ui/       base components in the shadcn style (button, input, badge, dialog, skeleton)
  components/landing/  landing page sections and demos
  components/          shell, command palette, auth form, password field, brand marks
  lib/                 API client (api.ts), class helper (utils.ts), password strength (password.ts)
public/brand/          logo, app icon and favicons
brand/                 logo sources and the concepts that were considered
docs/DESIGN.md        design contract
```

## Conventions

- Colours, radii and motion come from the tokens in `src/app/globals.css`. Components use semantic names (`bg-card`, `text-muted-foreground`, `bg-primary`), never raw colours.
- Components follow the shadcn style: `cva` variants, `cn()` for class merging, Radix primitives for behaviour.
- Animation uses `motion/react`. Everything respects reduced motion.
- The browser talks to the API through `/api`, a same-origin proxy defined in `next.config.ts`. Browser requests that change data send the CSRF value returned by sign up, log in and `GET /v1/me`.
- Copy: sentence case, no emoji, buttons name the action.

## Brand

The mark is an original "Gate P": a geometric P whose bowl has an open gate. Sources are in `brand/`, exports in `public/brand/`.
