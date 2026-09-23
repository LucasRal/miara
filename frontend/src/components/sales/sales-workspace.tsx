"use client";

import { ArrowDown, Link2Off, MessagesSquare, Send } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { AgentSteps } from "@/components/sales/agent-steps";
import { ConversationList } from "@/components/sales/conversation-list";
import { RichText } from "@/components/sales/rich-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ErrorState } from "@/components/ui/states";
import { SkipLink } from "@/components/ui/skip-link";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, type Integration } from "@/lib/api";
import { GRAND_ECRAN, useMediaQuery } from "@/lib/media";
import { defilement } from "@/lib/motion";
import { notifierErreur, notifierSucces } from "@/lib/notifications";
import {
  ecrituresDe,
  messagesAffichables,
  rattacherTours,
  quand,
  type Conversation,
  type Message,
  type Tour,
  type TraceEvent,
} from "@/lib/sales";
import { streamPost } from "@/lib/sse";
import { libelleOutil, libelleOutilFait } from "@/lib/tools";
import { cn } from "@/lib/utils";

interface PendingWrite {
  call_id: string;
  tool: string;
  preview: string;
}

/**
 * Distance au bas du fil en deçà de laquelle on considère que la personne
 * « y est ». Assez pour absorber une ligne qui s'ajoute pendant la frappe,
 * trop peu pour attraper quelqu'un qui est remonté lire.
 */
const SEUIL_BAS = 80;

type TurnResult =
  | { type: "final"; content: string; trace_id: string }
  | { type: "needs_confirmation"; call_id: string; tool: string; preview: string; args: unknown }
  | { type: "step_limit"; steps: number };

/**
 * Ce qu'un tour a fait, en une phrase — pour l'annoncer sans dérouler les
 * étapes une à une, ce qui couvrirait la réponse elle-même.
 */
function resumeTrace(etapes: TraceEvent[]): string {
  if (etapes.length === 0) return "";
  const faits = etapes
    .filter((e) => e.kind === "tool_exec" || e.kind === "tool_error")
    .map((e) => libelleOutilFait(e.tool).toLowerCase());
  const n = `${etapes.length} étape${etapes.length > 1 ? "s" : ""}`;
  return faits.length > 0 ? `${n} : ${[...new Set(faits)].join(", ")}.` : `${n}.`;
}

/**
 * Ce qu'a produit un tour, sous la réponse qu'il a produite : les accusés
 * d'écriture d'abord (le fait), la trace ensuite (la preuve), repliée.
 *
 * La trace est repliée parce qu'un fil de dix tours déroulerait autrement
 * cinquante lignes d'étapes entre deux réponses ; elle reste à un clic, et
 * ne contient jamais le résultat brut d'un outil — résumé et durée seulement.
 */
function BlocTour({ tour, instanceUrl }: { tour: Tour; instanceUrl: string | null }) {
  if (tour.ecritures.length === 0 && tour.trace.length === 0) return null;
  return (
    <>
      {tour.ecritures.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tour.ecritures.map((e) => (
            <Badge key={e.id} asChild>
              {instanceUrl ? (
                <a
                  href={`${instanceUrl}/lightning/r/${e.id}/view`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {libelleOutilFait(e.tool)} ✓ — {e.id}
                </a>
              ) : (
                <span>
                  {libelleOutilFait(e.tool)} ✓ — {e.id}
                </span>
              )}
            </Badge>
          ))}
        </div>
      )}
      {tour.trace.length > 0 && (
        // `aria-live="off"` : la trace vit DANS le fil, qui est une région
        // live. Sans cela, chaque étape rangée sous une réponse serait lue
        // par-dessus la réponse elle-même.
        <details aria-live="off" className="rounded-lg border bg-card">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-muted-foreground">
            Trace de l&apos;agent — {tour.trace.length} étape{tour.trace.length > 1 ? "s" : ""}
          </summary>
          <div className="px-3 pb-3">
            <AgentSteps events={tour.trace} running={false} />
          </div>
        </details>
      )}
    </>
  );
}

/**
 * Écran de l'agent commercial : fils à gauche, conversation à droite.
 *
 * Trois choses y sont rendues visibles, et c'est le sujet de la carte :
 * la trace des étapes pendant que l'agent travaille, le briefing sourcé avec
 * ses identifiants Salesforce cliquables, et le dialogue de confirmation avant
 * toute écriture dans le CRM (ADR-009).
 */
export function SalesWorkspace() {
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [actif, setActif] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  // Ce qu'a produit chaque réponse, indexé par sa position dans le fil : la
  // trace ne doit pas n'exister que dans l'onglet où le tour a été joué.
  const [tours, setTours] = useState<Tour[]>([]);
  // Trace d'un tour qui n'a produit aucune réponse — typiquement une écriture
  // proposée et jamais confirmée. Elle se rend en fin de fil.
  const [orphelins, setOrphelins] = useState<Tour | null>(null);
  const [enCours, setEnCours] = useState(false);
  const [saisie, setSaisie] = useState("");
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const [echecAction, setEchecAction] = useState<string | null>(null);
  // Ce que le lecteur d'écran doit entendre du tour en cours : « l'agent
  // réfléchit », puis le RÉSUMÉ des étapes — jamais les étapes une à une.
  const [annonce, setAnnonce] = useState("");
  const [instanceUrl, setInstanceUrl] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{
    connected: boolean;
    suggestions: string[];
  } | null>(null);
  const filRef = useRef<HTMLDivElement>(null);
  const grandEcran = useMediaQuery(GRAND_ECRAN);
  const [tiroir, setTiroir] = useState(false);
  // Où en est la lecture : `enBasRef` pour les décisions (une closure d'effet
  // ne verrait pas un état), `detache` pour ce qui s'affiche.
  const enBasRef = useRef(true);
  // Dernière position lue, pour distinguer « la personne remonte » de « le
  // contenu pousse le bas plus loin ».
  const yRef = useRef(0);
  const [detache, setDetache] = useState(false);
  const [nouveautes, setNouveautes] = useState(0);
  // Les étapes du tour en cours, hors état : la closure du flux SSE capture
  // `trace` au premier rendu et ne verrait jamais les suivantes.
  const traceRef = useRef<TraceEvent[]>([]);
  // Confirmer une écriture ne doit pas coûter la zone de saisie : c'est le
  // geste le plus fréquent de l'agent commercial.
  const saisieRef = useRef<HTMLTextAreaElement>(null);

  const chargerConversations = useCallback(async () => {
    setConversations(await api.get<Conversation[]>("/sales/conversations"));
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void chargerConversations().catch(() => setConversations([]));
    void api
      .get<Integration[]>("/integrations")
      .then((l) => setInstanceUrl(l.find((i) => i.provider === "salesforce")?.instance_url ?? null))
      .catch(() => setInstanceUrl(null));
    // Les questions proposées viennent des données de l'org (une requête SOQL
    // côté backend, jamais un appel de modèle) : une suggestion qui nomme un
    // compte absent du CRM échoue au premier clic.
    void api
      .get<{ connected: boolean; suggestions: string[] }>("/sales/suggestions")
      .then(setSuggestions)
      .catch(() => setSuggestions({ connected: true, suggestions: [] }));
  }, [chargerConversations]);

  /**
   * La zone qui défile vraiment.
   *
   * Aujourd'hui c'est toujours la page : le fil n'a pas de hauteur bornée, à
   * aucune largeur — deux zones imbriquées sur un téléphone sont un piège au
   * pouce, et sur grand écran le cadre ne défilait de toute façon jamais
   * (rien ne contraignait sa hauteur, son `overflow-y-auto` était décoratif).
   * La fonction mesure plutôt que de supposer : un cadre un jour borné serait
   * pris en compte sans rien réécrire ici.
   */
  const zone = useCallback(() => {
    const el = filRef.current;
    // `scrollHeight > clientHeight` ne suffit pas : un bloc sans `overflow`
    // déborde sans défiler, et on lui parlerait dans le vide.
    const interne = el && ["auto", "scroll"].includes(getComputedStyle(el).overflowY);
    if (el && interne && el.scrollHeight > el.clientHeight + 1)
      return {
        fenetre: false,
        y: () => el.scrollTop,
        restant: () => el.scrollHeight - el.scrollTop - el.clientHeight,
        enBas: () => el.scrollTo({ top: el.scrollHeight, behavior: defilement() }),
      };
    return {
      fenetre: true,
      y: () => window.scrollY,
      restant: () => document.documentElement.scrollHeight - window.scrollY - window.innerHeight,
      enBas: () =>
        window.scrollTo({ top: document.documentElement.scrollHeight, behavior: defilement() }),
    };
  }, []);

  const surDefilement = useCallback(() => {
    const courante = zone();
    const y = courante.y();
    const remonte = y < yRef.current - 2;
    yRef.current = y;
    if (courante.restant() <= SEUIL_BAS) {
      enBasRef.current = true;
      setDetache(false);
      setNouveautes(0);
      return;
    }
    // On ne décroche QUE si la personne est remontée. Mesurer seulement la
    // distance au bas décrochait à chaque réponse : le bas s'éloigne parce
    // que le fil s'allonge, sans que personne n'ait bougé — et le suivi
    // s'arrêtait au premier message, ce qui est exactement l'inverse de ce
    // qu'on veut (section NE PAS de la carte).
    if (remonte) {
      enBasRef.current = false;
      setDetache(true);
    }
  }, [zone]);

  // Sur mobile, c'est la fenêtre qui défile : l'événement n'arrive pas sur le
  // fil, il faut l'écouter là où il se produit.
  useEffect(() => {
    window.addEventListener("scroll", surDefilement, { passive: true });
    return () => window.removeEventListener("scroll", surDefilement);
  }, [surDefilement]);

  /**
   * Suivi du bas du fil — SEULEMENT si on y était déjà.
   *
   * L'écran rappelait en bas à chaque événement de trace : pendant qu'un tour
   * travaille, c'est un événement par étape, donc une personne remontée lire
   * un briefing était ramenée en bas plusieurs fois par tour. Rester collé au
   * bas quand on y est reste le comportement attendu (section NE PAS) ; c'est
   * l'inverse qui ne l'était pas.
   */
  useEffect(() => {
    if (!enBasRef.current) return;
    const courante = zone();
    // Ouvrir un fil depuis le tiroir mobile : le tiroir verrouille encore le
    // défilement de la page (`overflow: hidden` sur le `body`) au moment où
    // le fil arrive, et le `scrollTo` est alors silencieusement perdu. On
    // attend que la page soit rendue à elle-même. Ne concerne que le
    // défilement de fenêtre : un cadre interne, lui, n'est pas verrouillé.
    if (courante.fenetre && getComputedStyle(document.body).overflow === "hidden") {
      const observateur = new MutationObserver(() => {
        if (getComputedStyle(document.body).overflow === "hidden") return;
        observateur.disconnect();
        if (enBasRef.current) zone().enBas();
      });
      observateur.observe(document.body, { attributes: true });
      return () => observateur.disconnect();
    }
    courante.enBas();
  }, [messages, trace, zone]);

  /** Flèches entre questions suggérées — la barre ne coûte qu'un Tab. */
  function auClavierSuggestions(e: React.KeyboardEvent<HTMLDivElement>) {
    const boutons = Array.from(
      e.currentTarget.querySelectorAll<HTMLButtonElement>("[data-suggestion]")
    );
    const i = boutons.indexOf(e.target as HTMLButtonElement);
    if (i < 0) return;
    const pas: Record<string, number> = {
      ArrowDown: i + 1,
      ArrowRight: i + 1,
      ArrowUp: i - 1,
      ArrowLeft: i - 1,
      Home: 0,
      End: boutons.length - 1,
    };
    const but = pas[e.key];
    if (but === undefined) return;
    e.preventDefault();
    const cible = boutons[Math.max(0, Math.min(but, boutons.length - 1))];
    for (const b of boutons) b.tabIndex = b === cible ? 0 : -1;
    cible.focus();
  }

  /** Ramène au bas du fil et reprend le suivi. */
  function revenirEnBas() {
    enBasRef.current = true;
    setDetache(false);
    setNouveautes(0);
    zone().enBas();
  }

  async function ouvrir(id: string) {
    setActif(id);
    setTiroir(false);
    enBasRef.current = true;
    setDetache(false);
    setNouveautes(0);
    setTrace([]);
    setPending(null);
    setTours([]);
    setOrphelins(null);
    setMessages([]);
    const detail = await api.get<{ messages: Message[]; trace: TraceEvent[] }>(
      `/sales/conversations/${id}`
    );
    // `GET` renvoie déjà la trace : la perdre à l'ouverture, c'était présenter
    // la traçabilité comme une garantie et la laisser s'évaporer au premier
    // rechargement.
    const affichables = messagesAffichables(detail.messages);
    const { tours: rattaches, orphelins: restants } = rattacherTours(
      affichables,
      detail.trace ?? []
    );
    setMessages(affichables);
    setTours(rattaches);
    setOrphelins(restants);
  }

  async function nouvelleConversation(): Promise<string> {
    const conv = await api.post<{ id: string }>("/sales/conversations");
    setActif(conv.id);
    setTiroir(false);
    enBasRef.current = true;
    setDetache(false);
    setNouveautes(0);
    setMessages([]);
    setTrace([]);
    setTours([]);
    setOrphelins(null);
    await chargerConversations();
    saisieRef.current?.focus();
    return conv.id;
  }

  /**
   * Range la trace du tour qui vient de s'achever sous la réponse qu'il a
   * produite, pour que le fil ait exactement la forme qu'il aura après un
   * rechargement : un tour par réponse, dans l'ordre.
   */
  function cloturerTour(etapes: TraceEvent[]) {
    setTours((prev) => [...prev, { trace: etapes, ecritures: ecrituresDe(etapes) }]);
    setTrace([]);
    setAnnonce(resumeTrace(etapes));
  }

  function appliquerResultat(resultat: TurnResult, etapes: TraceEvent[]) {
    if (resultat.type === "final") {
      cloturerTour(etapes);
      // La réponse arrive pendant qu'on lit ailleurs : on ne déplace rien,
      // on le signale. C'est tout l'objet du bouton.
      if (!enBasRef.current) setNouveautes((n) => n + 1);
      setMessages((prev) => [
        ...prev,
        { position: prev.length, role: "assistant", content: resultat.content },
      ]);
    } else if (resultat.type === "needs_confirmation") {
      setPending({ call_id: resultat.call_id, tool: resultat.tool, preview: resultat.preview });
    } else {
      toast.warning(`L'agent s'est arrêté après ${resultat.steps} étapes sans conclure.`);
    }
  }

  async function envoyer(texte: string) {
    const contenu = texte.trim();
    if (!contenu || enCours) return;
    const conversationId = actif ?? (await nouvelleConversation());

    setSaisie("");
    // Envoyer est un geste explicite : son propre message se lit en bas.
    enBasRef.current = true;
    setDetache(false);
    setNouveautes(0);
    setMessages((prev) => [...prev, { position: prev.length, role: "user", content: contenu }]);
    setTrace([]);
    traceRef.current = [];
    setAnnonce("L'agent réfléchit…");
    setEnCours(true);

    let recu = false;
    try {
      await streamPost<TraceEvent & TurnResult>(
        `/sales/conversations/${conversationId}/messages/stream`,
        { message: contenu },
        {
          onEvent: (event, data) => {
            if (event === "step") {
              traceRef.current = [...traceRef.current, data as TraceEvent];
              setTrace(traceRef.current);
            } else if (event === "result") {
              recu = true;
              appliquerResultat(data as TurnResult, traceRef.current);
            } else if (event === "error") {
              signalerEchec("L'agent a rencontré une erreur pendant ce tour.");
              recu = true;
            }
          },
        }
      );
      if (!recu) throw new Error("flux interrompu");
    } catch {
      // Repli non-streaming : même tour, sans trace au fil de l'eau.
      try {
        const resultat = await api.post<TurnResult>(
          `/sales/conversations/${conversationId}/messages`,
          { message: contenu }
        );
        appliquerResultat(resultat, traceRef.current);
        setEchecAction(null);
        toast.info("Réponse obtenue sans diffusion en direct.");
      } catch (err) {
        signalerEchec(err instanceof ApiError ? err.message : "L'agent n'a pas répondu.");
      }
    } finally {
      setEnCours(false);
      // Le bouton « Envoyer » se désactive pendant le tour : le focus tombe
      // alors sur le `body` et le clavier repart du haut de la page. On le
      // rend à la saisie, d'où il venait — jamais s'il est parti ailleurs
      // entre-temps, ce serait voler le curseur à quelqu'un qui lit.
      if (document.activeElement === document.body) saisieRef.current?.focus();
      void chargerConversations();
    }
  }

  /**
   * Un échec se dit deux fois : en toast pour l'attention qui était ailleurs,
   * et dans la page pour qu'il y reste. Le toast se ferme ; la trace non.
   */
  function signalerEchec(message: string) {
    setAnnonce("");
    setEchecAction(message);
    notifierErreur(message);
  }

  async function confirmer() {
    if (!pending || !actif) return;
    try {
      await api.post<TurnResult>(`/sales/conversations/${actif}/confirm/${pending.call_id}`);
      setPending(null);
      // On relit la conversation plutôt que d'assembler le tour à la main :
      // l'identifiant de l'enregistrement écrit vit dans la trace côté
      // serveur, pas dans le texte de l'agent. Le fil prend alors exactement
      // la forme qu'il aura au prochain chargement — un accusé vérifiable,
      // pas une phrase du modèle.
      await ouvrir(actif);
      setEchecAction(null);
      notifierSucces("Action exécutée dans Salesforce.");
    } catch (err) {
      signalerEchec(err instanceof ApiError ? err.message : "L'écriture dans Salesforce a échoué.");
    }
  }

  function refuser() {
    setPending(null);
    setMessages((prev) => [
      ...prev,
      {
        position: prev.length,
        role: "assistant",
        content: "_Action refusée. Rien n'a été écrit._",
      },
    ]);
  }

  const courante = conversations?.find((c) => c.id === actif) ?? null;

  const liste = (
    <ConversationList
      conversations={conversations}
      actif={actif}
      onOuvrir={(id) => void ouvrir(id)}
      onNouvelle={() => void nouvelleConversation()}
      onRenommer={async (id, titre) => {
        await api.patch(`/sales/conversations/${id}`, { title: titre });
        notifierSucces("Conversation renommée.");
        await chargerConversations();
      }}
      onSupprimer={async (id) => {
        try {
          await api.delete(`/sales/conversations/${id}`);
          notifierSucces("Conversation supprimée.");
          if (actif === id) {
            setActif(null);
            setMessages([]);
            setTours([]);
            setOrphelins(null);
            setTrace([]);
          }
          await chargerConversations();
        } catch {
          signalerEchec("Suppression impossible. La conversation est toujours là.");
        }
      }}
    />
  );

  return (
    <div className="grid flex-1 gap-4 lg:grid-cols-[16rem_1fr]">
      {/* Écrire est ce qu'on vient faire ici. Même liste des fils réduite à
          un seul arrêt de tabulation, la saisie reste derrière la trace de
          chaque réponse — un dépliant focusable par tour, donc un nombre de
          Tab qui croît avec le fil. Ce lien la rend atteignable en un Tab,
          quelle que soit la longueur de l'historique. Il n'apparaît que quand
          il y a quelque chose à sauter : sur un fil vide, la saisie est déjà
          à trois Tab. */}
      {messages.length > 0 && (
        <SkipLink href="#saisie-message" className="lg:col-span-2">
          Aller à la zone de saisie
        </SkipLink>
      )}
      {/* Un seul des deux arbres existe à la fois : deux exemplaires de la
          liste, ce serait deux champs de recherche portant le même `id`. */}
      {grandEcran ? (
        liste
      ) : (
        <Sheet open={tiroir} onOpenChange={setTiroir}>
          <SheetTrigger asChild>
            <Button variant="outline" size="sm" className="justify-start">
              <MessagesSquare aria-hidden /> Conversations
              {conversations && conversations.length > 0 && ` (${conversations.length})`}
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-80">
            <SheetHeader>
              <SheetTitle>Conversations</SheetTitle>
              <SheetDescription>
                Vos fils de discussion avec l&apos;agent commercial.
              </SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">{liste}</div>
          </SheetContent>
        </Sheet>
      )}

      <section className="flex min-h-[28rem] min-w-0 flex-1 flex-col rounded-lg border">
        {/* Le titre du fil ouvert, sur le fil : sinon la seule façon de savoir
            où l'on est était de repérer l'entrée surlignée dans la colonne de
            gauche — impossible sous `lg`, où elle est repliée. */}
        {courante && (
          <div className="flex items-baseline justify-between gap-3 border-b px-4 py-2">
            <h2 className="truncate text-sm font-medium">{courante.title}</h2>
            <p className="shrink-0 text-xs text-muted-foreground">
              {quand(courante.created_at)} · {courante.messages} message
              {courante.messages > 1 ? "s" : ""}
            </p>
          </div>
        )}
        {/* Le fil ne défile PAS dans son cadre : c'est la page qui défile, à
            toutes les largeurs. Une seule zone de défilement verticale par
            écran, et le composeur reste atteignable parce qu'il est collant.
            (`onScroll` reste branché : si un jour le cadre est borné, le
            suivi du bas continue de fonctionner sans rien changer ici.) */}
        {/* `role="log"` : les ajouts sont annoncés, poliment, dans l'ordre —
            et rien n'est relu. La clé au fil ouvert remonte la région à
            chaque changement de conversation : une région live qui NAÎT avec
            son contenu ne le fait pas lire, alors qu'une région déjà en place
            qui reçoit trente messages d'un coup les lit tous. */}
        <div
          key={actif ?? "nouvelle"}
          ref={filRef}
          onScroll={surDefilement}
          role="log"
          aria-live="polite"
          aria-relevant="additions"
          aria-label="Fil de la conversation"
          className="flex-1 space-y-4 p-4"
        >
          {messages.length === 0 &&
            !enCours &&
            (suggestions?.connected === false ? (
              <EmptyState
                icon={<Link2Off />}
                title="Salesforce n'est pas connecté"
                description="L'agent commercial lit et écrit dans le Salesforce de votre organisation : sans connexion, il n'a rien à lire. Un administrateur peut la mettre en place depuis les paramètres."
                action={
                  <Button asChild variant="outline">
                    <Link href="/settings">Ouvrir les paramètres</Link>
                  </Button>
                }
                className="border-0"
              />
            ) : (
              <EmptyState
                title="Posez votre question"
                description="L'agent lit Salesforce pour votre organisation et cite ses sources."
                action={
                  // Les questions proposées nomment des comptes de CETTE org :
                  // elles viennent du backend, pas d'une liste écrite en dur
                  // qui parlait de comptes d'un jeu de démonstration.
                  // Barre d'outils : trois questions, un seul arrêt de
                  // tabulation, les flèches pour passer de l'une à l'autre.
                  // Chacune un arrêt, c'était trois crans de plus entre le
                  // début de l'écran et la zone de saisie.
                  <div
                    role="toolbar"
                    aria-orientation="vertical"
                    aria-label="Questions suggérées"
                    onKeyDown={auClavierSuggestions}
                    className="flex flex-col gap-2"
                  >
                    {(suggestions?.suggestions ?? []).map((q, i) => (
                      <Button
                        key={q}
                        variant="outline"
                        size="sm"
                        data-suggestion={i}
                        tabIndex={i === 0 ? 0 : -1}
                        className="h-auto py-2 text-left whitespace-normal"
                        onClick={() => void envoyer(q)}
                      >
                        {q}
                      </Button>
                    ))}
                  </div>
                }
                className="border-0"
              />
            ))}

          {messages.map((m, i) => {
            // Le n-ième tour a produit la n-ième réponse : la trace et les
            // accusés se rendent SOUS le message auquel ils appartiennent,
            // et non en bloc unique en bas de fil.
            const tour =
              m.role === "assistant"
                ? tours[messages.slice(0, i).filter((x) => x.role === "assistant").length]
                : undefined;
            return (
              <div key={`${m.position}-${m.role}`} className="space-y-2">
                <div className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-lg px-3 py-2 text-sm wrap-anywhere",
                      m.role === "user" ? "bg-ink text-background" : "bg-muted"
                    )}
                  >
                    <RichText content={m.content ?? ""} instanceUrl={instanceUrl} />
                  </div>
                </div>

                {tour && <BlocTour tour={tour} instanceUrl={instanceUrl} />}
              </div>
            );
          })}

          {/* Un tour sans réponse — une écriture proposée et laissée en
              suspens — garde sa trace ici plutôt que de disparaître. */}
          {orphelins && !enCours && (
            <div className="space-y-2">
              <BlocTour tour={orphelins} instanceUrl={instanceUrl} />
            </div>
          )}

          {/* L'échec reste dans le fil, à sa place chronologique, jusqu'à ce
              qu'on le masque. Le toast, lui, aura disparu. */}
          {echecAction && (
            <ErrorState
              titre="Ce tour n'a pas abouti"
              message={echecAction}
              onRetry={() => setEchecAction(null)}
              retryLabel="Masquer"
            />
          )}
        </div>

        {/* Uniquement le tour EN COURS : une fois la réponse rendue, la trace
            rejoint le message qu'elle a produit, plus haut. Elle est rendue
            HORS du `role="log"` : elle y grandissait d'une ligne par étape,
            et chaque ligne aurait été lue par-dessus la précédente. Ce qu'un
            lecteur d'écran entend du tour, c'est « l'agent réfléchit » puis le
            résumé — la région d'état juste en dessous. */}
        {enCours && (
          <div className="px-4 pb-4">
            <Card className="gap-2 py-3">
              <CardContent className="px-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Trace de l&apos;agent
                </p>
                <AgentSteps events={trace} running={enCours} />
              </CardContent>
            </Card>
          </div>
        )}

        <form
          className="relative sticky bottom-0 z-10 flex items-start gap-2 rounded-b-lg border-t bg-background p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void envoyer(saisie);
          }}
        >
          {/* Accroché AU COMPOSEUR, pas à une distance du bas de l'écran :
              le composeur est collant et sa hauteur dépend de son contenu
              (l'aide du raccourci l'a fait grandir, et un décalage en dur le
              faisait passer dessous). Il le suit donc, toujours juste
              au-dessus. Hors du `role="log"` : son apparition n'est pas un
              message. */}
          {detache && (
            <div className="absolute -top-12 right-0 left-0 flex justify-center">
              <Button size="sm" variant="secondary" className="shadow-md" onClick={revenirEnBas}>
                <ArrowDown aria-hidden />
                {nouveautes > 0
                  ? `${nouveautes} nouvelle${nouveautes > 1 ? "s" : ""} réponse${nouveautes > 1 ? "s" : ""}`
                  : "Revenir en bas"}
              </Button>
            </div>
          )}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <Textarea
              id="saisie-message"
              ref={saisieRef}
              rows={2}
              value={saisie}
              onChange={(e) => setSaisie(e.target.value)}
              onKeyDown={(e) => {
                // Entrée envoie ; Maj+Entrée passe à la ligne.
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void envoyer(saisie);
                }
              }}
              placeholder="Prépare mon appel avec…"
              aria-label="Votre message"
              aria-describedby="aide-saisie"
              className="resize-none text-sm"
            />
            {/* Le raccourci n'était écrit nulle part : on ne devine pas
                qu'Entrée envoie avant de l'avoir fait par accident. */}
            <p id="aide-saisie" className="text-xs text-muted-foreground">
              Entrée pour envoyer, Maj+Entrée pour une nouvelle ligne.
            </p>
          </div>
          <Button type="submit" disabled={enCours || !saisie.trim()} aria-label="Envoyer">
            <Send />
          </Button>
          {/* L'état du tour, pour qui ne voit pas la trace : « l'agent
              réfléchit », puis le nombre d'étapes et ce qu'elles ont fait.
              Le message, lui, est annoncé par le fil au moment où il s'y
              ajoute — une fois, et une seule. */}
          <p role="status" className="sr-only">
            {annonce}
          </p>
        </form>
      </section>

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(ouvert) => !ouvert && refuser()}
        title="Confirmer l'action dans Salesforce"
        description={
          pending ? (
            <>
              L&apos;agent propose cette action :{" "}
              <Badge variant="outline">{libelleOutil(pending.tool)}</Badge>. Rien n&apos;est écrit
              tant que vous n&apos;avez pas confirmé.
            </>
          ) : undefined
        }
        preview={pending?.preview}
        confirmLabel="Confirmer l'écriture"
        cancelLabel="Refuser"
        retourFocus={saisieRef}
        onConfirm={confirmer}
        onCancel={refuser}
      />
    </div>
  );
}
