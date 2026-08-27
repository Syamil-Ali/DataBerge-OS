# Data-Berge OS Agent Guide

This file applies to the entire repository. Treat it as the durable product and engineering contract for future work. User instructions for a specific task take precedence.

## Product identity

Data-Berge OS is a multi-tenant analytics workspace. It turns files, public datasets, and remote databases into governed profiles, relationship models, bounded analysis, chat exploration, charts, and executive reports.

The product should feel like a serious, approachable data tool. Prefer clarity, trust, and calm technical confidence over decorative complexity or generic dashboard styling.

## Product invariants

- Keep the public marketing landing page separate from the authenticated product.
- An authenticated user who reaches `/main` must return to `/workspace`; users without data are then routed to `/upload` and the Connect your data flow.
- Navigation must never silently log a user out. Logout is a separate, explicit action with confirmation.
- On the root Connect your data screen, show `Log out` when no workspace exists and `Back to workspace` when one does.
- Connector subpages use `Choose another source` to return to source selection.
- The Data-Berge brand on authenticated connector pages must not send users to the public landing page.
- Preserve user projects, datasets, chats, and reports across ordinary navigation.

## Connector architecture

There are two intentionally different ingestion paths:

1. Materialized sources
   - CSV, Excel, and OpenDOSM data are downloaded or uploaded, profiled, and materialized for DuckDB-backed analysis.
   - OpenDOSM requires a download before local processing.
2. Federated sources
   - Supabase and other online PostgreSQL databases remain remote.
   - Data-Berge stores connection metadata and queries bounded results on demand.
   - Do not download or duplicate an entire cloud database on the Data-Berge server.

New database providers should reuse the connector contracts and common PostgreSQL processing path. Provider-specific work belongs at connection discovery, authentication, and configuration boundaries rather than in duplicated query engines.

Federated connector rules:

- One registered remote table or view is one federated dataset until cross-table support is deliberately designed.
- Queries are read-only, bounded, timed out, and limited to the active logical `dataset` source.
- Do not permit writes, arbitrary joins, multiple statements, system-schema access, file functions, or sleep functions.
- Keep private/local destination blocking and DNS validation unless a narrowly scoped trusted-network mode is explicitly designed.
- Require TLS for public database endpoints.
- Use a dedicated read-only database role with only `CONNECT`, schema `USAGE`, and required `SELECT` grants.
- Encrypt stored credentials with `CONNECTOR_SECRET_KEY`. Never print, return, commit, or log database passwords or decrypted secrets.
- Changing `CONNECTOR_SECRET_KEY` makes previously stored connector credentials unreadable; treat it as a stable production secret.
- Supabase managed schemas such as `auth`, `storage`, `realtime`, and `vault` are not user analytics sources and must remain hidden from discovery.

## Multi-tenant and security rules

- Every project, connection, dataset, report, and chat operation must be scoped by the authenticated user and project.
- Never trust a resource ID without tenant ownership validation.
- Keep authentication tokens in HttpOnly cookies. Do not restore bearer tokens to local storage.
- Preserve CSRF checks for state-changing authenticated requests.
- Do not expose Supabase service-role keys, database owner credentials, WhatsApp secrets, OpenAI keys, or connector secrets to frontend code.
- Do not weaken connector SSRF protections or query restrictions merely to make a test connection pass.
- Prefer explicit allowlists and trusted deployment configuration over global security bypasses.

## Frontend visual system

### Design direction

Use a restrained, professional data-product language:

- Dark navy foundation
- Cyan/teal as the single primary accent
- Cool white and pale blue-gray surfaces
- Compact controls and deliberate whitespace
- Product-native diagrams and real interface previews
- Subtle motion that communicates state, hierarchy, or feedback

Do not introduce AI-purple gradients, generic glassmorphism, random warm neutrals, stock photos, oversized controls, or ornamental illustrations that do not explain the product.

### Typography

- Primary product and marketing body font: `DM Sans`.
- Display and section-heading font: `Bricolage Grotesque`.
- Technical identifiers, SQL-like values, schema details, and compact engineering metadata: `JetBrains Mono` when monospace materially improves comprehension.
- Do not introduce another font family.
- `frontend/src/styles/base.css` still contains an older Inter root fallback. Do not copy that fallback into new UI. Use the DM Sans/Bricolage system for new or substantially revised surfaces. A global legacy-font migration must be a deliberate standalone change.
- Buttons and form controls inherit the surrounding font. Do not allow browser-default button fonts.
- Use normal integer font sizes where possible. Avoid fractional sizes such as `13.5px` when they render soft or inconsistent.
- Body copy is normally 13-16px with comfortable line height. Compact metadata may be 9-12px if it remains legible.
- Prefer weights 400-600. Reserve 700+ for important headings and small uppercase labels.

### Core colors

Use the established palette before inventing new values:

- Primary ink/navy: `#172033`
- Deep navy: `#0B1624`
- Primary cyan: `#08B5CF`
- Dark teal: `#087F91`
- Page background: `#F8FAFC`
- Secondary text: `#64748B`
- Standard light border: `#E2E8F0`
- Soft cyan surface: values derived from `#08B5CF` at low opacity

Keep cyan as the main accent across a page. Red is reserved for destructive actions and logout hover/confirmation. Green is reserved for real success or healthy status.

### Shape, spacing, and elevation

- Standard controls: about 34-38px tall, 7-10px radius, 12-14px text.
- Primary cards: 12-16px radius. Compact internal panels: 7-12px radius.
- Pills are for statuses, tags, and compact filters, not every button or label.
- Use borders and whitespace before adding shadows.
- Shadows should be soft, cool, and low-opacity. Avoid heavy black shadows.
- Keep desktop content within the existing `max-w-7xl` or equivalent product container.
- Preserve the asymmetric feature hierarchy on the landing page: one strong primary visual with smaller supporting visuals.

### Product visuals

- Prefer visuals that explain actual application behavior: detected workbook tables, relationship graphs, metadata flow, charts, reports, and connector states.
- Do not use decorative background photographs behind explanatory copy.
- Keep previews understandable in one glance. Avoid internal metrics or jargon that a new visitor must decode.
- Example: `Table / Rows / Columns` is clearer for the workbook preview than completeness and coverage percentages.
- On mobile, remove redundant badges or secondary metadata instead of shrinking everything until it is unreadable.

### Copy and labels

- Use plain language and concrete outcomes.
- Avoid unexplained internal terms such as coverage, federation, semantic layer, or profiling scope in first-touch marketing copy.
- Button labels should describe the immediate action: `Test connection`, `Use table`, `Choose another source`, `Back to workspace`, `Log out`.
- Do not use a navigation label for a destructive or session-ending action.
- Keep capitalization consistent: sentence case for buttons and labels.

### Interaction and accessibility

- Every interactive element needs visible hover, focus, active, disabled, loading, empty, and error behavior when relevant.
- Menus and popovers must close on outside pointer press and `Escape`.
- Menu triggers must expose `aria-expanded`, `aria-haspopup`, and a menu relationship when open.
- Do not let clicks inside a menu trigger click-away dismissal before the action runs.
- Use semantic buttons for actions and links for navigation destinations.
- Maintain WCAG AA contrast for control labels and body copy.
- Respect `prefers-reduced-motion` and clean up every listener, observer, and timer.
- Use `100dvh` rather than `100vh` for full-height mobile layouts.
- Verify important surfaces at desktop, 390px mobile, and a narrow 320px viewport.

## Frontend implementation rules

- React 19, TypeScript, Vite, Tailwind v4 utilities, and the existing CSS layers are the current stack.
- Reuse `lucide-react`; do not mix icon families or hand-draw SVG paths for ordinary controls.
- Check `frontend/package.json` before adding a dependency. Prefer no new dependency for small interaction or layout work.
- Extract repeated behavior into focused components. For example, chart action menus share `ChartActionMenu` rather than duplicating open/close logic.
- Keep landing-specific composition in `frontend/src/landing.css` and `SampleLandingPage.tsx`.
- Keep workspace behavior in the focused components under `frontend/src/components/` and the existing style modules.
- Do not perform a broad visual rewrite when the request is a targeted repair.
- Preserve existing routes, labels, analytics-relevant field names, and information architecture unless the user explicitly requests a change.

## Reuse and anti-bloat rules

- Search the repository before creating a component, hook, utility, API wrapper, type, style, or backend service. Extend an existing suitable abstraction first.
- Reuse established components and behavior whenever their contract fits. Do not create a second version merely to avoid a small, compatible extension.
- Extract a shared component or utility when the same meaningful behavior appears twice, or when multiple near-identical implementations are already drifting.
- Keep shared APIs small and concrete. Do not add speculative options for hypothetical future use.
- Do not abstract a short one-off fragment solely to reduce line count. Extraction should improve reuse, testing, ownership, or comprehension.
- Keep components and functions focused on one responsibility. Split along real product or behavior boundaries, not arbitrary file-length targets.
- Prefer composition over boolean-heavy mega-components. If a component accumulates unrelated modes, separate the stable shared shell from mode-specific content.
- Reuse domain types from `frontend/src/types/`, connector contracts, repository helpers, and existing formatters instead of redefining local lookalikes.
- Centralize repeated interaction lifecycles such as click-away menus, dialogs, loading states, and error parsing.
- Reuse the established design tokens and CSS classes. Avoid repeated inline style objects, duplicated magic values, and nearly identical selectors.
- Keep data transformation out of JSX when it can be a named, tested formatter or utility.
- Do not add a dependency when the browser, React, Python standard library, or an installed package already solves the problem clearly.
- When replacing an implementation, remove superseded code, unused imports, dead styles, stale props, and obsolete tests in the same change.
- Do not leave `Old`, `New`, `V2`, `Temp`, or duplicate parallel implementations without a documented migration reason.
- Avoid broad helper modules that become dumping grounds. Place shared code in the narrowest domain-appropriate location.
- On the backend, add provider-specific behavior behind the existing connector contract rather than copying the full PostgreSQL discovery and query pipeline.
- Optimize for the smallest coherent change that fully solves the user-visible problem. Fewer lines are not automatically better, but duplicated or unreachable lines are defects.
- Before handoff, inspect the diff specifically for duplicate logic and unnecessary new abstractions.

## Backend implementation rules

- FastAPI delivery and product orchestration belong under `backend/app/`.
- Reusable storage-agnostic analytics behavior belongs under `backend/data_berge_core/`.
- Keep repositories tenant-scoped and use `backend/app/storage/database.py` only as the compatibility facade where required.
- Production metadata belongs in PostgreSQL. SQLite is a local development adapter.
- Production files belong in S3-compatible object storage. Local files are a development adapter.
- Long-running report and connector work should remain queue-compatible and not assume a single API process.
- Database migrations must be forward-only, repeatable where practical, and covered by storage tests.
- Return safe user-facing connector errors; log actionable internal causes without secrets.

## Important code locations

- `frontend/src/App.tsx`: authentication-aware routing and top-level workspace flow
- `frontend/src/routing/useAppRoute.ts`: browser history and route normalization
- `frontend/src/components/LandingPage.tsx`: authenticated data-source setup flow
- `frontend/src/components/SampleLandingPage.tsx`: public marketing landing page
- `frontend/src/landing.css`: current marketing/setup visual system
- `frontend/src/components/ChartActionMenu.tsx`: shared chart menu behavior
- `backend/app/connectors/`: federated connector contracts and PostgreSQL implementation
- `backend/app/services/federated.py`: remote dataset registration and sampled profiling
- `backend/app/api/connections.py`: connection and discovery API
- `backend/app/storage/`: tenant-scoped persistence and migrations
- `docs/ARCHITECTURE.md`: system architecture
- `docs/RUNBOOK.md`: production operations
- `docs/supabase-demo.sql`: safe Supabase connector demo dataset

## Verification requirements

Run checks in proportion to the change. Do not claim success without executing the relevant commands.

Frontend:

```powershell
cd frontend
npm run test:run
npm run build
```

For a focused interaction regression, add or run the relevant Vitest test. For layout changes, inspect the rendered page at desktop and mobile widths. Run Playwright E2E tests when routing, authentication, upload, or critical multi-page flows change materially.

Backend:

```powershell
cd backend
.venv\Scripts\python.exe -m compileall -q app data_berge_core scripts
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pip check
```

For connector changes, test connection, schema discovery, table discovery, preview, registration, permission failure, timeout, and unsafe-query rejection. Never use production credentials in automated tests.

## Change discipline

- Inspect the existing implementation before editing.
- Preserve unrelated user changes in a dirty worktree.
- Prefer focused patches over broad rewrites.
- Add regression coverage for bugs that can recur.
- Do not commit generated build output, local databases, uploaded data, logs, screenshots, `.env` files, or secrets.
- Keep documentation synchronized when behavior, configuration, architecture, or setup changes.
- At handoff, state what changed, what was verified, and any remaining limitation.

## Final review checklist

Before finishing a change, confirm:

- The behavior matches authenticated and unauthenticated flows.
- Navigation does not unexpectedly log out or lose user work.
- Desktop and mobile layouts remain readable.
- Fonts, colors, radii, and control sizing follow this guide.
- Copy is understandable without internal product knowledge.
- Popovers, dialogs, and menus have complete dismissal behavior.
- Secrets and tenant boundaries remain protected.
- Materialized and federated connectors remain correctly separated.
- Relevant tests and builds pass.
