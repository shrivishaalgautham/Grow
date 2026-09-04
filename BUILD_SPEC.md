# Smart Market Watchlist — Build Specification

**Target market:** India (NSE/BSE)
**Timebox:** ~13 hours (10h core + 3h differentiation layer)
**Context:** Take-home assignment — optimize for a defensible point of view and a demo that lands, not feature count.

---

## 0. Why this stands out — read this first

A reviewer sees a thousand watchlists. Almost all of them show a raw percentage change, a chart, and a news feed. This one makes ten decisions the others don't. Each is cheap; together they are the submission.

| # | Feature | What the reviewer sees | Why they haven't seen it |
|---|---|---|---|
| 1 | **Decomposed move** (§5.4) | `Today +2.1% │ Peers −0.3% │ Stock-specific +2.4%` on every card | Everyone shows the first number. Nobody separates market from stock. |
| 2 | **Measured, not claimed** (§7.2) | *"A 2% rule: 43 alerts. This engine: 7 — and 3 the 2% rule missed."* | No submission proves its own definition of "meaningful" against real data. |
| 3 | **"No catalyst found" is a headline** (§5.4) | A big unexplained move is surfaced *as* unexplained | Other apps show an empty news panel. Unexplained moves are what traders actually care about. |
| 4 | **Events explain, don't score** (§5.4) | News loads lazily under the top 5, not for all 50 | Inverts the usual pipeline; 10× fewer requests; reads as an assistant, not a feed. |
| 5 | **Behavioral peer groups** (§5.3) | *"These 9 stocks have moved together for 6 months; today this one broke away"* | Unsupervised clustering on returns, replacing sector labels. Zero extra API cost. |
| 6 | **Since *you* last checked** (§6) | *"You were away 3 days — 4 of 12 did something"* | Anchored server-side per user, so it survives closing the laptop and opening the phone. |
| 7 | **LLM as compiler, not judge** (§7.4) | Type a rule in English → see the compiled rule → confirm → Python runs it | Most take-home AI is a chat wrapper. This is a DSL with a human confirmation gate. |
| 8 | **Grounded briefing** (§7.3) | One paragraph on what mattered, using only computed facts | Output is rejected if it contains a number not in its input. |
| 9 | **Disputed prices suppress alerts** (§8) | Two exchanges disagree → both shown, no signal fired | Answers the brief's "conflicting data" question with a rule, not a paragraph. |
| 10 | **Named refusals** (§7.1, §4) | No price prediction. No anomaly ML. Licensing caveats stated. | "I deliberately didn't" is rarer and stronger than "I added." |

The hour plan (§13) is ordered so that 1, 2, 6 and 9 ship first. Those four alone are a top-tier submission; the rest is what makes it memorable.

---

## 1. The thesis

Every watchlist app answers *"what is the price now?"* Almost none answer the two questions a person actually opens the app with:

1. **"What did I miss?"** — anchored to when *I* last looked, not to today's session.
2. **"Does this move actually mean anything, or is it just the market?"**

**Our definition:** a move is meaningful when it is *statistically unusual for that specific stock*, *after removing the part explained by its peers and the broader market*, and *confirmed by volume*.

A 2% drop when Nifty is down 2% is not news. A 1.4% rise on a flat market with 3× normal volume is.

**And we prove it.** §8 measures this definition against a naive percentage threshold over 90 days of real data. The claim is tested, not asserted — that is the difference between a submission that argues and one that demonstrates.

---

## 2. Scope

### In scope
- Username-based session (no passwords) — enough to make state server-side and cross-device.
- Create/manage a watchlist from a curated NSE universe.
- Live-ish quotes with explicit freshness and source attribution.
- **Change engine**: peer-adjusted, volatility-normalized, volume-confirmed signals.
- **"Since you last checked" digest** anchored to a per-user server-side timestamp.
- **Noise-reduction proof** — measured evidence the definition beats a naive threshold.
- **Grounded LLM briefing** and **natural-language rule compilation**.
- Lazy catalyst lookup for surfaced symbols only, including explicit *"no catalyst found."*
- Conflict and staleness handling across two independent price sources.

### Explicitly out of scope (state these in the README)
- Real authentication, passwords, OAuth.
- Portfolio/P&L, order placement, brokerage integration.
- Options, futures, mutual funds, crypto.
- Push notifications / email digests.
- Intraday VWAP, round-number levels.
- Backtesting or any claim of predictive value.
- **Price prediction of any kind** — see §7.1.

### Non-goals worth naming out loud
This is **not** a trading signal generator. It is an attention-allocation tool. It tells you where to look; it never tells you what to do. Say this in the README — it pre-empts the obvious interview challenge.

---

## 3. Stack decision

**Backend: Python 3.11 + FastAPI**

Chosen for two concrete reasons, not preference:

1. The change engine is numerical work — rolling standard deviations, OLS beta, residual series, correlation clustering. `pandas`/`numpy`/`scikit-learn` make this ~60 lines. In TypeScript it is ~250 lines of hand-rolled statistics with more places to be subtly wrong.
2. The only working NSE price path is Yahoo's `v8/finance/chart`, and `yfinance` (v1.7.0, actively maintained) is the best-maintained client for it. It is Python-only.

**Frontend:** React 18 + Vite + TypeScript + Tailwind + TanStack Query

**Datastore: Postgres on Neon (deployed) / SQLite (local dev).** SQLAlchemy with `DATABASE_URL` as the only difference; the schema uses nothing dialect-specific.

Neon over the alternatives, verified 2026-09-04:
- **Neon free**: permanent ("not a trial"), no card, 0.5 GB/project, 100 CU-hours/month, scale-to-zero after 5 min with ~0.5–1s first-query cold start. TimescaleDB listed as supported — the natural upgrade path for `daily_bars` at scale.
- **Supabase free** is rejected: projects are *"paused after 1 week of inactivity."* A reviewer opening the link on day 8 finds a dead app.
- **Render Postgres free** is rejected: *"expire 30 days after creation."*

Deploying at all is what forces this — free web hosts have no persistent disk, so SQLite is wiped on restart. A live URL the reviewer can open on their phone *demonstrates* cross-device persistence rather than describing it.

**Scheduler:** APScheduler in-process, **restricted to NSE market hours** (09:15–15:30 IST, weekdays). Two reasons: there is nothing to refresh when the market is closed, and a 24/7 refresh loop keeps Neon from scaling to zero and burns the 100 CU-hour budget in a couple of weeks. Cost-aware scheduling is worth a line in the README. Celery/Redis is the scale path, not the day-one path.

**ML:** `scikit-learn` only — `AgglomerativeClustering` over a returns-correlation matrix (§5.3). Unsupervised, no training data, no model artifacts.

**LLM:** OpenRouter free tier (`:free` models; 50 req/day under $10 lifetime credit, 1,000/day above). Used in exactly two places, both with deterministic fallbacks. Never on the critical render path.

```
watchlist/
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  db.py  models.py  schemas.py
│   │   ├── api/
│   │   │   ├── auth.py  watchlist.py  symbols.py  rules.py  health.py
│   │   ├── providers/
│   │   │   ├── base.py  yahoo.py  bse.py  nse_announcements.py
│   │   │   ├── reconcile.py  ratelimit.py
│   │   ├── engine/
│   │   │   ├── baselines.py  peers.py  residual.py  volume.py
│   │   │   ├── levels.py  signals.py  score.py
│   │   ├── ai/
│   │   │   ├── client.py       # OpenRouter wrapper, cache, fallback
│   │   │   ├── briefing.py     # grounded narrative
│   │   │   ├── rules.py        # NL → validated DSL compiler
│   │   │   └── prompts.py
│   │   ├── evidence/
│   │   │   └── replay.py       # noise-reduction proof
│   │   ├── jobs/
│   │   │   ├── refresh.py  daily.py
│   │   └── data/universe.json
│   └── tests/
└── frontend/
    └── src/{api,hooks,components,pages}
```

---

## 4. Data sources — verified 2026-09-04

Every source below was tested against a live endpoint. The failure modes are real, not hypothetical.

| Purpose | Source | Notes |
|---|---|---|
| **Primary quotes + history** | Yahoo `v8/finance/chart` via `yfinance` | NSE is **real-time** (measured 4.3s and 13s staleness on `RELIANCE.NS` intraday). Use `.NS` suffix. |
| **Cross-check quotes** | `api.bseindia.com` | Requires a `Referer` header. Measured 1326.60 vs Yahoo's 1326.80. BSE is 15-min delayed. |
| **Market status** | NSE `/api/marketStatus` | Reachable from datacenter IPs. |
| **Corporate announcements** | NSE `/api/corporate-announcements` | Reachable from datacenter IPs. |
| **News headlines** | Yahoo per-ticker RSS | **Requires a browser `User-Agent` or it returns 404.** |
| **Broader news (optional)** | GDELT | Only source with an explicit commercial-use grant. Throttle: 1 req / 5s. |
| **LLM** | OpenRouter `:free` models | Only 18 of 427 models have free variants — batch inputs into one call. |

### Sources deliberately rejected
- **NSE `/api/quote-equity`** — Akamai-blocked from datacenter IPs. 403 across browser UA, cookie handshake, and Referer variations.
- **Alpha Vantage** — 25 req/day, and it returns valid-looking data for an *invalid API key*, so key failure and quota exhaustion are undetectable from the response. Disqualifying.
- **Stooq** — now serves a JavaScript proof-of-work challenge. Every tutorial recommending it as a yfinance fallback is stale.
- **NewsAPI.org free** — forbids deployed use, 24-hour article delay.
- **Twelve Data / FMP / Tiingo** — India coverage trial-only or absent; Tiingo additionally *forbids caching data to disk*.
- **Google Gemini free tier** — Google states free-tier prompts are used to improve their products and may be read by humans. Not appropriate for a tool handling a user's holdings.

### Licensing — put this in the README
Every commercial free tier (Finnhub, Alpha Vantage, Twelve Data, FMP, Tiingo) is licensed **personal, non-commercial use only** and forbids display in a multi-user app. Yahoo's ToS bans automated access. The unrestricted sources are the public ones: SEC EDGAR, FINRA, GDELT, AMFI.

Naming this yourself is a strength. State that production requires a licensed feed (Upstox at 50 req/sec, or Kite Connect at ₹500/month) and that `providers/base.py` isolates the swap to one file.

---

## 5. The change engine

Budget ~3.5 hours. Everything else is scaffolding around it.

### 5.1 The key economy
Signals 1–3 all derive from **one** API call per symbol (`range=6mo, interval=1d`), plus one shared index call. Peer clustering reuses the same cached bars. Only catalysts cost extra network budget.

### 5.2 Baselines (`engine/baselines.py`)
Computed once daily per symbol from 6 months of daily bars:

```
returns[t]        = close[t] / close[t-1] - 1
beta              = cov(returns, index_returns) / var(index_returns)   # 90d
residual_sigma    = stdev(residual[-90:])
avg_volume_20d    = median(volume[-20:])       # median, not mean
high_52w, low_52w = max(high[-252:]), min(low[-252:])
prev_close, prev_high, prev_low = last completed session
```

Use **median** for volume. A single earnings day inflates a 20-day mean by 30%+ and silently suppresses every subsequent signal.

### 5.3 Peer clustering (`engine/peers.py`) — the ML component

Unsupervised, no training data, no model artifacts, **zero extra API calls** — it runs on bars already cached.

```
R          = matrix of 6mo daily returns, all ~150 universe symbols
D          = 1 - corr(R)                       # correlation distance
clusters   = AgglomerativeClustering(metric='precomputed', linkage='average',
                                     distance_threshold=τ).fit(D)
```

This yields **behavioral** peer groups — stocks that actually move together, which is often *not* the same as stocks sharing a sector label. It replaces a hardcoded symbol→sector map and ~12 extra index calls, and it produces a better sentence: *"These 9 stocks have traded together for 6 months. Today they averaged −0.3%. This one is +2.1%."*

Recompute **weekly**, not daily — daily recomputation makes peer groups flicker between sessions and destroys the "unusual vs peers" narrative.

**Honest limitations for the README:** correlation clusters are unstable on short windows (require ≥60 trading days), they drift over time, and a 150-symbol universe produces coarse groupings. Fall back to `beta`-only market adjustment for any symbol in a cluster of size < 4.

### 5.4 Live signals (`engine/signals.py`)

**Signal 1 — `EXCESS_MOVE`**

```
today_return = (price - prev_close) / prev_close
peer_return  = median(today_return for symbols in same cluster)
residual     = today_return - peer_return          # cluster size >= 4
             = today_return - beta * index_return  # fallback
z            = residual / residual_sigma
```

Fires when **both**:
- `abs(residual) >= 0.0075` (absolute floor — 0.75%)
- `abs(z) >= 2.0`

The absolute floor is not optional. Without it, a stock that normally moves 0.3%/day produces a "4σ event" on a 1.2% move. The floor is what keeps this from being an alert-spam machine.

**Signal 2 — `VOLUME_CONFIRMED`**

Intraday volume must be normalized for time of day, or at 10:00 IST every stock looks dead and at 15:30 everything looks explosive.

```
NSE_SESSION_MINUTES = 375                      # 09:15–15:30 IST
elapsed_fraction    = clamp(minutes_since_open / 375, 0.05, 1.0)
expected_volume     = avg_volume_20d * elapsed_fraction
rvol                = today_volume / expected_volume
```

Fires when `rvol >= 1.5`.

**Known limitation:** real intraday volume is U-shaped, so linear scaling overstates RVOL in the first 30 minutes. The correct fix is a per-symbol intraday volume curve from 5-minute bars; that doubles the API budget and was cut. Label the value approximate before 10:00 IST.

**Signal 3 — `LEVEL_BREAK`**
Fires on crossing `high_52w`, `low_52w`, `prev_high`, `prev_low`. Free from data already fetched. VWAP and round numbers are cut — VWAP needs a second intraday call per symbol; round numbers are folklore.

**Signal 4 — `CATALYST` / `NO_CATALYST` — evidence, not score**

**This inversion is the most important architectural decision in the build.**

Do **not** score on events. That means fetching news for all 50 symbols; GDELT's 1-req/5s throttle makes it a 4-minute blocking crawl, 90% wasted on stocks that did nothing.

Instead: score with signals 1–3 (free), rank, then fetch catalysts **only for the top 3–5**. Five requests instead of fifty, inside the throttle, lazy so it never blocks page load.

**And when nothing is found, say so as a headline, not an empty panel:**

> **2.0% stock-specific move · 3× volume · no public catalyst found**

Unexplained moves are precisely what experienced traders care about. Shipping "we looked and found nothing" as a first-class result is cheap (~20 min) and signals unusual product maturity.

### 5.5 Ranking (`engine/score.py`)
Score orders the list. Explanation comes from the named signals, never the number. **Never show the raw score in the UI.**

```
volume_multiplier = 1.0 if rvol < 1.5 else 1.0 + min(rvol - 1.5, 2.0) / 2.0
level_bonus       = 1.0 if 52w break else (0.5 if prev-day break else 0.0)
score             = min(abs(z), 6.0) * volume_multiplier + level_bonus
```

### 5.6 Two statistical traps

**Do not present sigmas as probabilities.** Daily equity returns are fat-tailed; a "4σ" move is nowhere near the 1-in-15,000 a normal distribution implies. Present as *"largest stock-specific move in 3 months"* or a percentile. If your reviewer knows markets, this is a visible tell either way.

**Beta and clusters are unstable on illiquid names.** For thin history or `residual_sigma` near zero, fall back to `beta = 1.0`, flag low-confidence, and suppress signals rather than emit a garbage z-score.

---

## 6. "Since you last checked"

Signals answer *"is this notable now?"* The brief asks *"what changed since **you** last looked?"* A stock that gapped 6% three days ago and has been flat since is stale to a daily checker and the most important thing to someone back from a week away.

Per user, per symbol, store `last_seen_at` and `last_seen_price`:

```
delta_since_seen = (current_price - last_seen_price) / last_seen_price
fired_signals    = signals where fired_at > last_seen_at
away_duration    = now - last_seen_at
```

### The critical UX detail
**Do not mark symbols seen on page load.** The digest would destroy itself the instant the user reads it, and a refresh would show empty. This is the bug that quietly ruins the entire feature.

Seen-state advances only on an **explicit** action: a per-card *"Got it"* or a single *"Mark all reviewed"*.

Because the anchor is server-side and keyed to the session token, closing the laptop and opening the phone shows the same digest. Cross-device satisfied by design, not by a sync layer.

---

## 7. The differentiation layer

Three additions that move this from "well-engineered watchlist" to something a reviewer remembers. Build in this order — each is independently shippable, so you can stop anywhere.

### 7.1 Where AI is used, and where it is refused

**Refused — price prediction.** Unvalidatable in a day, and presenting an unbacktested forecast reads as naïveté rather than ambition. *"I deliberately didn't"* is the stronger answer.

**Refused — ML for anomaly detection.** Swapping z-scores for an IsolationForest loses the ability to say *"up 2.1% while peers were flat, 2.0% is stock-specific."* An anomaly score of `0.87` explains nothing. In a product whose entire pitch is legibility, that is a downgrade dressed as sophistication.

**Accepted — clustering (§5.3):** unsupervised, explainable, zero marginal cost.
**Accepted — LLM as narrator (§7.3) and as compiler (§7.4):** never as judge. The LLM never decides what is meaningful and never touches a price.

### 7.2 The noise-reduction proof (`evidence/replay.py`) — highest value per hour

Every submission *claims* its definition of meaningful is better. None prove it. Replay 90 days of cached daily bars through both engines:

```
naive_alerts = days where abs(today_return) >= 0.02
our_alerts   = days where EXCESS_MOVE fired
```

Render as a dedicated screen:

> **Over the last 90 days, on your watchlist:**
> A naive 2% threshold would have alerted you **43 times**.
> This engine alerted **7**.
>
> **36 suppressed** — 31 were market-wide moves your peers made too.
> **3 caught that a 2% rule missed** — including a **1.2%** move that was 4σ against its peers on 5× volume.

That last line is the money. It proves the engine is **bidirectional** — it removes noise *and* catches what magnitude-based rules miss. This converts the thesis from assertion to measured claim, needs no external dependency, and works with zero network. ~1 hour.

### 7.3 Grounded briefing (`ai/briefing.py`)

One narrative paragraph for the away-period — not per-stock summaries:

> You were away 3 days. Two things mattered: TMPV broke to a 52-week high on 3× volume, and the rest of your auto exposure didn't follow — unusual for a group that's moved together all quarter.

The differentiation is not the summary, it is the **grounding discipline**:

- **Input is structured JSON of computed facts only** — symbols, numbers, fired signals, headline+source+timestamp. No free browsing, no tool access.
- **System prompt constraints:** may only use numbers present in the input; must not infer causation from correlation; must state *"no catalyst was found"* rather than speculate; 2–4 sentences, no advice, no price targets.
- **Validation:** reject and fall back if the output contains a number absent from the input.
- **Cached** in SQLite keyed by `(user_id, last_seen_at, signal_set_hash)` — regenerating costs nothing and the demo is pre-warmed.
- **Deterministic template fallback** if the API is down or the budget is exhausted.

A hallucinated summary in a finance product is worse than no summary. The constraints and the fallback are not polish — they are what make the LLM safe to include. ~1 hour.

### 7.4 Natural-language rules (`ai/rules.py`) — the architectural flex

The user types: *"tell me when Tata Motors moves without the auto sector moving."*

**The LLM is a compiler, not a judge.** It never touches market data, never evaluates a condition, never decides what is meaningful. It translates intent into a filter over primitives you already compute:

```
NL text → LLM → JSON rule → Pydantic validation → plain-English confirmation → deterministic Python evaluation
```

```json
{
  "symbols": ["TMPV.NS"],
  "all": [
    {"field": "abs_residual_pct", "op": ">=", "value": 1.5},
    {"field": "abs_peer_return_pct", "op": "<=", "value": 0.5}
  ]
}
```

Available fields: `residual_pct`, `abs_residual_pct`, `z_score`, `rvol`, `peer_return_pct`, `level_break`, `has_catalyst`.

**The confirmation gate is the whole design.** Before saving, the UI renders the compiled rule back in plain English — *"I'll alert you when: stock-specific move ≥ 1.5% AND peer group moves ≤ 0.5%"* — so a model error is **visible rather than silent**. Invalid JSON or an unknown field is rejected outright; the model gets no second chance to improvise.

Most LLM features in take-homes are a chat wrapper around an API. This is a small DSL with a natural-language front-end, schema validation, and a human confirmation step. It is the item most likely to impress an engineering reviewer specifically. ~1.5 hours.

---

## 8. Stale, delayed, and conflicting data

The brief asks explicitly, so handle it visibly.

### Freshness contract
Every quote crossing the API boundary carries:

```json
{"price": 1326.80, "as_of": "2026-09-04T10:14:32+05:30",
 "source": "yahoo", "staleness_seconds": 8, "confidence": "fresh"}
```

`confidence` ∈ `fresh` | `delayed` | `stale` | `disputed` | `closed`

- Market **closed** → `closed`, *"Closed · last traded 15:30"*. **Never call a closed market "stale"** — the most common naive mistake here.
- Market open, `staleness_seconds > 120` → `stale`, greyed with a badge.
- Never render a number without its `as_of`. Silent staleness is the failure mode being tested for.

### Conflict resolution (`providers/reconcile.py`)
Yahoo (real-time NSE) and BSE (15-min delayed) are independent sources on different exchanges, so disagreement is expected and informative.

```
divergence = abs(yahoo_price - bse_price) / yahoo_price
```

- `<= 0.005` → agreement; serve Yahoo, note both checked.
- `> 0.005` → mark `disputed`, show **both** with sources and timestamps, prefer the fresher.
- **Suppress all signal firing on `disputed` data.** Never fire an alert off a price two sources disagree about — that is how you generate a confidently wrong alert, the worst demo outcome available.

### Provider resilience (`providers/ratelimit.py`)
- Token bucket ~2 req/sec against Yahoo — it rate-limits cloud IPs harder than residential.
- Circuit breaker: 3 consecutive failures → open 60s → serve last known good as `stale`.
- Exponential backoff with jitter on 429.
- **Never let a provider failure produce a blank screen.**

---

## 9. How this scales

**Symbol-level fan-in, not user-level fan-out.**

Naive: N users × M symbols. 500 users × 30 symbols = 15,000 calls, instant rate-limit death.

This design refreshes the **union of all symbols across all watchlists**. 500 users watching 30 each still resolve to ~200 unique symbols, because watchlists overlap heavily on large caps. **Cost is bounded by the traded universe (~2,000 NSE symbols), not by user count.**

- Baselines, clusters, and signals are computed **once per symbol**, shared by every user.
- Only `last_seen_at` / `last_seen_price` are per-user — a few bytes per row.
- The thousandth user costs approximately nothing.

**Tiered refresh:**

| Tier | Criterion | Interval |
|---|---|---|
| Hot | in ≥5 watchlists, market open | 60s |
| Warm | in ≥1 watchlist, market open | 5 min |
| Cold | market closed | daily after 16:00 IST |

**Scale path, stated but not built:** SQLite → Postgres (connection string only); in-process cache → Redis; APScheduler → Celery beat; client polling → WebSocket push.

---

## 10. Data model

```sql
users(id, username UNIQUE, created_at)
sessions(token PK, user_id, created_at, last_active_at)

watchlist_items(id, user_id, symbol, added_at, UNIQUE(user_id, symbol))
symbols(symbol PK, name, exchange, is_active)

daily_bars(symbol, date, open, high, low, close, volume,
           PRIMARY KEY(symbol, date))

baselines(symbol PK, beta, residual_sigma, avg_volume_20d,
          high_52w, low_52w, prev_close, prev_high, prev_low,
          cluster_id, confidence, computed_at)

peer_clusters(cluster_id, symbol, computed_at, PRIMARY KEY(cluster_id, symbol))

quotes(symbol PK, price, volume, as_of, source, confidence,
       alt_price, alt_source, divergence, updated_at)

signal_events(id, symbol, signal_type, trading_date, fired_at,
              magnitude, payload_json,
              UNIQUE(symbol, signal_type, trading_date))

user_symbol_state(user_id, symbol, last_seen_at, last_seen_price,
                  PRIMARY KEY(user_id, symbol))

user_rules(id, user_id, nl_text, compiled_json, enabled, created_at)
briefing_cache(cache_key PK, user_id, text, generated_at, was_fallback)
```

**`UNIQUE(symbol, signal_type, trading_date)` is load-bearing.** Without it a signal re-fires every 60-second refresh and the digest fills with fifty copies of one event. This is the single most likely bug in the build.

---

## 11. API surface

```
POST   /api/auth/session               {username} → {token}

GET    /api/watchlist                  items + quotes + live signals
POST   /api/watchlist/items            {symbol}
DELETE /api/watchlist/items/{symbol}

GET    /api/watchlist/digest           "since you last checked" payload
POST   /api/watchlist/seen             {symbols: [...] | "all"}
GET    /api/watchlist/briefing         grounded narrative (cached)

GET    /api/symbols/search?q=
GET    /api/symbols/{symbol}/catalysts lazy; news + NSE announcements
GET    /api/symbols/{symbol}/peers     cluster members + their moves today

POST   /api/rules/compile              {text} → compiled rule + plain-English preview
POST   /api/rules                      save a confirmed rule
GET    /api/rules

GET    /api/evidence/noise-reduction   90-day replay comparison
GET    /api/health/providers           per-provider status, circuit state, last success
```

`/api/health/providers` costs ten minutes and demonstrates operational thinking.

### Digest response shape

```json
{
  "away_duration_seconds": 271840,
  "market_status": "open",
  "changed_count": 4, "total_count": 12,
  "briefing": "You were away 3 days. Two things mattered: ...",
  "briefing_source": "llm",
  "items": [{
    "symbol": "TMPV.NS",
    "price": 982.40, "as_of": "2026-09-04T10:14:32+05:30", "confidence": "fresh",
    "change_since_seen_pct": 6.2,
    "today_change_pct": 2.1,
    "peer_change_pct": -0.3,
    "residual_pct": 2.4,
    "z_score": 3.4, "rvol": 3.1,
    "peer_cluster": ["MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS"],
    "catalyst_status": "none_found",
    "signals": [
      {"type": "EXCESS_MOVE", "headline": "Biggest stock-specific move in 3 months",
       "detail": "Up 2.1% while its peer group averaged -0.3%."},
      {"type": "VOLUME_CONFIRMED", "headline": "3.1× normal volume",
       "detail": "Adjusted for time of day."}
    ]
  }]
}
```

The response carries `today_change_pct`, `peer_change_pct`, and `residual_pct` **separately**. Showing the decomposition on screen is what makes the thesis legible without explanation.

---

## 12. Frontend

**Four screens.** Resist a fifth.

### Login
Username only. *"No password — this demo identifies you by name so your watchlist follows you across devices."*

### Watchlist (main)

**Top — the digest. This is the hero.**

> **While you were away — 3 days**
> 4 of your 12 stocks did something meaningful.
> *TMPV broke to a 52-week high on 3× volume, and the rest of your auto exposure didn't follow — unusual for a group that's moved together all quarter.*
> `[Mark all reviewed]`

Then changed symbols as cards ranked by score; below a divider, the unchanged remainder in a compact, deliberately quiet table.

**The visual argument that sells the project** — the decomposition on every card:

```
TMPV                                          ₹982.40
Today  +2.1%   │  Peer group  -0.3%   │  Stock-specific  +2.4%
                                        ▲ biggest in 3 months

[ 3.1× volume ]  [ 52-week high ]  [ no catalyst found ]
                                             fresh · 8s ago
```

Anyone who looks at that grasps the thesis in two seconds with no explanation. **That is the demo.**

### Evidence screen
The §7.2 noise-reduction comparison. Link it from the digest header as *"Why you're seeing 4 and not 43."*

### Detail drawer
90-day sparkline with residual overlaid, level markers, **peer cluster members and their moves today**, and lazily-loaded catalysts. Skeleton while catalysts load — the one intentionally slow path.

### States that must exist
Empty watchlist · loading · provider degraded · disputed price (**show both**) · market closed · LLM unavailable (template briefing, unlabelled — it should read naturally) · nothing changed (*"Quiet day. Nothing needed your attention."* — a good outcome, presented as one).

---

## 13. Hour-by-hour

| Hours | Work |
|---|---|
| 0.0–0.5 | Scaffold FastAPI + Vite, SQLite, models, `universe.json` (~150 symbols: Nifty 100 + liquid midcaps) |
| 0.5–1.5 | `providers/yahoo.py` — quotes + 6mo history, rate limiter, on-disk bar cache |
| 1.5–2.25 | `engine/peers.py` — correlation clustering |
| 2.25–3.75 | Engine: baselines, residual, z-score, RVOL, levels, signals, score. Unit-tested against fixtures. |
| 3.75–4.75 | Persistence + auth + watchlist CRUD + `user_symbol_state` |
| 4.75–5.5 | Digest endpoint + explicit seen-marking |
| 5.5–6.25 | APScheduler refresh, symbol-union fan-in, signal dedupe |
| 6.25–6.75 | BSE cross-check + reconciliation + confidence levels |
| 6.75–7.75 | **`evidence/replay.py`** — noise-reduction proof |
| 7.75–8.75 | **`ai/briefing.py`** — grounded briefing + cache + template fallback |
| 8.75–10.25 | **`ai/rules.py`** — NL → DSL compiler + confirmation gate |
| 10.25–12.0 | Frontend: login, watchlist, digest hero, decomposition cards, evidence screen |
| 12.0–12.5 | Detail drawer + lazy catalysts + peer panel |
| 12.5–13.0 | States, polish, README |

### Stop-anywhere priority
If you run short, cut in this order: **NL rules → detail drawer → BSE cross-check → catalysts**.

**Never cut:** the digest, the decomposition display, or the noise-reduction proof. Those three *are* the project.

If you only have 10 hours, build §7.2 and §7.3 and leave §7.4 as a documented roadmap item.

---

## 14. Tests

Test the engine, not the framework. Deterministic fixtures, no network.

```
tests/test_residual.py    beta on known series; residual strips a pure-peer move to ~0
tests/test_peers.py       synthetic correlated groups cluster correctly
                          cluster size < 4 falls back to beta adjustment
tests/test_signals.py     absolute floor suppresses low-vol 4σ noise
                          median volume resists a single earnings spike
tests/test_volume.py      RVOL time-of-day normalization at 09:30 vs 15:20
tests/test_reconcile.py   divergence > 0.5% → disputed; disputed suppresses signals
tests/test_digest.py      page load does NOT advance last_seen_at
                          explicit seen call DOES
tests/test_dedupe.py      same signal, same symbol, same day → fires once
tests/test_rules.py       invalid field → rejected, not coerced
                          compiled rule evaluates deterministically
tests/test_briefing.py    output containing a number absent from input → fallback
                          LLM unavailable → template, never an exception
```

The last four are regression tests for the four bugs most likely to ship.

---

## 15. Risks

| Risk | Mitigation |
|---|---|
| **Yahoo breaks or IP-blocks mid-demo** | On-disk bar cache + last-known-good quotes. **Demo must survive with zero network. Seed the cache before presenting — the highest-impact 20 minutes in the build.** |
| **LLM down / quota exhausted at demo time** | Pre-generate and cache briefings; deterministic template fallback; rules compile is not on the render path |
| **LLM hallucinates a number** | Structured-facts-only input; reject outputs containing numbers absent from input; confirmation gate on rules |
| Signals re-fire every refresh | `UNIQUE(symbol, signal_type, trading_date)` + regression test |
| Digest self-destructs on page load | Explicit seen-marking only + regression test |
| Peer clusters flicker | Recompute weekly, not daily; fall back to beta for clusters < 4 |
| Low-vol stocks give absurd z-scores | Absolute 0.75% floor; `beta = 1.0` fallback; low-confidence flag |
| Demo falls outside market hours | `--replay` flag pinning "now" to a recent volatile session. **Non-negotiable if presenting in the evening.** |
| Scope creep | The cut list in §13 is decided in advance, not in the moment |

---

## 16. What to say in the interview

1. **"Meaningful is relative, not absolute."** 2% means different things for different stocks on different days. We normalize by the stock's own volatility and subtract what its behavioral peers explain. Everything else follows from that one decision.

2. **"And I measured it."** Over 90 days a naive 2% rule fires 43 times; this fires 7, and catches 3 things the 2% rule misses entirely. The claim is tested, not asserted.

3. **"Events explain, they don't score."** Scoring on news means fetching news for every symbol — doesn't scale, mostly fetches nothing. We score on free always-available data, then spend the expensive call only on what surfaced. Ten times fewer requests, and it reads as an assistant rather than a dashboard.

4. **"The LLM is a compiler and a narrator, never a judge."** It never touches a price, never evaluates a condition, never decides what's meaningful. Natural language compiles to a validated DSL that Python executes deterministically, and the user confirms the compiled rule before it saves — so model error is visible, not silent.

5. **"Scaling is fan-in, not fan-out."** Cost is bounded by the traded universe, not user count, because watchlists overlap. The thousandth user costs approximately nothing.

6. **"I read the licenses."** Every free tier here forbids multi-user display, and NSE blocks datacenter IPs on price endpoints specifically. The provider layer isolates the production swap to one file.

**And one honest limitation, offered before it's asked:** this has never been validated against outcomes. It surfaces what is statistically unusual, which is not the same as what is important. Validating that needs labelled data and a real backtest — out of scope for a day, and I'd rather say so than imply otherwise.

---

## 17. README checklist

- [ ] The thesis in three sentences
- [ ] Definition of "meaningful change" with the formula
- [ ] **The noise-reduction numbers, above the fold**
- [ ] Architecture diagram (fan-in refresh → engine → per-user digest)
- [ ] Where AI is used — and the two places it was deliberately refused
- [ ] Data sources table, **including the rejected ones and why**
- [ ] Licensing caveat
- [ ] Stale/delayed/conflicting-data policy
- [ ] Scaling section
- [ ] What was cut, and why
- [ ] Known limitations (linear RVOL, unstable beta/clusters, no outcome validation)
- [ ] Setup + `--replay` demo instructions

---

## Appendix A — LLM prompts (`ai/prompts.py`)

These are the actual constraints, not a description of them. The briefing prompt is deliberately restrictive; the rules prompt is deliberately narrow.

### A.1 Briefing — system prompt

```
You write a short briefing for an investor returning to their stock watchlist.
You receive a JSON object of computed facts. Follow every rule below.

1. Use only numbers that appear verbatim in the input. Do not compute,
   re-round, estimate, or introduce any figure not present.
2. Do not infer causation. If a catalyst is listed you may say a move
   "coincided with" it. Never say a move happened "because of" anything.
3. If catalyst_status is "none_found", state plainly that no public
   catalyst was found. Do not speculate about what it might be.
4. No advice, no predictions, no price targets, no words like bullish,
   bearish, buy, sell, hold, opportunity, risk.
5. Lead with the item with the highest abs(z_score). Mention at most
   three symbols. Two to four sentences. Plain prose, no bullet points,
   no headings.
6. If the input has zero changed items, write exactly one sentence
   saying nothing on the watchlist needed attention.
```

**User message:** the digest JSON from §11, with `signals[].detail`, `peer_cluster`, and `catalysts[]` (headline, source, published_at) included. Nothing else.

**Post-validation (`ai/briefing.py`):** extract every numeric token from the output; if any is absent from the set of numeric tokens in the input, discard and use the template. Log the rejection — it's evidence the guardrail works, and worth a line in the README.

**Template fallback:**
```
You were away {away_human}. {changed_count} of {total_count} stocks did something
meaningful. The largest stock-specific move was {top.symbol} at {top.residual_pct:+.1f}%
against a peer group at {top.peer_change_pct:+.1f}%{catalyst_clause}.
```
where `catalyst_clause` is `", with no public catalyst found"` or `", coinciding with: {headline}"`.

### A.2 Rule compiler — system prompt

```
Translate the user's request into a JSON rule. Output JSON only. No prose.

Schema:
{"symbols": ["<SYMBOL>", ...] | "all",
 "all": [{"field": "<field>", "op": ">=" | "<=" | "==", "value": <number|string|bool>}]}

Allowed fields and units:
  residual_pct          stock-specific move today, percent, signed
  abs_residual_pct      absolute value of residual_pct
  z_score               residual / its 90-day standard deviation, absolute
  rvol                  volume relative to time-adjusted 20-day median (1.0 = normal)
  peer_return_pct       peer group median move today, percent, signed
  abs_peer_return_pct   absolute value of peer_return_pct
  level_break           one of "52w_high" | "52w_low" | "prev_high" | "prev_low"
  has_catalyst          true | false

Symbols must come from the provided universe list. Map company names to
symbols using that list only.

If the request references a symbol not in the universe, or cannot be
expressed with the fields above, output {"error": "<one sentence>"}.
Never invent a field. Never guess a symbol.
```

**User message:** `Universe: [...]\n\nRequest: {text}`

**Pipeline (`ai/rules.py`):**
```
text → LLM → json.loads (fail → error)
     → Pydantic Rule model (unknown field / bad op → error, no retry)
     → render_plain_english(rule)        # deterministic Python, NOT the LLM
     → user confirms → persist compiled_json
```

The confirmation text is rendered by code from the validated JSON, so what the user approves is exactly what will execute. The LLM is never asked to describe its own output.

**Worked example.**
Input: *"tell me when Tata Motors moves without the auto sector moving"*
Compiled:
```json
{"symbols": ["TMPV.NS"],
 "all": [{"field": "abs_residual_pct", "op": ">=", "value": 1.5},
         {"field": "abs_peer_return_pct", "op": "<=", "value": 0.5}]}
```
Rendered: *"Alert on TMPV when its stock-specific move is at least 1.5% and its peer group moves no more than 0.5%."*

Note the threshold `1.5` is the model's default when the user names no number. The rendered sentence makes that default visible so the user can correct it before saving.

---

## Appendix B — Config and demo runbook

### B.1 Environment

```
DATABASE_URL=sqlite:///./watchlist.db          # local
# DATABASE_URL=postgresql+psycopg://...neon.tech/...?sslmode=require   # deployed
DB_POOL_SIZE=3                 # Neon free compute is small; keep the pool tight
SCHEDULER_MARKET_HOURS_ONLY=true
OPENROUTER_API_KEY=            # optional — empty disables LLM, templates used
OPENROUTER_MODEL=              # any :free model; pin one that was tested
YAHOO_RPS=2
BSE_ENABLED=true
REPLAY_DATE=                   # e.g. 2026-08-27 — pins "now" for demos
REFRESH_HOT_SECONDS=60
REFRESH_WARM_SECONDS=300
```

Never put a key in the repo. `.env.example` ships with every value blank.

### B.2 First run

```
cd backend && uv sync && uv run alembic upgrade head
uv run python -m app.jobs.daily --seed      # fetch 6mo bars for the universe, compute baselines + clusters
uv run uvicorn app.main:app --reload
cd ../frontend && pnpm i && pnpm dev
```

The seed step is the slow one (~150 symbols at 2 rps ≈ 90s). It writes `daily_bars` to SQLite, so every later start is instant and network-free.

### B.3 Pre-demo checklist — do all of these the night before

- [ ] Run `--seed` so bars, baselines and clusters are on disk.
- [ ] Pick a `REPLAY_DATE` that was a volatile session and set it. The demo must not depend on the market being open or interesting.
- [ ] Create the demo user, add 10–12 symbols, then **set `last_seen_at` back 3 days** via a script so the digest has something to say.
- [ ] Hit `/api/watchlist/briefing` once so the LLM output is cached. Confirm `briefing_source: "llm"`.
- [ ] Then **unset `OPENROUTER_API_KEY` and hit it again** — confirm the cached briefing still serves. That is your proof the demo survives an LLM outage.
- [ ] Run `/api/evidence/noise-reduction` and put the real numbers in the README. Do not use the illustrative `43 / 7` from §7.2.
- [ ] Pull the network and reload the watchlist. Every card should render with a `stale` badge, none should be blank.
- [ ] `pytest` green.

**If deployed:**
- [ ] Run `--seed` against the Neon `DATABASE_URL`, not just local SQLite.
- [ ] Confirm `SCHEDULER_MARKET_HOURS_ONLY=true` in the host's env — otherwise the refresh loop burns Neon compute hours overnight.
- [ ] Keep the backend warm: a cron hitting `/api/health` every 10 minutes. Render free services spin down after 15 idle minutes and take ~1 minute to return; 750 free instance-hours/month covers one service running continuously.
- [ ] Open the deployed URL on your phone, add a symbol, then open it on the laptop. This is the cross-device proof — screenshot it for the README.

### B.4 What to show, in order

1. Login → the digest hero with the briefing. Let it sit for two seconds.
2. One card. Point at the three-number decomposition. Don't explain it; let them read it.
3. Click *"Why you're seeing 4 and not 43."* The evidence screen.
4. Open a card → peer group panel → *"no catalyst found."*
5. Type one natural-language rule. Show the compiled sentence. Save it.
6. If asked about scale, staleness, or licensing — §9, §8, §4. Don't volunteer them; they're better as answers.
