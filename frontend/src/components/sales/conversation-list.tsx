"use client";

import { MoreHorizontal, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SqueletteListe } from "@/components/ui/skeletons";
import { grouperParJour, reperes, type Conversation } from "@/lib/sales";
import { cn } from "@/lib/utils";

/** Fils affichés d'emblée ; les suivants sur demande. */
const TRANCHE = 20;

/** Insensible à la casse ET aux accents : « renouvellement » trouve « Renouvèlement ». */
function normaliser(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/**
 * Colonne des fils de discussion.
 *
 * Sept entrées « Que dois-je savoir avant d'appel… » identiques ne sont pas
 * une liste : chaque entrée porte donc son heure (ou sa date) et son nombre
 * de messages, et les fils sont groupés par jour. Renommer reste un geste de
 * l'utilisateur — on ne demande pas au modèle de nommer les fils (un appel
 * LLM pour une étiquette ne vaut pas son coût, ADR-011).
 *
 * La colonne n'avait aucune borne : elle rendait tout l'historique, et la
 * zone de saisie du chat reculait d'un arrêt de tabulation par conversation.
 * Vingt fils, puis une recherche ou « en afficher plus ».
 */
export function ConversationList({
  conversations,
  actif,
  onOuvrir,
  onNouvelle,
  onRenommer,
  onSupprimer,
}: {
  conversations: Conversation[] | null;
  actif: string | null;
  onOuvrir: (id: string) => void;
  onNouvelle: () => void;
  onRenommer: (id: string, titre: string) => Promise<void>;
  onSupprimer: (id: string) => Promise<void>;
}) {
  const [aRenommer, setARenommer] = useState<Conversation | null>(null);
  const [titre, setTitre] = useState("");
  const [aSupprimer, setASupprimer] = useState<Conversation | null>(null);
  const [envoi, setEnvoi] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [tranche, setTranche] = useState(TRANCHE);
  // Le menu qui a ouvert le dialogue disparaît si le fil disparaît : on
  // retombe sur « Nouvelle conversation », qui reste toujours là.
  const nouvelleRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);
  // Le fil qui porte l'unique arrêt de tabulation de la liste.
  const [curseur, setCurseur] = useState<string | null>(null);
  const repere = reperes(conversations ?? []);
  const q = normaliser(recherche.trim());
  const trouvees = (conversations ?? []).filter((c) => q === "" || normaliser(c.title).includes(q));
  const affichees = trouvees.slice(0, tranche);
  const reste = trouvees.length - affichees.length;
  const prochaines = Math.min(reste, TRANCHE);

  // Ordre d'affichage réel, groupes compris : c'est celui que suivent les
  // flèches.
  const groupes = grouperParJour(affichees);
  const ordre = groupes.flatMap((g) => g.fils.map((c) => c.id));
  const ancre =
    (curseur && ordre.includes(curseur) ? curseur : null) ??
    (actif && ordre.includes(actif) ? actif : null) ??
    ordre[0];

  /**
   * Navigation par flèches — la liste ne coûte qu'UN arrêt de tabulation.
   *
   * Avec un arrêt par fil, la zone de saisie du chat arrivait en 22e position
   * et reculait d'un cran à chaque conversation créée. Haut/bas parcourt les
   * fils, droite/gauche passe du titre à son menu d'actions.
   */
  function auClavier(e: React.KeyboardEvent<HTMLElement>) {
    const cible = e.target as HTMLElement;
    const id = cible.closest<HTMLElement>("[data-fil-id]")?.dataset.filId;
    if (!id) return;
    const i = ordre.indexOf(id);
    const colonne = cible.dataset.colonne === "actions" ? "actions" : "titre";
    const aller = (j: number, vers: string) => {
      const but = ordre[Math.max(0, Math.min(j, ordre.length - 1))];
      setCurseur(but);
      navRef.current
        ?.querySelector<HTMLButtonElement>(`[data-fil-id="${but}"] [data-colonne="${vers}"]`)
        ?.focus();
    };
    const touches: Record<string, () => void> = {
      ArrowDown: () => aller(i + 1, colonne),
      ArrowUp: () => aller(i - 1, colonne),
      Home: () => aller(0, colonne),
      End: () => aller(ordre.length - 1, colonne),
      ArrowRight: () => aller(i, "actions"),
      ArrowLeft: () => aller(i, "titre"),
    };
    const geste = touches[e.key];
    if (!geste) return;
    e.preventDefault();
    geste();
  }

  async function renommer() {
    if (!aRenommer || !titre.trim()) return;
    setEnvoi(true);
    try {
      await onRenommer(aRenommer.id, titre.trim());
      setARenommer(null);
    } finally {
      setEnvoi(false);
    }
  }

  return (
    <aside className="flex h-full min-h-0 min-w-0 flex-col gap-2">
      <Button ref={nouvelleRef} size="sm" onClick={onNouvelle} className="w-full">
        <Plus data-icon="inline-start" /> Nouvelle conversation
      </Button>

      {!conversations ? (
        <SqueletteListe lignes={3} label="Chargement des conversations…" />
      ) : conversations.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted-foreground">
          Aucune conversation. Posez votre première question à droite.
        </p>
      ) : (
        <>
          {/* La recherche n'apparaît que quand elle sert : sous vingt fils,
              c'est un champ de plus à parcourir pour rien. */}
          {conversations.length > TRANCHE && (
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Label htmlFor="recherche-fil" className="sr-only">
                Rechercher une conversation par titre
              </Label>
              <Input
                id="recherche-fil"
                type="search"
                className="pl-8"
                placeholder="Rechercher un fil…"
                value={recherche}
                onChange={(e) => {
                  setRecherche(e.target.value);
                  setTranche(TRANCHE);
                }}
              />
            </div>
          )}

          {/* La liste défile chez elle : « Nouvelle conversation » et la
              recherche restent en place, quelle que soit la longueur de
              l'historique — avant, vingt fils poussaient le bouton hors de
              l'écran et emportaient toute la page avec eux.
              `-mx-1 px-1` : la marge que réclame l'anneau de focus, pour
              qu'il ne déclenche pas une barre de défilement horizontale.
              `relative` : les noms accessibles des menus d'actions sont des
              éléments `sr-only`, donc positionnés en absolu. Sans bloc
              conteneur ici, le dernier d'entre eux se plaçait par rapport à
              la page, qui gagnait deux cents pixels de défilement vide. */}
          <div className="relative -mx-1 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto overscroll-contain px-1">
            {trouvees.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground" role="status">
                Aucun fil ne porte ce titre.
              </p>
            ) : (
              <nav
                ref={navRef}
                aria-label="Conversations"
                aria-describedby="aide-fils"
                onKeyDown={auClavier}
                className="flex flex-col gap-3"
              >
                <p id="aide-fils" className="sr-only">
                  Utilisez les flèches haut et bas pour parcourir les conversations, droite pour
                  ouvrir leurs actions.
                </p>
                {groupes.map((groupe) => (
                  <section key={groupe.jour} className="flex flex-col gap-1">
                    <h2 className="px-3 text-xs font-medium text-muted-foreground">
                      {groupe.jour}
                    </h2>
                    <ul className="flex flex-col gap-1">
                      {groupe.fils.map((c) => {
                        const courant = actif === c.id;
                        // Le nom accessible doit distinguer des voisines homonymes :
                        // l'heure et le nombre de messages sont déjà à l'écran.
                        const marque = repere[c.id];
                        return (
                          <li
                            key={c.id}
                            data-fil-id={c.id}
                            className="group/fil flex items-center gap-1"
                          >
                            <button
                              type="button"
                              data-colonne="titre"
                              tabIndex={c.id === ancre ? 0 : -1}
                              onFocus={() => setCurseur(c.id)}
                              onClick={() => onOuvrir(c.id)}
                              aria-current={courant ? "true" : undefined}
                              className={cn(
                                "min-w-0 flex-1 rounded-md px-3 py-2 text-left text-sm",
                                courant
                                  ? "bg-secondary text-secondary-foreground"
                                  : "text-muted-foreground hover:bg-muted"
                              )}
                            >
                              <span className="block truncate">{c.title}</span>
                              <span className="block text-xs">{marque}</span>
                            </button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  data-colonne="actions"
                                  tabIndex={-1}
                                  className="size-8 shrink-0"
                                >
                                  <MoreHorizontal aria-hidden />
                                  <span className="sr-only">
                                    Actions sur la conversation {c.title} — {marque}
                                  </span>
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onSelect={() => {
                                    setTitre(c.title);
                                    setARenommer(c);
                                  }}
                                >
                                  <Pencil aria-hidden /> Renommer
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  variant="destructive"
                                  onSelect={() => setASupprimer(c)}
                                >
                                  <Trash2 aria-hidden /> Supprimer
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))}
              </nav>
            )}

            {reste > 0 && (
              <Button variant="ghost" size="sm" onClick={() => setTranche((n) => n + TRANCHE)}>
                Afficher {prochaines} conversation{prochaines > 1 ? "s" : ""} de plus
                <span className="sr-only"> — {reste} restantes</span>
              </Button>
            )}
          </div>
        </>
      )}

      <Dialog open={aRenommer !== null} onOpenChange={(ouvert) => !ouvert && setARenommer(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Renommer la conversation</DialogTitle>
            <DialogDescription>
              Le titre n&apos;est utilisé que dans cette liste. Il ne change rien à l&apos;échange
              ni au CRM.
            </DialogDescription>
          </DialogHeader>
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              void renommer();
            }}
          >
            <div className="grid gap-2">
              <Label htmlFor="titre-fil">Titre</Label>
              <Input
                id="titre-fil"
                autoFocus
                required
                maxLength={200}
                value={titre}
                onChange={(e) => setTitre(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setARenommer(null)}>
                Annuler
              </Button>
              <Button type="submit" disabled={envoi || !titre.trim()}>
                {envoi ? "Enregistrement…" : "Renommer"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={aSupprimer !== null}
        onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        title="Supprimer cette conversation ?"
        description="Les messages sont effacés. Les écritures déjà faites dans Salesforce restent, elles : une conversation de travail disparaît, pas l'historique de ce qui a été fait dans le CRM."
        preview={aSupprimer?.title}
        confirmLabel="Supprimer"
        cancelLabel="Annuler"
        retourFocus={nouvelleRef}
        onConfirm={async () => {
          if (aSupprimer) await onSupprimer(aSupprimer.id);
          setASupprimer(null);
        }}
      />
    </aside>
  );
}
