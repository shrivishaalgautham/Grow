import { ApiError } from "./errors";
import { fixtureRequest } from "./fixture";
import { clearToken, readToken } from "./session";
import type { ErrorOut } from "./types";

const MODE = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "fixture";
const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const isFixtureMode = MODE === "fixture";

async function liveRequest(
  method: string,
  path: string,
  body: unknown,
): Promise<unknown> {
  const token = readToken();
  const response = await fetch(`${BASE_URL}/api${path}`, {
    method,
    headers: {
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 204) return null;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = (payload as ErrorOut | null)?.error;
    throw new ApiError(
      response.status,
      detail?.code ?? "internal_error",
      detail?.message ?? `Request failed with status ${response.status}.`,
      detail?.retry_after_seconds ?? null,
    );
  }

  return payload;
}

export async function apiRequest<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  try {
    const result = isFixtureMode
      ? await fixtureRequest(method, path, body)
      : await liveRequest(method, path, body);
    return result as T;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) clearToken();
    throw error;
  }
}
