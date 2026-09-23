"use client";

import { Archive, ArchiveRestore, FileText, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Paginateur } from "@/components/ui/paginateur";
import { ScrollX } from "@/components/ui/scroll-x";
import { SqueletteListe } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { api } from "@/lib/api";
import { statutOffre, type Job } from "@/lib/hr";
import { notifierErreur, notifierSucces } from "@/lib/notifications";

/** Offres par page. La liste ne peut que grandir ; l'écran, non. */
const TAILLE_PAGE = 20;

const RUN_LIBELLE: Record<string, string> = {
  queued: "en file",
  running: "en cours",
  done: "terminée",
  failed: "en échec",
};

function dateCourte(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });
}

/**
 * Date ET heure de création. L'heure n'est pas de la décoration : deux offres
 * homonymes créées le même jour — le cas qui a motivé cette carte — ne sont
 * distinguables que par elle, dans le texte visible comme dans le nom
 * accessible des liens de la ligne (WCAG 2.4.6).
 */
function dateLongue(iso: string | null | undefined): string {
  if (!iso) return "date inconnue";
  const d = new Date(iso);
  return `${d.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  })} à ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Insensible à la casse ET aux accents : « ingenieur » doit trouver « Ingénieur ». */
function normaliser(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

/**
 * Point d'entrée du cas d'usage RH : la liste des offres.
 *
 * Chaque ligne mène à l'étape où l'offre en est réellement — grille tant
 * qu'elle n'est pas validée, dépôt ensuite, campagne si elle existe — pour
 * que le recruteur n'ait jamais à deviner quel écran ouvrir.
 *
 * Une liste qui ne peut que grandir devient inutilisable : d'où la recherche,
 * le tri (récentes d'abord) et l'archivage. Une offre archivée n'est jamais
 * supprimée — elle porte des candidatures, donc des données personnelles dont
 * la suppression est un acte distinct.
 */
export function JobsList() {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [archivees, setArchivees] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [page, setPage] = useState(0);
  const [enCours, setEnCours] = useState<string | null>(null);
  // Le bouton d'archivage disparaît de la liste après l'action (l'offre change
  // de filtre) : on renvoie le focus sur la case « Afficher les archivées »,
  // qui est là où l'offre vient de partir.
  const filtreRef = useRef<HTMLButtonElement>(null);

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      setJobs(await api.get<Job[]>(`/hr/jobs?archived=${archivees}`));
    } catch {
      setErreur("Impossible de charger les offres.");
    }
  }, [archivees]);

  useEffect(() => {
    // Chargement initial : la règle vise les cascades de rendus, pas un appel
    // réseau au montage (même motif que components/settings/members-card.tsx).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJobs(null);
    void charger();
  }, [charger]);

  async function basculerArchive(job: Job) {
    setEnCours(job.id);
    const versArchive = job.archived_at === null;
    try {
      await api.patch(`/hr/jobs/${job.id}/archive`, { archived: versArchive });
      notifierSucces(
        versArchive
          ? `« ${job.title} » archivée. Cochez « Afficher les archivées » pour la retrouver.`
          : `« ${job.title} » rétablie dans les offres actives.`
      );
      await charger();
      filtreRef.current?.focus();
    } catch {
      notifierErreur(
        versArchive
          ? "Archivage impossible. L'offre est inchangée."
          : "Rétablissement impossible. L'offre reste archivée."
      );
    } finally {
      setEnCours(null);
    }
  }

  // Tri : les plus récentes d'abord. Fait ici et non côté serveur parce que la
  // recherche l'est aussi — les deux doivent porter sur le même jeu.
  const visibles = useMemo(() => {
    const q = normaliser(recherche.trim());
    return (jobs ?? [])
      .filter((j) => q === "" || normaliser(j.title).includes(q))
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));
  }, [jobs, recherche]);

  // La page courante peut ne plus exister après une recherche ou un
  // archivage : on revient à la première plutôt que d'afficher du vide.
  const pageSure = Math.min(page, Math.max(0, Math.ceil(visibles.length / TAILLE_PAGE) - 1));
  const affichees = visibles.slice(pageSure * TAILLE_PAGE, (pageSure + 1) * TAILLE_PAGE);

  const barre = (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Label htmlFor="recherche-offre" className="sr-only">
            Rechercher une offre par intitulé
          </Label>
          <Input
            id="recherche-offre"
            type="search"
            className="w-64 max-w-full pl-8"
            placeholder="Rechercher un intitulé…"
            value={recherche}
            onChange={(e) => {
              setRecherche(e.target.value);
              setPage(0);
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="voir-archivees"
            ref={filtreRef}
            checked={archivees}
            onCheckedChange={(v) => {
              setArchivees(v === true);
              setPage(0);
            }}
          />
          <Label htmlFor="voir-archivees" className="text-sm font-normal">
            Afficher les archivées
          </Label>
        </div>
      </div>
      <Button asChild size="sm">
        <Link href="/hr/new">
          <Plus aria-hidden /> Nouvelle offre
        </Link>
      </Button>
    </div>
  );

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;

  return (
    <div className="flex flex-col gap-4">
      {barre}

      {/* Le nombre de résultats est annoncé : une recherche qui filtre sans
          rien dire laisse croire à une liste vide. */}
      <p className="sr-only" role="status">
        {jobs === null
          ? "Chargement des offres…"
          : `${visibles.length} offre${visibles.length > 1 ? "s" : ""} ${
              archivees ? "archivée" : "active"
            }${visibles.length > 1 ? "s" : ""}${recherche.trim() ? ` pour « ${recherche.trim()} »` : ""}`}
      </p>

      {jobs === null ? (
        <SqueletteListe lignes={4} label="Chargement des offres…" />
      ) : visibles.length === 0 ? (
        recherche.trim() ? (
          <EmptyState
            icon={<Search />}
            title={`Aucune offre ne correspond à « ${recherche.trim()} »`}
            description={
              archivees
                ? "La recherche porte sur les offres archivées. Décochez le filtre pour chercher parmi les offres actives."
                : "Vérifiez l'orthographe, ou cochez « Afficher les archivées » si l'offre a été rangée."
            }
            action={
              <Button variant="outline" onClick={() => setRecherche("")}>
                Effacer la recherche
              </Button>
            }
          />
        ) : archivees ? (
          <EmptyState
            icon={<Archive />}
            title="Aucune offre archivée"
            description="Les offres que vous archivez sont rangées ici. Elles ne sont jamais supprimées."
          />
        ) : (
          <EmptyState
            icon={<FileText />}
            title="Aucune offre pour l'instant"
            description="Créez une offre, validez sa grille de critères, puis déposez les CV à présélectionner."
            action={
              <Button asChild>
                <Link href="/hr/new">Créer une offre</Link>
              </Button>
            }
          />
        )
      ) : (
        <ScrollX borne sommet={pageSure} label="Offres">
          <ul className="flex flex-col gap-3">
            {affichees.map((job) => {
              const cible =
                job.status === "draft"
                  ? `/hr/${job.id}/criteria`
                  : job.last_run
                    ? `/hr/${job.id}/runs/${job.last_run.run_id}`
                    : `/hr/${job.id}/candidates`;
              const statut = statutOffre(job.status);
              // Deux offres peuvent porter le même intitulé : la date de création
              // et le résumé — tous deux visibles — sont ce qui les distingue.
              // Ils complètent donc le nom accessible des deux liens de la carte,
              // qui seraient sinon identiques (WCAG 2.4.6).
              const resume = `créée le ${dateLongue(job.created_at)} · ${job.candidates} CV déposé${
                job.candidates > 1 ? "s" : ""
              }${
                job.last_run
                  ? ` · dernière analyse ${RUN_LIBELLE[job.last_run.status] ?? job.last_run.status} le ${dateCourte(job.last_run.created_at)}`
                  : " · aucune analyse"
              }`;
              const archivee = job.archived_at !== null;
              return (
                <li key={job.id}>
                  <Card className="transition-colors hover:border-primary/50">
                    <CardContent className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <Link href={cible} className="font-medium hover:underline">
                          {job.title}
                          <span className="sr-only"> — {resume}</span>
                        </Link>
                        <p className="text-xs text-muted-foreground">{resume}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {archivee && <Badge variant="outline">Archivée</Badge>}
                        <Badge variant={statut.variant}>{statut.libelle}</Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={enCours === job.id}
                          onClick={() => void basculerArchive(job)}
                        >
                          {archivee ? <ArchiveRestore aria-hidden /> : <Archive aria-hidden />}
                          <span className="sr-only">
                            {archivee ? "Rétablir" : "Archiver"} l&apos;offre {job.title} — {resume}
                          </span>
                        </Button>
                        <Button asChild variant="outline" size="sm">
                          <Link href={cible}>
                            Ouvrir
                            <span className="sr-only">
                              {" "}
                              l&apos;offre {job.title} — {resume}
                            </span>
                          </Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </li>
              );
            })}
          </ul>
        </ScrollX>
      )}

      <Paginateur
        page={pageSure}
        taille={TAILLE_PAGE}
        total={visibles.length}
        onPage={setPage}
        nom="Offres"
      />
    </div>
  );
}
