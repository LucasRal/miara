import { NextResponse, type NextRequest } from "next/server";

/**
 * Garde de navigation (convention Next 16 : proxy.ts, ex-middleware).
 *
 * Vérifie seulement la PRÉSENCE du cookie httpOnly `access` — la validité du
 * JWT est l'affaire du backend (le client api rejoue via /auth/refresh sur
 * 401). Les appels /api/* ne passent pas ici (matcher) : ils sont proxifiés
 * vers FastAPI par les rewrites de next.config.ts.
 */

const PUBLIC_PATHS = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has("access");
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (isPublic && hasSession) {
    return NextResponse.redirect(new URL("/", request.url));
  }
  if (!isPublic && !hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.svg$).*)"],
};
