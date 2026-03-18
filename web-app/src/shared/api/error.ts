export interface BackendErrorPayload {
  status: number;
  message: string;
  timestamp: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly payload?: BackendErrorPayload;

  constructor(message: string, status: number, payload?: BackendErrorPayload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
