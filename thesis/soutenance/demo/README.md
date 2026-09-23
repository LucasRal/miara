# Artefacts de la démonstration de soutenance

Ce dossier contient tout ce qui permet de rejouer, de vérifier et de projeter
la démonstration décrite dans `../demo.md`.

| Fichier | Rôle |
| --- | --- |
| `repetition.mjs` | Script Playwright qui rejoue la démonstration dans un vrai navigateur, prend les captures, filme et journalise. |
| `preparer_compte.py` | Prépare (de façon idempotente) le compte de démonstration et sa membership. |
| `repetitions.md` | Compte rendu factuel des répétitions : date, contenu, résultat, durées mesurées, incidents. |
| `journaux/` | Une sous-arborescence par exécution : `journal.txt`, `journal.jsonl`, `resume.json`, `captures/`, `legendes.md`, `video/`. |
| `.env.local` | Adresse et mot de passe du compte de démonstration. **Non versionné** (voir `.gitignore`). |
| `package.json`, `node_modules/` | La seule dépendance du script : `playwright-core`, qui pilote le Chromium déjà installé sur la machine. Aucun navigateur n'est téléchargé. |

## Artefacts de référence (répétition complète du 22/09/2026 à 14:47:34 UTC)

- **Vidéo** : `journaux/2026-09-22T14-47-34-complet/video/demonstration-complet-2026-09-22T14-47-34.webm`
  — 1440×900, VP8, durée **134,72 s** mesurée sur le fichier.
- **Captures commentées** : `journaux/2026-09-22T14-47-34-complet/captures/`
  (huit écrans, du tableau de bord au classement) et leurs légendes datées dans
  `journaux/2026-09-22T14-47-34-complet/legendes.md`.
- **Journal** : `journaux/2026-09-22T14-47-34-complet/journal.txt`.
- **Journal du worker Celery** : `journaux/worker.log` (démarrage 14:47:07,
  arrêt 14:51:45 UTC).

## Rejouer

```bash
cd thesis/soutenance/demo
node repetition.mjs --volet=complet --rythme=demo --cv=20
```

Options utiles : `--volet=commercial|rh|complet`, `--rythme=demo|rapide`,
`--cv=<n>`, `--sans-video`, `--sans-lancement` (s'arrête avant de poster des
tâches dans les files Celery), `--offre=<dossier de evals/data/hr>`,
`--sortie=<dossier>`.

## Conventions de vérité

Les durées écrites dans `resume.json` sont mesurées autour de chaque étape ; la
durée de la vidéo est relue sur le fichier produit avec le `ffmpeg` du cache
Playwright, jamais estimée. Chaque exécution enregistre si une campagne de
charge tournait au départ et à l'arrivée : si c'est le cas, les temps observés
ne valent pas comme mesure de performance et ne doivent alimenter aucun tableau
du mémoire.
