/**
 * Authenticated fetch wrapper.
 * Reads JWT from localStorage and attaches it as Authorization header.
 * All API calls in the dashboard should use this instead of raw fetch().
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function setAuthToken(token: string): void {
  localStorage.setItem("access_token", token);
}

export function clearAuthToken(): void {
  localStorage.removeItem("access_token");
}

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();

  // Build headers as a plain object to avoid Headers constructor issues.
  // Spread any existing headers from options, then set Authorization.
  const existingHeaders: Record<string, string> = {};

  // Handle options.headers being a Headers instance, array, or plain object
  if (options.headers instanceof Headers) {
    options.headers.forEach((value, key) => {
      existingHeaders[key] = value;
    });
  } else if (Array.isArray(options.headers)) {
    options.headers.forEach(([key, value]) => {
      existingHeaders[key] = value;
    });
  } else if (options.headers) {
    Object.assign(existingHeaders, options.headers);
  }

  if (token) {
    existingHeaders["Authorization"] = `Bearer ${token}`;
    // Backup: custom header in case proxy strips Authorization
    existingHeaders["X-Auth-Token"] = token;
  }

  return fetch(url, {
    ...options,
    headers: existingHeaders,
  });
}
