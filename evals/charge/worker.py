"""Workers Celery pilotés par la campagne, et relevé de leur mémoire.

La carte fait varier `worker_concurrency`. Ce paramètre n'existe que s'il y a
de vrais processus workers : la campagne en démarre donc un, à la concurrence
demandée, et l'arrête à la fin du scénario.

Deux garde-fous.

**Aucun worker étranger pendant une mesure.** Deux workers abonnés aux mêmes
files se partagent les messages : la concurrence effective ne serait plus
celle qu'on croit mesurer, et le chiffre serait faux sans que rien ne le dise.
La campagne refuse de démarrer tant qu'un autre worker répond au ping.

**La mémoire se relève sur l'arbre de processus, pas sur le seul parent.**
Celery préforke : la mémoire du lot est la somme des RSS du parent et de ses
enfants, échantillonnée pendant le lot.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

from app.core.celery_app import celery_app

PROC = Path("/proc")


def rss_ko(pid: int) -> int:
    """Résident en Ko d'un processus, 0 s'il a disparu entre-temps."""
    try:
        for ligne in (PROC / str(pid) / "status").read_text(encoding="utf-8").splitlines():
            if ligne.startswith("VmRSS:"):
                return int(ligne.split()[1])
    except (OSError, ValueError, IndexError):
        return 0
    return 0


def arbre(racine: int) -> list[int]:
    """`racine` et sa descendance directe et indirecte, lue dans /proc."""
    parents: dict[int, int] = {}
    for entree in PROC.iterdir():
        if not entree.name.isdigit():
            continue
        try:
            champs = (entree / "stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
            parents[int(entree.name)] = int(champs[1])
        except (OSError, ValueError, IndexError):
            continue
    sortie = [racine]
    ajoute = True
    while ajoute:
        ajoute = False
        for pid, ppid in parents.items():
            if ppid in sortie and pid not in sortie:
                sortie.append(pid)
                ajoute = True
    return sortie


def workers_etrangers(noms_attendus: str | Sequence[str], timeout: float = 3.0) -> list[str]:
    """Noms des workers qui répondent au ping et ne sont aucun des nôtres."""
    prefixes = (noms_attendus,) if isinstance(noms_attendus, str) else tuple(noms_attendus)
    try:
        reponses: Any = celery_app.control.ping(timeout=timeout)
    except Exception:  # noqa: BLE001 - courtier injoignable : pas de worker
        return []
    noms: list[str] = []
    for reponse in reponses or []:
        noms += [n for n in reponse if not n.startswith(prefixes)]
    return noms


@dataclass
class ReleveMemoire:
    """Échantillons de RSS d'un arbre de workers, en Ko."""

    echantillons: list[int] = field(default_factory=list)

    def ajouter(self, *racines: int) -> None:
        """Un échantillon = la somme des RSS de TOUS les arbres de workers.

        Avec deux workers, relever le seul arbre `heavy` sous-estimerait la
        mémoire que la machine doit réellement fournir.
        """
        total = 0
        for racine in racines:
            total += sum(rss_ko(pid) for pid in arbre(racine))
        self.echantillons.append(total)

    @property
    def pic_mo(self) -> float | None:
        return round(max(self.echantillons) / 1024, 1) if self.echantillons else None

    @property
    def moyenne_mo(self) -> float | None:
        if not self.echantillons:
            return None
        return round(sum(self.echantillons) / len(self.echantillons) / 1024, 1)


class WorkerCelery:
    """Un worker Celery dédié à la campagne, à concurrence imposée.

    Utilisé en gestionnaire de contexte : le worker est arrêté (SIGTERM, puis
    SIGKILL après un délai) quoi qu'il arrive, y compris si le scénario lève.
    """

    def __init__(
        self,
        concurrence: int,
        *,
        cwd: Path,
        files: str = "heavy,light",
        prefixe_nom: str = "bench",
        journal: Path | None = None,
    ) -> None:
        self.concurrence = concurrence
        self.cwd = cwd
        self.files = files
        self.nom = f"{prefixe_nom}{concurrence}"
        # Les noms de TOUS les workers du groupe, quand ce worker fait partie
        # d'une topologie à plusieurs workers : sinon chacun prendrait l'autre
        # pour un intrus au démarrage.
        self.attendus: Sequence[str] = (self.nom,)
        self.journal = journal
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def pid(self) -> int:
        if self._proc is None:
            raise RuntimeError("Worker non démarré")
        return self._proc.pid

    def __enter__(self) -> WorkerCelery:
        etrangers = workers_etrangers(self.attendus)
        if etrangers:
            raise RuntimeError(
                "Un worker Celery étranger consomme déjà les files "
                f"({', '.join(etrangers)}). Arrêtez-le avant de mesurer : deux "
                "workers se partagent les messages et la concurrence mesurée "
                "n'est plus celle demandée."
            )
        sortie = self.journal.open("ab") if self.journal else subprocess.DEVNULL
        self._proc = subprocess.Popen(
            [
                "uv",
                "run",
                "celery",
                "-A",
                "app.core.celery_app",
                "worker",
                "-Q",
                self.files,
                "--concurrency",
                str(self.concurrence),
                "-n",
                f"{self.nom}@%h",
                "--loglevel",
                "warning",
            ],
            cwd=str(self.cwd),
            stdout=sortie,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            start_new_session=True,
        )
        self._attendre_pret()
        return self

    def _attendre_pret(self, timeout: float = 90.0) -> None:
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError(
                    f"Le worker s'est arrêté au démarrage (code {self._proc.returncode}). "
                    f"Journal : {self.journal}"
                )
            try:
                reponses: Any = celery_app.control.ping(timeout=2.0)
            except Exception:  # noqa: BLE001 - courtier pas encore joignable
                reponses = None
            for reponse in reponses or []:
                if any(nom.startswith(self.nom) for nom in reponse):
                    return
            time.sleep(1.0)
        raise RuntimeError(f"Worker {self.nom} injoignable après {timeout:.0f} s")

    def __exit__(self, *_: object) -> None:
        if self._proc is None:
            return
        # Le worker a son propre groupe de processus (start_new_session) : le
        # signal atteint le parent ET ses forks, sinon des workers orphelins
        # continueraient à consommer la file pendant la mesure suivante.
        try:
            os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            self._proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            self._proc.wait(timeout=10)
        self._proc = None


# --- Topologie des workers -------------------------------------------------

# Un seul worker abonné aux deux files. C'était la topologie de `make worker`
# jusqu'à la mesure de famine, et elle ne correspond à aucun déploiement.
UNIQUE = "unique"

# Un worker par file, comme les unités systemd du VPS
# (`miara-worker-heavy` et `miara-worker-light`). C'est la topologie à mesurer
# par défaut : mesurer autre chose que ce qui est déployé donne un chiffre qui
# ne décrit aucune machine réelle.
SEPAREE = "separee"

TOPOLOGIES = (SEPAREE, UNIQUE)

# Concurrence du worker `light`, alignée sur `WORKER_LIGHT_CONCURRENCY` de
# `deploy/.env.example`. Ces tâches sont courtes et surtout en attente réseau.
CONCURRENCE_LIGHT = 2


class GroupeWorkers:
    """Les workers d'un point de mesure, selon la topologie demandée.

    `concurrence` est celle de la file `heavy`, la seule que la carte fait
    varier : c'est elle qui porte l'extraction et la notation. Le worker
    `light` garde la concurrence du déploiement, sinon on mesurerait une
    machine que personne n'exploite.
    """

    def __init__(
        self,
        topologie: str,
        concurrence: int,
        *,
        cwd: Path,
        journal: Path | None = None,
    ) -> None:
        if topologie not in TOPOLOGIES:
            raise ValueError(f"Topologie inconnue : {topologie!r}, attendu {TOPOLOGIES}")
        self.topologie = topologie
        if topologie == UNIQUE:
            self.workers = [
                WorkerCelery(
                    concurrence, cwd=cwd, files="heavy,light", prefixe_nom="bench", journal=journal
                )
            ]
        else:
            self.workers = [
                WorkerCelery(
                    concurrence, cwd=cwd, files="heavy", prefixe_nom="benchh", journal=journal
                ),
                WorkerCelery(
                    CONCURRENCE_LIGHT,
                    cwd=cwd,
                    files="light",
                    prefixe_nom="benchl",
                    journal=journal,
                ),
            ]

    @property
    def noms(self) -> list[str]:
        return [w.nom for w in self.workers]

    @property
    def pids(self) -> list[int]:
        return [w.pid for w in self.workers]

    def __enter__(self) -> GroupeWorkers:
        # Le contrôle des workers étrangers porte sur le GROUPE : sans cela le
        # second worker démarré prendrait le premier pour un intrus.
        etrangers = workers_etrangers(self.noms)
        if etrangers:
            raise RuntimeError(
                "Un worker Celery étranger consomme déjà les files "
                f"({', '.join(etrangers)}). Arrêtez-le avant de mesurer : deux "
                "workers se partagent les messages et la concurrence mesurée "
                "n'est plus celle demandée."
            )
        demarres: list[WorkerCelery] = []
        try:
            for worker in self.workers:
                worker.attendus = self.noms
                worker.__enter__()
                demarres.append(worker)
        except BaseException:
            for worker in reversed(demarres):
                worker.__exit__(None, None, None)
            raise
        return self

    def __exit__(
        self,
        type_exc: type[BaseException] | None,
        exc: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        for worker in reversed(self.workers):
            worker.__exit__(type_exc, exc, trace)
