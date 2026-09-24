// Cadrage des sections par espace de travail (`src/lib/navigation.ts`).
//
// Ce module est la source unique de la navigation ET des droits par segment :
// un onglet masqué doit rester une URL interdite. La séparation en espaces
// ajoute un second cadrage par-dessus le premier, et c'est là qu'une erreur
// serait coûteuse — cacher l'onglet d'un métier sans en interdire l'URL
// donnerait l'illusion d'une cloison qui n'existe pas.
//
// Le module est en TypeScript ; ce test le transpile avec le compilateur du
// projet plutôt que d'en recopier la logique, pour qu'il échoue quand le
// module change, pas quand la copie vieillit.
//
//   cd frontend && npm test

import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const SOURCE = join(dirname(fileURLToPath(import.meta.url)), "../src/lib/navigation.ts");
const js = ts.transpileModule(readFileSync(SOURCE, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const module_ = join(tmpdir(), `navigation-${process.pid}.mjs`);
writeFileSync(module_, js);
const nav = await import(module_);

test("chaque espace n'ouvre que ses propres sections métier", () => {
  const rh = nav.visibleSections("owner", "rh").map((s) => s.href);
  const commercial = nav.visibleSections("owner", "commercial").map((s) => s.href);

  assert.ok(rh.includes("/hr"), "l'espace RH montre la présélection");
  assert.ok(!rh.includes("/sales"), "l'espace RH ne montre pas l'agent commercial");
  assert.ok(!rh.includes("/sales/coach"), "ni le coach");
  assert.ok(commercial.includes("/sales") && commercial.includes("/sales/coach"));
  assert.ok(!commercial.includes("/hr"));

  // Les écrans transverses ne sont pas dupliqués : ils sont dans les deux.
  for (const href of ["/", "/activity", "/queue", "/usage", "/settings"]) {
    assert.ok(rh.includes(href) && commercial.includes(href), `${href} reste transverse`);
  }
});

test("l'espace cadre l'interface, il n'accorde aucun droit", () => {
  // Un membre RH dans « l'espace commercial » — état impossible par
  // l'interface, mais qu'un cookie forgé produirait — ne gagne rien.
  const forge = nav.visibleSections("hr", "commercial").map((s) => s.href);
  assert.ok(!forge.includes("/sales"), "le rôle continue de décider");
  assert.ok(!forge.includes("/usage"), "l'usage reste réservé à l'encadrement");

  // Et la garde serveur, qui ne connaît que le rôle, refuse le segment.
  assert.equal(nav.canAccess(nav.sectionFor("/sales"), "hr"), false);
  assert.equal(nav.canAccess(nav.sectionFor("/hr"), "sales"), false);
});

test("les espaces ouverts suivent le rôle", () => {
  assert.deepEqual(nav.espacesFor("owner"), ["rh", "commercial"]);
  assert.deepEqual(nav.espacesFor("admin"), ["rh", "commercial"]);
  assert.deepEqual(nav.espacesFor("hr"), ["rh"]);
  assert.deepEqual(nav.espacesFor("sales"), ["commercial"]);
  assert.deepEqual(nav.espacesFor(null), []);
});

test("l'URL prime sur le choix mémorisé, qui prime sur le premier espace ouvert", () => {
  // Suivre un lien vers /sales, c'est entrer dans l'espace commercial.
  assert.equal(nav.espaceActif("/sales/coach", "rh", "owner"), "commercial");
  // Sur un écran transverse, le choix mémorisé décide.
  assert.equal(nav.espaceActif("/activity", "commercial", "owner"), "commercial");
  // Sans choix, le premier espace ouvert au rôle.
  assert.equal(nav.espaceActif("/activity", null, "owner"), "rh");
  assert.equal(nav.espaceActif("/activity", null, "sales"), "commercial");
  // Un choix hors des espaces du rôle est ignoré, jamais honoré.
  assert.equal(nav.espaceActif("/activity", "commercial", "hr"), "rh");
  assert.equal(nav.espaceActif("/", "rh", null), null);
});

test("un espace sans section métier accessible n'est pas proposé", () => {
  // Invariant du modèle : un espace n'existe que par ses sections, donc
  // ajouter un espace sans section le rendrait invisible plutôt que vide.
  for (const espace of nav.ESPACES) {
    assert.ok(
      nav.SECTIONS.some((s) => s.espace === espace.id),
      `l'espace ${espace.id} n'a aucune section`
    );
    assert.ok(espace.accueil.startsWith("/"), "l'accueil d'un espace est un chemin");
    assert.ok(
      nav.SECTIONS.some((s) => s.href === espace.accueil),
      `l'accueil de ${espace.id} doit être une section connue`
    );
  }
});
