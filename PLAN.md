# Plan: Groww Hackathon — Smart Market Watchlist (two-person, one-day, reconciled)

Inputs reconciled: `BUILD_SPEC.md` (primary design), Notion "Market Intelligence for Watchlists — Product & Signal Spec", Miro "Groww hackathon" architecture board, security pre-review of the design, verified free-tier terms (Neon, Upstash, Render) as of 2026-09-04.

Decisions locked by the user: free data path (Yahoo `v8/chart` + BSE cross-check, no Breeze/Kite); modular monolith + real Redis + Neon Postgres; two people, frontend/backend split; ~13 h; NSE/BSE only; FastAPI + React/Vite/TS.

---

## DESIGN TRAPS (surfaced verbatim from the planner — resolve before hour 0)

**1. Redis-as-job-queue will exhaust a metered free Redis before the demo, and the free host can't run the worker anyway.**
Upstash free = 500K commands/month. An idle arq/RQ worker polls ~2×/s ≈ 170K commands/day → budget gone in ~3 days, before any real work. Render's free tier has no free instance type for background workers or cron jobs, only web services, Postgres and Key Value. So "arq worker + Upstash" fails twice. Resolution: APScheduler in-process, Redis as cache only with pipelined writes, Miro's queue box documented as the production mapping.

**2. Notion's additive score (`>5% move: +3`) contradicts the thesis and would be refuted by our own evidence screen.**
On a day Nifty falls 5%, every stock scores +3 and the digest says "everything changed". The noise-reduction proof exists precisely to show that rule is noise. Shipping both is self-contradiction on stage. Resolution: BUILD_SPEC's multiplicative score, with Notion's tiers mapped onto it as `attention` labels.

**3. Seeding from the cloud host.** Peer clustering needs all ~150 universe symbols' 6-month bars in one pass. Yahoo throttles datacenter IPs harder; a half-failed seed on the host yields garbage clusters and no baselines, silently. Resolution: `--seed` runs only from a laptop against the Neon `DATABASE_URL`; the deployed process never backfills history, only refreshes quotes.

**4. Two people, one seen-state bug.** The FE person can innocently "mark seen on mount" and destroy the digest. Contract rule: no read endpoint mutates seen-state; only `POST /api/watchlist/seen` does. Regression-tested on the backend; the fixture-mode client has no such call.

**5. Demo clock.** Today is Friday 2026-09-04. Any demo after 15:30 IST or on the weekend is a closed market. `REPLAY_DATE` is mandatory, and `signal_events.trading_date` and RVOL's `minutes_since_open` must derive from the replay clock (`clock.py`), or dedupe and volume normalization both break under replay.

**6. (from security review) Username-only login is account takeover by typing a name.** `users.username UNIQUE` + `POST /auth/session {username}` means the second caller who types `demo` gets the demo user's token and can wipe the reviewer's digest via `/seen`. Resolution: session creation always creates a new user; the token is the only way back; cross-device is a resume link. Details in Security section.

---

## Scope

A returning user opens one screen and sees what meaningfully changed since they last reviewed, ranked, with a three-number decomposition (today / peers / stock-specific) on every changed card, a grounded one-paragraph briefing, and an evidence screen proving the engine beats a naive 2% rule on real 90-day data. Watchlist CRUD over a curated ~150-symbol NSE universe. Deployed publicly on a free stack so a reviewer can open it on a phone.

## Area(s) touched

Greenfield. `watchlist/backend` (FastAPI, SQLAlchemy/Alembic, APScheduler, Redis client, pandas/sklearn, httpx) and `watchlist/frontend` (Vite + React + TS + Tailwind + TanStack Query). Neon Postgres, Upstash or Render Key Value Redis, Render web service. OpenRouter for the two LLM features.

## Goals

- Returning user sees what changed since their explicit last review in one screen load (<1.5 s warm), ranked, decomposition on every changed card.
- Signals fire only on peer-adjusted, volatility-normalized, volume-confirmed moves; the evidence screen shows real 90-day counts for naive-2%, raw-z, and this engine on the demo watchlist.
- Zero-network demo: Wi-Fi off, every card renders with a `stale`/`closed` badge, cached briefing serves, evidence computes from bars on disk.
- Both people ship in parallel: FE has a rendering app by hour 4 on fixtures, hits real data by hour 7, never blocked on BE.
- `pytest` green including the fixture-contract test and the auth-scoping test; deployed URL works on a phone via resume link.

## Non-goals

- Multiple named watchlists, passwords/MFA/recovery, portfolio/P&L, notifications, price prediction, anomaly ML.
- RSI, Bollinger, SMA crossovers, gap signals, VWAP, per-symbol intraday volume curves (backlog with reasons in README).
- A real job queue/worker process, WebSocket push, Breeze integration (documented production path only).
- Symbols outside the seeded universe; on-demand history backfill.

## Conflicts resolved (Notion / Miro / BUILD_SPEC)

| # | Conflict | Resolution |
|---|---|---|
| 1 | Notion raw z (return vs 20D μ/σ) vs BUILD_SPEC peer-residual z | Ship both from the same arrays. Residual z fires `EXCESS_MOVE`, drives score, is the "Stock-specific" column. Raw z is exposed as `raw_z_score`, generates the Notion phrase "largest daily move in 3 months", and is a third baseline in the evidence screen (`raw_z_2`). Never fires a signal on its own. |
| 2 | Additive points vs multiplicative score | Multiplicative. Mapping: `z>2:+3` ≡ `EXCESS_MOVE`; `RelVol>2×:+3` ≡ `volume_multiplier`; `52w:+2` ≡ `level_bonus`; `price move >5%` dropped as an input. Notion's tiers survive as `attention: high \| notable \| quiet`. Raw score never shown. |
| 3 | "Distance from 20/50/200 DMA" absent in BUILD_SPEC | Add as context, not signal: `sma_distance_pct{20,50,200}` in baselines, shown in drawer and as sparkline overlays. A state, not a change. |
| 4 | RSI, Bollinger, crossover, gap, intraday H/L | In: intraday `day_high`/`day_low` on every quote. Backlog: Bollinger (≡ raw_z ≥ 2), RSI (state, no change narrative), crossover (won't demo), gap (covered by `LEVEL_BREAK` on prev H/L). |
| 5 | Miro queue + workers vs APScheduler | APScheduler in-process; Redis cache only. Miro's queue/workers map to `jobs/scheduler.py` → `jobs/refresh.py` → `engine/` sequentially in one process under a Redis `SET NX` lock. |
| 6 | Miro "Auth & Watchlist Service" | A module: `api/auth.py`, `api/watchlist.py`, `deps.py::current_user`. No gateway. |
| 7 | Notion "already shown alerts" vs `UNIQUE(symbol, signal_type, trading_date)` + seen state | Two layers, both needed. UNIQUE = symbol-level dedupe shared by all users (fan-in). Per-user "already shown" = `fired_at > last_seen_at` at digest time. Notion's snapshot time = `users.last_reviewed_at` (advanced by "Mark all reviewed"); per-symbol `user_symbol_state` advanced by "Got it". |
| 8 | Notion `P_prev = previous close OR last snapshot` | Two numbers, never conflated: `today_change_pct` (vs `prev_close`) and `change_since_seen_pct` (vs `last_seen_price`). New per-user read-time signal `SINCE_SEEN_MOVE`: fires when `|change_since_seen| / (σ_daily × √trading_days_away) ≥ 2` and `|change| ≥ 1.5%`. Makes "you were away 3 days, 4 of 12 did something" true even when no single day fired. |
| 9 | Notion examples are NVDA/AAPL | Demo data is NSE names: TATAMOTORS, HDFCBANK, RELIANCE, etc. |
| 10 | Miro API reads market data from Redis; BUILD_SPEC has a `quotes` table | Redis hash is the hot read path; `quotes` table written every refresh as last-known-good. Read order Redis → Postgres. App boots and serves with `REDIS_URL` unset. |

## Options considered

**Queue / scheduler**

- **A. APScheduler in-process + Redis pipelined cache (chosen).** `AsyncIOScheduler` in lifespan; every 60–90 s during 09:15–15:30 IST weekdays, `SET refresh:lock NX EX 55`, fetch watched-union, one pipeline of `HSET`s, compute signals, upsert events. Command budget: refresh only the watched union hot (~12–30 symbols at 90 s) and the rest warm at 5 min → ~300K/month, shown live on `/health/providers`. Pros: one process, works on Render free, Redis outage degrades to Postgres. Cons: not horizontally scalable without the lock (lock is in). Cost S (0.75 h).
- **B. arq worker + Redis queue (Miro literal).** Pros: matches diagram. Cons: worker polling alone kills Upstash free in ~3 days; no free worker instance on Render; second deploy; nothing in the demo needs async fan-out. Cost M (+1.5–2 h). Rejected.
- **C. Postgres as queue (`FOR UPDATE SKIP LOCKED`).** Pros: durable, no Redis cost. Cons: polling Neon defeats scale-to-zero unless market-gated, at which point it's A with a table. Cost M. Rejected.
- **D. Docker Redis locally, Upstash/Render KV deployed.** Adopted as complement to A.

**Scoring**

- **1. Notion additive points.** Trivially explainable; but raw thresholds score market-wide days and contradict the evidence screen. Rejected.
- **2. BUILD_SPEC multiplicative (chosen).** `min(|z|,6) × volume_multiplier + level_bonus`. Fires only on stock-specific, normalized, confirmed moves; volume amplifies. Number never shown.
- **3. Additive over BUILD_SPEC primitives.** Loses the magnitude gradient (z=2.1 ties z=5). Rejected; tier mapping gives Notion its vocabulary without the flaw.

**Auth (from security review)**

- **1. Username lookup login (as spec'd).** Guessable identifier doubles as credential. Rejected for public deploy.
- **2. Always-create + opaque token + resume link (chosen).** ~30 min, no password story intact, demos better ("scan this, it's on your phone").
- **3. Magic-link email.** Needs an email provider and an inbox on stage. Rejected for the timebox.

## Chosen approach

- APScheduler in-process; Redis is a pipelined cache with a refresh lock; app runs with Redis absent. Miro's queue/workers are the documented production mapping (arq is a one-hour swap because job functions are plain async functions).
- Multiplicative score, Notion tiers as `attention` labels, raw score hidden. Both z-scores; residual is the only one that fires. MA distance and intraday H/L as context.
- Per-user `SINCE_SEEN_MOVE` computed at read time.
- Contract frozen at hour 0.5, enforced by a Pydantic-validated FE fixture and generated `types.ts`.
- Auth: `POST /auth/session` always creates a user and returns an opaque token; no login-by-username; resume link for cross-device; every user-scoped query keyed off the token-derived `user_id`.
- Public-API hardening scheduled as backend line items: symbol allow-list at every boundary, cache-first catalysts with fetch lock and own-watchlist gate, per-IP/per-user rate limits and a global daily LLM ceiling, injection validators on briefing output, briefing rendered as plain text.
- Differentiation-layer priority for two people: evidence proof (P0) → grounded briefing (P1) → catalysts incl. "no catalyst found" (P1) → NL rules (P2, declared first cut).

## API contract (frozen at hour 0.5)

Conventions: base `/api`; `Authorization: Bearer <token>` on everything except `POST /auth/session`, `GET /health`; timestamps ISO-8601 with `+05:30`; percentages signed floats ×100; errors `{"error": {"code", "message"}}` with 400/401/404/409/429; **all explanation strings are generated server-side**; **no GET mutates seen-state**; **no endpoint accepts a user identifier from path, query, or body** — `user_id` comes only from the token.

Shared objects:

```
Quote   { price, prev_close, day_high, day_low, volume, as_of, source: "yahoo"|"bse",
          staleness_seconds, confidence: "fresh"|"delayed"|"stale"|"disputed"|"closed",
          alt: { price, source, as_of } | null, divergence_pct: number | null }

Signal  { type: "EXCESS_MOVE"|"VOLUME_CONFIRMED"|"LEVEL_BREAK"|"SINCE_SEEN_MOVE"|"USER_RULE",
          headline, detail, fired_at, rule_id: string | null }

Item    { symbol, name, quote: Quote,
          today_change_pct, peer_change_pct, residual_pct,
          z_score, raw_z_score, rvol, rvol_is_approximate: bool,
          change_since_seen_pct: number | null, last_seen_at: string | null,
          attention: "high"|"notable"|"quiet", is_changed: bool, low_confidence: bool,
          signals: Signal[],
          levels: { high_52w, low_52w, prev_high, prev_low },
          sma_distance_pct: { "20": n, "50": n, "200": n },
          peer: { method: "cluster"|"beta", cluster_id: string|null, size: int, members: string[] },
          catalyst_status: "not_fetched"|"pending"|"found"|"none_found"|"unavailable" }

Rule    { symbols: string[] | "all", all: [{ field, op: ">="|"<="|"==", value }] }
        fields: residual_pct, abs_residual_pct, z_score, rvol, peer_return_pct,
                abs_peer_return_pct, level_break, has_catalyst
```

Endpoints:

```
POST   /auth/session      {display_name}            → 201 {token, user:{id, display_name}}
                                                      ALWAYS creates a new user. 429 after 10/hour/IP.
GET    /auth/me                                      → 200 {id, display_name, last_reviewed_at|null, resume_url}
DELETE /auth/session                                 → 204  drops the user's rows (README delete path)

GET    /watchlist/digest                             → 200 { now, market_status: "open"|"closed"|"pre_open",
          replay_date|null, away_duration_seconds|null, last_reviewed_at|null,
          changed_count, total_count, items: Item[] (changed by score desc, then quiet alpha),
          providers_degraded: bool }
POST   /watchlist/items   {symbol}                   → 201 Item   (400 not_in_universe, 409 already_added, 400 watchlist_full at 50)
DELETE /watchlist/items/{symbol}                     → 204
POST   /watchlist/seen    {symbols: string[]|"all"}  → 200 {marked, reviewed_at}   (≤100 symbols, each must be in caller's watchlist)
GET    /watchlist/briefing                           → 200 {text, source: "llm"|"template", generated_at, was_cached}

GET    /symbols/search?q=                            → 200 [{symbol, name, exchange}]  (≤10, local table only, q ≤ 32 chars)
GET    /symbols/{symbol}/history?days=90             → 200 {bars:[{date, close, volume, today_change_pct, residual_pct}], levels, sma:{"20":[],"50":[],"200":[]}}
GET    /symbols/{symbol}/peers                       → 200 {method, cluster_id, size, peer_change_pct, members:[{symbol, name, today_change_pct}]}
GET    /symbols/{symbol}/catalysts                   → 200 {status: "found"|"none_found"|"unavailable"|"pending", fetched_at, items:[{headline, source, url, published_at}]}
                                                      cache-first; upstream fetch only if symbol is in caller's watchlist AND surfaced (is_changed); 5/min/IP

POST   /rules/compile     {text}                     → 200 {rule: Rule|null, preview: string|null, error: string|null}
                                                      text ≤ 200 chars; 5/hour/user, 20/day/user, global 30/day → 429 rate_limited
POST   /rules             {nl_text, rule: Rule}      → 201 {id, nl_text, rule, preview, enabled, created_at}   (≤10 rules/user; symbols re-validated vs universe)
GET    /rules                                        → 200 [{id, nl_text, preview, enabled, created_at, matched_today: string[]}]
DELETE /rules/{id}                                   → 204

GET    /evidence/noise-reduction?days=90             → 200 {days, symbols_count, from_date, to_date, computed_at,
          naive_pct_2:{alerts}, raw_z_2:{alerts}, engine:{alerts},
          suppressed:{total, market_wide, below_floor, unconfirmed_volume},
          caught_extra:[{symbol, date, today_change_pct, peer_change_pct, residual_pct, z_score, rvol}]}

GET    /health                                       → 200 {ok: true}   (keep-warm; no DB/Redis touch)
GET    /health/providers                             → 200 {providers:[{name, circuit, last_success_at, consecutive_failures}],
          scheduler:{enabled, last_refresh_at, next_refresh_at, market_status},
          redis:"ok"|"down"|"disabled", redis_commands_estimate_month, db:"ok"|"down"}
                                                      no URLs, headers, key prefixes, or exception strings
```

Every `{symbol}` in a path or body is validated against the `symbols` table (404 `not_in_universe` otherwise) and regex `^[A-Z0-9&-]{1,20}\.(NS|BO)$`. Per-IP global bucket ~30 req/min. CORS: explicit origin allow-list; bearer header + `localStorage`; no cookies.

Sync artifact: BE exports `backend/openapi.json` at hour 1; FE generates `src/api/types.ts` with `openapi-typescript` and commits it. FE fixtures are validated by `tests/test_fixture_contract.py`. Any contract change after 0.5 h = a message to the other person + regenerated `types.ts`.

## File-level breakdown

Backend `watchlist/backend/app/`:
- `main.py` — app factory, lifespan (scheduler, Redis ping), CORS allow-list, global exception handler (no tracebacks), static mount of built FE in prod.
- `config.py` — env settings: `DATABASE_URL`, `REDIS_URL`, `OPENROUTER_API_KEY/MODEL`, `YAHOO_RPS`, `BSE_ENABLED`, `REPLAY_DATE`, `REFRESH_HOT_SECONDS`, `SCHEDULER_MARKET_HOURS_ONLY`, `CORS_ORIGINS`, `DEBUG=false`.
- `clock.py` — `now()` honoring `REPLAY_DATE`, IST helpers, `market_status()`, `minutes_since_open()`.
- `db.py` — engine (pool 3, `pool_pre_ping`, `echo=False`), session dependency.
- `cache.py` — get/mget/pipeline-set/lock/incr over Redis (`rediss://`), in-memory fallback, command counter, token-bucket + circuit-breaker state.
- `ratelimit.py` — per-IP and per-user buckets, global daily LLM counter (`INCR` on date key).
- `models.py` — BUILD_SPEC §10 tables with: `users(id, display_name, last_reviewed_at, created_at)` (no UNIQUE on name), `sessions(token_hash PK, user_id, expires_at)`, `baselines` + `sma_20/50/200`, `raw_mean_20`, `raw_sigma_20`, `sigma_daily_90`.
- `schemas.py` — the contract as Pydantic; bounded rule values (`parse_constant` rejects NaN/Inf; `rvol ∈ [0,100]`, `z ∈ [0,20]`, `*_pct ∈ [-100,100]`, `level_break` Literal), symbol regex, `display_name ^[a-z0-9_-]{3,32}$` NFKC-casefolded.
- `deps.py` — `current_user` from bearer token (sha256 lookup, expiry check); `validated_symbol` (universe allow-list).
- `api/auth.py`, `api/watchlist.py`, `api/symbols.py`, `api/rules.py`, `api/evidence.py`, `api/health.py` — thin routers.
- `providers/base.py` (`QuoteProvider` protocol), `yahoo.py`, `bse.py`, `nse_announcements.py`, `yahoo_rss.py` — all params via `params=`, never f-strings; `providers/reconcile.py` — divergence → confidence.
- `engine/baselines.py`, `peers.py`, `residual.py`, `volume.py`, `levels.py`, `signals.py` (incl. raw-z phrasing, `SINCE_SEEN_MOVE`), `score.py`, `rules_eval.py` (deterministic eval + `render_plain_english`), `digest.py` (quotes → signals → seen → rules → sort, all filtered on `user_id`).
- `ai/client.py` (OpenRouter, `max_tokens`, never includes user identifiers), `ai/briefing.py` (headline sanitizer, UNTRUSTED delimiting, numeric validator, injection validators: ≤600 chars, no URL/@/markdown link, banned words, no foreign symbols; template fallback; `briefing_cache`), `ai/rules.py` (LLM → JSON → Pydantic → universe re-validation; error text truncated to 200), `ai/prompts.py`.
- `evidence/replay.py` — 90-day replay: naive 2%, raw z ≥ 2, engine; suppression reasons; `caught_extra`.
- `jobs/refresh.py` (watched-union fan-in, tiering, pipelined writes, quote+signal in one transaction, `ON CONFLICT DO NOTHING`), `jobs/daily.py` (`--seed`, baselines, weekly clusters, bar cache keyed by DB row not by symbol string), `jobs/scheduler.py` (APScheduler, `max_instances=1, coalesce=True`, Redis lock, market-hours gate).
- `data/universe.json` — ~150 NSE symbols with names.
- `alembic/` — one initial additive migration; `scripts/seed_demo.py` — synthetic demo user, 12 symbols, `last_reviewed_at` backdated 3 days, briefing pre-warm.
- `.gitignore` — `.env`, `*.db`, `uv.lock` committed, `pip-audit` once before deploy.

Frontend `watchlist/frontend/src/`:
- `api/client.ts` (bearer header, `VITE_API_MODE=fixture|live`), `api/types.ts` (generated).
- `fixtures/` — `digest.json` (4 changed covering every signal type, one `disputed`, one `stale`, one `low_confidence`, 8 quiet), `briefing.json`, `evidence.json`, `history.json`, `peers.json`, `catalysts.{found,none_found,unavailable}.json`, `rules.json`, `health.json`.
- `hooks/` — `useSession` (token in `localStorage`, reads `?t=` on load), `useDigest`, `useBriefing`, `useSeen` (optimistic), `useSymbolSearch`, `useHistory`, `usePeers`, `useCatalysts` (enabled on drawer open), `useRules`, `useEvidence`, `useHealth`.
- `pages/Start.tsx` (display name → session → shows resume link + copy/share), `Watchlist.tsx`, `Evidence.tsx`.
- `components/` — `DigestHero` (briefing as a text node, never HTML), `StockCard`, `Decomposition`, `SignalChips`, `FreshnessBadge`, `QuietTable`, `SymbolSearch`, `DetailDrawer`, `Sparkline` (inline SVG), `PeerPanel`, `CatalystList`, `RuleComposer` (compile → preview sentence → confirm; `rate_limited` state), `ResumeLink`, `StateBanner` (degraded / closed / replay / first-visit / quiet day).
- `lib/format.ts` — away-duration humanizer, signed percent, INR.

## Execution plan — two tracks

| Hour | Backend | Frontend | Sync |
|---|---|---|---|
| 0–0.5 | Scaffold `uv`, FastAPI, Alembic, Neon dev branch, Docker Redis; `.gitignore` first; commit `schemas.py` | Scaffold Vite+TS+Tailwind+TanStack Query+Router; hand-write `types.ts` from contract | **S1 Contract freeze** (0.5 h) |
| 0.5–1.5 | `clock.py`, `cache.py`, `ratelimit.py`, `providers/yahoo.py`; **start `--seed` against Neon from laptop at ~1.5 h in a second terminal** | `client.ts` fixture mode; author all fixtures; regenerate `types.ts` from `openapi.json` (~1 h) | |
| 1.5–3.5 | `engine/*` incl. peers, raw z, SMA, score, `SINCE_SEEN_MOVE`; unit tests green | Start page + session + resume link; Watchlist skeleton, `DigestHero`, `StockCard`, `Decomposition`, `SignalChips`, `FreshnessBadge` | |
| 3.5–5.5 | `models.py`, migration; **auth: always-create, token hash, expiry, `current_user`, 10/hr/IP**; watchlist CRUD with **universe allow-list + cap 50**; seen (≤100, own-watchlist); `engine/digest.py` filtered on `user_id`; `GET /digest` live; **`test_auth_scoping` green** | `QuietTable`, attention tiers, "Got it" / "Mark all reviewed" optimistic; `SymbolSearch` | **S2 First fixture render** (4 h) |
| 5.5–6.5 | `jobs/scheduler.py` refresh + lock + tiering + dedupe + market hours + replay clock; one-transaction writes | Evidence page on fixture | |
| 6.5–7.5 | BSE cross-check, reconcile, confidence; `/health`, `/health/providers` (thin); `search` (local, LIKE-escaped), `history`, `peers` | Drawer shell, `Sparkline`, levels, MA distance | **S3 First real-data render** (7 h): flip `VITE_API_MODE=live`; `test_fixture_contract` green |
| 7.5–8.5 | `evidence/replay.py` + endpoint (P0) | `PeerPanel`, `CatalystList` skeleton, "no catalyst found" headline | |
| 8.5–9.75 | `ai/briefing.py`: client (`max_tokens`, no user ids), headline sanitizer + UNTRUSTED delimiting, numeric + **injection validators**, template, cache | `RuleComposer` (compile → preview → confirm → list), `USER_RULE` chips, `rate_limited` state | |
| 9.75–11.25 | Catalysts: `yahoo_rss`, `nse_announcements`, **cache-first + `SET NX` fetch lock + own-watchlist/surfaced gate + 5/min/IP**; `ai/rules.py` compile + **rate limits + global ceiling** + `rules_eval.py` in digest | States: empty, loading, degraded, disputed (both prices), closed, quiet day, first visit, replay banner | |
| 11.25–12.25 | Deploy: Render web + Upstash/Render KV (`rediss://`) + Neon prod; env; keep-warm cron on `/health`; `seed_demo.py`; `pip-audit`; `git ls-files \| grep -i env` empty | `pnpm build` served by FastAPI; phone → resume link → add symbol → laptop | **S4 Integration** (11.5 h): full B.4 walkthrough on deployed URL |
| 12.25–13 | Pre-demo checklist, real evidence numbers into README, LLM-outage rehearsal, README security/ToS/privacy disclosures | Screenshots, polish, README demo section | Rehearse once with Wi-Fi off |

Stop-anywhere cuts, in order: NL rules → catalysts → BSE cross-check → detail drawer. Never cut: digest, decomposition, evidence, auth hardening (C1/C2), symbol allow-list.

Migrations: one additive revision day one; later changes are new additive revisions (`downgrade -1` is the rollback). Feature flags: empty `OPENROUTER_API_KEY` → templates; `BSE_ENABLED`; `SCHEDULER_MARKET_HOURS_ONLY`; empty `REDIS_URL` → memory cache. Observability: structured log per provider call (count, latency, status), per refresh (symbols, fired, deduped), per LLM call (model, tokens, `rejected_reason`), `/health/providers` as operator page; never log `(display_name, watchlist)` together, never log config or headers.

## Security (from the pre-review; must-fix items are in the schedule above)

**Critical**
- **C1 Username-only sessions = account takeover.** Fixed by always-create + opaque `secrets.token_urlsafe(32)` stored as sha256 + `expires_at` + resume link + 10/hr/IP on creation. README must state: "There is no authentication. Anyone holding a session link has full access to that watchlist. Do not put anything you care about in it."
- **C2 No endpoint states where `user_id` comes from.** Fixed by `deps.current_user`; no handler accepts a user identifier; every user-scoped query filters on it; `test_auth_scoping`.
- **C3 Redis is a network service.** `rediss://` + token (Upstash default). No queue library → no pickle surface; if arq is ever added, pin JSON serializer and Pydantic-validate the job envelope.

**High**
- **H1 `/rules/compile` is an unmetered LLM proxy** against a 50/day budget. Session required; 5/hr, 20/day per user; global 30/day; `text ≤ 200`; `max_tokens`; 429 state in UI.
- **H2 `/catalysts` fans out to rate-limited upstreams on demand** — looping 150 symbols gets the deploy IP blocked. Cache-first, `SET NX` lock, own-watchlist + surfaced gate, 5/min/IP; `search` is local-only.
- **H3 In-process rate limiter vs multi-process.** Single process + APScheduler makes this moot today; bucket and breaker state live in `cache.py` so a second replica is safe.
- **H4 Prompt injection via headlines; numeric validator doesn't catch it.** Delimit as UNTRUSTED + system line; sanitize (control chars, 160-char truncate, drop URLs); output validators (≤600 chars, no URL/@/markdown link, banned words enforced in code, no foreign symbols); render as plain text. Numeric check defends hallucination; these defend injection — README names both.
- **H5 Symbol strings reach provider URLs and a disk cache path.** Allow-list at every boundary; regex defense-in-depth; bar cache keyed by DB row; `params=` only; `/seen` ≤100 and own-watchlist.

**Medium (one-liners, all in the file breakdown)** — rule values bounded and `NaN/Inf` rejected; rule symbols re-validated; ≤10 conditions, ≤20 symbols, ≤10 rules/user; reject `"all"` + always-true; model error text truncated; never put `display_name`/`user_id` in an LLM payload (this is the honest answer to the OpenRouter-free-tier data policy — verify their current terms before the README claims a posture, and disclose symmetrically); `DEBUG=false`, `echo=False`, no tracebacks; `/health/providers` thin; `.gitignore` before first commit; CORS allow-list + bearer + `localStorage`; refresh dedupe key with `SET NX`; poison-symbol DLQ after 3 failures → `is_active=false`, DLQ depth on health; watchlist cap 50; `REPLAY_DATE` env-only; LIKE escaping on search; synthetic demo user, not a real name; `DELETE /auth/session` as the delete path.

**Acceptable with README disclosure:** no passwords/MFA/recovery (given C1); no encryption beyond provider default; ToS-noncompliant sourcing — disclosed, unlisted, time-boxed, taken down after review, and the `Referer`/`User-Agent` headers described honestly as working around access controls, with an explicit refusal of proxy rotation, CAPTCHA solving, or bypassing NSE's Akamai block; at-most-once jobs with idempotent handlers.

## Test strategy

Unit (no network; fixture bars in `tests/fixtures/bars/*.json` recorded from one real seed):
- `test_residual`, `test_peers`, `test_signals`, `test_volume`, `test_reconcile`, `test_dedupe`, `test_rules`, `test_briefing` — per BUILD_SPEC §14.
- `test_raw_z` — raw z ≥ 2 on a market-wide day does not fire `EXCESS_MOVE`; residual does on the stock-specific day.
- `test_since_seen` — 3-day drift beyond √t-scaled σ fires; same drift over 30 days doesn't; null `last_seen_at` → null.
- `test_score` — z=3/rvol=3 outranks z=5/rvol=1 + level; tiers.
- `test_clock` — `REPLAY_DATE` pins `trading_date`, `market_status`, `minutes_since_open`.
- `test_cache` — Redis down → memory fallback; batch writes use one pipeline (command count asserted).
- `test_replay_evidence` — synthetic 90 days: naive, raw-z, engine counts; `caught_extra` has the 1.2%/4σ case.
- `test_fixture_contract` — every FE fixture parses into its response model.
- **`test_auth_scoping`** — no token → 401 on every endpoint except session/health; another user's valid token → only their own rows on digest/items/rules/seen; second `POST /auth/session` with the same name → different `user_id`.
- **`test_symbol_allowlist`** — `../etc`, `RELIANCE.NS?range=max`, unknown symbol → 404 on items/history/peers/catalysts/seen.
- **`test_rate_limits`** — 6th compile in an hour → 429; global ceiling → 429; 11th session/hour/IP → 429.
- **`test_briefing_injection`** — headline "Ignore prior instructions… http://evil" → output containing a URL or banned word is rejected → template served.

Integration (`-m integration`, Neon dev branch + Docker Redis): seed fixture bars → refresh → digest for backdated user → GET does not advance seen → `POST /seen all` does → second refresh same day adds zero events → quote and signal rows committed together.

Mocked at the boundary only: HTTP to Yahoo/BSE/NSE/OpenRouter (respx). Never mock the engine, DB, or cache.

Frontend: vitest on `lib/format.ts` and `Decomposition`; a test that `DigestHero` renders briefing via a text node; manual states checklist instead of Playwright.

## Risks

- **Yahoo throttles/blocks the cloud IP** — seed from laptop; tiering; 2 rps bucket; breaker serves last-known-good as `stale`; replay needs no network.
- **Upstash 500K commands/month** — pipelined writes, watched-union only, 90 s hot tier, no polling worker; estimate on health page; Docker Redis locally; app runs without Redis.
- **Neon cold start + Render spin-down (~1–2 min)** — keep-warm cron on `/health` every 10 min; `pool_pre_ping`; open URL 5 min before presenting.
- **Neon CU-hours** — market-hours scheduler; refresh disabled when no items exist.
- **Signals re-fire** — UNIQUE + `ON CONFLICT DO NOTHING` + `test_dedupe`.
- **Digest self-destructs** — only `POST /seen` mutates; integration test; fixture mode has no such call.
- **LLM down / quota / hallucination / injection** — cache pre-warmed; numeric + injection validators; template fallback; compile off the render path; global ceiling.
- **Someone kills the demo through the public API** — allow-list, cache-first catalysts, rate limits, always-create auth. Rollback: none needed; all are additive guards.
- **NSE announcements 403 from datacenter IP** — `catalyst_status: "unavailable"` ≠ `none_found`; never claim "we looked and found nothing" when we couldn't look.
- **Demo outside market hours** — `REPLAY_DATE` chosen after seed from a session where ≥3 demo symbols fired; replay banner.
- **Contract drift** — `openapi.json` + generated `types.ts` + fixture-contract test.
- **Secret leak via logs or `git add -A`** — `DEBUG=false`, `echo=False`, global exception handler, `.gitignore` first, `git ls-files` check, OpenRouter key rotatable in seconds.
- **Illiquid names** — 0.75% floor, `beta=1.0` fallback, `low_confidence` suppresses firing.
- **Rollback** — single additive migration; stateless app; redeploy previous image; derived tables rebuildable from `daily_bars`.

## Validation checklist

- [ ] `pytest` green incl. `test_fixture_contract`, `test_auth_scoping`, `test_symbol_allowlist`, `test_rate_limits`, `test_briefing_injection`; `-m integration` green on Neon dev branch.
- [ ] Seed complete from laptop: ≥140/150 symbols with ≥60 sessions; clusters computed; skipped symbols logged.
- [ ] `REPLAY_DATE` set; demo user shows ≥3 changed items with distinct signal types and one `none_found`.
- [ ] Reload three times: `changed_count` unchanged. `POST /seen all` → 0. Backdate again.
- [ ] Two refresh ticks same day → `signal_events` count unchanged.
- [ ] Two `POST /auth/session` with the same name → two users; token A cannot read user B's digest.
- [ ] `curl` items with `../etc` and `RELIANCE.NS?range=max` → 404. Sixth compile → 429.
- [ ] `briefing_source: "llm"` once; unset key; still serves from cache.
- [ ] Wi-Fi off: every card renders `stale`/`closed`, evidence renders, no blank panels.
- [ ] `/health/providers` shows circuit states, `redis_commands_estimate_month < 400K`, no URLs/keys.
- [ ] Real evidence numbers in README, not the illustrative 43/7.
- [ ] Phone (via resume link) → add symbol → laptop shows it. Screenshot.
- [ ] `.env.example` all blank; `git ls-files | grep -i env` empty; `git grep -i "sk-or-"` empty; `pip-audit` clean.
- [ ] README has: auth disclaimer, data-stored disclosure, ToS/sourcing posture + takedown commitment, LLM data-transit note, backlog with reasons.

## Open questions

1. Demo time and timezone — evening or weekend makes `REPLAY_DATE` mandatory; which recent volatile session? (Decide after seed by scanning `signal_events` counts per date.)
2. Hosting: Render web service or Fly/Railway? Redis: Upstash (metered, persistent, TLS) vs Render Key Value (unmetered, 25 MB, ephemeral, Render-internal)? Plan assumes Render + Upstash.
3. OpenRouter key available today, and which `:free` model was tested? Verify OpenRouter's current free-tier data policy before the README claims a privacy posture.
4. Source of the ~150-symbol universe with names — hand-curated Nifty 100 + midcaps, or an existing list?
5. Demo display name (synthetic, not "Aklamaash") and the 10–12 demo symbols.
6. Do reviewers open the deployed URL unattended (keep-warm matters more) or watch a live walkthrough (replay matters more)?
7. Who takes down the deploy after review, and when?

---

**Next step**: Review, edit if needed — especially the contract section, which both of you sign at hour 0.5 — then run `/implement` with the same prompt to execute. Backend starts at `schemas.py`; frontend starts at the fixtures.
