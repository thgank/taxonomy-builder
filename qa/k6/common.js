import http from "k6/http";

export const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
export const apiKey = __ENV.API_KEY || "dev-api-key-change-me";

export function envInt(name, fallback) {
  const raw = __ENV[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function envFloat(name, fallback) {
  const raw = __ENV[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number.parseFloat(raw);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function authHeaders(contentType = "application/json") {
  return {
    headers: {
      "Content-Type": contentType,
      "X-API-Key": apiKey,
    },
  };
}

export function get(path, params = {}) {
  return http.get(`${baseUrl}${path}`, {
    ...params,
    headers: {
      "X-API-Key": apiKey,
      ...(params.headers || {}),
    },
  });
}

export function post(path, payload, params = {}) {
  return http.post(`${baseUrl}${path}`, payload, {
    ...params,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...(params.headers || {}),
    },
  });
}

export function safeJson(response, selector) {
  try {
    return selector ? response.json(selector) : response.json();
  } catch (_) {
    return null;
  }
}

export function jsonBody(response) {
  try {
    return response.json();
  } catch (_) {
    return null;
  }
}

export function jsonItems(response) {
  const body = jsonBody(response);
  if (Array.isArray(body)) {
    return body;
  }

  if (body && Array.isArray(body.content)) {
    return body.content;
  }

  return [];
}

export function firstJsonItem(response) {
  const items = jsonItems(response);
  return items.length > 0 ? items[0] : null;
}
