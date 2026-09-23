import { NextResponse, type NextRequest } from "next/server";

import { ENTETE_CHEMIN } from "@/lib/session";

/**
 * Garde de navigation (convention Next 16 : proxy.ts, ex-middleware).
 *
 * Vérifie seulement la PRÉSENCE du cookie httpOnly `access` — la validité du
 * JWT est l'affaire du backend (le client api rejoue via /auth/refresh sur
 * 401). Les appels /api/* ne passent pas ici (matcher) : ils sont proxifiés
 * vers FastAPI par les rewrites de next.config.ts.
 */

const PUBLIC_PATHS = ["/login", "/register", "/mot-de-passe-oublie"];

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
  // Le chemin demandé, pour le rendu serveur : un layout ne connaît pas
  // l'URL courante, et la reprise de session doit savoir où revenir.
  const entetes = new Headers(request.headers);
  entetes.set(ENTETE_CHEMIN, pathname + request.nextUrl.search);
  return NextResponse.next({ request: { headers: entetes } });
}

/**
 * Ce que la garde NE voit PAS.
 *
 * `_next` en entier, et pas ses sous-chemins un par un : le serveur de
 * développement sert sous ce préfixe des routes internes que rien n'oblige à
 * rester stables (`_next/hmr` pour le rechargement à chaud, `_next/dev/*`).
 * Une garde de navigation, qui décide d'une redirection en fonction d'un
 * cookie de session, n'a rien à décider sur ces requêtes ; les énumérer
 * revenait à attendre la prochaine.
 *
 * Même raison pour `__nextjs*` (surcouche d'erreurs) et pour les fichiers de
 * métadonnées servis à la racine, qui doivent répondre à un visiteur anonyme :
 * un `robots.txt` qui redirige vers `/login` n'est pas un `robots.txt`.
 *
 * Tout le reste passe par la garde, y compris les requêtes de navigation
 * React des routes applicatives : c'est exactement ce qu'elle doit protéger.
 */
export const config = {
  matcher: [
    "/((?!api|_next|__nextjs|favicon.ico|robots.txt|sitemap.xml|manifest.webmanifest|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico)$).*)",
  ],
};
