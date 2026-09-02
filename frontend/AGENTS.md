<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# Project UI rules

## Design tokens — single source of truth
- Every visual token (colors, fonts, spacing, radii, shadows, transitions) lives ONLY in `src/app/globals.css`. Re-theming the app must mean editing that one file.
- Components use Tailwind utility classes that reference those tokens — never hardcoded hex/rgb/px design values, never inline `style={{}}` for design-system properties.
- shadcn/ui components consume the same CSS variables (`--primary`, `--background`, `--radius`, ...) defined there. There is ONE palette — never introduce a second.

## Component layer — shadcn/ui + Radix
- `src/components/ui/` holds the generated shadcn primitives (button, dialog, select, dropdown-menu, table, badge, tooltip, tabs, sonner). They are owned code: edit freely, but keep them generic and app-agnostic so they stay portable.
- `src/components/<feature>/` holds app-specific compositions built FROM those primitives. Never rebuild a modal/select/toast/dropdown by hand once a primitive exists.
- Need a new primitive? `npx shadcn@latest add <name>` — don't hand-roll it.
- Style variants live inside the component (cva variants), not as ad-hoc className soup at call sites.

## Backend contract
- The FastAPI backend is a separate deployable, spoken to ONLY over REST via `src/lib/api.ts` (`/api/v1/...`). Never import backend code.
- `NEXT_PUBLIC_API_URL` in `.env.local` points at the backend origin (default `http://localhost:8000`).
