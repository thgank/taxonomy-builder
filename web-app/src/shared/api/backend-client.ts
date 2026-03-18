import "server-only";

import { serverEnv } from "@/shared/config/env";

import { ApiError, type BackendErrorPayload } from "./error";

type Primitive = string | number | boolean;
type SearchValue = Primitive | Primitive[] | null | undefined;

export interface BackendRequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | FormData | object;
  query?: Record<string, SearchValue>;
}

function buildUrl(path: string, query?: Record<string, SearchValue>) {
  const url = new URL(path, serverEnv.TAXONOMY_API_BASE_URL);

  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === null || value === undefined || value === "") {
        continue;
      }

      if (Array.isArray(value)) {
        for (const item of value) {
          url.searchParams.append(key, String(item));
        }

        continue;
      }

      url.searchParams.set(key, String(value));
    }
  }

  return url;
}

async function parseError(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as BackendErrorPayload;
    return new ApiError(payload.message, response.status, payload);
  }

  const message = await response.text();
  return new ApiError(message || response.statusText, response.status);
}

function isBodyInit(value: unknown): value is BodyInit {
  return (
    typeof value === "string" ||
    value instanceof Blob ||
    value instanceof URLSearchParams ||
    value instanceof ArrayBuffer ||
    ArrayBuffer.isView(value) ||
    value instanceof ReadableStream
  );
}

export async function backendRequest<T>(
  path: string,
  options: BackendRequestOptions = {},
): Promise<T> {
  const response = await backendRawRequest(path, options);

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}

export async function backendRawRequest(
  path: string,
  options: BackendRequestOptions = {},
): Promise<Response> {
  const { body, headers, query, ...rest } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("X-API-Key", serverEnv.TAXONOMY_API_KEY);

  let resolvedBody: BodyInit | FormData | undefined;

  if (body instanceof FormData) {
    resolvedBody = body;
  } else if (body && isBodyInit(body)) {
    resolvedBody = body;
  } else if (body) {
    requestHeaders.set("Content-Type", "application/json");
    resolvedBody = JSON.stringify(body);
  }

  const response = await fetch(buildUrl(path, query), {
    ...rest,
    body: resolvedBody,
    headers: requestHeaders,
    cache: rest.cache ?? "no-store",
  });

  if (!response.ok) {
    throw await parseError(response);
  }

  return response;
}
