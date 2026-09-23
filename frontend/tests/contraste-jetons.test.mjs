// Contraste des jetons de `globals.css` (WCAG 1.4.3 et 1.4.11).
//
// Le fichier de jetons est la seule source de vérité des couleurs du projet
// (règle de `AGENTS.md`) : il est donc le seul endroit où un contraste peut
// se dégrader. Ce test le lit tel quel, résout les `var(--x)` en chaîne, et
// échoue sous le seuil — 4,5:1 pour du texte, 3:1 pour un élément non textuel
// (bordure de champ, anneau de focus, pastille d'étape).
//
// Il ne remplace pas axe : axe ne calcule ni le texte SVG (le chiffre du
// `ScoreRing`) ni les éléments `aria-hidden`, qui sont précisément ceux que
// l'audit du 22/09/2026 a trouvés sous le seuil.

import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const CSS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../src/app/globals.css"),
  "utf8"
);

/** Jetons d'un bloc (`:root` ou `.dark`), `var()` non résolus. */
function bloc(selecteur) {
  const debut = CSS.indexOf(`\n${selecteur} {`);
  assert.ok(debut !== -1, `bloc ${selecteur} introuvable dans globals.css`);
  const fin = CSS.indexOf("\n}", debut);
  const jetons = {};
  for (const ligne of CSS.slice(debut, fin).split("\n")) {
    const m = ligne.match(/^\s*(--[a-z0-9-]+):\s*([^;]+);/i);
    if (m) jetons[m[1]] = m[2].trim();
  }
  return jetons;
}

const CLAIR = bloc(":root");
// `.dark` hérite de `:root` pour tout ce qu'il ne redéfinit pas.
const SOMBRE = { ...CLAIR, ...bloc(".dark") };

/** `var(--a)` -> valeur finale, en suivant la chaîne d'indirections. */
function resoudre(jetons, nom, profondeur = 0) {
  assert.ok(profondeur < 10, `cycle de var() sur ${nom}`);
  const brut = jetons[nom];
  assert.ok(brut, `jeton ${nom} absent`);
  const indirection = brut.match(/^var\((--[a-z0-9-]+)\)$/i);
  return indirection ? resoudre(jetons, indirection[1], profondeur + 1) : brut;
}

/** #rgb, #rrggbb, #rrggbbaa (alpha composé sur `fond`) -> [r, g, b]. */
function rgb(hex, fond = [255, 255, 255]) {
  let h = hex.replace("#", "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  assert.ok(/^[0-9a-f]{6}([0-9a-f]{2})?$/i.test(h), `couleur non hexadécimale : ${hex}`);
  const canaux = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  if (h.length === 8) {
    const a = parseInt(h.slice(6, 8), 16) / 255;
    return canaux.map((c, i) => Math.round(c * a + fond[i] * (1 - a)));
  }
  return canaux;
}

function luminance([r, g, b]) {
  const l = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
}

function contraste(jetons, avant, arriere) {
  const fond = rgb(resoudre(jetons, arriere));
  const [a, b] = [luminance(rgb(resoudre(jetons, avant), fond)), luminance(fond)].sort(
    (x, y) => y - x
  );
  return (a + 0.05) / (b + 0.05);
}

// [texte, fond, ce que ça rend à l'écran]
const TEXTE = [
  ["--foreground", "--background", "texte courant"],
  ["--muted-foreground", "--background", "texte secondaire"],
  ["--muted-foreground", "--muted", "texte secondaire sur surface atténuée"],
  ["--muted-foreground", "--secondary", "texte secondaire sur surface secondaire"],
  ["--amber-text", "--background", "ScoreRing bande 40-69, étape RH non atteignable"],
  ["--success", "--background", "ScoreRing bande 70-100"],
  ["--destructive", "--background", "ScoreRing bande 0-39, erreurs"],
  ["--primary", "--background", "liens et libellés de marque"],
  ["--primary-foreground", "--primary", "texte du bouton primaire"],
  ["--secondary-foreground", "--secondary", "texte du bouton secondaire"],
  ["--card-foreground", "--card", "texte d'une carte"],
];

// [couleur, fond adjacent, ce que ça rend à l'écran]
const NON_TEXTE = [
  ["--ring", "--background", "anneau de focus"],
  ["--ring", "--muted", "anneau de focus sur surface atténuée"],
  ["--input", "--background", "contour d'un champ de saisie"],
  ["--step-active", "--background", "pastille de l'étape en cours"],
  ["--primary-foreground", "--step-active", "icône blanche sur l'étape en cours"],
  ["--step-done", "--background", "pastille d'une étape terminée"],
];

for (const [nom, jetons] of [
  ["clair", CLAIR],
  ["sombre", SOMBRE],
]) {
  test(`contraste des jetons — thème ${nom}, texte (seuil 4,5:1)`, () => {
    for (const [avant, arriere, usage] of TEXTE) {
      const r = contraste(jetons, avant, arriere);
      assert.ok(
        r >= 4.5,
        `${usage} : ${avant} sur ${arriere} = ${r.toFixed(2)}:1, seuil 4,5:1`
      );
    }
  });

  test(`contraste des jetons — thème ${nom}, non textuel (seuil 3:1)`, () => {
    for (const [avant, arriere, usage] of NON_TEXTE) {
      const r = contraste(jetons, avant, arriere);
      assert.ok(r >= 3, `${usage} : ${avant} sur ${arriere} = ${r.toFixed(2)}:1, seuil 3:1`);
    }
  });
}

// `--step-todo` (étape à venir) et les chevrons du fil sont décoratifs : ils
// redoublent une information déjà portée par le texte (« (à venir) », lu par
// les lecteurs d'écran). Le test fige ce choix plutôt que de le taire.
test("les jetons décoratifs assumés restent sous le seuil, sciemment", () => {
  assert.ok(contraste(CLAIR, "--step-todo", "--background") < 3);
  assert.ok(contraste(CLAIR, "--amber", "--background") < 3, "--amber reste un aplat décoratif");
});
