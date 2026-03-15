import { NextRequest, NextResponse } from 'next/server';

/**
 * Routes that require the user to be authenticated.
 * Unauthenticated requests are redirected to /login.
 */
const PROTECTED_PREFIXES = ['/dashboard', '/wiki', '/user'];

/**
 * Routes that should redirect to /dashboard when the user IS already logged in
 * (e.g. showing the login/register page to a logged-in user is pointless).
 */
const AUTH_ONLY_PATHS = ['/login', '/register'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check authentication via the token cookie (set by the frontend after login).
  // We store the JWT in localStorage on the client, so the middleware relies on
  // a lightweight "cw_authed" cookie that the frontend sets upon login/logout.
  const isAuthenticated = request.cookies.has('cw_authed');

  // Redirect unauthenticated users away from protected pages
  if (PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    if (!isAuthenticated) {
      const loginUrl = new URL('/login', request.url);
      loginUrl.searchParams.set('redirect', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // Redirect already-authenticated users away from login/register
  if (AUTH_ONLY_PATHS.includes(pathname) && isAuthenticated) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     *  - _next/static (static files)
     *  - _next/image  (image optimisation)
     *  - favicon.ico
     *  - public assets (images, etc.)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
