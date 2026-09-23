# Démonstration de soutenance — déroulé reproductible

Ce document décrit, pas à pas, la démonstration de trois minutes présentée en
soutenance. Il est écrit pour être rejoué : une personne qui dispose de la
machine de développement, du dépôt et du mot de passe du compte de
démonstration doit pouvoir obtenir exactement les mêmes écrans, dans le même
ordre, sans rien improviser. Les deux volets correspondent aux deux agents du
mémoire : l'agent commercial, qui lit le CRM et propose une écriture soumise à
confirmation humaine, et l'agent RH, qui présélectionne un lot de CV contre la
grille de critères d'une offre.

Tout ce qui est affirmé ici a été observé lors des répétitions consignées dans
`demo/repetitions.md` ; les durées citées sont des mesures, pas des
estimations, et les journaux correspondants se trouvent sous `demo/journaux/`.

## 1. Prérequis

### 1.1 Services à démarrer

La démonstration suppose les services natifs du poste de développement
(PostgreSQL, RabbitMQ, Redis) déjà lancés, puis, depuis la racine du dépôt,
trois processus dans trois terminaux distincts :

| Terminal | Commande | Rôle |
| --- | --- | --- |
| 1 | `make api` | API FastAPI sur le port **8010** |
| 2 | `make web` | Frontend Next.js sur le port **3010** |
| 3 | `make worker` | Deux workers Celery, un par file (`heavy` c4, `light` c2), comme le VPS |

Les ports sont fixes : 3010 pour le frontend, 8010 pour l'API. Le navigateur ne
parle qu'au 3010, qui réécrit `/api/*` vers le 8010. Depuis un poste distant,
on ouvre un tunnel SSH (`ssh -L 3010:localhost:3010 ubuntu@<vps>`) plutôt qu'un
port dans le pare-feu.

Deux vérifications valent la peine d'être faites avant d'entrer dans la salle :

1. `curl -s localhost:8010/health` doit renvoyer `"status":"healthy"` — c'est la
   sonde qui teste à la fois la base, le broker et Redis ;
2. le worker Celery doit être le **seul** consommateur des files. Si une
   campagne de charge (`make bench`) ou une évaluation (`make eval`) tourne,
   les messages se partagent entre consommateurs et la démonstration devient
   imprévisible. `ps ax | grep -E "celery|scripts.bench"` tranche la question.

Dans le navigateur, on utilise impérativement l'adresse **`http://localhost:3010`**
et non `http://127.0.0.1:3010`. Le serveur de développement Next 16 bloque ses
ressources de développement pour toute origine non déclarée dans
`allowedDevOrigins` : avec `127.0.0.1`, les pages s'affichent mais ne
s'hydratent jamais, si bien qu'aucun bouton ne répond. Cette subtilité a coûté
deux répétitions ; elle est consignée ici pour qu'elle n'en coûte pas une
troisième le jour de la soutenance.

### 1.2 Compte utilisé

La démonstration se fait avec un compte dédié, `demo-soutenance@test.miara.dev`,
membre `admin` de l'organisation **Lucas Corp** (`lucas-corp`). Cette
organisation est celle qui porte une connexion Salesforce réelle, établie par
le flux OAuth de l'application : le volet commercial lit et écrit donc dans une
véritable organisation Salesforce de développement, pas dans un simulateur.

Le compte se prépare, de façon idempotente, par le script
`demo/preparer_compte.py`, qui inscrit l'utilisateur par l'API publique puis
insère sa membership avec la connexion d'administration de la base — même
procédure que l'outillage de captures du mémoire :

```bash
cd backend && uv run python ../thesis/soutenance/demo/preparer_compte.py
```

Le mot de passe n'est pas dans le dépôt : il vit dans
`thesis/soutenance/demo/.env.local`, ignoré par git, aux côtés de l'adresse du
compte et du slug de l'organisation.

### 1.3 Bac à sable CRM (variante sans Salesforce)

Si la connexion Salesforce n'est pas disponible le jour J, le projet dispose
d'un bac à sable : `evals/data/sales/crm_seed.json`, chargé dans un `FakeCRM`
par `backend/scripts/crm_seed.py` (fonction `charger`). Deux réserves, qui
conditionnent son usage :

- le `FakeCRM` vit **en mémoire dans le processus de l'API** ; le peupler
  suppose donc de charger la graine au démarrage de ce processus, et non depuis
  un script séparé ;
- l'organisation visée doit porter une intégration `salesforce` dont les
  credentials chiffrés valent `{"mode": "fake"}`, ce que fait déjà
  `preparer_organisation()` du harnais d'évaluation pour l'organisation
  `harnais-eval`.

Le peuplement lui-même tient en trois lignes, à exécuter **dans le processus
qui sert l'API** (par exemple depuis un point d'entrée qui importe
`app.main:app` avant de lancer uvicorn) :

```python
from app.sales.crm import FakeCRM, register_fake
from scripts.crm_seed import charger, lire

crm = FakeCRM()
refs = await charger(crm, lire())   # 30 questions du jeu doré rejouables
register_fake(org_id, crm)          # org_id : l'organisation de démonstration
```

Cette variante n'a pas été jouée pendant les répétitions : le volet commercial
a été répété contre le Salesforce réel. Elle est documentée comme repli, non
comme chemin nominal, et elle demanderait de redémarrer l'API — ce qu'il vaut
mieux faire la veille, pas devant le jury.

### 1.4 Données du volet RH

Le volet RH s'appuie sur le jeu doré du mémoire : l'offre
`evals/data/hr/commercial-b2b/offre.md` et les vingt premiers CV (PDF et DOCX)
de `evals/data/hr/commercial-b2b/cv/`, pris dans l'ordre alphabétique
(`cv-001.pdf` à `cv-020.docx`). La grille de critères n'est pas recopiée depuis
`grille.json` : elle est **proposée par le modèle à partir du texte de l'offre**
pendant la démonstration, puis validée d'un clic, ce qui montre le geste réel
de l'utilisateur RH.

### 1.5 Réserve sur les modèles utilisés

`backend/.env` ne contient **pas** de clé Anthropic. Les alias de
`backend/config/llm.yaml` (`sales.route`, `sales.synthesize`, `hr.extract`,
`hr.score`) désignent tous un modèle Anthropic en `primary` ; faute de clé,
chaque appel bascule sur le repli OpenAI. Concrètement, pendant les
répétitions, `sales.route` a été servi par `gpt-4o-mini` et `sales.synthesize`
par `gpt-4o`, comme le montrent les lignes `llm_call` du journal de l'API.

C'est une démonstration parfaitement valable de l'architecture — c'est même la
démonstration du mécanisme de repli de l'ADR-011 — mais il faut le dire au jury
si la question des modèles est posée, et ne pas présenter les latences
observées comme celles de la configuration nominale.

## 2. Déroulé minute par minute

La démonstration dure trois minutes. Les temps ci-dessous sont des repères de
conduite ; les durées machine mesurées figurent au § 3.

### 00:00 — 00:20 · Ouverture et cadrage

Écran de départ : le tableau de bord (`http://localhost:3010/`), déjà
authentifié, avec l'en-tête « Miara · Lucas Corp · admin » visible. On annonce
en une phrase ce que la plateforme est : une application multi-locataire qui
héberge deux agents, l'un commercial, l'autre RH, pour une même organisation.

Ce qu'il faut montrer à l'écran : la barre de navigation (Tableau de bord,
Agent RH, Agent commercial, Coach, File de traitement, Usage, Paramètres) et le
nom de l'organisation active, qui matérialise le cloisonnement des données.

### 00:20 — 01:20 · Volet commercial

**00:20** — Aller sur *Agent commercial*, cliquer sur **Nouvelle
conversation**, puis saisir la question, au mot près :

> Que dois-je savoir avant d'appeler Edge Communications ?

**00:30** — Pendant que l'agent travaille, la trace s'écrit sous la
conversation, étape par étape. Il faut la commenter à voix haute : « Réflexion
du modèle (`sales.route`) », « Lecture Salesforce (`get_account_context`) »,
« Réflexion du modèle (`sales.synthesize`) », « Réponse rédigée ». C'est le
cœur du propos : l'agent est une boucle bornée d'appels d'outils typés, pas une
boîte noire.

**00:40** — Le briefing s'affiche. Montrer que chaque fait est accompagné de
l'identifiant Salesforce de l'enregistrement dont il provient — les deux
opportunités « Edge Emergency Generator », leur étape, leur montant, leur
échéance, puis les contacts principaux. Ces identifiants sont cliquables et
ouvrent la fiche dans Salesforce : le briefing est vérifiable, ce qui est la
réponse du mémoire à l'objection d'hallucination.

**00:55** — Deuxième message, au mot près :

> Crée une tâche de rappel pour vendredi : rappeler Edge Communications au sujet de l'opportunité Edge Emergency Generator.

**01:05** — Un dialogue de confirmation s'ouvre : « Confirmer l'action dans
Salesforce ». Il faut s'y arrêter. Il nomme l'outil (`create_task`), affiche en
français l'aperçu exact de ce qui sera écrit, et rappelle que rien n'est écrit
tant que l'humain n'a pas confirmé. C'est l'ADR-009 rendu visible : l'agent
propose, l'humain dispose.

**01:10** — Cliquer sur **Confirmer l'écriture**. L'écriture part, et
l'application affiche un accusé : une pastille « Enregistrement Salesforce
`00T…` ✓ ». Insister sur le fait que cet identifiant n'est pas une phrase du
modèle : il est relu dans le résultat de l'outil, donc dans la trace
d'exécution. Lors de la dernière répétition, la tâche créée portait
l'identifiant `00Tbm00000GvMLxEAN`.

### 01:20 — 02:50 · Volet RH

**01:20** — Aller sur *Agent RH*, puis **Nouvelle offre**. Coller le texte de
l'offre `commercial-b2b` dans le formulaire et valider par **Créer et proposer
la grille**.

**01:30** — Sur l'écran « 1. Grille de critères », cliquer sur **Proposer une
grille**. Le modèle lit l'offre et propose cinq à huit critères pondérés, dont
certains éliminatoires. Montrer qu'ils sont éditables : le recruteur reste
maître de la grille, l'agent ne fait qu'un premier jet. Valider par **Valider
la grille**.

**01:45** — Sur l'écran « 2. Dépôt des CV », déposer les vingt CV. Le compteur
« 20 CV déposés » apparaît, chaque ligne au statut « Déposé ». Cliquer sur
**Lancer l'analyse**.

**01:50** — L'écran de campagne s'ouvre. La barre de progression avance au fur
et à mesure que les CV sont extraits puis notés. Deux choses à dire pendant que
ça tourne : chaque CV est traité indépendamment, par deux tâches Celery sur la
file `heavy` (extraction puis notation), et la progression est relue en base —
on peut rafraîchir la page, fermer l'onglet, revenir : rien n'est perdu. C'est
aussi le moment d'ouvrir *File de traitement* dans un second onglet si l'on
veut montrer les tâches en cours.

**02:30** — Lorsque « Analyse terminée » s'affiche (comptez une quarantaine de
secondes à une minute pour vingt CV, d'après les répétitions), ouvrir l'onglet
**Classement**. Dérouler la carte du premier candidat : la note globale, le
détail critère par critère, et surtout les extraits du CV cités comme preuve.
Dire que la note n'a d'intérêt que parce qu'elle est justifiée, et que les
critères éliminatoires ramènent la note à zéro.

### 02:50 — 03:00 · Clôture

Revenir sur *Usage* pour montrer, en une phrase, que chaque appel de modèle est
journalisé avec son alias, son coût et sa version de prompt : la plateforme sait
ce qu'elle a dépensé et avec quel prompt elle l'a dépensé.

## 3. Ce que les répétitions ont mesuré

Les durées machine mesurées lors des répétitions (voir `demo/repetitions.md`
pour le détail, et `demo/journaux/*/journal.txt` pour la preuve) :

- volet commercial, rythme de démonstration (frappe au clavier visible et temps
  de lecture ménagés pour le film) : **51,1 s** et **51,7 s** sur deux
  répétitions ;
- volet commercial, rythme rapide (sans respiration) : **18,2 s** puis
  **16,6 s**. Dans ce mode, le temps machine se lit directement : environ 6 s
  entre l'envoi de la question et le briefing complet, 2 à 3 s entre la demande
  d'écriture et le dialogue de confirmation, 3 s entre la confirmation et
  l'accusé d'écriture ;
- volet RH, de la création de l'offre au dépôt des vingt CV : **11,3 s** ;
- volet RH, du clic sur « Lancer l'analyse » à « Analyse terminée », pour vingt
  CV : **43,7 s** lors de la répétition filmée, **55,9 s** lors de la répétition
  suivante, sur la même machine et le même lot ;
- démonstration complète, des deux volets enchaînés : **133,3 s** au rythme de
  démonstration (vidéo de **134,72 s**, durée mesurée sur le fichier) et
  **83,3 s** au rythme rapide.

Deux réserves sur ces chiffres. Les répétitions du seul volet commercial ont été
relevées **pendant qu'une campagne de charge occupait la machine** : elles ne
sont pas représentatives. Les deux répétitions complètes, elles, ont eu lieu
après la fin de cette campagne — mais l'écart de douze secondes entre 43,7 s et
55,9 s pour le même lot de vingt CV montre assez que la latence des modèles
varie d'une exécution à l'autre. Aucune de ces durées ne doit alimenter un
tableau de performance du mémoire : elles servent à caler la conduite de la
démonstration, rien de plus. Les chiffres de performance du mémoire viennent de
la campagne de charge (`make bench`), pas d'ici.

La vidéo de référence, qui montre le déroulé complet, est
`demo/journaux/2026-09-22T14-47-34-complet/video/demonstration-complet-2026-09-22T14-47-34.webm`
(1440×900, VP8, 134,72 s).

## 4. Répétition automatisée

Le déroulé ci-dessus est rejouable sans opérateur par le script Playwright
`demo/repetition.mjs`, qui pilote un vrai navigateur, prend les captures,
enregistre la vidéo et écrit un journal horodaté :

```bash
cd thesis/soutenance/demo
node repetition.mjs --volet=commercial --rythme=demo   # volet commercial, filmé
node repetition.mjs --volet=rh --cv=20                 # volet RH (worker requis)
node repetition.mjs --volet=complet --cv=20            # les deux d'une traite
node repetition.mjs --volet=rh --sans-lancement        # jusqu'au dépôt, sans toucher aux files
```

Le script n'installe aucun navigateur : il utilise le Chromium déjà présent
dans le cache Playwright de la machine, et le ffmpeg de ce même cache pour
encoder la vidéo. Chaque exécution écrit sous `demo/journaux/<horodatage>-<volet>/`
un `journal.jsonl`, un `journal.txt`, un `resume.json`, les captures commentées
(`legendes.md`) et, le cas échéant, la vidéo.

Une précaution est intégrée : le résumé note si une campagne de charge tournait
au départ et à l'arrivée, et l'option `--sans-lancement` permet de répéter tout
le volet RH sans jamais poster de tâche dans les files, ce qu'il faut faire tant
qu'une campagne occupe les workers.

## 5. Procédure de repli

Les incidents envisageables, par ordre de probabilité décroissante, et la
conduite à tenir.

**La première question commerciale échoue avec une erreur Salesforce.** Le
jeton d'accès stocké a expiré ; l'application le renouvelle toute seule, mais la
requête qui tombe pendant la fenêtre d'expiration peut échouer une fois. C'est
arrivé lors de la mise au point (erreur « Erreur Salesforce 404 »), et la
question posée à nouveau a fonctionné immédiatement. **Parade** : poser une
question anodine (« Cherche le compte Edge Communications. ») cinq minutes avant
la soutenance pour réveiller la connexion, et, si l'incident se produit devant
le jury, reposer simplement la question.

**Les boutons ne répondent pas.** L'adresse utilisée est probablement
`127.0.0.1:3010` : passer à `localhost:3010` et recharger.

**L'agent commercial ne trouve pas le compte.** Poser la question sur un autre
compte de l'organisation Salesforce de développement. Attention : les trois
suggestions affichées sur l'écran vide de la conversation (`TechStart`, `Edge
Communications`) proviennent du jeu de démonstration du `FakeCRM` et ne
correspondent pas toutes à des comptes de l'organisation réelle ; seule
`Edge Communications` a été vérifiée lors des répétitions.

**Le worker Celery ne consomme pas.** La barre de progression reste à zéro.
Vérifier qu'aucune autre campagne ne tourne, redémarrer `make worker`, et, si
rien n'y fait, passer à une campagne déjà terminée : l'écran de classement d'une
analyse antérieure se rouvre depuis la page de l'offre et montre exactement le
même écran de résultats.

**Le réseau ou un fournisseur de modèle est indisponible.** Projeter la vidéo de
la répétition (`demo/journaux/<horodatage>/video/*.webm`) et commenter par
dessus. La vidéo est produite par le même script que la démonstration : ce n'est
pas une reconstitution.

**Dernier repli, si tout est indisponible.** Les captures commentées de
`demo/journaux/<horodatage>/captures/` couvrent les quatre écrans clés :
briefing avec trace, dialogue de confirmation, accusé d'écriture, classement des
candidats.

## 6. Effets de bord à connaître

Chaque répétition du volet commercial crée une véritable tâche dans
l'organisation Salesforce de développement, et chaque répétition du volet RH
crée une offre nommée « Démonstration soutenance — commercial-b2b
(<horodatage>) » avec ses vingt candidatures. Ce n'est pas gênant pour un
environnement de développement, mais il faut le savoir avant de répéter dix
fois, et ne pas s'étonner de trouver, le jour J, la liste des offres peuplée de
répétitions passées.
