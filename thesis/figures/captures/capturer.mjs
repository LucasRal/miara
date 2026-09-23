// Captures d'ecran datees de l'application, pour les figures du memoire.
//
//   cd thesis/figures && CAPTURES_PASSWORD='...' node captures/capturer.mjs
//
// Le frontend doit tourner sur le port 3010 et le backend sur le 8010 (ports
// fixes du projet, en developpement comme en production). Le navigateur est
// celui deja installe sur la machine : ce script n'en telecharge aucun.
//
// Chaque execution ecrit dans captures/out/ :
//   <nom>.png          la capture
//   manifeste.json     date ISO, revision git, adresse visitee, taille
// La date du manifeste est celle qui doit figurer dans la legende de la figure.

import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import puppeteer from "puppeteer-core";

const ICI = dirname(fileURLToPath(import.meta.url));
const SORTIE = resolve(ICI, "out");
const BASE = process.env.CAPTURES_URL ?? "http://127.0.0.1:3010";
const EMAIL = process.env.CAPTURES_EMAIL ?? "captures-memoire@test.miara.dev";
const MOT_DE_PASSE = process.env.CAPTURES_PASSWORD;

if (!MOT_DE_PASSE) {
  console.error("CAPTURES_PASSWORD absent de l'environnement");
  process.exit(1);
}

const NAVIGATEUR =
  process.env.PUPPETEER_EXECUTABLE_PATH ??
  execSync(
    `find "${process.env.PLAYWRIGHT_BROWSERS_PATH ?? `${process.env.HOME}/.cache/ms-playwright`}" -maxdepth 3 -type f -name chrome | sort | tail -1`,
    { encoding: "utf8" },
  ).trim();

// Les pages a photographier. `attendre` est un selecteur qui prouve que les
// donnees sont arrivees : sans lui on photographierait un squelette de
// chargement.
// `clics` : selecteurs actionnes apres le chargement, pour les ecrans dont
// l'etat interessant n'a pas d'adresse propre (ouverture d'une conversation).
const PAGES = JSON.parse(
  process.env.CAPTURES_PAGES ??
    JSON.stringify([
      { nom: "ecran-tableau-de-bord", chemin: "/", attendre: "main" },
      { nom: "ecran-agent-commercial", chemin: "/sales", attendre: "main" },
      { nom: "ecran-coach", chemin: "/sales/coach", attendre: "main" },
      { nom: "ecran-hr-offres", chemin: "/hr", attendre: "main" },
      { nom: "ecran-file-traitement", chemin: "/queue", attendre: "main" },
      { nom: "ecran-usage", chemin: "/usage", attendre: "main" },
      { nom: "ecran-parametres", chemin: "/settings", attendre: "main" },
    ]),
);

const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

mkdirSync(SORTIE, { recursive: true });

const navigateur = await puppeteer.launch({
  executablePath: NAVIGATEUR,
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
});
const page = await navigateur.newPage();
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

// Connexion : on demande le jeton a l'API et on le depose dans le navigateur.
// Passer par le formulaire obligerait a attendre l'hydratation du composant
// client du serveur de developpement, ce qui rend le script instable ; le
// cookie obtenu est exactement celui que l'API pose a un utilisateur reel.
const auth = await fetch(`${BASE}/api/v1/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email: EMAIL, password: MOT_DE_PASSE }),
});
if (auth.status !== 200) {
  console.error(`connexion refusee : ${auth.status} ${await auth.text()}`);
  await navigateur.close();
  process.exit(1);
}
const cookies = (auth.headers.getSetCookie?.() ?? []).map((brut) => {
  const [paire, ...attributs] = brut.split("; ");
  const index = paire.indexOf("=");
  const chemin = attributs.find((a) => a.toLowerCase().startsWith("path="));
  return {
    name: paire.slice(0, index),
    value: paire.slice(index + 1),
    domain: new URL(BASE).hostname,
    path: chemin ? chemin.slice(5) : "/",
    httpOnly: true,
  };
});
await navigateur.setCookie(...cookies);

// L'ecran de connexion lui-meme, avant d'etre authentifie.
const anonyme = await navigateur.createBrowserContext();
const pageAnonyme = await anonyme.newPage();
await pageAnonyme.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
await pageAnonyme.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
await dormir(2500);
await pageAnonyme.screenshot({ path: resolve(SORTIE, "ecran-connexion.png") });
await anonyme.close();

const revision = execSync("git rev-parse --short HEAD", { cwd: ICI, encoding: "utf8" }).trim();
const entrees = [{ nom: "ecran-connexion", adresse: "/login", fichier: "captures/out/ecran-connexion.png", largeur: 1440, hauteur: 900 }];
const supplementaires = JSON.parse(process.env.CAPTURES_EXTRA ?? "[]");

// Une page n'est photographiable que lorsque ses donnees sont arrivees : on
// attend la disparition des libelles de chargement plutot qu'un delai fixe.
async function attendreDonnees(limite = 60000) {
  const debut = Date.now();
  while (Date.now() - debut < limite) {
    const charge = await page
      .evaluate(() => !/Chargement/.test(document.body.innerText))
      .catch(() => false);
    if (charge) return true;
    await dormir(500);
  }
  return false;
}

for (const cible of [...PAGES, ...supplementaires]) {
  await page.goto(`${BASE}${cible.chemin}`, { waitUntil: "networkidle2" });
  await page.waitForSelector(cible.attendre, { timeout: 20000 }).catch(() => {});
  await dormir(1500);
  for (const selecteur of cible.clics ?? []) {
    await page.waitForSelector(selecteur, { timeout: 15000 }).catch(() => {});
    await page.click(selecteur).catch(() => {});
    await dormir(1500);
  }
  if (!(await attendreDonnees())) {
    // Le serveur de developpement compile la route au premier acces : une
    // seconde tentative suffit en general.
    await page.reload({ waitUntil: "networkidle2" });
    for (const selecteur of cible.clics ?? []) {
      await page.waitForSelector(selecteur, { timeout: 15000 }).catch(() => {});
      await page.click(selecteur).catch(() => {});
      await dormir(1500);
    }
    if (!(await attendreDonnees())) {
      console.warn(`   ATTENTION ${cible.nom} : donnees non chargees, capture inutilisable`);
    }
  }
  await dormir(1500);
  const fichier = resolve(SORTIE, `${cible.nom}.png`);
  await page.screenshot({ path: fichier, fullPage: false });
  entrees.push({
    nom: cible.nom,
    adresse: cible.chemin,
    fichier: `captures/out/${cible.nom}.png`,
    largeur: 1440,
    hauteur: 900,
  });
  console.log(`-> ${cible.nom}`);
}

writeFileSync(
  resolve(SORTIE, "manifeste.json"),
  `${JSON.stringify({ date: new Date().toISOString(), revision, base: BASE, captures: entrees }, null, 2)}\n`,
);

await navigateur.close();
console.log(`Captures ecrites dans thesis/figures/captures/out/ (revision ${revision})`);
