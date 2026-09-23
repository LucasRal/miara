// Répétition filmée de la démonstration de soutenance (Miara).
//
//   cd thesis/soutenance/demo
//   node repetition.mjs --volet=commercial          # volet commercial seul
//   node repetition.mjs --volet=rh --cv=20          # volet RH seul (worker requis)
//   node repetition.mjs --volet=complet --cv=20     # les deux, d'une traite
//   node repetition.mjs --volet=commercial --sans-video
//
// Ports fixes du projet : frontend 3010, backend 8010. Le navigateur ne parle
// qu'au 3010 (les appels /api sont réécrits vers le 8010 par Next).
//
// Le navigateur est celui déjà installé sur la machine (cache Playwright) :
// ce script n'en télécharge aucun. La vidéo est enregistrée par Playwright
// lui-même (`recordVideo`), qui utilise le ffmpeg de ce même cache.
//
// Chaque exécution écrit, sous --sortie (par défaut `journaux/<horodatage>/`) :
//   journal.jsonl   une ligne par étape : horodatage ISO, étape, durée en ms
//   journal.txt     le même journal en lecture directe
//   resume.json     le bilan : succès/échec, durées mesurées, vidéo produite
//   captures/*.png  les captures datées, décrites dans legendes.md
//   video/*.webm    la vidéo du contexte de navigation, si demandée
//
// Rien n'est inventé : les durées viennent de `performance.now()` autour de
// chaque étape, la durée de la vidéo se mesure sur le fichier produit.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, writeFileSync, appendFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright-core";

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE = resolve(ICI, "../../.."); // racine du dépôt

// --- options ---------------------------------------------------------------

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [cle, valeur] = a.replace(/^--/, "").split("=");
    return [cle, valeur ?? true];
  }),
);
const VOLET = args.volet ?? "complet";
const AVEC_VIDEO = !args["sans-video"];
const NB_CV = Number(args.cv ?? 20);
// `--rythme=demo` : frappe au clavier visible et temps de lecture entre les
// écrans, pour que la vidéo ressemble à ce que verra le jury. `rapide` (par
// défaut) enchaîne sans respiration : c'est le mode des répétitions.
const RYTHME = args.rythme ?? "rapide";
const DEMO = RYTHME === "demo";
const OFFRE = args.offre ?? "commercial-b2b";
// IMPORTANT : `localhost` et non `127.0.0.1`. Le serveur de développement Next
// bloque ses ressources de développement pour toute origine qui n'est pas
// déclarée (`allowedDevOrigins`) ; avec 127.0.0.1 la page s'affiche mais ne
// s'hydrate jamais, donc aucun bouton ne répond.
const BASE = process.env.DEMO_URL ?? "http://localhost:3010";
const HORODATAGE = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const SORTIE = resolve(ICI, args.sortie ?? join("journaux", `${HORODATAGE}-${VOLET}`));
const CAPTURES = join(SORTIE, "captures");
const VIDEO = join(SORTIE, "video");

// Le mot de passe ne figure pas dans le dépôt : il vient de .env.local.
const env = Object.fromEntries(
  (existsSync(join(ICI, ".env.local")) ? readFileSync(join(ICI, ".env.local"), "utf8") : "")
    .split("\n")
    .filter((l) => l.trim() && !l.startsWith("#") && l.includes("="))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i).trim(), l.slice(i + 1).trim()];
    }),
);
const EMAIL = process.env.DEMO_EMAIL ?? env.DEMO_EMAIL;
const MOT_DE_PASSE = process.env.DEMO_PASSWORD ?? env.DEMO_PASSWORD;
if (!EMAIL || !MOT_DE_PASSE) {
  console.error("DEMO_EMAIL / DEMO_PASSWORD absents (voir .env.local)");
  process.exit(2);
}

// --- questions et textes exacts de la démonstration -------------------------

const QUESTION_LECTURE =
  "Que dois-je savoir avant d'appeler Edge Communications ?";
const QUESTION_ECRITURE =
  "Crée une tâche de rappel pour vendredi : rappeler Edge Communications au sujet de l'opportunité Edge Emergency Generator.";

// --- journalisation ---------------------------------------------------------

mkdirSync(CAPTURES, { recursive: true });
if (AVEC_VIDEO) mkdirSync(VIDEO, { recursive: true });
const JOURNAL = join(SORTIE, "journal.jsonl");
const JOURNAL_TXT = join(SORTIE, "journal.txt");
const legendes = [];
const etapes = [];
const t0 = performance.now();

function noter(etape, extra = {}) {
  const entree = {
    horodatage: new Date().toISOString(),
    depuis_debut_ms: Math.round(performance.now() - t0),
    etape,
    ...extra,
  };
  etapes.push(entree);
  appendFileSync(JOURNAL, `${JSON.stringify(entree)}\n`);
  appendFileSync(
    JOURNAL_TXT,
    `${entree.horodatage}  +${String(entree.depuis_debut_ms).padStart(6)} ms  ${etape}` +
      `${extra.duree_ms !== undefined ? ` (${extra.duree_ms} ms)` : ""}` +
      `${extra.detail ? ` — ${extra.detail}` : ""}\n`,
  );
  console.log(`[${entree.depuis_debut_ms} ms] ${etape}${extra.detail ? ` — ${extra.detail}` : ""}`);
}

async function chronometrer(etape, fn) {
  const debut = performance.now();
  try {
    const valeur = await fn();
    noter(etape, { duree_ms: Math.round(performance.now() - debut), resultat: "ok" });
    return valeur;
  } catch (erreur) {
    noter(etape, {
      duree_ms: Math.round(performance.now() - debut),
      resultat: "echec",
      detail: String(erreur).slice(0, 300),
    });
    throw erreur;
  }
}

/** Temps de lecture, uniquement en rythme de démonstration. */
async function respirer(page, ms) {
  if (DEMO) await page.waitForTimeout(ms);
}

/** Saisie : au clavier (visible à l'écran) en rythme de démonstration. */
async function saisir(page, selecteur, texte) {
  if (DEMO) {
    await page.click(selecteur);
    await page.type(selecteur, texte, { delay: 28 });
  } else {
    await page.fill(selecteur, texte);
  }
}

async function capturer(page, nom, commentaire) {
  const date = new Date().toISOString();
  const fichier = join(CAPTURES, `${nom}.png`);
  await page.screenshot({ path: fichier, fullPage: false });
  legendes.push({ fichier: `captures/${nom}.png`, date, commentaire });
  noter(`capture ${nom}`, { detail: commentaire });
}

/** Sortie volontaire du déroulé (option --sans-lancement) : ce n'est pas un
 * échec, et le résumé ne doit pas le compter comme tel. */
class SortieAnticipee extends Error {}

// --- campagne de charge concurrente ----------------------------------------

function campagneDeChargeEnCours() {
  try {
    const sortie = execFileSync("bash", ["-lc", "ps ax | grep -c '[s]cripts.bench'"], {
      encoding: "utf8",
    });
    return Number(sortie.trim()) > 0;
  } catch {
    return false;
  }
}

// --- déroulé ----------------------------------------------------------------

const chargeAuDepart = campagneDeChargeEnCours();
noter("debut", {
  detail: `volet=${VOLET} video=${AVEC_VIDEO} campagne_de_charge=${chargeAuDepart}`,
});

const navigateur = await chromium.launch({
  args: ["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
});
const contexte = await navigateur.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: AVEC_VIDEO ? { dir: VIDEO, size: { width: 1440, height: 900 } } : undefined,
  locale: "fr-FR",
});
const page = await contexte.newPage();
page.setDefaultTimeout(60000);

let echec = null;
let arretVolontaire = false;
try {
  // 1. Connexion par le formulaire, comme un utilisateur.
  //
  // Le serveur de développement Next compile la route au premier accès :
  // cliquer avant l'hydratation du composant client déclenche une soumission
  // HTML native, qui recharge /login sans rien envoyer à l'API. On attend donc
  // que React soit attaché au champ avant de remplir quoi que ce soit.
  await chronometrer("connexion", async () => {
    let derniereErreur = null;
    for (const tentative of [1, 2, 3]) {
      try {
        await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
        await page.waitForSelector("#email");
        await page.waitForFunction(
          () => {
            const el = document.querySelector("#email");
            return (
              !!el &&
              Object.keys(el).some(
                (k) => k.startsWith("__reactProps$") || k.startsWith("__reactFiber$"),
              )
            );
          },
          null,
          { timeout: 30000 },
        );
        await page.waitForLoadState("networkidle").catch(() => {});
        await page.waitForTimeout(500);
        await page.fill("#email", EMAIL);
        await page.fill("#password", MOT_DE_PASSE);
        await Promise.all([
          page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 45000 }),
          page.click('button[type="submit"]'),
        ]);
        await page.waitForLoadState("networkidle").catch(() => {});
        return;
      } catch (erreur) {
        derniereErreur = erreur;
        noter("connexion — nouvelle tentative", { detail: `tentative ${tentative}` });
      }
    }
    // Repli documenté : on demande le jeton à l'API et on dépose dans le
    // navigateur exactement les cookies que l'API poserait à un utilisateur
    // réel. La session est la même ; seul l'écran de saisie est court-circuité.
    noter("connexion — repli par l'API", { detail: String(derniereErreur).slice(0, 200) });
    const reponse = await fetch(`${BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: EMAIL, password: MOT_DE_PASSE }),
    });
    if (reponse.status !== 200) throw derniereErreur;
    const cookies = (reponse.headers.getSetCookie?.() ?? []).map((brut) => {
      const [paire, ...attributs] = brut.split("; ");
      const i = paire.indexOf("=");
      const chemin = attributs.find((a) => a.toLowerCase().startsWith("path="));
      return {
        name: paire.slice(0, i),
        value: paire.slice(i + 1),
        domain: new URL(BASE).hostname,
        path: chemin ? chemin.slice(5) : "/",
        httpOnly: true,
      };
    });
    await contexte.addCookies(cookies);
    await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" });
  });
  await capturer(page, "00-tableau-de-bord", "Tableau de bord après connexion du compte de démonstration.");

  if (VOLET === "commercial" || VOLET === "complet") {
    await chronometrer("ouverture agent commercial", async () => {
      await page.goto(`${BASE}/sales`, { waitUntil: "domcontentloaded" });
      await page.waitForSelector('textarea[aria-label="Votre message"]');
      await page.click("text=Nouvelle conversation");
      await page.waitForTimeout(1000);
    });

    // 2. Question de lecture : briefing + trace des outils.
    await chronometrer("question de lecture", async () => {
      await respirer(page, 2000);
      await saisir(page, 'textarea[aria-label="Votre message"]', QUESTION_LECTURE);
      await page.click('button[aria-label="Envoyer"]');
      // La réponse est arrivée quand la zone de saisie est réactivée ET
      // qu'une bulle d'assistant contient du texte.
      await page.waitForFunction(
        () => {
          const bulles = [...document.querySelectorAll(".bg-muted")];
          return bulles.some((b) => (b.textContent ?? "").length > 80);
        },
        null,
        { timeout: 120000 },
      );
      await page.waitForTimeout(1500);
      await respirer(page, 8000);
    });
    await capturer(
      page,
      "01-briefing-et-trace",
      "Briefing sourcé rendu par l'agent commercial, avec la trace des outils appelés sous la réponse.",
    );

    // 3. Action d'écriture : proposée, puis confirmée par l'humain (ADR-009).
    await chronometrer("demande d'écriture", async () => {
      await respirer(page, 4000);
      await saisir(page, 'textarea[aria-label="Votre message"]', QUESTION_ECRITURE);
      await page.click('button[aria-label="Envoyer"]');
      await page.waitForSelector('[role="dialog"]', { timeout: 120000 });
      await page.waitForTimeout(800);
      await respirer(page, 5000);
    });
    await capturer(
      page,
      "02-confirmation-ecriture",
      "Dialogue de confirmation : l'agent propose create_task, rien n'est écrit tant que l'humain n'a pas confirmé (ADR-009).",
    );

    await chronometrer("confirmation humaine", async () => {
      await page.click("text=Confirmer l'écriture");
      await page.waitForFunction(
        () => /Enregistrement Salesforce \w+/.test(document.body.innerText),
        null,
        { timeout: 120000 },
      );
      await page.waitForTimeout(1200);
      await respirer(page, 5000);
    });
    await capturer(
      page,
      "03-ecriture-confirmee",
      "Accusé d'écriture : l'identifiant de l'enregistrement créé dans Salesforce, relu dans la trace d'exécution.",
    );
  }

  if (VOLET === "rh" || VOLET === "complet") {
    const dossierOffre = join(RACINE, "evals", "data", "hr", OFFRE);
    const texteOffre = readFileSync(join(dossierOffre, "offre.md"), "utf8").slice(0, 4000);
    const titre = `Démonstration soutenance — ${OFFRE} (${HORODATAGE})`;
    const cvs = readdirSync(join(dossierOffre, "cv"))
      .filter((f) => /\.(pdf|docx)$/i.test(f))
      .sort()
      .slice(0, NB_CV)
      .map((f) => join(dossierOffre, "cv", f));

    // 4. Création de l'offre.
    await chronometrer("création de l'offre", async () => {
      await page.goto(`${BASE}/hr/new`, { waitUntil: "domcontentloaded" });
      await page.waitForSelector("#title");
      await saisir(page, "#title", titre);
      await page.fill("#description", texteOffre);
      await respirer(page, 2000);
      await Promise.all([
        page.waitForURL(/\/hr\/[0-9a-f-]+\/criteria/, { timeout: 120000 }),
        page.click('button[type="submit"]'),
      ]);
    });

    // 5. Grille de critères : proposition par le modèle, puis validation.
    // La proposition de grille n'est pas automatique : c'est un geste de
    // l'utilisateur (bouton « Proposer une grille »), et le modèle répond en
    // quelques secondes à partir du seul texte de l'offre.
    await chronometrer("proposition de la grille", async () => {
      await page.waitForSelector("text=Proposer une grille", { timeout: 60000 });
      await respirer(page, 2000);
      await page.click("text=Proposer une grille");
      await page.waitForSelector('input[placeholder="Intitulé du critère"]', { timeout: 180000 });
      await page.waitForTimeout(1000);
      await respirer(page, 6000);
    });
    await capturer(
      page,
      "04-grille-de-criteres",
      "Grille de critères proposée à partir du texte de l'offre, avant validation humaine.",
    );

    await chronometrer("validation de la grille", async () => {
      await page.click("text=Valider la grille");
      await page.waitForURL(/\/hr\/[0-9a-f-]+\/candidates/, { timeout: 60000 });
      await page.waitForSelector('input[aria-label="Choisir des CV à déposer"]', {
        state: "attached",
      });
    });

    // 6. Dépôt des CV.
    await chronometrer(`dépôt de ${cvs.length} CV`, async () => {
      await page.setInputFiles('input[aria-label="Choisir des CV à déposer"]', cvs);
      await page.waitForFunction(
        (n) => new RegExp(`${n} CV déposés`).test(document.body.innerText),
        cvs.length,
        { timeout: 300000 },
      );
    });
    await capturer(
      page,
      "05-cv-deposes",
      `Les ${cvs.length} CV du jeu doré déposés sur l'offre, prêts à être analysés.`,
    );

    // `--sans-lancement` : on s'arrête avant de mettre des tâches dans les
    // files. Indispensable tant qu'une campagne de charge tourne : ses propres
    // workers consommeraient nos messages et fausseraient ses mesures.
    if (args["sans-lancement"]) {
      noter("arrêt avant lancement (--sans-lancement)");
      throw new SortieAnticipee();
    }

    // 7. Lancement de la campagne et suivi de la progression.
    await chronometrer("lancement de l'analyse", async () => {
      await page.click("text=Lancer l'analyse");
      await page.waitForURL(/\/hr\/[0-9a-f-]+\/runs\/[0-9a-f-]+/, { timeout: 60000 });
      await page.waitForSelector('[role="progressbar"]', { timeout: 60000 });
    });
    await page.waitForTimeout(6000);
    await respirer(page, 6000);
    await capturer(
      page,
      "06-progression",
      "Progression de la présélection : la barre est relue en base, la campagne survit à un rafraîchissement.",
    );

    await chronometrer("analyse terminée", async () => {
      await page.waitForFunction(() => /Analyse terminée/.test(document.body.innerText), null, {
        timeout: 1800000,
      });
    });
    // Le classement n'est pas un onglet : il s'écrit sous la progression, au
    // fur et à mesure. On attend le décompte des CV affichés, puis on déplie la
    // carte du premier candidat pour montrer les preuves citées.
    await chronometrer("affichage du classement", async () => {
      await page.waitForFunction(() => /CV affichés? sur \d+/.test(document.body.innerText), null, {
        timeout: 120000,
      });
      await page.evaluate(() => window.scrollBy(0, 420));
      await page.waitForTimeout(800);
      const detail = page.locator("text=Détail").first();
      if (await detail.count()) {
        await detail.click().catch(() => {});
        await page.waitForTimeout(1200);
      }
      await respirer(page, 8000);
    });
    await capturer(
      page,
      "07-classement",
      "Classement des candidats : note globale, critères et preuves citées, CV par CV.",
    );
  }
} catch (erreur) {
  if (erreur instanceof SortieAnticipee) {
    arretVolontaire = true;
  } else {
  echec = String(erreur);
  noter("echec", { detail: echec.slice(0, 500) });
  await capturer(page, "99-echec", `État de l'écran au moment de l'échec : ${echec.slice(0, 200)}`).catch(
    () => {},
  );
  }
} finally {
  const dureeTotaleMs = Math.round(performance.now() - t0);
  await page.close();
  await contexte.close(); // c'est la fermeture du contexte qui finalise la vidéo
  await navigateur.close();

  // Nomme la vidéo et mesure sa durée réelle sur le fichier.
  let video = null;
  if (AVEC_VIDEO && existsSync(VIDEO)) {
    const fichiers = readdirSync(VIDEO).filter((f) => f.endsWith(".webm"));
    if (fichiers.length === 1) {
      const cible = join(VIDEO, `demonstration-${VOLET}-${HORODATAGE}.webm`);
      renameSync(join(VIDEO, fichiers[0]), cible);
      video = cible;
    } else if (fichiers.length > 1) {
      video = join(VIDEO, fichiers[0]);
    }
  }

  // Durée de la vidéo : MESURÉE sur le fichier, avec le ffmpeg du cache
  // Playwright (celui-là même qui a encodé la vidéo). Jamais estimée.
  let videoDureeS = null;
  if (video) {
    try {
      const ffmpeg = execFileSync("bash", [
        "-lc",
        `ls "${process.env.PLAYWRIGHT_BROWSERS_PATH ?? `${process.env.HOME}/.cache/ms-playwright`}"/ffmpeg-*/ffmpeg-linux | tail -1`,
      ])
        .toString()
        .trim();
      const sortie = execFileSync("bash", ["-lc", `"${ffmpeg}" -i "${video}" 2>&1 | grep Duration`])
        .toString()
        .trim();
      const m = /Duration: (\d+):(\d+):(\d+\.\d+)/.exec(sortie);
      if (m) videoDureeS = Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]);
      noter("durée de la vidéo mesurée", { detail: `${videoDureeS} s (${sortie})` });
    } catch (erreur) {
      noter("durée de la vidéo non mesurable", { detail: String(erreur).slice(0, 200) });
    }
  }

  writeFileSync(
    join(SORTIE, "legendes.md"),
    `# Captures de la répétition ${HORODATAGE} (volet ${VOLET})\n\n` +
      legendes
        .map((l) => `## ${l.fichier}\n\nPrise le ${l.date}.\n\n${l.commentaire}\n`)
        .join("\n") +
      "\n",
  );

  const resume = {
    horodatage: HORODATAGE,
    debut: etapes[0]?.horodatage,
    fin: new Date().toISOString(),
    volet: VOLET,
    resultat: echec ? "echec" : arretVolontaire ? "arret-volontaire" : "reussite",
    erreur: echec,
    duree_totale_ms: dureeTotaleMs,
    duree_totale_s: Math.round(dureeTotaleMs / 100) / 10,
    campagne_de_charge_en_cours_au_depart: chargeAuDepart,
    campagne_de_charge_en_cours_a_la_fin: campagneDeChargeEnCours(),
    nb_cv: VOLET === "commercial" ? 0 : NB_CV,
    captures: legendes,
    video,
    video_duree_s_mesuree: videoDureeS,
    rythme: RYTHME,
    etapes,
  };
  writeFileSync(join(SORTIE, "resume.json"), `${JSON.stringify(resume, null, 2)}\n`);
  console.log(`\n-> ${SORTIE}`);
  console.log(`   ${echec ? "ÉCHEC" : "réussite"} en ${resume.duree_totale_s} s`);
  if (video) console.log(`   vidéo : ${video}`);
  process.exit(echec ? 1 : 0);
}
