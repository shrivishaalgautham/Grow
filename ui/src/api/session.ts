const TOKEN_KEY = "swl.token";
const EXPIRY_KEY = "swl.expires_at";

const listeners = new Set<() => void>();
let cached: string | null = null;
let isCacheValid = false;

function computeToken(): string | null {
  const token = window.localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  const expiresAt = window.localStorage.getItem(EXPIRY_KEY);
  if (expiresAt && Date.parse(expiresAt) <= Date.now()) {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(EXPIRY_KEY);
    return null;
  }
  return token;
}

function invalidate() {
  isCacheValid = false;
  for (const listener of listeners) listener();
}

export function subscribeToToken(listener: () => void) {
  if (listeners.size === 0) window.addEventListener("storage", invalidate);
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) window.removeEventListener("storage", invalidate);
  };
}

export function tokenSnapshot(): string | null {
  if (!isCacheValid) {
    cached = computeToken();
    isCacheValid = true;
  }
  return cached;
}

export const serverTokenSnapshot = (): undefined => undefined;

export function readToken(): string | null {
  return typeof window === "undefined" ? null : tokenSnapshot();
}

export function storeToken(token: string, expiresAt?: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
  if (expiresAt) window.localStorage.setItem(EXPIRY_KEY, expiresAt);
  else window.localStorage.removeItem(EXPIRY_KEY);
  invalidate();
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(EXPIRY_KEY);
  invalidate();
}

export function resumeTokenFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get("t");
}
