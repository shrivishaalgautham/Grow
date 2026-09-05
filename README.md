# Smart Market Watchlist

A watchlist for NSE stocks that answers two questions most watchlists skip: *what did I miss since I last looked?* and *does this move mean anything, or is it just the market?*

A move is meaningful when it is statistically unusual for that stock, after removing what its behavioural peer group and the index explain, and when volume confirms it. A 2% drop on a day Nifty fell 2% is not news. A 1.4% rise on a flat market with 3x normal volume is.

## The numbers, above the fold

Replaying the last 90 sessions of real NSE bars over the 12-stock sample watchlist (`GET /api/evidence/noise-reduction`, computed 2026-09-05):

| Rule | Alerts |
|---|---|
| Naive: any day the stock moved 2% or more | 168 |
| Raw z-score of 2 or more against the stock's own 20-day range | 76 |
| This engine (peer-adjusted residual, floor 0.75%, z of 2 or more) | 62 |

Of the 124 naive alerts the engine suppressed, 39 were market-wide moves the peer group made too, and 85 were inside the stock's own normal volatility. The engine also fired 18 times on moves *under* 2% that a naive rule would never show, the largest being ICICI Bank on 2026-06-15: down 1.0% while its peer group rose 2.7%, a 3.1-sigma residual.

The page at `/evidence` renders this for whatever watchlist the viewer holds.

## What the reviewer sees

- **Decomposed move on every card**: `Today +2.1% | Peers -0.3% | Stock-specific +2.4%`.
- **Since you last checked**: the digest is anchored to a server-side timestamp that only advances on an explicit "Got it" or "Mark all reviewed". Reloading never marks anything seen. A sample watchlist starts with the anchor backdated seven days before the latest bar, so a new visitor lands on a populated digest with real events.
- **Behavioural peer groups**: agglomerative clustering on one year of return correlations across 150 symbols, recomputed weekly. Sector labels are shown but never used for the maths.
- **"No catalyst found" as a headline**: catalysts are fetched lazily for surfaced stocks only, and an unexplained move is reported as unexplained.
- **Grounded briefing**: one paragraph, written by a free OpenRouter model from computed facts only, rejected if it contains a number not in its input, a link, an unknown symbol, or advice words. A deterministic template serves when the model is absent, rejected, or over budget.
- **Natural-language rules**: "tell me when Tata Motors moves without the auto sector moving" compiles to a bounded JSON rule, is rendered back to English by code, and only runs after the user confirms it.
- **Disputed prices suppress alerts**: Yahoo and BSE are cross-checked; if they disagree by more than 0.5% both prices are shown and no signal fires.
- **Email alerts, opt-in and verified**: one email at most every 30 minutes, only when a watched stock fires a signal or a rule matches, batched, with a one-click unsubscribe. Never a buy or sell call.
- **Plain-words explanation with web-searched context**: for a surfaced stock, the drawer narrates the decomposition and any headlines found on NSE filings, Google News, and GDELT, through the same grounding validators as the briefing.

## Where AI is used, and where it is refused

Used: unsupervised clustering for peer groups, an LLM as narrator for the briefing, and an LLM as compiler for rules. In all three the model never touches a price and never decides what is meaningful.

Refused: price prediction of any kind, and ML anomaly scores. An anomaly score of 0.87 explains nothing; "up 2.1% while peers were flat" does. This is an attention-allocation tool, not a signal generator. It has never been validated against outcomes, and it does not claim to be.

## Architecture

```
APScheduler (in-process, market hours only)
  -> jobs/refresh.py   fan-in over the union of all watchlists, Yahoo + BSE, reconcile
  -> engine/           baselines, peers, residual z, time-adjusted rvol, levels, score
  -> Postgres          quotes (last known good) + signal_events UNIQUE(symbol, type, date)
  -> Redis             quote hash, catalyst cache, rate-limit windows, refresh lock

FastAPI request path reads Redis then Postgres. No request handler calls an upstream price
provider. Per-user state is a few bytes: last_reviewed_at and last_seen_price per symbol.
```

Cost is bounded by the traded universe, not by users: 500 users watching 30 stocks each still resolve to a couple of hundred unique symbols. The thousandth user costs approximately nothing.

## Running it

Prerequisites: Docker, `uv`, Node 20+ (pnpm is fetched by `npx`).

```bash
cd watchlist/backend
docker compose up -d                                   # Postgres 16 + Redis 7
cp .env.local.example .env
uv sync && uv run alembic upgrade head
uv run python -m app.jobs.daily --seed                 # 1y bars for 150 symbols, ~2 min at 2 rps
uv run uvicorn --factory app.main:create_app --port 8000

cd ../../ui
printf 'NEXT_PUBLIC_API_MODE=live\nNEXT_PUBLIC_API_BASE_URL=http://localhost:8000\n' > .env.local
npx pnpm install && npx pnpm dev                       # http://localhost:3000
```

`NEXT_PUBLIC_API_MODE=fixture` runs the UI against bundled fixtures with `?scenario=` switches (`empty`, `quiet`, `closed`, `degraded`, `replay`, `first_visit`, `rate_limited`, `expired`, `down`, `slow`).

Tests: `uv run pytest` (310 tests, needs the docker Postgres; provider and LLM calls are mocked at the HTTP boundary). `pytest -m integration` runs the migration test.

Optional: set `OPENROUTER_API_KEY` to enable the model-written briefing, rule compiler, and per-stock explanation. Without it, briefings come from the template and rules compile through a small deterministic parser; both are labelled honestly in the API (`source: template`).

Email alerts default to `EMAIL_TRANSPORT=console`, which prints every message (including the confirmation link) to the API log so the flow can be demonstrated without credentials. Set `EMAIL_TRANSPORT=smtp` with `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_FROM` to send for real; `APP_BASE_URL` and `API_BASE_URL` are the public origins used in the links. The dispatcher runs every `NOTIFY_INTERVAL_SECONDS` during market hours and once after the end-of-day job, and waits `NOTIFY_MIN_GAP_SECONDS` between emails to the same address.

### Keys and credentials

All secrets live in `watchlist/backend/.env` (git-ignored; `.env.example` ships blank). Restart the API after editing it.

| Variable | What it enables | Where to get it |
|---|---|---|
| `OPENROUTER_API_KEY` | Model-written briefing, rule compiler, per-stock explanation. Empty means templates. | openrouter.ai → Keys. Free `:free` models need no credit; set the account privacy setting to disallow training providers. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | Real email delivery when `EMAIL_TRANSPORT=smtp`. | Any SMTP relay. Gmail: host `smtp.gmail.com`, port 587, user is the Gmail address, password is a 16-character app password (Google account → Security → 2-Step Verification → App passwords). Brevo and Resend also expose SMTP credentials on their free tiers. |
| `APP_BASE_URL`, `API_BASE_URL` | Origins written into confirmation and unsubscribe links. | Local defaults are fine; set to the public URLs when deployed. |

### Testing email alerts

The scheduler only dispatches during market hours (09:15–15:30 IST, weekdays) and once after the 16:00 end-of-day job, so use the manual trigger when testing at other times.

**Without credentials (console transport, the default):**

1. Open http://localhost:3000, start a sample watchlist, scroll to "Email alerts", enter any address, and click "Send confirmation link".
2. The confirmation email is printed in the API log. Copy the link (`http://localhost:3000/?verify=…`) and open it; the panel now shows "Active".
3. Trigger a dispatch: `cd watchlist/backend && uv run python -m app.notify.dispatch`. The alert email body is printed to the terminal. Run it again and it reports `sent=0`, because every signal is logged per address and never repeated; `--ignore-gap` bypasses only the 30-minute spacing, not the dedupe.
4. Open the unsubscribe link from the email body; the panel shows "Switched off".

**With a real inbox:** set `EMAIL_TRANSPORT=smtp` and the SMTP variables, restart the API, then repeat the steps above using your own address. Confirmation and alert emails arrive in the inbox instead of the log; the API log shows only a masked address. An address only ever receives each signal once, so to re-send during a test, clear the per-address history and dispatch again:

```bash
uv run python -c "from sqlalchemy import delete; from app import db; from app.models import NotificationLog; s=db.SessionLocal(); s.execute(delete(NotificationLog)); s.commit()"
uv run python -m app.notify.dispatch --ignore-gap
```

`REPLAY_DATE=2026-09-01` pins the clock to a real volatile session for rehearsal. It disables the scheduler.

## Data sources

| Purpose | Source | Note |
|---|---|---|
| Quotes and 1y history | Yahoo `v8/finance/chart` | Blocks plain HTTP clients from this network with 429; served through `curl-cffi` browser impersonation. |
| Cross-check quotes | `api.bseindia.com` | 15-minute delayed, needs a `Referer`. Scrip codes are mapped for the 12 sample symbols. |
| Corporate announcements | NSE `/api/corporate-announcements` | Works; the cookie handshake returns 403 but the API still answers. |
| Headlines | Yahoo per-ticker RSS | Returns 200 with zero items for every `.NS` ticker as of 2026-09-05. Kept as a fallback source. |
| News search | Google News RSS (`news.google.com/rss/search`) | Public feed queried by company name, India edition. Terms of use grey area; disclosed below. |
| News search | GDELT DOC 2.0 API | The one news source with an explicit free-use grant. Throttled to 1 request per 5 seconds. |
| LLM | OpenRouter `:free` models, ordered list | Every request sets `provider.data_collection: deny`. |

Rejected: NSE quote endpoints (Akamai-blocked from datacenters), Alpha Vantage (returns valid-looking data for an invalid key), Stooq (JavaScript proof-of-work), NewsAPI free (forbids deployed use), Google Gemini free tier (prompts may be read by humans).

### Licensing and terms

Every commercial free tier is licensed for personal, non-commercial use and forbids display in a multi-user app. Yahoo's terms ban automated access, and the browser `User-Agent` and TLS impersonation here are a workaround for an access control, not a permission. This is a take-home demonstration: unlisted, and any deployment is taken down 14 days after submission. No proxy rotation, CAPTCHA solving, or bypassing of NSE's Akamai block. Production needs a licensed feed; `providers/base.py` isolates the swap to one file.

## Stale, delayed, and conflicting data

Every quote carries `as_of`, `source`, `staleness_seconds`, and a `confidence` of `fresh`, `delayed`, `stale`, `disputed`, or `closed`. A closed market is `closed`, never `stale`. Yahoo and BSE diverging by more than 0.5% marks the quote `disputed`, shows both, and suppresses every signal. Three consecutive provider failures open a 60-second circuit and the last known good quote is served as `stale`. Nothing renders blank.

## Security posture

- **There is no authentication.** Sessions are create-only: every visit makes a new user and a 30-day opaque token stored as a SHA-256 hash. A display name is a label and is never looked up. Anyone holding a session link has full access to that watchlist. Do not put anything you care about in it.
- **Data stored**: a self-chosen display name and a list of stock symbols. An email address is stored only if you opt in to alerts and confirm it from the address; it is deleted when you turn alerts off, and every alert carries an unsubscribe link that needs no session. No phone, holdings, or account data. Demo data may be deleted without notice.
- Alert emails contain symbols, computed numbers, and signal text. They never contain buy or sell language and never mention another user.
- Every user-scoped query filters on the token's user; no request carries a user id. Symbols are allow-listed against the universe table and a regex at every boundary.
- Per-IP 30/min on all routes, 10 sessions/hour, 5 catalyst fetches/min; per-user 5/hour and 20/day on the compiler, global 30/day on the model. Catalysts are cache-first under a lock and only served for a stock that surfaced in the caller's own digest.
- Headlines are delimited as untrusted in prompts and sanitised; model output is validated by code and rendered as a text node.
- LLM payloads contain only symbols and computed numbers, never a user identifier. OpenRouter describes its data-policy knowledge as best-effort rather than a guarantee.

## Known limitations

- RVOL scales linearly with time of day; real intraday volume is U-shaped, so early-session values are labelled approximate.
- Correlation clusters need at least 60 sessions, drift, and are coarse on a 150-symbol universe; one cluster holds 51 large caps. Symbols in a cluster smaller than four fall back to beta.
- Thin history or near-zero residual sigma marks a symbol low-confidence and suppresses its signals rather than emitting a garbage z-score.
- Backfilled events are end-of-day. Volume confirmation and previous-day level breaks only persist alongside an excess move or a 52-week break; standalone they fired on 85% of symbol-sessions and would have marked every stock as changed.
- Sigmas are not probabilities. Daily returns are fat-tailed, so the UI says "largest stock-specific move in 3 months", not "1 in 15,000".
- Never validated against outcomes. It surfaces what is statistically unusual, which is not the same as what is important.

## What was cut, and why

Broker order placement (out of scope by design and no free broker API; alerts stop at email and a documented webhook path), RSI (state, not change), Bollinger bands (equivalent to raw z of 2), SMA crossovers (won't demo), gap signals (covered by previous-day level breaks), VWAP (second intraday call per symbol), per-symbol intraday volume curves (doubles the API budget), a job queue and worker (no free worker tier and a polling worker exhausts a metered Redis), WebSocket push, passwords or OAuth, portfolio and P&L, notifications.

## Contract

`watchlist/backend/openapi.json` is exported from the Pydantic models and `ui/src/api/types.ts` mirrors it. `tests/test_fixture_contract.py` validates every frontend fixture against the response models, so the two halves cannot drift silently.
