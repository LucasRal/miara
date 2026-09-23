/**
 * Reconstruction d'une conversation commerciale à partir de ce que renvoie
 * `GET /sales/conversations/{id}`.
 *
 * La trace d'exécution est la promesse du produit (ADR-009 : une écriture CRM
 * est traçable, une lecture est sourcée). Elle ne peut donc pas n'exister que
 * dans l'onglet où le tour a été joué : ces fonctions la rattachent, au
 * rechargement comme à l'ouverture, au message qu'elle a produit.
 */

import { outil } from "@/lib/tools";

export interface Conversation {
  id: string;
  title: string;
  messages: number;
  created_at: string;
}

export interface Message {
  position: number;
  role: string;
  content: string | null;
}

export interface TraceEvent {
  trace_id?: string;
  step: number;
  kind: string;
  tool?: string | null;
  summary?: string | null;
  latency_ms?: number | null;
}

export interface Ecriture {
  tool: string;
  id: string;
}

/** Ce qui s'est passé pendant un tour : ses étapes et ce qu'il a écrit. */
export interface Tour {
  trace: TraceEvent[];
  ecritures: Ecriture[];
}

/**
 * Identifiant de l'enregistrement créé ou mis à jour par une étape d'outil.
 *
 * Il vit dans le résumé du résultat, pas dans le texte final de l'agent : un
 * accusé tiré du résumé est vérifiable (le lien mène à l'enregistrement),
 * une phrase du modèle ne l'est pas.
 */
export function identifiantEcrit(summary: string | null | undefined): string | null {
  return /"sf_record_id":\s*"([^"]+)"/.exec(summary ?? "")?.[1] ?? null;
}

/** Écritures CRM abouties d'une trace de tour, dans l'ordre. */
export function ecrituresDe(trace: TraceEvent[]): Ecriture[] {
  const vues = new Set<string>();
  const sorties: Ecriture[] = [];
  for (const etape of trace) {
    if (etape.kind !== "tool_exec" || !etape.tool || !outil(etape.tool).ecriture) continue;
    const id = identifiantEcrit(etape.summary);
    if (!id || vues.has(id)) continue;
    vues.add(id);
    sorties.push({ tool: etape.tool, id });
  }
  return sorties;
}

/**
 * Découpe une trace plate en tours, dans l'ordre de réception.
 *
 * Le backend renvoie toutes les étapes de la conversation triées par date
 * puis par numéro d'étape ; `trace_id` est ce qui distingue un tour du
 * suivant. À défaut (vieilles lignes sans identifiant), une étape dont le
 * numéro repart en arrière ouvre un nouveau tour.
 */
export function decouperEnTours(trace: TraceEvent[]): TraceEvent[][] {
  const tours: TraceEvent[][] = [];
  let courant: string | null = null;
  for (const etape of trace) {
    const cle = etape.trace_id ?? null;
    const nouveau =
      tours.length === 0 ||
      (cle !== null ? cle !== courant : etape.step <= tours[tours.length - 1].at(-1)!.step);
    if (nouveau) tours.push([]);
    tours[tours.length - 1].push(etape);
    courant = cle;
  }
  return tours;
}

/**
 * Ne garde du fil que ce qui s'affiche : les questions et les réponses
 * rédigées. Un message d'assistant sans contenu est un appel d'outil — il est
 * raconté par la trace, pas par une bulle vide.
 */
export function messagesAffichables(messages: Message[]): Message[] {
  return messages.filter(
    (m) => (m.role === "user" || m.role === "assistant") && (m.content ?? "").trim() !== ""
  );
}

/**
 * Un `Tour` par réponse de l'agent, dans l'ordre : le n-ième tour a produit la
 * n-ième réponse du fil.
 *
 * Tous les tours ne produisent pas une réponse — un tour qui s'arrête sur une
 * demande de confirmation jamais tranchée n'en a pas. Ces tours ne sont pas
 * perdus pour autant : ils repartent en `orphelins`, à rendre en fin de fil.
 * C'est précisément le tour où une écriture CRM a été proposée, donc celui
 * qu'il est le plus coûteux d'effacer.
 *
 * L'index, plutôt que la position du message, parce que c'est la seule clé
 * que l'écran peut aussi calculer pendant un tour en direct, sans relire le
 * fil : les deux chemins produisent alors exactement la même forme.
 */
export function rattacherTours(
  affichables: Message[],
  trace: TraceEvent[]
): { tours: Tour[]; orphelins: Tour | null } {
  const groupes = decouperEnTours(trace);
  const reponses = affichables.filter((m) => m.role === "assistant").length;
  const tour = (etapes: TraceEvent[]): Tour => ({ trace: etapes, ecritures: ecrituresDe(etapes) });

  const restants = groupes.slice(reponses).flat();
  return {
    tours: groupes.slice(0, reponses).map(tour),
    orphelins: restants.length ? tour(restants) : null,
  };
}

// --- liste des conversations ---------------------------------------------

/**
 * Libellé de jour, relatif quand ça aide : « Aujourd'hui », « Hier », puis la
 * date. Sert d'en-tête de groupe dans la liste des fils.
 */
export function jour(iso: string): string {
  const d = new Date(iso);
  const minuit = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const jours = Math.round((minuit(new Date()) - minuit(d)) / 86_400_000);
  if (jours === 0) return "Aujourd'hui";
  if (jours === 1) return "Hier";
  if (jours < 7) return d.toLocaleDateString("fr-FR", { weekday: "long" });
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
}

/** Heure d'aujourd'hui, date courte sinon : ce qui distingue deux voisines. */
export function quand(iso: string, secondes = false): string {
  const d = new Date(iso);
  return jour(iso) === "Aujourd'hui"
    ? d.toLocaleTimeString("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
        ...(secondes ? { second: "2-digit" } : {}),
      })
    : d.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}

/**
 * Repère affiché sous chaque fil — heure et nombre de messages — garanti
 * unique dans la liste.
 *
 * Deux fils ouverts dans la même minute avec la même première question
 * restaient rigoureusement indiscernables, à l'écran comme dans le nom
 * accessible : on descend alors à la seconde, pour ceux-là seulement. Le
 * renommage reste la vraie réponse, mais il ne doit pas être obligatoire.
 */
export function reperes(conversations: Conversation[]): Record<string, string> {
  const texte = (c: Conversation, sec: boolean) =>
    `${quand(c.created_at, sec)}, ${c.messages} message${c.messages > 1 ? "s" : ""}`;
  const collisions = new Set<string>();
  const vus = new Map<string, number>();
  for (const c of conversations) {
    const cle = `${c.title}|${texte(c, false)}`;
    vus.set(cle, (vus.get(cle) ?? 0) + 1);
  }
  for (const [cle, n] of vus) if (n > 1) collisions.add(cle);

  return Object.fromEntries(
    conversations.map((c) => [c.id, texte(c, collisions.has(`${c.title}|${texte(c, false)}`))])
  );
}

/** Conversations groupées par jour, l'ordre reçu (récentes d'abord) préservé. */
export function grouperParJour(conversations: Conversation[]): {
  jour: string;
  fils: Conversation[];
}[] {
  const groupes: { jour: string; fils: Conversation[] }[] = [];
  for (const c of conversations) {
    const j = jour(c.created_at);
    const dernier = groupes.at(-1);
    if (dernier?.jour === j) dernier.fils.push(c);
    else groupes.push({ jour: j, fils: [c] });
  }
  return groupes;
}
