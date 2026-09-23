import { libelleOutilFait } from "@/lib/tools";

/**
 * Contrat de lecture des écrans transverses (tableau de bord, file, usage).
 *
 * Ces endpoints renvoient `dict[str, Any]` côté FastAPI : l'OpenAPI n'en dit
 * rien, les types sont donc écrits à la main et alignés sur `app/dashboard.py`,
 * `app/queue.py` et `app/usage.py`.
 */

export interface DashboardMetrics {
  cv_analyses: number;
  heures_economisees: number;
  /** Hypothèse de temps de tri manuel, affichée pour pouvoir être contestée. */
  minutes_par_cv: number;
  ecritures_crm: number;
  latence_moyenne_ms: number | null;
}

/**
 * Événement d'activité, tel que le backend le produit : des données, pas des
 * phrases. La mise en mots (accords, libellés d'outil) est le travail de
 * l'interface, qui connaît la langue — voir `libelleActivite`.
 */
export type ActivityEvent = {
  kind: string;
  status: string;
  at: string;
  href: string;
} & (
  | { kind: "hr_run"; counts: { candidates: number; scored: number; failed: number } }
  | { kind: "crm_write"; tool: string; record_id: string | null; error: string | null }
  | { kind: "coaching"; coaching_kind: string; score: number | null }
  | { kind: string }
);

export interface DashboardSummary {
  organization_id: string;
  period_start: string;
  generated_at: string;
  metrics: DashboardMetrics;
  cv_total: number;
  activity: ActivityEvent[];
  /** Instance Salesforce de l'org : sans elle, un identifiant n'est pas un lien. */
  crm_instance_url: string | null;
  cached: boolean;
}

/** Une page de la vue complète de l'activité (`GET /dashboard/activity`). */
export interface ActivityPage {
  events: ActivityEvent[];
  total: number;
  limit: number;
  offset: number;
  /** Sources connues du backend : la liste des filtres vient de lui. */
  kinds: string[];
  crm_instance_url: string | null;
}

/** Nom lisible d'une source d'activité, pour le filtre de la vue complète. */
export const SOURCE_LIBELLE: Record<string, string> = {
  hr_run: "Présélections de CV",
  crm_write: "Écritures Salesforce",
  coaching: "Analyses du coach",
};

export type TaskStatus = "started" | "succeeded" | "failed";

export interface TaskEvent {
  id: string;
  task_id: string;
  name: string;
  queue: string | null;
  status: TaskStatus | string;
  trace_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
  /** Motif d'échec traduit par le backend ; `error` garde la trace technique. */
  reason: string | null;
  retried: number;
}

/** `GET /queue/tasks` : page bornée côté serveur + total pour la pagination. */
export interface TaskPage {
  tasks: TaskEvent[];
  total: number;
}

export interface UsageDay {
  day: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface UsageAgent {
  agent: string;
  calls: number;
  cost_usd: number;
  tokens: number;
}

export interface UsageAgentAlias extends UsageAgent {
  alias: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number | null;
}

export interface UsageCall {
  id: string;
  agent: string;
  alias: string;
  model_used: string;
  prompt_version: number | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  cost_usd: number | null;
  status: string;
  error: string | null;
  created_at: string;
}

/** Durée lisible : 4200 ms devient « 4,2 s », 90000 ms devient « 1 min 30 s ». */
export function duree(ms: number | null): string {
  if (ms === null) return "";
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
  const minutes = Math.floor(ms / 60000);
  return `${minutes} min ${Math.round((ms % 60000) / 1000)} s`;
}

/**
 * Nombre décimal en français : virgule, et le nombre de décimales choisi une
 * fois par grandeur plutôt qu'au cas par cas. « 13.99 s » et « 0.016 USD »
 * voisinaient avec « 1,3 s » et « 0,0004 USD » dans la même application.
 */
export function nombre(valeur: number, decimales = 1): string {
  return valeur.toLocaleString("fr-FR", {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  });
}

/** Montant en dollars. Le fournisseur facture en USD : l'unité est dite. */
export function usd(valeur: number): string {
  return `${valeur.toFixed(valeur < 1 ? 4 : 2).replace(".", ",")} USD`;
}

/** Heure locale courte, pour des lignes de journal qui restent lisibles. */
export function heure(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Accord au singulier ou au pluriel, sans répéter la règle à chaque appel. */
export function pluriel(n: number, singulier: string, plurielMot = `${singulier}s`): string {
  return `${n} ${n > 1 ? plurielMot : singulier}`;
}

/**
 * Un événement d'activité mis en mots.
 *
 * Le backend renvoie `{"kind": "crm_write", "tool": "create_contact"}` ; le
 * tableau de bord affichait cela tel quel. Ici, une phrase métier et un
 * détail facultatif — l'identifiant Salesforce devenant un lien quand
 * l'instance de l'organisation est connue.
 */
export interface ActiviteLisible {
  titre: string;
  detail: string | null;
  /** Identifiant Salesforce, s'il y en a un, pour en faire un lien. */
  recordId: string | null;
}

export function libelleActivite(e: ActivityEvent): ActiviteLisible {
  if (e.kind === "hr_run" && "counts" in e) {
    const { candidates, scored, failed } = e.counts;
    const issue =
      e.status === "done"
        ? `${pluriel(scored, "CV noté")}${failed > 0 ? `, ${pluriel(failed, "en échec", "en échec")}` : ""}`
        : e.status === "failed"
          ? "analyse interrompue"
          : "analyse en cours";
    return {
      titre: `Présélection de ${pluriel(candidates, "CV", "CV")}`,
      detail: issue,
      recordId: null,
    };
  }
  if (e.kind === "crm_write" && "tool" in e) {
    const fait = libelleOutilFait(e.tool);
    return {
      titre: e.status === "created" || e.status === "updated" ? fait : `${fait} — en échec`,
      detail: e.error ? "l'écriture n'est pas passée" : "confirmée par une personne",
      recordId: e.record_id,
    };
  }
  if (e.kind === "coaching" && "coaching_kind" in e) {
    return {
      titre: `Texte analysé par le coach (${COACHING_LIBELLE[e.coaching_kind] ?? "texte"})`,
      detail: e.score === null ? null : `note globale ${e.score} sur 100`,
      recordId: null,
    };
  }
  return { titre: "Activité de l'organisation", detail: null, recordId: null };
}

const COACHING_LIBELLE: Record<string, string> = {
  call_note: "compte-rendu d'appel",
  email: "courriel",
  script: "script",
};
