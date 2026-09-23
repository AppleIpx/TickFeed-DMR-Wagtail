import type { ErrorDetail, ErrorModel } from "@/api/types";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: ErrorDetail[];

  constructor(status: number, detail: ErrorDetail[], message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isErrorModel(value: unknown): value is ErrorModel {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const detail: unknown = (value as { detail?: unknown }).detail;
  return (
    Array.isArray(detail) &&
    detail.every(
      (item) =>
        typeof item === "object" &&
        item !== null &&
        typeof (item as { msg?: unknown }).msg === "string",
    )
  );
}

export function toApiError(status: number, body: unknown): ApiError {
  if (!isErrorModel(body)) {
    return new ApiError(status, [], `HTTP ${status}`);
  }
  const first = body.detail[0];
  const message = first ? first.msg : `HTTP ${status}`;
  return new ApiError(status, body.detail, message);
}

export interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

export function unwrap<T>(result: FetchResult<T>): T {
  if (result.data !== undefined) {
    return result.data;
  }
  throw toApiError(result.response.status, result.error);
}
