const configuredBase = (import.meta.env.VITE_API_BASE_URL || '').trim();

/**
 * One configurable origin for API requests. Leave empty for same-origin web
 * hosting; the Android build injects the published HTTPS origin here.
 */
export const API_BASE_URL = configuredBase.replace(/\/+$/, '');

export function apiUrl(path: string): string {
  if (!API_BASE_URL) return path;
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}
