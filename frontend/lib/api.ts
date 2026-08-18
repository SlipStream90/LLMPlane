const API_V1_PREFIX = "/api/v1";

/**
 * Resolve the API base URL, tolerating the two forms people actually paste into
 * `NEXT_PUBLIC_API_URL`: the bare service origin (`https://x.up.railway.app`)
 * and the fully-qualified base (`https://x.up.railway.app/api/v1`).
 *
 * The backend mounts every v1 route under `settings.api_v1_prefix` (`/api/v1`),
 * so a bare origin made every single request 404 — which is what "API error:
 * 404" on a correct API key actually was.
 */
function resolveBaseUrl(raw: string | undefined): string {
  const fallback = `http://localhost:8000${API_V1_PREFIX}`;
  const trimmed = (raw ?? "").trim().replace(/\/+$/, "");
  if (!trimmed) return fallback;
  return trimmed.endsWith(API_V1_PREFIX) ? trimmed : `${trimmed}${API_V1_PREFIX}`;
}

const API_BASE_URL = resolveBaseUrl(process.env.NEXT_PUBLIC_API_URL);

/*
 * Guard against a misconfigured NEXT_PUBLIC_API_URL.
 *
 * This has now gone wrong twice in ways that are invisible from the UI, because
 * the backend answers a wrong path with a plain `{"detail":"Not Found"}` that
 * looks exactly like an application-level 404:
 *
 *   - a value with no scheme ("host.up.railway.app") makes fetch treat the
 *     result as a RELATIVE url, so requests silently go to the frontend origin;
 *   - a value carrying a near-miss prefix ("…/api/vi", letter i rather than
 *     digit 1) gets `/api/v1` appended to it, producing `/api/vi/api/v1/…`.
 *
 * Neither is recoverable here without guessing at intent, so this warns loudly
 * at startup instead of failing silently on every request.
 */
if (typeof window !== "undefined") {
  const occurrences = (API_BASE_URL.match(/\/api\//g) ?? []).length;
  if (!/^https?:\/\//i.test(API_BASE_URL)) {
    console.error(
      `[llmplane] NEXT_PUBLIC_API_URL has no http(s):// scheme, so every API ` +
        `request will be sent to this site's own origin instead of the backend. ` +
        `Resolved base: ${API_BASE_URL}`
    );
  } else if (occurrences > 1) {
    console.error(
      `[llmplane] NEXT_PUBLIC_API_URL looks misconfigured: the resolved API base ` +
        `contains "/api/" more than once, which means it already carried a ` +
        `path prefix before "${API_V1_PREFIX}" was appended. Every request will ` +
        `404. Resolved base: ${API_BASE_URL} — it should be either the bare ` +
        `origin (https://host) or the full base (https://host${API_V1_PREFIX}).`
    );
  }
}

/** Requests that outlive this are aborted rather than hanging the UI. */
const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("llcp_api_key");
}

/**
 * Pull a human-readable message out of a FastAPI error body. The backend emits
 * RFC 7807 problem details (`detail`/`title`), and `detail` may itself be a
 * pydantic validation array — surfacing "API error: 422" for those told the
 * user nothing about which field was wrong.
 */
function messageFromBody(status: number, statusText: string, body: unknown): string {
  const generic = `API error: ${status}${statusText ? ` ${statusText}` : ""}`;
  if (typeof body === "string" && body.trim()) return body.trim();
  if (!body || typeof body !== "object") return generic;

  const rec = body as Record<string, unknown>;
  const detail = rec.detail ?? rec.title ?? rec.message;

  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (!d || typeof d !== "object") return null;
        const e = d as Record<string, unknown>;
        const loc = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body").join(".") : "";
        const msg = typeof e.msg === "string" ? e.msg : null;
        if (!msg) return null;
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }
  return generic;
}

export interface ApiFetchOptions extends RequestInit {
  /** Overrides `DEFAULT_TIMEOUT_MS`. Pass `0` to disable the timeout. */
  timeoutMs?: number;
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...init } = options;
  const url = `${API_BASE_URL}${path}`;
  const apiKey = getApiKey();

  // A FormData body must keep the browser-generated multipart boundary, so we
  // must NOT set Content-Type ourselves. Forcing application/json here is why
  // dataset upload failed — FastAPI could not parse the multipart request.
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(init.headers as Record<string, string> | undefined),
  };
  if (isFormData) delete headers["Content-Type"];

  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const controller = new AbortController();
  const timer =
    timeoutMs > 0 ? setTimeout(() => controller.abort(), timeoutMs) : null;
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers, signal: controller.signal });
  } catch (err) {
    if (controller.signal.aborted && !signal?.aborted) {
      throw new ApiError(408, `Request to ${path} timed out.`);
    }
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    throw new ApiError(
      response.status,
      messageFromBody(response.status, response.statusText, body),
      body
    );
  }

  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }

  // Some endpoints (DELETE, health pings) legitimately return an empty 200.
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

/**
 * The API is not consistent about list shapes: `/projects`, `/traces`,
 * `/experiments` and `/evaluations` return a `Page[T]` envelope
 * (`{data, next_cursor}`), while `/deployments`, `/providers`, `/benchmarks`,
 * `/benchmark-datasets`, `/routing-policies` and `/logs` return a bare array.
 *
 * Hooks that assumed a bare array would call `.map` on the envelope object and
 * throw — but only once the endpoint returned a non-empty result, which is why
 * this survived testing against an empty project.
 */
export interface Paginated<T> {
  data: T[];
  next_cursor?: string | null;
  total?: number;
}

export function unwrapList<T>(res: Paginated<T> | T[] | null | undefined): T[] {
  if (Array.isArray(res)) return res;
  if (res && Array.isArray(res.data)) return res.data;
  return [];
}

export { getApiKey, API_BASE_URL };
