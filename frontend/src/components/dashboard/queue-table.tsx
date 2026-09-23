"use client";

import { ChevronDown, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, type Colonne } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteTableau } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { duree, heure, type TaskEvent, type TaskPage } from "@/lib/dashboard";
import type { Role } from "@/lib/api";
import { notifierErreur, notifierSucces } from "@/lib/notifications";

const STATUT: Record<
  string,
  { libelle: string; variant: "default" | "secondary" | "destructive" }
> = {
  started: { libelle: "En cours", variant: "secondary" },
  succeeded: { libelle: "Réussie", variant: "default" },
  failed: { libelle: "En échec", variant: "destructive" },
};

// Noms techniques des tâches, rendus lisibles. Une tâche inconnue garde son
// nom brut plutôt que d'être masquée : mieux vaut lisible qu'absent.
const LIBELLE: Record<string, string> = {
  "hr.extract_text": "Extraction du texte d'un CV",
  "hr.score_candidate": "Profil et notation d'un CV",
  "hr.rank_run": "Classement d'une campagne",
  "core.ping": "Contrôle du worker",
};

const RAFRAICHISSEMENT_MS = 5000;
const TAILLE_PAGE = 25;

/** Détail technique d'un échec : replié, jamais absent. */
function DetailTechnique({ error }: { error: string }) {
  return (
    <details className="mt-1">
      <summary className="inline-flex cursor-pointer items-center gap-1 text-xs text-muted-foreground">
        <ChevronDown
          className="size-3 transition-transform [details[open]_&]:rotate-180"
          aria-hidden
        />
        Détail technique
      </summary>
      {/* `break-all` : une trace SQLAlchemy n'a pas d'espace pour se couper. */}
      <pre className="mt-1 max-h-40 overflow-auto rounded-md border bg-muted/50 p-2 text-xs break-all whitespace-pre-wrap">
        {error}
      </pre>
    </details>
  );
}

/**
 * File de traitement : le pipeline Celery rendu observable.
 *
 * L'écran répond à « est-ce que ça tourne, et sinon pourquoi ». La relance
 * est réservée à l'encadrement : elle consomme du budget modèle et peut
 * republier une écriture.
 *
 * Bornée côté serveur : 25 tâches par page sur une fenêtre de 24 h. La file
 * grandit sans limite ; la paginer côté client reviendrait à tout télécharger
 * d'abord — ce que faisait la version précédente (88 lignes d'un coup, toutes
 * les 5 s).
 */
export function QueueTable({ role }: { role: Role | null }) {
  const [page, setPage] = useState<TaskPage | null>(null);
  const [filtre, setFiltre] = useState("toutes");
  const [numero, setNumero] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);
  const [relance, setRelance] = useState<string | null>(null);

  const charger = useCallback(async () => {
    const params = new URLSearchParams({
      limit: String(TAILLE_PAGE),
      offset: String(numero * TAILLE_PAGE),
    });
    if (filtre !== "toutes") params.set("status", filtre);
    try {
      setPage(await api.get<TaskPage>(`/queue/tasks?${params}`));
      setErreur(null);
    } catch {
      setErreur("Impossible de charger la file.");
    }
  }, [filtre, numero]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
    // Les tâches avancent sans action de l'utilisateur : l'écran se rafraîchit
    // tout seul, sinon il faudrait recharger pour voir une reprise. Seule la
    // page courante est rechargée, pas la file entière.
    const minuteur = setInterval(() => void charger(), RAFRAICHISSEMENT_MS);
    return () => clearInterval(minuteur);
  }, [charger]);

  async function relancer(tache: TaskEvent) {
    setRelance(tache.task_id);
    try {
      await api.post(`/queue/tasks/${tache.task_id}/retry`);
      notifierSucces("Tâche republiée.");
      await charger();
    } catch (err) {
      notifierErreur(
        err instanceof ApiError && err.status === 403
          ? "Seul un administrateur peut relancer une tâche."
          : err instanceof ApiError
            ? err.message
            : "Relance impossible."
      );
    } finally {
      setRelance(null);
    }
  }

  const peutRelancer = role === "owner" || role === "admin";

  /** Bouton de relance, nommé pour les lecteurs d'écran (WCAG 2.4.6). */
  function BoutonRelance({ tache }: { tache: TaskEvent }) {
    if (tache.status !== "failed" || !peutRelancer) return null;
    const quoi = LIBELLE[tache.name] ?? tache.name;
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={relance === tache.task_id}
        onClick={() => void relancer(tache)}
      >
        <RotateCcw aria-hidden />
        Relancer
        <span className="sr-only">
          {" "}
          : {quoi}, démarrée à {heure(tache.started_at)}
        </span>
      </Button>
    );
  }

  function Statut({ tache }: { tache: TaskEvent }) {
    const s = STATUT[tache.status] ?? { libelle: tache.status, variant: "secondary" as const };
    return <Badge variant={s.variant}>{s.libelle}</Badge>;
  }

  const colonnes: Colonne<TaskEvent>[] = [
    {
      id: "tache",
      accessorKey: "name",
      header: "Tâche",
      sortFn: "text",
      cell: ({ row }) => {
        const t = row.original;
        return (
          <div className="max-w-96">
            <span className="block truncate">{LIBELLE[t.name] ?? t.name}</span>
            {/* Le motif traduit est la phrase ; la trace reste accessible,
                repliée. Une exception Python n'est pas un message. */}
            {t.reason && <span className="block text-xs text-destructive">{t.reason}</span>}
            {t.error && <DetailTechnique error={t.error} />}
            {t.retried > 0 && (
              <span className="block text-xs text-muted-foreground">relancée {t.retried} fois</span>
            )}
          </div>
        );
      },
    },
    {
      id: "file",
      accessorKey: "queue",
      header: "File",
      sortFn: "text",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{row.original.queue}</span>
      ),
    },
    {
      id: "statut",
      accessorKey: "status",
      header: "Statut",
      sortFn: "text",
      cell: ({ row }) => <Statut tache={row.original} />,
    },
    {
      id: "duree",
      accessorKey: "duration_ms",
      header: "Durée",
      sortFn: "basic",
      cell: ({ row }) => (
        <span className="text-sm tabular-nums">{duree(row.original.duration_ms)}</span>
      ),
    },
    {
      id: "demarree",
      accessorKey: "started_at",
      header: "Démarrée",
      sortFn: "datetime",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{heure(row.original.started_at)}</span>
      ),
    },
    {
      id: "action",
      header: () => <span className="sr-only">Action</span>,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="text-right">
          <BoutonRelance tache={row.original} />
        </div>
      ),
    },
  ];

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (page === null)
    return <SqueletteTableau lignes={8} colonnes={5} label="Chargement de la file…" />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={filtre}
          onValueChange={(v) => {
            setFiltre(v);
            setNumero(0);
          }}
        >
          <SelectTrigger className="w-48" aria-label="Filtrer par statut">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="toutes">Toutes les tâches</SelectItem>
            <SelectItem value="started">En cours</SelectItem>
            <SelectItem value="succeeded">Réussies</SelectItem>
            <SelectItem value="failed">En échec</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-sm text-muted-foreground">
          {page.total} tâche{page.total > 1 ? "s" : ""} sur les 24 dernières heures
        </p>
      </div>

      <DataTable
        colonnes={colonnes}
        donnees={page.tasks}
        caption="File de traitement"
        cleLigne={(t) => t.id}
        paginationServeur={{
          page: numero,
          taillePage: TAILLE_PAGE,
          total: page.total,
          onPage: setNumero,
        }}
        vide={
          <EmptyState
            title="Aucune tâche"
            description="Les traitements lancés par vos agents apparaîtront ici, avec leur durée et leur issue."
          />
        }
        carte={(t) => (
          // Sous `sm` : statut et relance en tête, jamais hors écran.
          <div className="flex flex-col gap-2 rounded-lg border p-3">
            <div className="flex items-center justify-between gap-2">
              <Statut tache={t} />
              <BoutonRelance tache={t} />
            </div>
            <span className="text-sm">{LIBELLE[t.name] ?? t.name}</span>
            {t.reason && <span className="text-xs text-destructive">{t.reason}</span>}
            {t.error && <DetailTechnique error={t.error} />}
            <span className="text-xs text-muted-foreground">
              file {t.queue} · {duree(t.duration_ms)} · démarrée à {heure(t.started_at)}
              {t.retried > 0 && ` · relancée ${t.retried} fois`}
            </span>
          </div>
        )}
      />
    </div>
  );
}
