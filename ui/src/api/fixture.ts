import digestFixture from "@/fixtures/digest.json";
import briefingFixture from "@/fixtures/briefing.json";
import evidenceFixture from "@/fixtures/evidence.json";
import historyFixture from "@/fixtures/history.json";
import peersFixture from "@/fixtures/peers.json";
import catalystsFound from "@/fixtures/catalysts.found.json";
import catalystsNoneFound from "@/fixtures/catalysts.none_found.json";
import catalystsPending from "@/fixtures/catalysts.pending.json";
import catalystsUnavailable from "@/fixtures/catalysts.unavailable.json";
import rulesFixture from "@/fixtures/rules.json";
import searchFixture from "@/fixtures/search.json";
import healthFixture from "@/fixtures/health.json";

import { ApiError } from "./errors";
import type {
  CatalystsOut,
  DigestOut,
  HistoryOut,
  Item,
  Rule,
  RuleListItem,
  SessionCreate,
  SessionOut,
  SymbolSearchOut,
} from "./types";

export const SCENARIOS = [
  "default",
  "empty",
  "quiet",
  "closed",
  "degraded",
  "replay",
  "first_visit",
  "rate_limited",
  "expired",
  "down",
  "slow",
] as const;

export type Scenario = (typeof SCENARIOS)[number];

const BASE = digestFixture as DigestOut;
const SAMPLE_SYMBOLS = BASE.items.map((item) => item.symbol);
const STATE_KEY = "swl.fixture";

interface FixtureState {
  watchlist: string[];
  seen: string[];
  rules: RuleListItem[];
  reviewedAt: string | null;
  isSample: boolean;
  alertEmail: string | null;
}

const initialState = (): FixtureState => ({
  watchlist: SAMPLE_SYMBOLS,
  seen: [],
  rules: rulesFixture as RuleListItem[],
  reviewedAt: null,
  isSample: true,
  alertEmail: null,
});

function loadState(): FixtureState {
  if (typeof window === "undefined") return initialState();
  const raw = window.localStorage.getItem(STATE_KEY);
  if (!raw) return initialState();
  try {
    return JSON.parse(raw) as FixtureState;
  } catch {
    return initialState();
  }
}

function saveState(state: FixtureState) {
  window.localStorage.setItem(STATE_KEY, JSON.stringify(state));
}

export function currentScenario(): Scenario {
  if (typeof window === "undefined") return "default";
  const value = new URLSearchParams(window.location.search).get("scenario");
  return (SCENARIOS as readonly string[]).includes(value ?? "")
    ? (value as Scenario)
    : "default";
}

const pendingCatalysts = new Set<string>();

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function markQuiet(item: Item): Item {
  return {
    ...item,
    attention: "quiet",
    is_changed: false,
    signals: [],
    change_since_seen_pct: 0,
    last_seen_at: new Date().toISOString(),
  };
}

function dampen(item: Item): Item {
  const today = Math.round(item.today_change_pct * 0.12 * 100) / 100;
  return {
    ...markQuiet(item),
    today_change_pct: today,
    residual_pct: Math.round((today - item.peer_change_pct) * 100) / 100,
    z_score: Math.round(item.z_score * 0.2 * 100) / 100,
    raw_z_score: Math.round(item.raw_z_score * 0.2 * 100) / 100,
    change_since_seen_pct: Math.round(today * 1.4 * 100) / 100,
  };
}

function applyScenario(digest: DigestOut, scenario: Scenario): DigestOut {
  if (scenario === "quiet") {
    digest.items = digest.items.map(dampen);
  }
  if (scenario === "closed") {
    digest.market_status = "closed";
    digest.items = digest.items.map((item) => ({
      ...item,
      quote: { ...item.quote, confidence: "closed", staleness_seconds: 63_240 },
    }));
  }
  if (scenario === "degraded") {
    digest.providers_degraded = true;
    digest.items = digest.items.map((item) => ({
      ...item,
      quote: { ...item.quote, confidence: "stale", staleness_seconds: 7_200 },
    }));
  }
  if (scenario === "replay") {
    digest.replay_date = "2026-09-01";
  }
  if (scenario === "first_visit") {
    digest.last_reviewed_at = null;
    digest.away_duration_seconds = null;
    digest.items = digest.items.map((item) => ({
      ...item,
      change_since_seen_pct: null,
      last_seen_at: null,
      signals: item.signals.filter((s) => s.type !== "SINCE_SEEN_MOVE"),
    }));
  }
  return digest;
}

function synthesize(symbol: string): Item {
  const known = (searchFixture as SymbolSearchOut[]).find(
    (row) => row.symbol === symbol,
  );
  const template = clone(BASE.items[BASE.items.length - 1]);
  const price = 400 + (symbol.length * 137) % 2_400;
  const today = ((symbol.charCodeAt(0) % 9) - 4) / 10;

  return {
    ...markQuiet(template),
    symbol,
    name: known?.name ?? symbol.replace(".NS", ""),
    industry: known?.industry ?? "Unclassified",
    quote: {
      ...template.quote,
      price,
      prev_close: Math.round((price / (1 + today / 100)) * 100) / 100,
      day_high: Math.round(price * 1.004 * 100) / 100,
      day_low: Math.round(price * 0.996 * 100) / 100,
      confidence: "delayed",
      staleness_seconds: 300,
      alt: null,
      divergence_pct: null,
    },
    today_change_pct: today,
    peer_change_pct: 0.05,
    residual_pct: Math.round((today - 0.05) * 100) / 100,
    z_score: 0.2,
    raw_z_score: 0.18,
    rvol: 0.9,
    rvol_is_approximate: true,
    change_since_seen_pct: null,
    last_seen_at: null,
    levels: {
      high_52w: Math.round(price * 1.35 * 100) / 100,
      low_52w: Math.round(price * 0.72 * 100) / 100,
      prev_high: Math.round(price * 1.01 * 100) / 100,
      prev_low: Math.round(price * 0.99 * 100) / 100,
    },
    sma_distance_pct: { "20": 0.4, "50": 1.1, "200": 3.2 },
    peer: { method: "beta", cluster_id: null, size: 0, members: [] },
    catalyst_status: "not_fetched",
  };
}

function buildDigest(state: FixtureState, scenario: Scenario): DigestOut {
  const watchlist = scenario === "empty" ? [] : state.watchlist;
  const seen = new Set(state.seen);
  const known = new Set(SAMPLE_SYMBOLS);

  const digest = clone(BASE);
  digest.items = [
    ...digest.items.filter((item) => watchlist.includes(item.symbol)),
    ...watchlist.filter((symbol) => !known.has(symbol)).map(synthesize),
  ].map((item) => (seen.has(item.symbol) ? markQuiet(item) : item));

  if (state.reviewedAt) {
    digest.last_reviewed_at = state.reviewedAt;
    digest.away_duration_seconds = Math.max(
      0,
      Math.round((Date.parse(digest.now) - Date.parse(state.reviewedAt)) / 1000),
    );
  } else if (!state.isSample) {
    digest.last_reviewed_at = null;
    digest.away_duration_seconds = null;
  }

  applyScenario(digest, scenario);

  digest.items.sort((a, b) => {
    if (a.is_changed !== b.is_changed) return a.is_changed ? -1 : 1;
    if (a.is_changed) return Math.abs(b.z_score) - Math.abs(a.z_score);
    return a.symbol.localeCompare(b.symbol);
  });
  digest.changed_count = digest.items.filter((item) => item.is_changed).length;
  digest.total_count = digest.items.length;
  return digest;
}

function scaleHistory(symbol: string, state: FixtureState): HistoryOut {
  const history = clone(historyFixture as HistoryOut);
  const item = BASE.items.find((candidate) => candidate.symbol === symbol);
  if (!item || state.watchlist.length === 0) return history;

  const last = history.bars[history.bars.length - 1].close;
  const factor = item.quote.price / last;
  history.bars = history.bars.map((bar) => ({
    ...bar,
    close: Math.round(bar.close * factor * 100) / 100,
  }));
  const scaleSeries = (series: (number | null)[]) =>
    series.map((v) => (v === null ? null : Math.round(v * factor * 100) / 100));
  history.sma = {
    "20": scaleSeries(history.sma["20"]),
    "50": scaleSeries(history.sma["50"]),
    "200": scaleSeries(history.sma["200"]),
  };
  history.levels = item.levels;
  return history;
}

function catalystsFor(symbol: string, state: FixtureState): CatalystsOut {
  const item = BASE.items.find((candidate) => candidate.symbol === symbol);
  if (!item || !state.watchlist.includes(symbol)) {
    throw new ApiError(403, "not_surfaced", "Symbol is not in your watchlist.");
  }
  if (!item.is_changed || state.seen.includes(symbol)) {
    throw new ApiError(
      403,
      "not_surfaced",
      "Catalysts are only fetched for stocks that changed.",
    );
  }
  if (item.catalyst_status === "unavailable")
    return catalystsUnavailable as CatalystsOut;
  if (item.catalyst_status === "none_found")
    return catalystsNoneFound as CatalystsOut;
  if (item.catalyst_status === "pending" && !pendingCatalysts.has(symbol)) {
    pendingCatalysts.add(symbol);
    return catalystsPending as CatalystsOut;
  }
  return catalystsFound as CatalystsOut;
}

function compileRule(text: string): {
  rule: Rule | null;
  preview: string | null;
  error: string | null;
} {
  const lowered = text.toLowerCase();
  const percent = lowered.match(/(\d+(?:\.\d+)?)\s*%/);
  const volume = lowered.match(/(\d+(?:\.\d+)?)\s*(?:x|times)/);
  const isDrop = /drop|fall|down|below|loses?/.test(lowered);

  if (!percent && !volume) {
    return {
      rule: null,
      preview: null,
      error:
        "Could not find a threshold. Try naming a percentage or a volume multiple, e.g. \"drops 2% against its peers on 3x volume\".",
    };
  }

  const conditions: Rule["all"] = [];
  if (percent) {
    const value = Number(percent[1]);
    conditions.push({
      field: "residual_pct",
      op: isDrop ? "<=" : ">=",
      value: isDrop ? -value : value,
    });
  }
  if (volume) {
    conditions.push({ field: "rvol", op: ">=", value: Number(volume[1]) });
  }

  const named = BASE.items
    .filter(
      (item) =>
        lowered.includes(item.symbol.replace(".NS", "").toLowerCase()) ||
        item.name
          .toLowerCase()
          .split(" ")
          .some((word) => word.length > 3 && lowered.includes(word)),
    )
    .map((item) => item.symbol);
  const symbols: Rule["symbols"] = named.length > 0 ? named : "all";
  const scope = named.length > 0 ? named.join(", ") : "Any watchlist symbol";
  const preview = `${scope} where ${conditions
    .map((c) => `${c.field} ${c.op} ${c.value}`)
    .join(" and ")}`;

  return { rule: { symbols, all: conditions }, preview, error: null };
}

export async function fixtureRequest(
  method: string,
  path: string,
  body: unknown,
): Promise<unknown> {
  const scenario = currentScenario();
  await delay(scenario === "slow" ? 2_500 : 180);

  if (scenario === "expired" && path !== "/auth/session") {
    throw new ApiError(401, "session_expired", "Your session has expired.");
  }

  if (scenario === "down" && path !== "/auth/session") {
    throw new ApiError(500, "internal_error", "The API is not responding.");
  }

  const state = loadState();
  const [pathname] = path.split("?");
  const query = new URLSearchParams(path.split("?")[1] ?? "");

  if (method === "POST" && pathname === "/auth/session") {
    const input = (body ?? {}) as SessionCreate;
    saveState({
      ...initialState(),
      watchlist: input.start_with_sample ? SAMPLE_SYMBOLS : [],
      isSample: Boolean(input.start_with_sample),
    });
    pendingCatalysts.clear();
    const session: SessionOut = {
      token: `fixture-${Math.random().toString(36).slice(2, 14)}`,
      expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
      user: {
        id: "fixture-user",
        display_name: input.display_name ?? "sample-a41c",
        is_sample: Boolean(input.start_with_sample),
      },
    };
    return session;
  }

  if (method === "GET" && pathname === "/auth/me") {
    return {
      id: "fixture-user",
      display_name: "sample-a41c",
      is_sample: true,
      email: null,
      last_reviewed_at: state.reviewedAt ?? BASE.last_reviewed_at,
      expires_at: new Date(Date.now() + 30 * 86_400_000).toISOString(),
    };
  }

  if (method === "DELETE" && pathname === "/auth/session") {
    window.localStorage.removeItem(STATE_KEY);
    return null;
  }

  if (method === "GET" && pathname === "/watchlist/digest") {
    return buildDigest(state, scenario);
  }

  if (method === "GET" && pathname === "/watchlist/briefing") {
    if (scenario === "rate_limited") {
      throw new ApiError(429, "rate_limited", "Too many requests.", 47);
    }
    const digest = buildDigest(state, scenario);
    if (scenario === "first_visit") {
      return {
        text: `${digest.changed_count} of your ${digest.total_count} stocks moved for reasons their peer group does not explain. Adani Enterprises is the largest: down 6.8% on 3.8x normal volume against a flat Nifty. There is no earlier review to compare against yet, so nothing here is measured since you last looked.`,
        source: "template",
        generated_at: digest.now,
        was_cached: false,
      };
    }
    if (digest.changed_count === 0) {
      return {
        text: `Nothing in your ${digest.total_count} stocks moved beyond its own noise since you last looked. The largest peer-adjusted move was under one standard deviation, which is the engine saying there is no story here rather than that it found nothing.`,
        source: "template",
        generated_at: digest.now,
        was_cached: true,
      };
    }
    return briefingFixture;
  }

  if (method === "POST" && pathname === "/watchlist/items") {
    const symbol = (body as { symbol: string }).symbol;
    if (state.watchlist.includes(symbol)) {
      throw new ApiError(409, "already_added", "Already in your watchlist.");
    }
    if (state.watchlist.length >= 50) {
      throw new ApiError(400, "watchlist_full", "Watchlist is full (50 max).");
    }
    saveState({ ...state, watchlist: [...state.watchlist, symbol] });
    return (
      BASE.items.find((item) => item.symbol === symbol) ?? synthesize(symbol)
    );
  }

  if (method === "DELETE" && pathname.startsWith("/watchlist/items/")) {
    const symbol = decodeURIComponent(pathname.split("/").pop() ?? "");
    saveState({
      ...state,
      watchlist: state.watchlist.filter((s) => s !== symbol),
      seen: state.seen.filter((s) => s !== symbol),
    });
    return null;
  }

  if (method === "POST" && pathname === "/watchlist/seen") {
    const input = (body as { symbols: string[] | "all" }).symbols;
    const symbols = input === "all" ? state.watchlist : input;
    const reviewedAt = new Date().toISOString();
    saveState({
      ...state,
      seen: [...new Set([...state.seen, ...symbols])],
      reviewedAt: input === "all" ? reviewedAt : state.reviewedAt,
    });
    return { marked: symbols.length, reviewed_at: reviewedAt };
  }

  if (method === "GET" && pathname === "/symbols/search") {
    const q = (query.get("q") ?? "").trim().toLowerCase();
    if (!q) return [];
    const pool = [
      ...(searchFixture as SymbolSearchOut[]),
      ...BASE.items.map(({ symbol, name, industry }) => ({
        symbol,
        name,
        industry,
      })),
    ];
    return pool
      .filter(
        (row) =>
          row.symbol.toLowerCase().includes(q) ||
          row.name.toLowerCase().includes(q),
      )
      .slice(0, 10);
  }

  if (method === "GET" && pathname.startsWith("/symbols/")) {
    const [, , symbol, resource] = pathname.split("/");
    if (resource === "history") return scaleHistory(symbol, state);
    if (resource === "peers") return peersFixture;
    if (resource === "catalysts") return catalystsFor(symbol, state);
  }

  if (method === "POST" && pathname === "/rules/compile") {
    if (scenario === "rate_limited") {
      throw new ApiError(429, "rate_limited", "Rule limit reached.", 1_820);
    }
    return compileRule((body as { text: string }).text);
  }

  if (method === "GET" && pathname === "/rules") return state.rules;

  if (method === "POST" && pathname === "/rules") {
    const input = body as { nl_text: string; rule: Rule };
    const created: RuleListItem = {
      id: `rule_${Math.random().toString(36).slice(2, 6)}`,
      nl_text: input.nl_text,
      preview: compileRule(input.nl_text).preview ?? input.nl_text,
      enabled: true,
      created_at: new Date().toISOString(),
      matched_today: [],
    };
    saveState({ ...state, rules: [...state.rules, created] });
    return created;
  }

  if (method === "DELETE" && pathname.startsWith("/rules/")) {
    const id = pathname.split("/").pop();
    saveState({ ...state, rules: state.rules.filter((r) => r.id !== id) });
    return null;
  }

  if (method === "GET" && pathname === "/notifications") {
    return { email: state.alertEmail ? { address_masked: state.alertEmail, status: "verified", verify_expires_at: null, last_notified_at: null } : null };
  }
  if (method === "POST" && pathname === "/notifications/email") {
    const address = (body as { email: string }).email;
    const masked = `${address[0]}***@${address.split("@")[1]}`;
    saveState({ ...state, alertEmail: masked });
    return { address_masked: masked, status: "verified", verify_expires_at: null, last_notified_at: null };
  }
  if (method === "DELETE" && pathname === "/notifications/email") {
    saveState({ ...state, alertEmail: null });
    return null;
  }
  if (method === "POST" && pathname === "/notifications/email/verify") {
    return { status: "verified", address_masked: state.alertEmail ?? "y***@example.com" };
  }
  if (method === "GET" && pathname.startsWith("/symbols/") && pathname.endsWith("/explanation")) {
    const symbol = pathname.split("/")[2];
    const item = BASE.items.find((candidate) => candidate.symbol === symbol);
    if (!item || !item.is_changed) throw new ApiError(403, "not_surfaced", "Only stocks that changed are explained.");
    return {
      status: "ready",
      text: `${symbol.replace(".NS", "")} moved ${item.today_change_pct}% while its peer group moved ${item.peer_change_pct}%, leaving ${item.residual_pct}% that is stock-specific. No public catalyst was found in the last three days of filings and headlines.`,
      source: "template",
      catalyst_status: item.catalyst_status === "found" ? "found" : "none_found",
      items: [],
      generated_at: new Date().toISOString(),
      was_cached: false,
    };
  }

  if (method === "GET" && pathname === "/evidence/noise-reduction") {
    return evidenceFixture;
  }

  if (method === "GET" && pathname === "/health") return { ok: true };
  if (method === "GET" && pathname === "/health/providers") {
    if (scenario === "degraded") {
      const degraded = clone(healthFixture);
      degraded.providers[0].circuit_state = "open";
      degraded.providers[0].consecutive_failures = 6;
      return degraded;
    }
    return healthFixture;
  }

  throw new ApiError(404, "invalid_request", `No fixture for ${method} ${path}`);
}
