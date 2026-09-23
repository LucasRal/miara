// Non-régression du matcher de la garde de navigation (`src/proxy.ts`).
//
// Le matcher de Next doit être un littéral statique dans le fichier : il est
// lu par analyse statique au build, il ne peut donc pas être importé d'un
// module partagé avec ce test. Le test relit donc la source et reconstruit
// l'expression, ce qui a un avantage : il échoue aussi si quelqu'un remplace
// l'exclusion par une énumération de sous-chemins.
//
//   cd frontend && npm test

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const SOURCE = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "proxy.ts");
const source = readFileSync(SOURCE, "utf8");

const bloc = /matcher:\s*(\[[\s\S]*?\])\s*,?\s*\}/.exec(source);
assert.ok(bloc, "matcher introuvable dans src/proxy.ts");
// Prettier laisse une virgule finale dans le tableau : JSON ne l'accepte pas.
const motifs = JSON.parse(bloc[1].replace(/,(\s*])/, "$1"));
assert.equal(motifs.length, 1, "un seul motif attendu");

// Next compile le motif en expression ancrée sur le chemin complet.
const matcher = new RegExp(`^${motifs[0]}$`);
const garde = (chemin) => matcher.test(chemin);

test("le trafic interne de Next échappe à la garde", () => {
  for (const chemin of [
    "/_next/hmr", // rechargement à chaud : c'est le défaut qui a motivé ce test
    "/_next/dev/fallback",
    "/_next/static/chunks/main.js",
    "/_next/image",
    "/__nextjs_source-map",
    "/__nextjs_original-stack-frames",
  ]) {
    assert.equal(garde(chemin), false, `${chemin} ne doit pas traverser la garde`);
  }
});

test("l'exclusion porte sur tout _next, pas sur une liste de sous-chemins", () => {
  // Un sous-chemin inventé : si l'exclusion redevient une énumération, il
  // repasse par la garde et ce test tombe.
  assert.equal(garde("/_next/une-route-interne-future"), false);
  assert.equal(garde("/__nextjs_quelque_chose"), false);
});

test("les appels API et les fichiers publics échappent à la garde", () => {
  for (const chemin of [
    "/api/v1/auth/login",
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
    "/logo.svg",
    "/capture.png",
  ]) {
    assert.equal(garde(chemin), false, `${chemin} ne doit pas traverser la garde`);
  }
});

test("les routes applicatives restent gardées", () => {
  for (const chemin of [
    "/",
    "/login",
    "/register",
    "/sales",
    "/hr/new",
    "/hr/jobs/42/candidates",
    "/queue",
    "/settings",
    "/usage",
  ]) {
    assert.equal(garde(chemin), true, `${chemin} doit traverser la garde`);
  }
});
