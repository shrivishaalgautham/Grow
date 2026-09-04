import type { ErrorCode } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  readonly retryAfterSeconds: number | null;

  constructor(
    status: number,
    code: ErrorCode,
    message: string,
    retryAfterSeconds: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export function isRateLimited(error: unknown): error is ApiError {
  return error instanceof ApiError && error.code === "rate_limited";
}

export function isSessionGone(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    (error.code === "unauthorized" || error.code === "session_expired")
  );
}
