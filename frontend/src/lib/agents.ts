/**
 * Noms d'agents journalisés → libellés métier.
 *
 * La page Usage est destinée à l'encadrement (et reprise comme figure du
 * mémoire, chapitre 8) : `hr.profile` n'y dit rien, « Agent RH – profil du
 * candidat » si. La convention des noms journalisés est `module.fonction`,
 * vérifiée côté backend à la construction du `CallContext`.
 *
 * Les agents techniques — l'agent de test `core.echo`, le harnais
 * d'évaluation `eval.*` — sont regroupés sous une seule entrée « Tests et
 * évaluation » : ils consomment un budget réel, les cacher fausserait le
 * total, mais ils n'ont pas à figurer comme un agent de production.
 */

export const LIBELLE_AGENT: Record<string, string> = {
  "sales.assistant": "Agent commercial",
  "sales.coach": "Coach commercial",
  "hr.criteria": "Agent RH – grille de critères",
  "hr.profile": "Agent RH – profil du candidat",
  "hr.score": "Agent RH – notation",
  "hr.calibrate": "Agent RH – calibrage",
};

export const TECHNIQUE = "Tests et évaluation";

/** Libellé métier d'un agent, ou le regroupement technique. */
export function libelleAgent(agent: string): string {
  return LIBELLE_AGENT[agent] ?? TECHNIQUE;
}

export interface AgentAgrege {
  libelle: string;
  technique: boolean;
  cost_usd: number;
  tokens: number;
  calls: number;
}

/** Agrège par libellé métier : les agents techniques fusionnent en une barre. */
export function parLibelle(
  lignes: { agent: string; calls: number; cost_usd: number; tokens: number }[]
): AgentAgrege[] {
  const paquets = new Map<string, AgentAgrege>();
  for (const ligne of lignes) {
    const libelle = libelleAgent(ligne.agent);
    const cumul = paquets.get(libelle) ?? {
      libelle,
      technique: libelle === TECHNIQUE,
      cost_usd: 0,
      tokens: 0,
      calls: 0,
    };
    cumul.cost_usd += ligne.cost_usd;
    cumul.tokens += ligne.tokens;
    cumul.calls += ligne.calls;
    paquets.set(libelle, cumul);
  }
  // Les agents de production d'abord, le regroupement technique en dernier.
  return [...paquets.values()]
    .map((a) => ({ ...a, cost_usd: Number(a.cost_usd.toFixed(6)) }))
    .sort((a, b) => Number(a.technique) - Number(b.technique) || b.cost_usd - a.cost_usd);
}
