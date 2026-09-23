// Non-régression : jeton présent mais refusé ne doit plus boucler.
//
// La boucle corrigée venait d'une paire de règles, pas d'une seule :
// `proxy.ts` renvoie `/login` vers `/` dès qu'un cookie `access` existe, et le
// rendu serveur renvoyait `/` vers `/login` dès que `/me` refusait la session.
// Ces tests tiennent les deux bouts de la paire. Ils lisent les sources : ce
// projet n'embarque pas de moteur de test capable d'exécuter du TSX, et les
// comportements eux-mêmes sont vérifiés dans un navigateur (voir le
// commentaire de la carte Trello correspondante).
//
//   cd frontend && npm test

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const lire = (...morceaux) => readFileSync(join(SRC, ...morceaux), "utf8");

function fichiers(racine) {
  return readdirSync(racine).flatMap((nom) => {
    const chemin = join(racine, nom);
    if (statSync(chemin).isDirectory()) return fichiers(chemin);
    return [".ts", ".tsx"].includes(extname(nom)) ? [chemin] : [];
  });
}

test("aucun rendu serveur ne renvoie une session refusée droit vers /login", () => {
  const coupables = fichiers(SRC).filter((f) =>
    readFileSync(f, "utf8").includes('redirect("/login")')
  );
  assert.deepEqual(
    coupables,
    [],
    "une session refusée doit passer par reprendreSession() : rediriger vers /login reboucle " +
      "sur la garde, qui renvoie /login vers / tant que le cookie access existe"
  );
});

test("la reprise de session est branchée là où la session est refusée", () => {
  for (const fichier of ["app/(app)/layout.tsx", "lib/guard.tsx"]) {
    const source = lire(...fichier.split("/"));
    assert.match(source, /reprendreSession\(/, `${fichier} doit déléguer à la reprise de session`);
  }
});

test("la page de reprise tente la rotation, puis déconnecte, et borne la récidive", () => {
  const page = lire("app", "session", "page.tsx");
  assert.match(
    page,
    /^"use client";/,
    "la rotation a besoin du navigateur : le cookie refresh est limité à /api/v1/auth"
  );
  assert.match(page, /auth\/refresh/, "elle doit tenter la rotation avant d'abandonner");
  assert.match(page, /auth\/logout/, "elle doit effacer les cookies quand la rotation échoue");
  assert.match(
    page,
    /sessionStorage/,
    "sans garde-fou de récidive, une session refusée pour une autre raison reboucle"
  );
});

test("le chemin de retour est refusé s'il n'est pas interne", () => {
  const source = lire("lib", "session.ts");
  assert.match(
    source,
    /startsWith\("\/\/"\)/,
    "un //hote externe doit être rejeté (open redirect)"
  );
  assert.match(source, /startsWith\("\/"\)/, "seul un chemin absolu interne est accepté");
  assert.match(source, /CHEMIN_REPRISE/, "la reprise ne doit pas pouvoir se renvoyer à elle-même");
});

test("la garde ne traite pas la reprise comme une route publique", () => {
  const proxy = lire("proxy.ts");
  const publiques = /const PUBLIC_PATHS = (\[[^\]]*\])/.exec(proxy);
  assert.ok(publiques, "PUBLIC_PATHS introuvable");
  const chemins = JSON.parse(publiques[1].replace(/,(\s*])/, "$1"));
  assert.ok(
    !chemins.includes("/session"),
    "publique, /session serait renvoyée vers / par la garde : la boucle reviendrait par l'autre bout"
  );
});

test("la garde renvoie toujours une session valide hors des pages publiques", () => {
  // Règle correcte, que la carte interdit de supprimer pour casser la boucle.
  assert.match(lire("proxy.ts"), /isPublic && hasSession/);
});
