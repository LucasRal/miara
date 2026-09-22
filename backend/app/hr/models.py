"""Tables du module RH : une offre, N candidatures, des campagnes de notation.

Découpage en quatre tables (carte [HR] socle) :

- `jobs` : l'offre et SA grille de critères. La grille est extraite une fois,
  ajustée par le RH, puis figée : c'est elle que la notation appliquera
  identiquement à chaque CV (ADR-007). `status='ready'` signifie « grille
  validée par un humain » — sans quoi aucune analyse ne doit démarrer.
- `candidates` : un CV déposé. Le fichier vit sur disque derrière `FileStore`
  (`file_path` = chemin RELATIF interne, jamais exposé par l'API) ;
  `extracted_text` et `profile_json` restent vides ici, ils sont remplis par
  le pipeline de présélection (carte suivante).
- `screening_runs` : une campagne de notation d'une offre. Créée par le
  pipeline, pas par cette carte : la table existe pour que la migration du
  socle RH soit complète et que les FK de `candidate_scores` tiennent.
- `candidate_scores` : la note d'un CV dans une campagne. Une ligne par
  (campagne, candidat) — jamais de notation croisée entre CV (ADR-007).

Données personnelles : un CV en est plein. Aucun nom de fichier ni contenu
n'est journalisé (métadonnées et compteurs uniquement), et le stockage vit
hors du dépôt.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TenantScoped

# Cycle de vie d'une offre.
JOB_DRAFT = "draft"  # créée ; grille absente ou seulement suggérée
JOB_READY = "ready"  # grille validée par le RH : la notation peut démarrer
JOB_STATUSES = (JOB_DRAFT, JOB_READY)

# Cycle de vie d'une candidature.
CANDIDATE_UPLOADED = "uploaded"
CANDIDATE_EXTRACTED = "extracted"
# Document valide mais sans texte (CV scanné) : distinct d'un fichier cassé.
CANDIDATE_NEEDS_OCR = "needs_ocr"
CANDIDATE_ERROR = "error"

# Cycle de vie d'une campagne de présélection.
RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_DONE = "done"
RUN_FAILED = "failed"

# Issue d'une candidature DANS une campagne donnée. Le même CV peut être noté
# dans une campagne et en échec dans une autre : l'état vit sur la ligne de
# résultat, pas sur la candidature.
SCORE_SCORED = "scored"
SCORE_FAILED = "failed"


class Job(TenantScoped, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200))
    description_text: Mapped[str] = mapped_column(Text())
    # Grille de critères au format `app.hr.criteria.Criteria` (5 à 8 critères
    # pondérés). Présente dès la suggestion ; fait foi une fois `status=ready`.
    criteria_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Version du prompt ayant produit la suggestion (reproductibilité, ADR-010).
    criteria_prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text(f"'{JOB_DRAFT}'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    # Archivage plutôt que suppression : une offre qui porte des candidatures
    # porte aussi l'historique des analyses. On la sort de la liste courante,
    # on ne l'efface pas.
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class Candidate(TenantScoped, Base):
    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    # Chemin RELATIF dans le FileStore ({org}/{job}/{uuid}.pdf). Interne :
    # l'API ne le renvoie jamais (carte [HR] socle, section NE PAS).
    file_path: Mapped[str] = mapped_column(String(300))
    # Nom d'origine conservé pour l'affichage RH uniquement — il ne sert
    # JAMAIS à construire un chemin sur disque.
    original_filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text(f"'{CANDIDATE_UPLOADED}'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ScreeningRun(TenantScoped, Base):
    __tablename__ = "screening_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Compteurs de la campagne (traités, en erreur, coût, durée) — chap. 8.
    stats_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CandidateScore(TenantScoped, Base):
    __tablename__ = "candidate_scores"
    # Une seule ligne par (campagne, candidature) : deux workers qui rejouent
    # la même tâche ne peuvent pas produire deux notations.
    __table_args__ = (UniqueConstraint("run_id", "candidate_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("screening_runs.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Détail par critère : note, preuve citée du CV, justification.
    # Nul quand la candidature a échoué : la ligne existe quand même, c'est
    # elle qui porte l'issue et le motif (et qui rend le rejeu idempotent).
    score_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    overall: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100, pondéré
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 = meilleur
    status: Mapped[str] = mapped_column(String(20), server_default=text(f"'{SCORE_SCORED}'"))
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
