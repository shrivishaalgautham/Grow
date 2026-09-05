export type MarketStatus = "open" | "closed" | "pre_open";
export type QuoteSource = "yahoo" | "bse";
export type Confidence = "fresh" | "delayed" | "stale" | "disputed" | "closed";
export type SignalType =
  | "EXCESS_MOVE"
  | "VOLUME_CONFIRMED"
  | "LEVEL_BREAK"
  | "SINCE_SEEN_MOVE"
  | "USER_RULE";
export type Attention = "high" | "notable" | "quiet";
export type PeerMethod = "cluster" | "beta";
export type CatalystStatus =
  | "not_fetched"
  | "pending"
  | "found"
  | "none_found"
  | "unavailable";
export type BriefingSource = "llm" | "template";
export type LevelName = "52w_high" | "52w_low" | "prev_high" | "prev_low";
export type RuleField =
  | "residual_pct"
  | "abs_residual_pct"
  | "z_score"
  | "rvol"
  | "peer_return_pct"
  | "abs_peer_return_pct"
  | "level_break"
  | "has_catalyst";
export type RuleOp = ">=" | "<=" | "==";
export type ErrorCode =
  | "unauthorized"
  | "session_expired"
  | "not_surfaced"
  | "invalid_symbol"
  | "not_in_universe"
  | "watchlist_full"
  | "invalid_rule"
  | "already_added"
  | "rate_limited"
  | "internal_error"
  | "not_in_watchlist"
  | "not_seeded"
  | "invalid_request";

export type IsoDateTime = string;
export type IsoDate = string;

export interface AltQuote {
  price: number;
  source: QuoteSource;
  as_of: IsoDateTime;
}

export interface Quote {
  price: number;
  prev_close: number;
  day_high: number;
  day_low: number;
  volume: number;
  as_of: IsoDateTime;
  source: QuoteSource;
  staleness_seconds: number;
  confidence: Confidence;
  alt: AltQuote | null;
  divergence_pct: number | null;
}

export interface Signal {
  type: SignalType;
  headline: string;
  detail: string;
  fired_at: IsoDateTime;
  trading_date: IsoDate;
  rule_id: string | null;
}

export interface Levels {
  high_52w: number;
  low_52w: number;
  prev_high: number;
  prev_low: number;
}

export interface SmaDistance {
  "20": number;
  "50": number;
  "200": number;
}

export interface Peer {
  method: PeerMethod;
  cluster_id: string | null;
  size: number;
  members: string[];
}

export interface Item {
  symbol: string;
  name: string;
  industry: string;
  quote: Quote;
  today_change_pct: number;
  peer_change_pct: number;
  residual_pct: number;
  z_score: number;
  raw_z_score: number;
  rvol: number;
  rvol_is_approximate: boolean;
  change_since_seen_pct: number | null;
  last_seen_at: IsoDateTime | null;
  attention: Attention;
  is_changed: boolean;
  low_confidence: boolean;
  signals: Signal[];
  levels: Levels;
  sma_distance_pct: SmaDistance;
  peer: Peer;
  catalyst_status: CatalystStatus;
}

export interface RuleCondition {
  field: RuleField;
  op: RuleOp;
  value: number | string | boolean;
}

export interface Rule {
  symbols: string[] | "all";
  all: RuleCondition[];
}

export interface SessionCreate {
  display_name?: string;
  start_with_sample?: boolean;
}

export interface UserOut {
  id: string;
  display_name: string;
  is_sample: boolean;
}

export interface SessionOut {
  token: string;
  expires_at: IsoDateTime;
  user: UserOut;
}

export interface MeOut {
  id: string;
  display_name: string;
  is_sample: boolean;
  email: string | null;
  last_reviewed_at: IsoDateTime | null;
  expires_at: IsoDateTime;
}

export interface DigestOut {
  now: IsoDateTime;
  market_status: MarketStatus;
  replay_date: IsoDate | null;
  latest_bar_date: IsoDate;
  away_duration_seconds: number | null;
  last_reviewed_at: IsoDateTime | null;
  changed_count: number;
  total_count: number;
  items: Item[];
  providers_degraded: boolean;
}

export interface SeenOut {
  marked: number;
  reviewed_at: IsoDateTime;
}

export interface BriefingOut {
  text: string;
  source: BriefingSource;
  generated_at: IsoDateTime;
  was_cached: boolean;
}

export interface SymbolSearchOut {
  symbol: string;
  name: string;
  industry: string;
}

export interface HistoryBar {
  date: IsoDate;
  close: number;
  volume: number;
  today_change_pct: number;
  residual_pct: number;
}

export interface SmaSeries {
  "20": (number | null)[];
  "50": (number | null)[];
  "200": (number | null)[];
}

export interface HistoryOut {
  bars: HistoryBar[];
  levels: Levels;
  sma: SmaSeries;
}

export interface PeerMember {
  symbol: string;
  name: string;
  today_change_pct: number;
}

export interface PeersOut {
  method: PeerMethod;
  cluster_id: string | null;
  size: number;
  peer_change_pct: number;
  members: PeerMember[];
}

export interface CatalystItem {
  headline: string;
  source: string;
  url: string;
  published_at: IsoDateTime | null;
}

export interface CatalystsOut {
  status: "found" | "none_found" | "unavailable" | "pending";
  fetched_at: IsoDateTime | null;
  items: CatalystItem[];
}

export interface RuleCompileOut {
  rule: Rule | null;
  preview: string | null;
  error: string | null;
}

export interface RuleOut {
  id: string;
  nl_text: string;
  rule: Rule;
  preview: string;
  enabled: boolean;
  created_at: IsoDateTime;
}

export interface RuleListItem {
  id: string;
  nl_text: string;
  preview: string;
  enabled: boolean;
  created_at: IsoDateTime;
  matched_today: string[];
}

export interface AlertCount {
  alerts: number;
}

export interface Suppressed {
  total: number;
  market_wide: number;
  below_floor: number;
  within_noise: number;
}

export interface CaughtExtra {
  symbol: string;
  date: IsoDate;
  today_change_pct: number;
  peer_change_pct: number;
  residual_pct: number;
  z_score: number;
  rvol: number;
}

export interface EvidenceOut {
  days: number;
  symbols_count: number;
  from_date: IsoDate;
  to_date: IsoDate;
  computed_at: IsoDateTime;
  naive_pct_2: AlertCount;
  raw_z_2: AlertCount;
  engine: AlertCount;
  suppressed: Suppressed;
  caught_extra: CaughtExtra[];
}

export interface ProviderHealth {
  provider: string;
  circuit_state: "closed" | "open" | "half_open";
  last_success_at: IsoDateTime | null;
  consecutive_failures: number;
}

export interface ProvidersHealthOut {
  providers: ProviderHealth[];
  scheduler: { last_refresh_at: IsoDateTime | null };
  redis: "ok" | "down" | "disabled";
  db: "ok" | "down";
}

export interface ErrorBody {
  code: ErrorCode;
  message: string;
  retry_after_seconds?: number | null;
}

export interface ErrorOut {
  error: ErrorBody;
}

export interface ExplanationOut {
  status: "ready" | "pending";
  text: string | null;
  source: BriefingSource | null;
  catalyst_status: CatalystStatus;
  items: CatalystItem[];
  generated_at: IsoDateTime | null;
  was_cached: boolean;
}

export type ChannelStatus = "pending" | "verified" | "disabled";

export interface EmailChannelOut {
  address_masked: string;
  status: ChannelStatus;
  verify_expires_at: IsoDateTime | null;
  last_notified_at: IsoDateTime | null;
}

export interface NotificationsOut {
  email: EmailChannelOut | null;
}

export interface VerifyOut {
  status: "verified";
  address_masked: string;
}
