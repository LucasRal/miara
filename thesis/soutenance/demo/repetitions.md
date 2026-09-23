# Compte rendu des répétitions

Ce fichier est factuel. Chaque répétition y figure avec sa date, ce qui a été
exécuté, son résultat, son temps total **mesuré** et ses incidents. Les temps
proviennent des journaux écrits par `repetition.mjs` (`journaux/<horodatage>-<volet>/journal.txt`
et `resume.json`) ; aucun n'est estimé. Les échecs sont consignés comme tels.

**Bilan : dix exécutions, sept réussies et trois en échec**, toutes documentées
ci-dessous avec leur cause. Parmi les sept réussites, deux couvrent la
démonstration complète (volet commercial puis volet RH de bout en bout), quatre
le seul volet commercial, et une — R4 — s'arrête volontairement au dépôt des CV
parce que la campagne de charge occupait encore les files. La carte demandait
cinq répétitions.

**Worker Celery.** Le volet RH exige un worker ; la campagne de charge en
faisait tourner les siens. Le worker de ces répétitions a donc été démarré
**après** la fin de la campagne, à **14:47:07 UTC** (prêt à 14:47:16), et arrêté
**à 14:51:45 UTC**, soit quatre minutes et demie d'existence, le temps des deux
répétitions complètes. Son journal est dans `journaux/worker.log`. Un autre worker, étranger à ces
répétitions, est apparu sur la machine à 14:52:54 UTC, après l'arrêt du nôtre :
il appartient à un autre travail en cours et n'a été ni utilisé ni arrêté ici.

**Avertissement, valable pour les répétitions E1 à R5 ci-dessous.** Une campagne
de tests de charge (`make bench`, sortie `bench/reports/20260922-134336/`)
occupait la machine pendant ces répétitions. Le script le vérifie lui-même au
démarrage et à la fin de chaque exécution, et le consigne dans `resume.json`
(champs `campagne_de_charge_en_cours_au_depart` et `..._a_la_fin`). Les temps
observés ne sont donc **pas représentatifs** et ne doivent alimenter aucun
tableau de performance du mémoire : ils ne servent qu'à caler la conduite de la
démonstration.

Deuxième réserve, de nature différente : `backend/.env` ne contient pas de clé
Anthropic. Tous les alias de modèles sont donc servis par leur repli OpenAI
(`sales.route` → `gpt-4o-mini`, `sales.synthesize` → `gpt-4o`, et de même pour
les alias RH). C'est le mécanisme de repli de l'ADR-011 qui fonctionne, mais ce
n'est pas la configuration nominale.

## Tableau de bord

| # | Début (UTC) | Contenu | Résultat | Durée mesurée | Campagne de charge |
| --- | --- | --- | --- | --- | --- |
| E1 | 2026-09-22 14:00:50 | Volet commercial, mise au point | **Échec** | 61,7 s | oui |
| E2 | 2026-09-22 14:02:36 | Volet commercial, mise au point | **Échec** | 181,9 s | oui |
| R1 | 2026-09-22 14:10:34 | Volet commercial, rythme rapide | Réussite | 18,2 s | oui |
| R2 | 2026-09-22 14:12:20 | Volet commercial, rythme démonstration | Réussite | 51,1 s | oui |
| R3 | 2026-09-22 14:12:44 | Volet commercial, rythme démonstration | Réussite | 51,7 s | oui |
| E3 | 2026-09-22 14:14:14 | Volet RH jusqu'au dépôt | **Échec** | 185,0 s | oui |
| R4 | 2026-09-22 14:17:41 | Volet RH jusqu'au dépôt des 20 CV | Réussite (arrêt volontaire) | 11,3 s | oui |
| R5 | 2026-09-22 14:22:06 | Volet commercial, rythme rapide, après correction du script | Réussite | 16,6 s | oui |
| **R6** | 2026-09-22 14:47:34 | **Démonstration complète (commercial + RH, 20 CV), rythme démonstration, filmée** | Réussite | 133,3 s · vidéo 134,72 s | **non** |
| R7 | 2026-09-22 14:50:09 | Démonstration complète, rythme rapide | Réussite | 83,3 s | **non** |

Les deux répétitions complètes R6 et R7 ont été jouées **après** la fin de la
campagne de charge (`campagne_de_charge_en_cours_au_depart` et `..._a_la_fin`
valent tous deux `false` dans leur `resume.json`). Leurs temps sont donc moins
suspects que les autres — ce qui ne veut pas dire qu'ils sont publiables : deux
exécutions ne font pas une mesure, et le mémoire tient ses chiffres de
performance de la campagne de charge, pas d'une démonstration.

**Lecture des durées.** En rythme de démonstration (`--rythme=demo`), les
durées d'étape incluent la frappe au clavier simulée et les temps de lecture
volontairement ménagés pour le film : elles décrivent la conduite de la
démonstration, pas le temps machine. Seules les répétitions en rythme rapide
donnent une idée du temps machine — et encore, sous la réserve de charge
rappelée plus haut.

## Détail

### E1 — 14:00:50 · échec · 61,7 s

**Exécuté** : `node repetition.mjs --volet=commercial`.

**Résultat** : échec à la première étape. Le script a rempli le formulaire de
connexion et cliqué sur « Se connecter » ; la page a simplement rechargé
`/login?` sans qu'aucune requête ne parte vers l'API.

**Incident et diagnostic** : le composant client de la page de connexion
n'était pas hydraté, si bien que le clic déclenchait la soumission HTML native
du formulaire. La cause n'était pas la lenteur du serveur de développement,
comme d'abord supposé, mais l'origine utilisée : le navigateur visitait
`http://127.0.0.1:3010`, et Next 16 bloque ses ressources de développement pour
toute origine absente d'`allowedDevOrigins` (message « Blocked cross-origin
request to Next.js dev resource »). Aucun script client n'était donc exécuté.

**Journal** : supprimé pendant la mise au point, avant que la décision de tout
consigner ne soit prise. Les durées ci-dessus proviennent de la sortie console
conservée au moment de l'exécution. C'est une faiblesse de traçabilité, signalée
ici plutôt que masquée.

### E2 — 14:02:36 · échec · 181,9 s

**Exécuté** : même commande, après ajout d'une attente d'hydratation et de deux
nouvelles tentatives.

**Résultat** : échec identique, trois fois de suite, pour la même raison
d'origine bloquée. C'est cet échec qui a conduit au diagnostic correct.

**Correction apportée** : le script utilise désormais `http://localhost:3010`,
et un repli est prévu si le formulaire reste inerte (ouverture de session par
l'API, cookies déposés dans le navigateur). Journal supprimé, même réserve que
pour E1.

### R1 — 14:10:34 · réussite · 18,2 s

**Exécuté** : `node repetition.mjs --volet=commercial`, rythme rapide.

**Déroulé mesuré** : connexion 2,5 s ; ouverture de l’agent commercial 1,7 s ;
question de lecture (briefing complet rendu) 6,1 s ; demande d'écriture jusqu'à
l'ouverture du dialogue de confirmation 3,4 s ; confirmation humaine jusqu'à
l'accusé d'écriture 3,3 s.

**Vérifié** : le briefing cite les deux opportunités « Edge Emergency
Generator » avec leur étape, leur montant et leur échéance, chacune suivie de
son identifiant Salesforce ; la trace affiche les quatre étapes de la boucle
(`sales.route` 1,1 s, `get_account_context` 0,8 s, `sales.synthesize` 2,3 s,
réponse rédigée) ; le dialogue de confirmation nomme `create_task` et affiche
l'aperçu en français ; après confirmation, la pastille « Enregistrement
Salesforce 00Tbm00000GvMLxEAN ✓ » apparaît.

**Incident** : aucun.

**Journal** : `journaux/2026-09-22T14-10-34-commercial/`.

### R2 — 14:12:20 · réussite · 51,1 s · vidéo 52,28 s

**Exécuté** : `node repetition.mjs --volet=commercial --rythme=demo`, en tâche
de fond.

**Résultat** : réussite complète, avec frappe au clavier visible et temps de
lecture entre les écrans. Vidéo produite et **mesurée** à 52,28 s avec le
ffmpeg du cache Playwright (`Duration: 00:00:52.28`).

**Incident** : l'outillage qui a lancé la tâche de fond a signalé un échec
(code de sortie 1) alors que le script s'est déroulé jusqu'au bout et a écrit
son résumé « réussite ». Le signal d'échec venait de la gestion de processus,
pas de l'application ; la vérification a porté sur les fichiers produits, qui
font foi.

**Journal** : `journaux/2026-09-22T14-12-20-commercial/`.

### R3 — 14:12:44 · réussite · 51,7 s · vidéo 53,12 s

**Exécuté** : même commande, au premier plan. Cette répétition a **chevauché**
R2 : deux navigateurs et deux conversations menaient la même démonstration en
parallèle, sur la même organisation. Les deux ont abouti, ce qui n'est pas une
mesure de tenue en charge mais montre au moins que rien ne s'est mélangé entre
les deux conversations.

**Vérifié** : mêmes écrans que R1, plus le rythme de démonstration.

**Incident** : aucun.

**Journal** : `journaux/2026-09-22T14-12-44-commercial/`.

### E3 — 14:14:14 · échec · 185,0 s

**Exécuté** : `node repetition.mjs --volet=rh --cv=20 --sans-lancement --sans-video`.

**Résultat** : échec après la création de l'offre. Le script attendait que les
champs de la grille de critères apparaissent d'eux-mêmes ; ils ne sont jamais
venus.

**Diagnostic** : la proposition de grille n'est pas automatique. L'écran
s'ouvre vide, avec un bouton « Proposer une grille » : c'est un geste explicite
de l'utilisateur, et le journal de l'API confirme qu'aucun appel
`/hr/jobs/{id}/criteria/suggest` n'avait été émis. Le script a été corrigé pour
cliquer ce bouton, ce qui rend d'ailleurs la démonstration plus fidèle au
parcours réel du recruteur. Journal supprimé pendant la mise au point.

### R4 — 14:17:41 · réussite (arrêt volontaire) · 11,3 s

**Exécuté** : `node repetition.mjs --volet=rh --cv=20 --sans-lancement --sans-video`.

**Résultat** : parcours RH validé de bout en bout **jusqu'au dépôt des CV**.
Création de l'offre 0,8 s ; proposition de la grille par le modèle 5,1 s ;
validation de la grille 1,7 s ; dépôt des vingt CV 0,3 s. La capture
`05-cv-deposes.png` montre le compteur « 20 CV déposés » et les vingt lignes au
statut « Déposé ».

**Pourquoi l'arrêt volontaire** : l'option `--sans-lancement` interrompt le
déroulé juste avant « Lancer l'analyse ». Une campagne de charge occupait alors
les files Celery avec ses propres workers ; poster nos tâches aurait faussé ses
mesures autant que les nôtres. Le résumé porte donc `"resultat":
"arret-volontaire"`, et non « réussite » : la partie analyse et classement n'a
pas été jouée à ce moment-là.

**Journal** : `journaux/2026-09-22T14-17-41-rh/`.

### R5 — 14:22:06 · réussite · 16,6 s

**Exécuté** : `node repetition.mjs --volet=commercial --sans-video`, après
correction d'un défaut du script de répétition.

**Défaut corrigé** : les appels `page.waitForFunction(fn, { timeout })`
passaient les options en deuxième position, là où Playwright attend l'argument
de la fonction évaluée. Le délai demandé était donc ignoré et le délai par
défaut (60 s) s'appliquait. Sans correction, l'attente de la fin d'analyse RH
— qui demande plusieurs minutes — aurait expiré au bout d'une minute et fait
échouer la répétition pour une raison purement instrumentale.

**Déroulé mesuré** : connexion 2,5 s ; ouverture de l’agent 1,6 s ; question de
lecture 5,8 s ; proposition d'écriture 2,4 s ; confirmation et accusé 3,0 s.

**Incident** : aucun.

**Journal** : `journaux/2026-09-22T14-22-06-commercial/`.

### R6 — 14:47:34 · réussite · 133,3 s · vidéo 134,72 s · **démonstration complète**

**Exécuté** : `node repetition.mjs --volet=complet --rythme=demo --cv=20`,
worker Celery démarré 27 secondes plus tôt, aucune campagne de charge en cours.

**Déroulé mesuré** (durées d'étape, respirations de démonstration incluses) :
connexion 2,7 s ; ouverture de l'agent commercial 1,8 s ; question de lecture
20,9 s ; demande d'écriture 19,3 s ; confirmation humaine 8,4 s ; création de
l'offre 6,2 s ; proposition de la grille 14,1 s ; validation de la grille
0,6 s ; dépôt des vingt CV 0,3 s ; lancement de l'analyse 2,8 s ; attente de la
fin d'analyse 31,5 s ; affichage du classement 10,3 s.

**Temps machine notable** : du clic sur « Lancer l'analyse » à l'affichage de
« Analyse terminée », **43,7 s pour vingt CV**, extraction et notation
comprises.

**Vérifié sur les captures** : la barre de progression à 1/20 avec les quatre
étapes de la campagne (extraction 20/20 lus, profil structuré, notation 1/20,
classement à venir) ; le classement final « 20 CV affichés sur 20 · 7 à
convoquer », le premier candidat noté 90 avec le détail critère par critère, les
preuves citées, les forces, les réserves et la confiance du modèle ; un candidat
« Hors profil » dont les critères éliminatoires non tenus sont nommés.

**Vidéo** : `journaux/2026-09-22T14-47-34-complet/video/demonstration-complet-2026-09-22T14-47-34.webm`,
1440×900, VP8, **durée mesurée 134,72 s** (`Duration: 00:02:14.72`, relevée sur
le fichier avec le ffmpeg du cache Playwright).

**Incident** : aucun.

### R7 — 14:50:09 · réussite · 83,3 s

**Exécuté** : `node repetition.mjs --volet=complet --cv=20 --sans-video`, rythme
rapide, pour vérifier que R6 n'était pas un coup de chance.

**Déroulé mesuré** : connexion 2,4 s ; ouverture de l'agent 1,6 s ; question de
lecture 6,1 s ; demande d'écriture 2,5 s ; confirmation 3,3 s ; création de
l'offre 0,9 s ; proposition de la grille 4,9 s ; validation 0,6 s ; dépôt des
vingt CV 0,2 s ; lancement 0,7 s ; attente de fin d'analyse 49,8 s ; classement
2,3 s. Du lancement à « Analyse terminée » : **55,9 s pour vingt CV**.

**Écart avec R6** : 43,7 s contre 55,9 s pour le même lot de vingt CV sur la
même machine, à douze minutes d'intervalle. C'est la variabilité ordinaire des
latences de modèle ; elle suffit à rappeler qu'aucun chiffre de performance ne
doit sortir d'une démonstration.

**Incident** : aucun.

**Journal** : `journaux/2026-09-22T14-50-09-complet/`.

## Ce qui reste incertain

- La variante « bac à sable `FakeCRM` » du volet commercial (§ 1.3 de
  `../demo.md`) n'a **pas** été répétée : elle suppose de peupler le `FakeCRM`
  dans le processus de l'API, donc de redémarrer celui-ci, ce qui n'était pas
  souhaitable pendant qu'une campagne et d'autres travaux partageaient la
  machine.
- Le repli « ouvrir une analyse antérieure » de la procédure de repli est
  désormais réalisable — les répétitions R6 et R7 ont laissé deux campagnes
  terminées dans l'organisation — mais il n'a pas été répété comme tel.
- Chaque répétition du volet commercial a créé une vraie tâche dans
  l'organisation Salesforce de développement (sept au total), et chaque
  répétition RH une offre avec vingt candidatures. Rien n'a été nettoyé.
