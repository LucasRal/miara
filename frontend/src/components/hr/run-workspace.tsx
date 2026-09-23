"use client";

import { Download, Search, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { JobSteps } from "@/components/hr/job-steps";
import { Ranking } from "@/components/hr/ranking";
import { AgentTrace, type TraceStep } from "@/components/agent-trace";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Paginateur } from "@/components/ui/paginateur";
import { ScrollX } from "@/components/ui/scroll-x";
import { SqueletteClassement } from "@/components/ui/skeletons";
import { ErrorState, NotFoundState } from "@/components/ui/states";
import { api, estIntrouvable } from "@/lib/api";
import { duree, usd } from "@/lib/dashboard";
import { notifierErreur, notifierSucces } from "@/lib/notifications";
import {
  downloadCsv,
  rankingToCsv,
  type Job,
  type RankedCandidate,
  type Results,
  type Run,
} from "@/lib/hr";

const PERIODE_MS = 2000;
/** Fiches de classement par page. La cible du produit est 500 CV par lot. */
const TAILLE_PAGE = 20;
/** Borne du serveur sur une page de résultats : sert à l'export complet. */
const EXPORT_MAX = 500;

/**
 * Paramètres de lecture du classement, identiques pour l'affichage et pour
 * l'export : un CSV qui ne contient pas ce qui est à l'écran est un piège.
 */
function requete(filtres: Filtres, limit: number, offset: number): string {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    min_score: String(filtres.seuil),
    must_have_only: String(filtres.mustHaveOk),
  });
  if (filtres.q) params.set("q", filtres.q);
  return params.toString();
}

interface Filtres {
  seuil: number;
  mustHaveOk: boolean;
  q: string;
}

/**
 * Étapes du pipeline, telles qu'elles existent VRAIMENT côté worker.
 *
 * Le profil et la notation sont enchaînés dans la même tâche Celery (ils
 * partagent le texte du CV) : leur avancement est donc le même compteur. Le
 * dire ici plutôt que d'animer deux barres indépendantes qui mentiraient.
 */
function etapes(run: Run): TraceStep[] {
  const total = run.total || 1;
  const lus = run.candidates.filter((c) => c.file_status !== "uploaded").length;
  const traites = run.candidates.filter((c) => c.status !== "pending").length;
  const fini = run.status === "done";
  const etat = (fait: number, attendu: number): TraceStep["status"] =>
    fait >= attendu ? "done" : fait > 0 || run.status === "running" ? "active" : "todo";

  return [
    {
      key: "extract",
      label: "Extraction du texte",
      detail: `${lus} / ${total} CV lus`,
      status: etat(lus, total),
    },
    {
      key: "profile",
      label: "Profil structuré",
      detail: "Enchaîné à la notation dans la même tâche",
      status: lus === 0 ? "todo" : etat(traites, total),
    },
    {
      key: "score",
      label: "Notation contre la grille",
      detail: `${traites} / ${total} CV notés`,
      status: lus === 0 ? "todo" : etat(traites, total),
    },
    {
      key: "rank",
      label: "Classement",
      detail: fini ? `${run.stats?.scored ?? 0} CV classés` : undefined,
      status: fini ? "done" : traites >= total ? "active" : "todo",
    },
  ];
}

/**
 * Suivi d'une campagne puis classement.
 *
 * La progression est relue en base toutes les deux secondes plutôt que tenue
 * en mémoire : un rechargement, un autre onglet ou une reconnexion retrouvent
 * exactement le même état. La page reste utilisable pendant l'analyse, et le
 * classement se remplit au fur et à mesure au lieu d'apparaître à la fin.
 */
export function RunWorkspace({ jobId, runId }: { jobId: string; runId: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  // Campagne absente, offre absente, ou panne passagère : trois issues
  // différentes, et une seule d'entre elles mérite « Réessayer ».
  const [absente, setAbsente] = useState<"run" | "job" | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  // Échec d'une action, distinct de l'échec de chargement : le toast est un
  // rappel, la page doit garder la trace (WCAG 4.1.3).
  const [echecAction, setEchecAction] = useState<string | null>(null);
  const [seuil, setSeuil] = useState(0);
  const [recherche, setRecherche] = useState("");
  // Terme réellement envoyé : la frappe ne déclenche pas une requête par
  // caractère sur un classement de 500 lignes.
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  // Nombre de CV « à convoquer » sur TOUT le classement, pas sur la page :
  // c'est le chiffre que le recruteur retient, il ne peut pas dépendre de la
  // page ouverte. Le serveur le compte (note >= 70 et éliminatoires tenus,
  // exactement la règle de `recommendation`).
  const [convocables, setConvocables] = useState<number | null>(null);
  const [exportEnCours, setExportEnCours] = useState(false);
  // Incrémenté par une relance : redémarre la boucle de suivi, qui s'était
  // arrêtée à la fin de la campagne. Sans cela le CV repris n'avancerait plus
  // à l'écran jusqu'au prochain rechargement.
  const [reprise, setReprise] = useState(0);
  // Incrémenté dès que l'avancement change : c'est le signal de relecture du
  // classement, découplé des filtres et de la page.
  const [fraicheur, setFraicheur] = useState(0);
  const [mustHaveOk, setMustHaveOk] = useState(false);
  const dernierFait = useRef(-1);

  const relire = useCallback(async () => {
    const etat = await api.get<Run>(`/hr/runs/${runId}`);
    setRun(etat);
    // Le classement n'est rechargé que si quelque chose a bougé : inutile de
    // redemander la page toutes les deux secondes pendant une extraction.
    if (etat.done !== dernierFait.current) {
      dernierFait.current = etat.done;
      setFraicheur((n) => n + 1);
    }
    return etat;
  }, [runId]);

  // Débat de frappe : le terme part quand la saisie se pose.
  useEffect(() => {
    const minuteur = setTimeout(() => {
      setQ(recherche.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(minuteur);
  }, [recherche]);

  /**
   * Classement PAGINÉ ET FILTRÉ PAR LE SERVEUR.
   *
   * Filtrer côté navigateur ce que le serveur avait déjà tronqué donnait un
   * classement faux : « les CV au-dessus de 70 » ne pouvait désigner que les
   * vingt premiers reçus. Les filtres partent donc avec la requête, et le
   * total renvoyé porte sur la campagne entière.
   */
  useEffect(() => {
    // Rien avant le premier état de campagne : le classement serait demandé
    // deux fois au montage, une fois pour rien.
    if (fraicheur === 0) return;
    let actif = true;
    const filtres = { seuil, mustHaveOk, q };
    void api
      .get<Results>(
        `/hr/runs/${runId}/results?${requete(filtres, TAILLE_PAGE, page * TAILLE_PAGE)}`
      )
      .then((r) => actif && setResults(r))
      .catch(() => actif && setEchecAction("Chargement du classement impossible."));
    // Le nombre de CV à convoquer est un comptage à part : même filtres de
    // recherche, plus la règle de recommandation.
    void api
      .get<Results>(
        `/hr/runs/${runId}/results?${requete({ seuil: 70, mustHaveOk: true, q }, 1, 0)}`
      )
      .then((r) => actif && setConvocables(r.total))
      .catch(() => actif && setConvocables(null));
    return () => {
      actif = false;
    };
  }, [runId, page, seuil, mustHaveOk, q, fraicheur]);

  useEffect(() => {
    let actif = true;
    let minuteur: ReturnType<typeof setTimeout>;

    async function boucle() {
      try {
        const etat = await relire();
        if (!actif) return;
        // On continue tant que la campagne tourne ; une campagne terminée ne
        // laisse pas un minuteur qui interroge le serveur indéfiniment.
        if (etat.status === "queued" || etat.status === "running")
          minuteur = setTimeout(() => void boucle(), PERIODE_MS);
      } catch (err) {
        if (!actif) return;
        if (estIntrouvable(err)) setAbsente("run");
        else setErreur("Chargement de la campagne impossible.");
      }
    }

    void api
      .get<Job>(`/hr/jobs/${jobId}`)
      .then((j) => actif && setJob(j))
      .catch((err: unknown) => {
        if (!actif) return;
        if (estIntrouvable(err)) setAbsente("job");
        else setErreur("Chargement de l'offre impossible.");
      });
    void boucle();
    return () => {
      actif = false;
      clearTimeout(minuteur);
    };
  }, [jobId, relire, reprise]);

  /**
   * Export du classement TEL QUE FILTRÉ, pas de la page ouverte.
   *
   * La page affiche vingt lignes ; le CSV doit contenir les 57 CV retenus par
   * les filtres, plus les CV en échec, qui restent à traiter à la main. D'où
   * une requête dédiée, bornée à ce que le serveur accepte de rendre d'un
   * coup.
   */
  async function exporter() {
    setExportEnCours(true);
    try {
      const tout = await api.get<Results>(
        `/hr/runs/${runId}/results?${requete({ seuil, mustHaveOk, q }, EXPORT_MAX, 0)}`
      );
      downloadCsv(
        `classement-${runId.slice(0, 8)}.csv`,
        rankingToCsv([...tout.ranking, ...tout.failed])
      );
      if (tout.total > tout.ranking.length) {
        notifierErreur(
          `Export limité aux ${tout.ranking.length} premiers CV sur ${tout.total} : affinez les filtres pour exporter le reste.`
        );
      }
    } catch {
      notifierErreur("Export impossible : le classement n'a pas pu être relu.");
    } finally {
      setExportEnCours(false);
    }
  }

  async function relancer(candidateId: string) {
    try {
      await api.post(`/hr/runs/${runId}/candidates/${candidateId}/retry`);
      notifierSucces("CV replacé dans la file.");
      setEchecAction(null);
      dernierFait.current = -1;
      setReprise((n) => n + 1);
    } catch {
      const message = "Relance impossible : le CV n'a pas été replacé dans la file.";
      setEchecAction(message);
      notifierErreur(message);
    }
  }

  // Le fil d'étapes n'est rendu nulle part ici : sans offre chargée, il n'y a
  // pas de parcours à parcourir, et ses liens pointeraient dans le vide.
  if (absente === "job")
    return (
      <NotFoundState
        titre="Cette offre n'existe plus"
        description="Elle a été supprimée, ou elle appartient à une autre organisation. Le lien que vous avez suivi est périmé."
        retour={{ href: "/hr", label: "Voir les offres" }}
      />
    );
  if (absente === "run")
    return (
      <NotFoundState
        titre="Cette analyse n'existe plus"
        description="La campagne a été supprimée, ou elle appartient à une autre organisation. Vous pouvez en relancer une depuis les CV déposés."
        retour={{ href: `/hr/${jobId}/candidates`, label: "Revenir aux CV déposés" }}
      />
    );
  if (erreur) return <ErrorState message={erreur} onRetry={() => setReprise((n) => n + 1)} />;
  if (run === null) return <SqueletteClassement lignes={3} label="Chargement de la campagne…" />;

  // Page courante du classement : déjà filtrée et triée par le serveur.
  const visibles: RankedCandidate[] = results?.ranking ?? [];
  // Les CV en échec ne passent PAS par les filtres — le serveur les sort à
  // part. Un filtre porte sur des notes ; un CV non noté n'en a pas, et le
  // sortir sur « note < 40 » revient à affirmer quelque chose de lui. C'est
  // aussi le seul CV qui demande une action humaine : le masquer, c'est le
  // perdre.
  const echecs: RankedCandidate[] = results?.failed ?? [];
  const retenus = results?.total ?? 0;
  // Le total noté vient de l'état de campagne, les retenus du classement :
  // deux lectures, donc deux instants. Pendant une analyse en cours, le
  // classement peut être en avance — « 29 retenus sur 1 » n'aurait aucun
  // sens, on prend le plus grand des deux.
  const notes = Math.max(run.candidates.filter((c) => c.status === "scored").length, retenus);
  const masques = Math.max(0, notes - retenus);
  const filtre = seuil > 0 || mustHaveOk || q !== "";
  const enCours = run.status === "queued" || run.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <JobSteps jobId={jobId} current="run" runId={runId} title={job?.title} />

      {echecAction && (
        <ErrorState
          titre="Action impossible"
          message={echecAction}
          onRetry={() => setEchecAction(null)}
          retryLabel="Masquer"
        />
      )}

      <Card>
        <CardContent className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">
                {enCours
                  ? "Analyse en cours"
                  : run.status === "done"
                    ? "Analyse terminée"
                    : "Campagne interrompue"}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {run.done} / {run.total} CV
              </span>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={run.total}
              aria-valuenow={run.done}
              aria-label="Progression de l'analyse"
              className="h-2 w-full overflow-hidden rounded-4xl bg-muted"
            >
              <div
                className="h-full rounded-4xl bg-primary transition-[width] duration-500"
                style={{ width: `${Math.round(run.progress * 100)}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Vous pouvez quitter cette page : l&apos;analyse continue côté serveur et la
              progression se retrouve au retour.
            </p>
            {run.stats?.seconds_per_candidate != null && (
              <p className="text-xs text-muted-foreground">
                {duree(run.stats.seconds_per_candidate * 1000)} par CV en moyenne
                {run.stats.llm?.cost_usd != null && ` · ${usd(run.stats.llm.cost_usd)} pour le lot`}
              </p>
            )}
          </div>
          <AgentTrace steps={etapes(run)} className="min-w-0" />
        </CardContent>
      </Card>

      {retenus === 0 && echecs.length === 0 && !filtre ? (
        <EmptyState
          title={enCours ? "Premiers résultats à venir" : "Aucun résultat"}
          description={
            enCours
              ? "Les CV apparaissent ici au fur et à mesure de leur notation."
              : "Aucun CV n'a pu être noté pour cette campagne."
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-4">
              <div className="grid gap-1">
                <Label htmlFor="recherche-cv" className="text-xs">
                  Nom de fichier
                </Label>
                <div className="relative">
                  <Search
                    className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden
                  />
                  <Input
                    id="recherche-cv"
                    type="search"
                    className="w-56 max-w-full pl-8"
                    placeholder="Rechercher un CV…"
                    value={recherche}
                    onChange={(e) => setRecherche(e.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-1">
                <Label htmlFor="seuil" className="text-xs">
                  Note minimale
                </Label>
                <Input
                  id="seuil"
                  type="number"
                  min={0}
                  max={100}
                  step={5}
                  value={seuil}
                  onChange={(e) => {
                    setSeuil(Math.max(0, Math.min(100, Number(e.target.value))));
                    setPage(0);
                  }}
                  className="w-24"
                />
              </div>
              <div className="flex items-center gap-2 pb-2">
                <Checkbox
                  id="must-have"
                  checked={mustHaveOk}
                  onCheckedChange={(v) => {
                    setMustHaveOk(v === true);
                    setPage(0);
                  }}
                />
                <Label htmlFor="must-have" className="text-sm">
                  Éliminatoires tenus uniquement
                </Label>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              disabled={retenus + echecs.length === 0 || exportEnCours}
              onClick={() => void exporter()}
            >
              <Download aria-hidden />
              {exportEnCours
                ? "Préparation…"
                : `Exporter le classement (${retenus + echecs.length})`}
            </Button>
          </div>

          {/* Le compteur nommait « 2 sur 3 » sans dire ce qu'était le
              troisième. Ce qui est masqué est compté et qualifié. */}
          <p className="text-sm text-muted-foreground" role="status">
            {retenus} CV noté{retenus > 1 ? "s" : ""} retenu{retenus > 1 ? "s" : ""} sur {notes}
            {masques > 0 && ` · ${masques} masqué${masques > 1 ? "s" : ""} par les filtres`}
            {convocables !== null && convocables > 0 && ` · ${convocables} à convoquer`}
            {echecs.length > 0 &&
              ` · ${echecs.length} CV en échec, listé${echecs.length > 1 ? "s" : ""} à part ci-dessous`}
          </p>

          {retenus === 0 && notes > 0 ? (
            <EmptyState
              icon={<SlidersHorizontal />}
              title="Aucun CV noté ne passe ces filtres"
              description={`Aucun des ${notes} CV notés de cette campagne ne porte ce nom de fichier, n'atteint la note minimale ou ne tient tous les critères éliminatoires.`}
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setSeuil(0);
                    setMustHaveOk(false);
                    setRecherche("");
                    setPage(0);
                  }}
                >
                  Effacer les filtres
                </Button>
              }
            />
          ) : (
            <>
              <ScrollX borne sommet={page} label="Classement des CV">
                <Ranking rows={visibles} onRetry={(id) => void relancer(id)} />
              </ScrollX>
              <Paginateur
                page={page}
                taille={TAILLE_PAGE}
                total={retenus}
                onPage={setPage}
                nom="CV classés"
              />
            </>
          )}

          {/* Section à part, JAMAIS filtrée : « Relancer ce CV » doit rester
              atteignable quel que soit l'état des filtres. */}
          {echecs.length > 0 && (
            <section className="flex flex-col gap-3 border-t pt-4">
              <div>
                <h2 className="font-heading text-base font-medium">
                  {echecs.length} CV n&apos;{echecs.length > 1 ? "ont" : "a"} pas pu être noté
                  {echecs.length > 1 ? "s" : ""}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Ces CV ne sont soumis à aucun filtre : sans note, un seuil de note ne dit rien
                  d&apos;eux. Relancez-les, ou traitez-les à la main.
                </p>
              </div>
              <Ranking rows={echecs} onRetry={(id) => void relancer(id)} />
            </section>
          )}
        </div>
      )}
    </div>
  );
}
