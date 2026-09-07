/**
 * AUREXIS Auth Architecture — intentionally deferred.
 *
 * Authentication against the backend is NOT yet implemented.
 *
 * When backend auth is added, this module will expose:
 * - AuthContext: current user, session, login state
 * - useAuth(): hook for reading auth state
 * - AuthGuard: route-level protection component
 * - Token storage: server-only HTTP-only cookies (NOT localStorage)
 * - Token refresh: transparent background refresh via cookie
 * - Logout: server-side session invalidation
 * - Unauthorized: redirect to /login when 401 received
 *
 * Security constraints (pre-enforced even before implementation):
 * - NO JWT or session tokens in localStorage
 * - NO credentials in query strings
 * - NO secrets in any client-side file
 * - Auth token transmission via Authorization header only
 * - API_BASE and WS_BASE via env vars only
 *
 * This file is a placeholder. No auth is active. All pages are accessible.
 * Deferred: pending backend auth endpoint definition.
 */

export type AuthStatus = "AUTHENTICATED" | "UNAUTHENTICATED" | "LOADING" | "DEFERRED";

export const AUTH_STATUS: AuthStatus = "DEFERRED";

export const AUTH_DEFERRED_REASON =
  "Authentication is intentionally deferred. Backend auth endpoints not yet implemented.";
