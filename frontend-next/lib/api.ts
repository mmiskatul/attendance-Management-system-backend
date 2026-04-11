const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}

export function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function buildWebSocketUrl(path: string, params?: Record<string, string>): string {
  const apiUrl = new URL(buildApiUrl(path));
  apiUrl.protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value) {
      apiUrl.searchParams.set(key, value);
    }
  });
  return apiUrl.toString();
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers,
    cache: "no-store",
  });

  const text = await response.text();
  let payload: unknown = null;

  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text;
  }

  if (!response.ok) {
    if (typeof payload === "object" && payload !== null) {
      throw new Error(JSON.stringify(payload, null, 2));
    }
    throw new Error(typeof payload === "string" && payload ? payload : `${response.status} ${response.statusText}`);
  }

  return payload as T;
}
