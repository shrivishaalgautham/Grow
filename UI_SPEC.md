# UI specification — Smart Market Watchlist

Source of truth for the new UI. Derived from PLAN.md (contract section) and BUILD_SPEC.md §12, and checked against the running backend (`watchlist/backend/openapi.json`, 19 routes). Every endpoint is assigned to a screen below; nothing is left unmapped.

## Global rules the design must respect

- **Four screens, no fifth**: Start, Watchlist, Stock detail (drawer over Watchlist), Evidence.
- **No page load ever marks anything as seen.** Seen-state advances only through two explicit controls: "Got it" on a card and "Mark all reviewed" on the digest.
- **Every price is shown with its freshness.** A number never appears without `confidence` and "as of" next to it. A closed market reads "Closed", never "Stale".
- **The raw score is never shown.** Ranking is implicit in card order; explanation comes from signal text.
- **All explanation strings come from the server** (signal headlines and details, briefing, rule previews, error messages). The UI renders them as plain text, never as HTML or markdown.
- **Decomposition on every changed card**: Today / Peers / Stock-specific, three numbers side by side, is the visual argument of the whole product.
- **Sigmas are not probabilities.** Show "z 3.4" as a small technical footnote at most; the headline is the server's wording ("Unusually large stock-specific move").
- **No user id ever travels from the client.** The only credential is a bearer token in local storage.
- Percentages are signed floats already multiplied by 100 (`2.1` means +2.1%). Timestamps are ISO-8601. Prices are INR.

## Shared conventions

**Auth**: `Authorization: Bearer <token>` on every call except `POST /auth/session`, `GET /health`, and `GET /health/providers`. A 401 with code `unauthorized` or `session_expired` clears the token and returns to Start with an "expired" notice.

**Errors** arrive as `{ error: { code, message, retry_after_seconds? } }`. Codes and where they surface:

| Code | HTTP | Where the design needs a state |
|---|---|---|
| `unauthorized`, `session_expired` | 401 | Redirect to Start with a notice |
| `rate_limited` | 429 | Inline notice with countdown from `retry_after_seconds` (compile, catalysts, briefing, global 30/min) |
| `not_surfaced` | 403 | Catalyst panel: "News is only fetched for stocks that changed" |
| `invalid_symbol` | 404 | Search and add flows |
| `not_in_universe`, `watchlist_full`, `invalid_rule`, `invalid_request` | 400 | Inline under the control that caused it |
| `not_in_watchlist` | 400 | Seen call for a symbol no longer watched |
| `already_added` | 409 | Search result already in list |
| `not_seeded` | 503 | Whole-page "market data not loaded yet" state |
| `internal_error` | 500 | Generic retry banner; message is always "internal error" |

**Freshness palette** (five states of `quote.confidence`): `fresh` (live), `delayed`, `stale` (greyed, badge), `disputed` (both prices shown), `closed` (neutral, "last traded 15:30").

**Signal types** (five, each needs a distinguishable chip): `EXCESS_MOVE`, `VOLUME_CONFIRMED`, `LEVEL_BREAK`, `SINCE_SEEN_MOVE`, `USER_RULE`.

**Attention tiers** (three): `high`, `notable`, `quiet`. Only the first two appear as cards; `quiet` goes to the table.

---

## Screen 1 — Start

Purpose: create a session or land from a resume link. This is the only unauthenticated screen.

### Endpoints

| Call | Trigger |
|---|---|
| `POST /auth/session` `{ display_name?, start_with_sample? }` → 201 `{ token, expires_at, user: { id, display_name, is_sample } }` | Either primary button |
| Resume link `/?t=<token>` (frontend route, no backend call) | Page load with `t` in the query string: store token, strip it from the URL, go to Watchlist |
| `GET /health` → `{ ok: true }` | Optional: silent probe to show an "API unreachable" notice before the user clicks |

### Content

- Product name and a one-line thesis: what changed since *you* last looked, and whether it is the stock or the market.
- Optional display-name input. Rule: 3–32 chars, lowercase letters, digits, `-`, `_`. It is a label only; the copy must say sessions are never looked up by name.
- Two actions: **Start with a sample watchlist** (primary; 12 NSE names, last review backdated 7 days so the first screen is populated) and **Start empty**.
- Disclosure footer: no password; anyone holding the session link has full access; only a display name and a symbol list are stored; demo data may be deleted.
- Link to Evidence (it needs a session, so the Evidence screen must handle "no session yet").

### States

Idle · submitting · error (`rate_limited` at 10 sessions/hour/IP, or API down) · resuming ("Opening your watchlist…") · expired-notice variant when arriving from a 401.

---

## Screen 2 — Watchlist (the hero screen)

Purpose: answer "what did I miss?" in one load. Layout top to bottom: banners → digest hero → add-a-stock → changed cards → quiet table → rules.

### Endpoints

| Call | Trigger | Cadence |
|---|---|---|
| `GET /watchlist/digest` | Mount, after every mutation, and every 90 s while open | Polling |
| `GET /watchlist/briefing` | After the digest arrives with `total_count > 0` | Cached 5 min client-side; server caches by digest state |
| `POST /watchlist/seen` `{ symbols: string[] \| "all" }` → `{ marked, reviewed_at }` | "Got it" (one symbol) or "Mark all reviewed" | Optimistic: card collapses to quiet immediately, rolled back on error |
| `GET /symbols/search?q=` → `[{ symbol, name, industry }]` (≤10) | Typing 2+ chars in the add box, debounced | Local table only, `q` ≤ 32 chars |
| `POST /watchlist/items` `{ symbol }` → 201 `Item` | Choosing a search result | Refetch digest now and again after 3 s (a one-off refresh is scheduled server-side) |
| `DELETE /watchlist/items/{symbol}` → 204 | Remove control on a quiet row (and in the drawer) | Refetch digest |
| `GET /health/providers` | Only when the digest says `providers_degraded: true` | Every 60 s while degraded |
| `GET /auth/me` → `{ id, display_name, is_sample, last_reviewed_at, expires_at }` | Header identity chip and session expiry | Once per mount |
| `DELETE /auth/session` → 204 | "End session" (destructive: deletes the user's rows) | Then return to Start |
| Rules block: see Screen 2b | | |

### Digest payload → what to show

```
DigestOut {
  now, market_status: "open"|"closed"|"pre_open", replay_date|null, latest_bar_date,
  away_duration_seconds|null, last_reviewed_at|null,
  changed_count, total_count, items: Item[], providers_degraded
}
```

**Banners** (stackable, in this priority): session expired · rate limited · API error with retry · replay mode (`replay_date` set: "clock pinned to <date> for rehearsal") · providers degraded (name the failing providers from `/health/providers`) · market closed (only when not degraded) · pre-open · first look (`last_reviewed_at` null and `total_count > 0`) · quiet day (`total_count > 0` and `changed_count == 0`: present as a good outcome).

**Digest hero**:
- Headline built from `away_duration_seconds`, `changed_count`, `total_count`: "You were away 3 days — 4 of 12 stocks did something." Variants: first look, empty list, quiet day.
- Briefing paragraph (`BriefingOut.text`, ≤600 chars, plain prose) with a small provenance line: `source` (`llm` → "written by a model", `template` → "assembled from a template") and `was_cached`. While loading, a three-line skeleton. On 429, the hero still renders; the paragraph area shows the retry notice.
- "Bars through <latest_bar_date>".
- Link to Evidence worded as "Why you're seeing 4 and not 43".
- **Mark all reviewed** (only when `changed_count > 0`).

**Add a stock**: combobox with keyboard navigation over search results showing `symbol`, `name`, `industry`, and an "already in watchlist" disabled state. Errors inline: `already_added`, `watchlist_full` (cap 50), `invalid_symbol`, `not_in_universe`.

**Changed cards** (items with `is_changed: true`, already sorted by the server: score descending). Each card presents:

```
Item {
  symbol, name, industry,
  quote: { price, prev_close, day_high, day_low, volume, as_of, source: "yahoo"|"bse",
           staleness_seconds, confidence, alt: { price, source, as_of }|null, divergence_pct|null },
  today_change_pct, peer_change_pct, residual_pct,      ← the three-column decomposition
  z_score, raw_z_score, rvol, rvol_is_approximate,
  change_since_seen_pct|null, last_seen_at|null,
  attention: "high"|"notable"|"quiet", is_changed, low_confidence,
  signals: [{ type, headline, detail, fired_at, trading_date, rule_id|null }],
  levels: { high_52w, low_52w, prev_high, prev_low },
  sma_distance_pct: { "20", "50", "200" },
  peer: { method: "cluster"|"beta", cluster_id|null, size, members: string[] },
  catalyst_status: "not_fetched"|"pending"|"found"|"none_found"|"unavailable"
}
```

Card anatomy, in order of visual weight:
1. Symbol (without `.NS`), name, industry, attention label (`high` → "Worth a look", `notable` → "Notable"), price and `today_change_pct`.
2. **Decomposition**: Today `today_change_pct` · Peers `peer_change_pct` · Stock-specific `residual_pct`. Peer column hint depends on `peer.method`: "N behavioural peers" or "Beta-adjusted Nifty move". A share bar showing how much of the move is stock-specific is optional but effective.
3. Signal list: `headline` bold, `detail` beneath, chip colour by `type`. `USER_RULE` signals are the user's own rules firing (`rule_id` links to the rules block).
4. Catalyst chip from `catalyst_status`: "No public catalyst found" is a headline-weight chip (this is a feature, not an empty state); "Catalyst found"; "Looking for a catalyst…"; "Catalyst source unavailable"; nothing for `not_fetched`. The top 3 cards may prefetch `GET /symbols/{symbol}/catalysts` so the chip fills without opening the drawer.
5. Disputed notice when `quote.alt` is present: both prices with sources and `divergence_pct`; the copy says no signal fires on a disputed price.
6. Low-confidence note when `low_confidence: true`.
7. Footer: freshness badge (`confidence`, `staleness_seconds`, `source`), `z_score`, `rvol` (with "≈" when `rvol_is_approximate`), volume, `change_since_seen_pct` "since you looked". Actions: **Details** (opens Screen 3) and **Got it** (seen for this symbol).

**Quiet table** (items with `is_changed: false`, alphabetical): symbol, name, price, `today_change_pct`, `residual_pct`, freshness badge, open-details, remove. Caption: "moved less than their own noise". Deliberately low-contrast.

**Empty watchlist**: friendly prompt to add symbols (`total_count == 0`).

**Header** (shared with Evidence): brand, nav (Digest · Evidence), display name from `/auth/me`, **Open on phone** (resume link modal), **End session**.

**Resume link modal**: QR code and copyable URL of `<origin>/?t=<token>`; warning that anyone holding it has full access. Shown once automatically on a new session (dismissable hint) and always from the header.

### Screen 2b — Rules block (bottom of Watchlist)

Purpose: natural-language rules compiled to a DSL, confirmed by the user before saving. The LLM never evaluates anything; Python does.

| Call | Trigger |
|---|---|
| `POST /rules/compile` `{ text ≤200 }` → `{ rule\|null, preview\|null, error\|null }` | "Preview" button. Limits: 5/hour and 20/day per user, 30/day global → 429 with `retry_after_seconds` |
| `POST /rules` `{ nl_text, rule }` → 201 `{ id, nl_text, rule, preview, enabled, created_at }` | "Save rule" after the user reads the preview. Max 10 per user → 400 `invalid_rule` |
| `GET /rules` → `[{ id, nl_text, preview, enabled, created_at, matched_today: string[] }]` | Mount and after save/delete |
| `DELETE /rules/{id}` → 204 | Delete control on a rule |

Content: a single text input with placeholder example ("drops more than 2% against its peers on 3x volume"); on preview, show the compiled rule **as the server's plain-English `preview`** with a Save / Discard pair (this confirmation gate is the point of the feature). Optionally show the raw `rule` JSON in a collapsed disclosure:

```
Rule { symbols: string[] | "all",
       all: [{ field: residual_pct|abs_residual_pct|z_score|rvol|peer_return_pct|
                      abs_peer_return_pct|level_break|has_catalyst,
               op: ">="|"<="|"==", value }] }
```

List of saved rules: `nl_text`, `preview`, `created_at`, `matched_today` (symbols it fired on today, link/scroll to those cards), delete. Empty state copy: the engine already flags peer-adjusted moves; rules are for what only you care about. Error states: compile `error` string (≤200 chars), 429 with countdown, 400 `invalid_rule` / `not_in_universe` on save.

---

## Screen 3 — Stock detail (drawer over Watchlist)

Purpose: the one intentionally slower path. Opened from a card or a quiet row; the item itself comes from the digest already in memory, then three lazy calls.

| Call | Trigger | Notes |
|---|---|---|
| `GET /symbols/{symbol}/history?days=90` → `{ bars: [{ date, close, volume, today_change_pct, residual_pct }], levels, sma: { "20": [], "50": [], "200": [] } }` | On open | `days` 1–365; arrays align with `bars` and may contain nulls at the start |
| `GET /symbols/{symbol}/peers` → `{ method, cluster_id, size, peer_change_pct, members: [{ symbol, name, today_change_pct }] }` | On open | `method: "beta"` means no stable cluster; members may be empty |
| `GET /symbols/{symbol}/catalysts` → `{ status: found\|none_found\|unavailable\|pending, fetched_at, items: [{ headline, source, url, published_at }] }` | On open | 403 `not_surfaced` unless the symbol is watched **and** changed. First call may return `pending`; poll once after 4 s. 12/min/IP |
| `DELETE /watchlist/items/{symbol}` | Remove from watchlist | Closes the drawer |
| `POST /watchlist/seen` `{ symbols: [symbol] }` | Optional "Got it" inside the drawer | |

Sections, top to bottom:
1. Header: symbol, name, price, `today_change_pct`, freshness badge, close.
2. Decomposition (same three numbers as the card) and the disputed notice if any.
3. **90 sessions chart**: close line; residual overlay (bar or second line from `bars[].residual_pct`); dashed SMA-20 (optionally 50/200); level markers for `levels.high_52w`, `low_52w`, `prev_high`, `prev_low`. Legend text must name what each line is.
4. **Where it sits**: `sma_distance_pct` for 20/50/200 DMA, 52-week high and low, day range (`quote.day_low`–`quote.day_high`), room to high/low.
5. **Why it surfaced**: full signal list with headline and detail (only when `signals` non-empty).
6. **Peer group**: one sentence built from `method`, `size`, `peer_change_pct` ("These 9 stocks have moved together for 6 months; today the group moved −0.3%") and a horizontal bar per member with `today_change_pct`, the current stock highlighted. Beta fallback sentence when `method: "beta"`.
7. **Catalysts**: skeleton while loading; list of `headline` (text node), `source`, `published_at`, link out to `url`; "No catalyst found" rendered as a positive, explicit result; "source unavailable" distinguishes fetch failure from absence; `not_surfaced` copy for quiet stocks.
8. Footer actions: Got it · Remove from watchlist.

Accessibility: focus trap, Escape closes, focus returns to the opener.

---

## Screen 4 — Evidence

Purpose: prove the definition of "meaningful" against real data. Linked from the digest hero and the nav. Requires a session (uses the caller's watchlist; falls back to the whole universe when the list is empty).

| Call | Trigger |
|---|---|
| `GET /evidence/noise-reduction?days=90` → below | Mount; `days` 30–250 (a selector for 30/90/180 is optional). Server caches for an hour per watchlist and bar date |

```
EvidenceOut {
  days, symbols_count, from_date, to_date, computed_at,
  naive_pct_2: { alerts }, raw_z_2: { alerts }, engine: { alerts },
  suppressed: { total, market_wide, below_floor, within_noise },
  caught_extra: [{ symbol, date, today_change_pct, peer_change_pct, residual_pct, z_score, rvol }]
}
```

Content:
1. Headline computed from the ratio: "A 2% rule would have interrupted you 2.7× more often." Sub-line: `symbols_count` symbols · `days` days · `from_date` to `to_date`.
2. Three-bar comparison: Naive 2% (`naive_pct_2.alerts`), Raw z ≥ 2 (`raw_z_2.alerts`), This engine (`engine.alerts`), scaled to the naive count, each with a one-line description.
3. **Suppressed, and why**: `suppressed.total` split into `market_wide` (peers moved too), `below_floor` (residual under 0.75%), `within_noise` (above the floor but under 2σ for that stock). The three sum to the total.
4. **Caught extra**: table of `caught_extra` rows (moves under 2% the naive rule never saw), columns symbol, date, today, peers, stock-specific, z, rvol. This is the "bidirectional" proof; give it weight.
5. Provenance line: computed `computed_at` from stored end-of-day bars, no live network.
6. Named refusals block: where AI is used (clustering, narrator, compiler) and where it was refused (price prediction, anomaly ML).

States: no session (prompt to start one) · loading · `not_seeded` · error with retry.

---

## Operational surfaces (no dedicated screen)

| Call | Used by |
|---|---|
| `GET /health` → `{ ok: true }` | Start-page reachability probe; keep-warm only otherwise |
| `GET /health/providers` → `{ providers: [{ provider, circuit_state: closed\|open\|half_open, last_success_at, consecutive_failures }], scheduler: { last_refresh_at }, redis: ok\|down\|disabled, db: ok\|down }` | Degraded banner on Watchlist. Optional: a small "system" popover from the header showing the same fields. Never shows error strings or URLs |

---

## Endpoint coverage checklist

| Endpoint | Screen |
|---|---|
| `POST /auth/session` | Start |
| `GET /auth/me` | Header (Watchlist, Evidence) |
| `DELETE /auth/session` | Header: End session |
| `GET /watchlist/digest` | Watchlist |
| `GET /watchlist/briefing` | Watchlist hero |
| `POST /watchlist/items` | Watchlist: add |
| `DELETE /watchlist/items/{symbol}` | Quiet table, drawer |
| `POST /watchlist/seen` | Card "Got it", hero "Mark all reviewed", drawer |
| `GET /symbols/search` | Watchlist: add combobox |
| `GET /symbols/{symbol}/history` | Drawer chart |
| `GET /symbols/{symbol}/peers` | Drawer peer panel |
| `GET /symbols/{symbol}/catalysts` | Drawer catalysts, card chip prefetch |
| `POST /rules/compile` | Rules block: Preview |
| `POST /rules` | Rules block: Save |
| `GET /rules` | Rules block: list |
| `DELETE /rules/{id}` | Rules block: delete |
| `GET /evidence/noise-reduction` | Evidence |
| `GET /health` | Start probe |
| `GET /health/providers` | Degraded banner |

## States checklist for the designer (every one must exist)

Empty watchlist · loading skeletons (hero, cards, drawer sections) · provider degraded · disputed price (both prices) · market closed · pre-open · replay mode · first visit · quiet day · rate limited (compile, catalysts, briefing, global) · session expired · API down with retry · market data not seeded · low-confidence stock · catalyst pending / found / none found / unavailable / not surfaced · watchlist full · already added · rule compile error · rule limit reached · resume-link modal · end-session confirmation.
