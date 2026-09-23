import { AgentTrace, type TraceStep } from "@/components/agent-trace";
import { libelleOutil, outil } from "@/lib/tools";

/** Événement de trace tel que diffusé par le backend (SSE ou GET conversation). */
export interface TraceEvent {
  step: number;
  kind: string;
  tool?: string | null;
  summary?: string | null;
  latency_ms?: number | null;
}

const LIBELLE: Record<string, string> = {
  llm_call: "Réflexion du modèle",
  // `tool_exec` n'a pas de libellé fixe : il en avait un — « Lecture
  // Salesforce » — qui annonçait une lecture alors que l'étape pouvait être
  // une création de contact. C'est l'outil qui donne la phrase.
  tool_error: "Outil en échec",
  needs_confirmation: "Confirmation demandée",
  step_limit: "Boucle arrêtée (limite d'étapes)",
  final: "Réponse rédigée",
};

/** Libellé d'une étape : l'outil quand il y en a un, le type d'étape sinon. */
function libelle(event: TraceEvent): string {
  if (event.kind === "tool_exec") return libelleOutil(event.tool);
  if (event.kind === "tool_error") return `${libelleOutil(event.tool)} — en échec`;
  return LIBELLE[event.kind] ?? event.kind;
}

/** Détail court et lisible : jamais le contenu brut renvoyé par un outil. */
function detail(event: TraceEvent): string | undefined {
  const duree = event.latency_ms ? `${(event.latency_ms / 1000).toFixed(1)} s` : null;
  if (event.kind === "tool_exec" || event.kind === "tool_error") {
    // Le libellé porte déjà le quoi ; le détail dit la nature et le temps.
    return [outil(event.tool).ecriture ? "écriture" : "lecture", duree].filter(Boolean).join(" · ");
  }
  if (event.kind === "llm_call") {
    // L'alias de modèle (`sales.route`) est un identifiant de configuration :
    // il reste dans les journaux, pas à l'écran.
    return duree ?? undefined;
  }
  return duree ?? undefined;
}

/**
 * Trace de l'agent commercial : les étapes reçues, puis l'étape en cours.
 * Tant que la réponse n'est pas rendue, la dernière ligne pulse.
 */
export function AgentSteps({
  events,
  running,
  className,
}: {
  events: TraceEvent[];
  running: boolean;
  className?: string;
}) {
  const steps: TraceStep[] = events.map((e, i) => ({
    key: `${e.step}-${i}`,
    label: libelle(e),
    detail: detail(e),
    status: e.kind === "tool_error" ? "failed" : "done",
  }));
  if (running) {
    steps.push({ key: "en-cours", label: "En cours…", status: "active" });
  }
  return steps.length ? <AgentTrace steps={steps} className={className} /> : null;
}
