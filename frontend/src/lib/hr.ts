/**
 * Contrat de lecture du module RH et règles d'affichage du classement.
 *
 * Les endpoints RH renvoient `dict[str, Any]` côté FastAPI : l'OpenAPI n'en
 * décrit pas la forme, ces types sont donc écrits à la main et alignés sur
 * `backend/app/hr/jobs.py` et `backend/app/hr/runs.py`.
 *
 * La recommandation (« À convoquer », « À examiner », « Hors profil ») est
 * calculée ICI, jamais demandée au modèle : elle doit être la même pour deux
 * CV qui obtiennent la même note, sous peine de rendre la présélection
 * indéfendable devant un candidat.
 */

// Bornes de la grille, reprises de backend/app/hr/criteria.py.
export const MIN_CRITERIA = 5;
export const MAX_CRITERIA = 8;

export interface Criterion {
  name: string;
  weight_1_5: number;
  description: string;
  must_have: boolean;
}

export type JobStatus = "draft" | "ready";

/**
 * Vocabulaire d'état d'une offre, UNIQUE pour toute l'application.
 *
 * `draft` s'appelait « Grille à valider » dans la liste et « Non validée » sur
 * la page de grille ; `ready` s'appelait « Prête » (prête à quoi ?) ici et
 * « Grille validée » là-bas. Deux libellés pour une valeur ne se lisent pas
 * comme les deux faces d'un même champ : une seule table, importée des deux
 * côtés.
 */
export const JOB_STATUT: Record<JobStatus, { libelle: string; variant: "secondary" | "default" }> =
  {
    draft: { libelle: "Grille à valider", variant: "secondary" },
    ready: { libelle: "Grille validée", variant: "default" },
  };

export function statutOffre(status: string): { libelle: string; variant: "secondary" | "default" } {
  return JOB_STATUT[status as JobStatus] ?? { libelle: status, variant: "secondary" };
}

export interface RunSummary {
  run_id: string;
  status: string;
  stats: RunStats | null;
  created_at: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface Job {
  id: string;
  title: string;
  description_text: string;
  status: JobStatus;
  criteria: Criterion[];
  criteria_prompt_version: number | null;
  candidates: number;
  last_run: RunSummary | null;
  created_at: string | null;
  /** Non nul = archivée : masquée de la liste par défaut, jamais supprimée. */
  archived_at: string | null;
}

export interface Candidate {
  id: string;
  original_filename: string;
  mime: string;
  size_bytes: number;
  status: "uploaded" | "extracted" | "needs_ocr" | "error" | string;
  created_at: string | null;
}

export interface UploadResult {
  job_id: string;
  accepted: Candidate[];
  rejected: { filename: string; reason: string }[];
}

export interface RunStats {
  candidates?: number;
  scored?: number;
  failed?: number;
  steps?: Record<string, { count: number; total_seconds: number; mean_seconds: number }>;
  llm?: { calls: number; tokens: number; cost_usd: number };
  seconds_per_candidate?: number;
}

export interface RunCandidate {
  candidate_id: string;
  original_filename: string;
  status: "pending" | "scored" | "failed" | string;
  overall: number | null;
  error: string | null;
  file_status: string;
}

export interface Run {
  run_id: string;
  job_id: string;
  status: "queued" | "running" | "done" | "failed" | string;
  total: number;
  done: number;
  progress: number;
  started_at: string | null;
  finished_at: string | null;
  stats: RunStats | null;
  candidates: RunCandidate[];
}

export interface CriterionResult {
  name: string;
  weight: number;
  score_0_5: number;
  evidence: string;
  missing: string | null;
}

export interface RankedCandidate {
  rank: number | null;
  candidate_id: string;
  original_filename: string | null;
  headline: string | null;
  years_experience: number | null;
  skills: string[];
  overall: number | null;
  status: string;
  error: string | null;
  criteria?: CriterionResult[];
  must_have_failed?: string[];
  strengths?: string[];
  concerns?: string[];
  confidence?: number;
  calibration_rationale?: string | null;
}

export interface Results {
  run_id: string;
  status: string;
  stats: RunStats | null;
  /** Page courante du classement : CV notés, déjà filtrés par le serveur. */
  ranking: RankedCandidate[];
  /**
   * CV non notés, renvoyés HORS pagination et HORS filtres : sans note, un
   * seuil de note ne dit rien d'eux, et ils sont les seuls à demander une
   * action humaine.
   */
  failed: RankedCandidate[];
  /** Nombre de CV notés retenus par les filtres, campagne entière. */
  total: number;
}

/**
 * Coût et durée qu'une nouvelle campagne devrait avoir, estimés à partir de
 * ce que la PRÉCÉDENTE a réellement coûté sur cette offre — pas d'un tarif
 * codé en dur, qui serait faux dès le prochain changement de modèle.
 *
 * `null` quand la campagne précédente n'a pas de mesures exploitables : mieux
 * vaut ne rien annoncer qu'annoncer un chiffre inventé.
 */
export function estimationRelance(
  precedente: RunSummary | null,
  nbCandidats: number
): { cout: number | null; secondes: number | null } | null {
  const stats = precedente?.stats;
  if (!stats || nbCandidats === 0) return null;
  const notes = stats.candidates ?? 0;
  const cout =
    stats.llm?.cost_usd != null && notes > 0 ? (stats.llm.cost_usd / notes) * nbCandidats : null;
  const secondes =
    stats.seconds_per_candidate != null ? stats.seconds_per_candidate * nbCandidats : null;
  if (cout === null && secondes === null) return null;
  return { cout, secondes };
}

/** Durée approximative, en minutes dès que la seconde n'a plus de sens. */
export function dureeApprox(secondes: number): string {
  if (secondes < 90) return `${Math.round(secondes)} s`;
  return `${Math.round(secondes / 60)} min`;
}

// --- règles d'affichage ---------------------------------------------------

export type Recommendation = "convoquer" | "examiner" | "hors_profil";

export const RECOMMENDATION_LABEL: Record<Recommendation, string> = {
  convoquer: "À convoquer",
  examiner: "À examiner",
  hors_profil: "Hors profil",
};

/**
 * Seuils identiques à ceux de l'anneau de score (70 / 40), plus la règle
 * éliminatoire : un must-have manqué sort le CV, quelle que soit la note.
 */
export function recommendation(candidate: RankedCandidate): Recommendation {
  if ((candidate.must_have_failed?.length ?? 0) > 0) return "hors_profil";
  const note = candidate.overall ?? 0;
  if (note >= 70) return "convoquer";
  if (note >= 40) return "examiner";
  return "hors_profil";
}

/** Motif d'échec d'un CV, en français, à partir du statut du fichier. */
export function failureReason(candidate: { status: string; error: string | null }): string {
  if (candidate.status === "needs_ocr")
    return "CV probablement scanné : aucun texte extractible (OCR nécessaire).";
  return candidate.error ?? "Fichier illisible ou corrompu.";
}

/**
 * Export CSV du classement TEL QU'AFFICHÉ : les lignes reçues sont déjà
 * filtrées et triées par l'écran. Séparateur point-virgule et BOM, pour
 * qu'Excel en français ouvre le fichier sans écran d'import.
 */
export function rankingToCsv(rows: RankedCandidate[]): string {
  const entetes = [
    "rang",
    "fichier",
    "accroche",
    "annees_experience",
    "note_sur_100",
    "recommandation",
    "eliminatoires_manques",
    "forces",
    "reserves",
    "motif_echec",
  ];
  const echapper = (valeur: unknown) => `"${String(valeur ?? "").replace(/"/g, '""')}"`;
  const lignes = rows.map((r) =>
    [
      r.rank ?? "",
      r.original_filename ?? "",
      r.headline ?? "",
      r.years_experience ?? "",
      r.overall ?? "",
      // Un CV non noté n'a pas de recommandation : lui coller « Hors profil »
      // (ce que donnerait `recommendation` sur une note nulle) serait une
      // affirmation fausse, figée dans un fichier qui circule.
      r.status === "scored" ? RECOMMENDATION_LABEL[recommendation(r)] : "Non noté",
      (r.must_have_failed ?? []).join(" | "),
      (r.strengths ?? []).join(" | "),
      (r.concerns ?? []).join(" | "),
      r.status === "scored" ? "" : failureReason(r),
    ]
      .map(echapper)
      .join(";")
  );
  return `﻿${entetes.join(";")}\n${lignes.join("\n")}\n`;
}

/** Déclenche le téléchargement d'un CSV sans quitter la page. */
export function downloadCsv(filename: string, contenu: string): void {
  const url = URL.createObjectURL(new Blob([contenu], { type: "text/csv;charset=utf-8" }));
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = filename;
  lien.click();
  URL.revokeObjectURL(url);
}
