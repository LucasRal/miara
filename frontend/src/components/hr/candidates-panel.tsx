"use client";

import { FileUp, Info, ListChecks, Play, RotateCw, Search, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { JobSteps } from "@/components/hr/job-steps";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Paginateur } from "@/components/ui/paginateur";
import { ScrollX } from "@/components/ui/scroll-x";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteListe } from "@/components/ui/skeletons";
import { ErrorState, NotFoundState } from "@/components/ui/states";
import { api, ApiError, estIntrouvable } from "@/lib/api";
import { usd } from "@/lib/dashboard";
import { dureeApprox, estimationRelance } from "@/lib/hr";
import { notifierErreur, notifierSucces } from "@/lib/notifications";
import { cn } from "@/lib/utils";
import type { Candidate, Job, UploadResult } from "@/lib/hr";

// Le backend borne un dépôt à 20 fichiers (HR_MAX_UPLOAD_FILES) : un lot de
// 57 CV part donc en plusieurs requêtes, transparentes pour le recruteur.
const PAR_LOT = 20;
const TYPES_ACCEPTES = ".pdf,.docx";
/** CV listés par page : un lot vise 500 fichiers, l'écran en montre 20. */
const TAILLE_PAGE = 20;

const STATUT: Record<
  string,
  { libelle: string; variant: "default" | "secondary" | "destructive" }
> = {
  uploaded: { libelle: "Déposé", variant: "secondary" },
  // `secondary` et non `default` : « Texte extrait » est un état, pas une
  // action. En couleur primaire pleine, il avait le poids visuel d'un bouton.
  extracted: { libelle: "Texte extrait", variant: "secondary" },
  needs_ocr: { libelle: "Scanné (OCR nécessaire)", variant: "destructive" },
  error: { libelle: "Illisible", variant: "destructive" },
};

function dateLongue(iso: string | null | undefined): string {
  if (!iso) return "date inconnue";
  const d = new Date(iso);
  return `${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })} à ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

/** Insensible à la casse ET aux accents : « resume » doit trouver « Résumé ». */
function normaliser(texte: string): string {
  return texte
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function taille(octets: number): string {
  return octets >= 1024 * 1024
    ? `${(octets / 1024 / 1024).toFixed(1)} Mo`
    : `${Math.round(octets / 1024)} Ko`;
}

/**
 * Dépôt des CV et lancement de la campagne.
 *
 * Les fichiers partent par lots : le recruteur dépose 57 CV d'un geste sans
 * savoir que l'API en accepte 20 par requête. Chaque fichier est accepté ou
 * refusé indépendamment, et les refus sont affichés avec leur motif plutôt
 * que d'échouer silencieusement.
 */
export function CandidatesPanel({ jobId }: { jobId: string }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listeRef = useRef<HTMLUListElement>(null);
  // Où rendre le focus quand le dialogue de suppression se ferme : le bouton
  // cliqué tant qu'il existe encore, sinon le premier qui reste, sinon le
  // champ de dépôt. Une ref, pas un état : la valeur n'affiche rien.
  const retourRef = useRef<HTMLElement | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [cvs, setCvs] = useState<Candidate[] | null>(null);
  const [absente, setAbsente] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [echecAction, setEchecAction] = useState<string | null>(null);
  const [survol, setSurvol] = useState(false);
  const [envoi, setEnvoi] = useState<{ faits: number; total: number } | null>(null);
  const [refuses, setRefuses] = useState<{ filename: string; reason: string }[]>([]);
  const [aSupprimer, setASupprimer] = useState<Candidate | null>(null);
  const [lancement, setLancement] = useState(false);
  const [aRelancer, setARelancer] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [statut, setStatut] = useState("tous");
  const [page, setPage] = useState(0);
  const lancerRef = useRef<HTMLButtonElement>(null);

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      const [offre, liste] = await Promise.all([
        api.get<Job>(`/hr/jobs/${jobId}`),
        api.get<Candidate[]>(`/hr/jobs/${jobId}/candidates`),
      ]);
      setJob(offre);
      setCvs(liste);
    } catch (err) {
      if (estIntrouvable(err)) setAbsente(true);
      else setErreur("Chargement de l'offre impossible.");
    }
  }, [jobId]);

  useEffect(() => {
    // Chargement initial : la règle vise les cascades de rendus, pas un appel
    // réseau au montage (même motif que components/settings/members-card.tsx).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  const deposer = useCallback(
    async (fichiers: File[]) => {
      if (fichiers.length === 0) return;
      setRefuses([]);
      setEnvoi({ faits: 0, total: fichiers.length });
      const acceptes: Candidate[] = [];
      const rejetes: { filename: string; reason: string }[] = [];
      try {
        for (let i = 0; i < fichiers.length; i += PAR_LOT) {
          const lot = fichiers.slice(i, i + PAR_LOT);
          const form = new FormData();
          for (const f of lot) form.append("files", f);
          const res = await api.upload<UploadResult>(`/hr/jobs/${jobId}/candidates`, form);
          acceptes.push(...res.accepted);
          rejetes.push(...res.rejected);
          setEnvoi({ faits: Math.min(i + PAR_LOT, fichiers.length), total: fichiers.length });
        }
        setCvs((prev) => [...(prev ?? []), ...acceptes]);
        setRefuses(rejetes);
        setEchecAction(null);
        notifierSucces(
          `${acceptes.length} CV déposé${acceptes.length > 1 ? "s" : ""}` +
            (rejetes.length ? `, ${rejetes.length} refusé${rejetes.length > 1 ? "s" : ""}` : "")
        );
      } catch (err) {
        const message =
          err instanceof ApiError && err.status === 413
            ? "Lot trop volumineux pour le serveur : déposez moins de fichiers à la fois."
            : "Le dépôt a échoué. Les CV déjà acceptés sont conservés.";
        setEchecAction(message);
        notifierErreur(message);
      } finally {
        setEnvoi(null);
      }
    },
    [jobId]
  );

  async function supprimer(candidat: Candidate) {
    try {
      await api.delete(`/hr/jobs/${jobId}/candidates/${candidat.id}`);
      setCvs((prev) => (prev ?? []).filter((c) => c.id !== candidat.id));
      notifierSucces("CV supprimé, fichier compris.");
      setEchecAction(null);
    } catch {
      const message = "Suppression impossible : le CV est toujours là.";
      setEchecAction(message);
      notifierErreur(message);
    } finally {
      // La ligne vient de disparaître : le bouton mémorisé n'existe plus.
      retourRef.current =
        listeRef.current?.querySelector<HTMLElement>("[data-supprimer]") ?? inputRef.current;
      setASupprimer(null);
    }
  }

  /**
   * Une campagne coûte de l'argent et du temps, et c'est le seul bouton
   * primaire de la page : la relancer par mégarde est le geste le plus cher
   * de l'application. Tant qu'aucune campagne n'existe, il n'y a rien à
   * refaire deux fois — on part directement.
   */
  function demanderLancement() {
    if (job?.last_run) setARelancer(true);
    else void lancer();
  }

  async function lancer() {
    setARelancer(false);
    setLancement(true);
    try {
      const run = await api.post<{ run_id: string }>(`/hr/jobs/${jobId}/runs`);
      router.push(`/hr/${jobId}/runs/${run.run_id}`);
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 409
          ? err.message
          : "Le lancement de l'analyse a échoué.";
      setEchecAction(message);
      notifierErreur(message);
      setLancement(false);
    }
  }

  if (absente)
    return (
      <NotFoundState
        titre="Cette offre n'existe plus"
        description="Elle a été supprimée, ou elle appartient à une autre organisation. Les CV déposés pour elle ne sont plus accessibles."
        retour={{ href: "/hr", label: "Voir les offres" }}
      />
    );
  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (job === null || cvs === null)
    return <SqueletteListe lignes={5} label="Chargement des candidatures…" />;

  const pretAAnalyser = job.status === "ready" && cvs.some((c) => c.status !== "error");
  const precedente = job.last_run;
  const analysables = cvs.filter((c) => c.status !== "error").length;
  const estimation = estimationRelance(precedente, analysables);

  // Chercher un CV par son nom de fichier et ne garder qu'un statut : à 57
  // lignes, Ctrl+F était le seul outil du recruteur, et il ne sait pas quels
  // fichiers sont illisibles sans parcourir toute la liste.
  const q = normaliser(recherche.trim());
  const filtres = cvs.filter(
    (cv) =>
      (q === "" || normaliser(cv.original_filename).includes(q)) &&
      (statut === "tous" || cv.status === statut)
  );
  const pageSure = Math.min(page, Math.max(0, Math.ceil(filtres.length / TAILLE_PAGE) - 1));
  const affiches = filtres.slice(pageSure * TAILLE_PAGE, (pageSure + 1) * TAILLE_PAGE);
  // Les statuts réellement présents, dans l'ordre du vocabulaire : proposer
  // « Illisible » quand aucun fichier ne l'est mène à une liste vide.
  const statutsPresents = Object.keys(STATUT).filter((code) =>
    cvs.some((cv) => cv.status === code)
  );

  return (
    <div className="flex flex-col gap-6">
      <JobSteps jobId={jobId} current="candidates" runId={job.last_run?.run_id} title={job.title} />

      {/* Le toast est un rappel, pas la trace : il disparaît dès qu'on le
          ferme, et quelqu'un qui regardait ailleurs ne l'a jamais vu. */}
      {echecAction && (
        <ErrorState
          titre="Action impossible"
          message={echecAction}
          onRetry={() => setEchecAction(null)}
          retryLabel="Masquer"
        />
      )}

      {job.status !== "ready" && (
        <Alert>
          <Info aria-hidden />
          <AlertTitle>La grille de critères n&apos;est pas encore validée</AlertTitle>
          <AlertDescription>
            <p>
              Vous pouvez déposer les CV dès maintenant, mais l&apos;analyse restera bloquée tant
              qu&apos;un humain n&apos;a pas validé la grille.
            </p>
            {/* Le bandeau expliquait le blocage sans dire où le lever. */}
            <Button asChild variant="outline" size="sm" className="mt-1">
              <Link href={`/hr/${jobId}/criteria`}>
                <ListChecks aria-hidden /> Ouvrir la grille de critères
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setSurvol(true);
        }}
        onDragLeave={() => setSurvol(false)}
        onDrop={(e) => {
          e.preventDefault();
          setSurvol(false);
          void deposer(Array.from(e.dataTransfer.files));
        }}
        className={cn(
          "flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center transition-colors",
          survol && "border-primary bg-primary/5"
        )}
      >
        <FileUp className="size-8 text-muted-foreground" aria-hidden />
        <p className="text-sm">
          Glissez vos CV ici, au format PDF ou DOCX.
          <br />
          <span className="text-muted-foreground">10 Mo par fichier au maximum.</span>
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={TYPES_ACCEPTES}
          className="sr-only"
          aria-label="Choisir des CV à déposer"
          onChange={(e) => {
            void deposer(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          <Upload aria-hidden /> Choisir des fichiers
        </Button>
        {envoi && (
          <p role="status" className="text-sm text-muted-foreground">
            Envoi {envoi.faits} / {envoi.total}…
          </p>
        )}
      </div>

      {refuses.length > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-1">
            <p className="text-sm font-medium text-destructive">
              {refuses.length} fichier{refuses.length > 1 ? "s" : ""} refusé
              {refuses.length > 1 ? "s" : ""}
            </p>
            <ul className="text-xs text-muted-foreground">
              {refuses.map((r) => (
                <li key={r.filename}>
                  {r.filename} : {r.reason}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {cvs.length === 0 ? (
        <EmptyState
          title="Aucun CV déposé"
          description="Déposez les candidatures à présélectionner pour cette offre."
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {cvs.length} CV déposé{cvs.length > 1 ? "s" : ""}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {/* La campagne existante doit être atteignable depuis ici :
                  sinon la seule façon d'y retourner est de relancer. */}
              {precedente && (
                <Button asChild variant="outline" size="sm">
                  <Link href={`/hr/${jobId}/runs/${precedente.run_id}`}>
                    Voir la dernière analyse
                  </Link>
                </Button>
              )}
              <Button
                ref={lancerRef}
                onClick={demanderLancement}
                disabled={!pretAAnalyser || lancement}
              >
                {precedente ? <RotateCw aria-hidden /> : <Play aria-hidden />}
                {lancement ? "Lancement…" : precedente ? "Relancer l'analyse" : "Lancer l'analyse"}
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search
                className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Label htmlFor="recherche-cv" className="sr-only">
                Rechercher un CV par nom de fichier
              </Label>
              <Input
                id="recherche-cv"
                type="search"
                className="w-64 max-w-full pl-8"
                placeholder="Rechercher un nom de fichier…"
                value={recherche}
                onChange={(e) => {
                  setRecherche(e.target.value);
                  setPage(0);
                }}
              />
            </div>
            <div className="flex items-center gap-2">
              <Label htmlFor="statut-cv" className="sr-only">
                Filtrer par statut de fichier
              </Label>
              <Select
                value={statut}
                onValueChange={(v) => {
                  setStatut(v);
                  setPage(0);
                }}
              >
                <SelectTrigger id="statut-cv" className="w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tous">Tous les statuts</SelectItem>
                  {statutsPresents.map((code) => (
                    <SelectItem key={code} value={code}>
                      {STATUT[code].libelle}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {(q !== "" || statut !== "tous") && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setRecherche("");
                  setStatut("tous");
                  setPage(0);
                }}
              >
                Effacer les filtres
              </Button>
            )}
            {/* Présent en permanence, même vide : une région live ajoutée
                après coup n'est pas annoncée de façon fiable. Sans filtre,
                elle ne répète pas le « 59 CV déposés » d'au-dessus. */}
            <p className="text-sm text-muted-foreground" role="status">
              {filtres.length === cvs.length
                ? ""
                : `${filtres.length} CV sur ${cvs.length} après filtrage`}
            </p>
          </div>

          {filtres.length === 0 ? (
            <EmptyState
              icon={<Search />}
              title="Aucun CV ne correspond"
              description="Aucun fichier déposé ne porte ce nom avec ce statut. Effacez les filtres pour revoir le dépôt complet."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setRecherche("");
                    setStatut("tous");
                    setPage(0);
                  }}
                >
                  Effacer les filtres
                </Button>
              }
            />
          ) : (
            <ScrollX borne sommet={pageSure} label="CV déposés" className="rounded-lg border">
              <ul ref={listeRef} className="flex flex-col divide-y">
                {affiches.map((cv) => {
                  const statut = STATUT[cv.status] ?? { libelle: cv.status, variant: "secondary" };
                  return (
                    <li key={cv.id} className="flex items-center justify-between gap-3 px-4 py-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm">{cv.original_filename}</p>
                        <p className="text-xs text-muted-foreground">{taille(cv.size_bytes)}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge variant={statut.variant}>{statut.libelle}</Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          data-supprimer=""
                          aria-label={`Supprimer ${cv.original_filename}`}
                          onClick={(e) => {
                            retourRef.current = e.currentTarget;
                            setASupprimer(cv);
                          }}
                        >
                          <Trash2 aria-hidden />
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </ScrollX>
          )}

          <Paginateur
            page={pageSure}
            taille={TAILLE_PAGE}
            total={filtres.length}
            onPage={setPage}
            nom="CV"
          />
        </div>
      )}

      <ConfirmDialog
        open={aRelancer}
        onOpenChange={setARelancer}
        title="Lancer une nouvelle analyse sur cette offre ?"
        description={
          `Une campagne du ${dateLongue(precedente?.created_at)} existe déjà pour cette offre` +
          `${
            precedente?.stats?.candidates
              ? ` (${precedente.stats.candidates} CV noté${precedente.stats.candidates > 1 ? "s" : ""})`
              : ""
          }. ` +
          `Elle est conservée : la nouvelle s'y ajoute, elle ne la remplace pas. ` +
          `${
            analysables > 1
              ? `Les ${analysables} CV analysables seront tous renotés, et refacturés.`
              : "Le CV analysable sera renoté, et refacturé."
          }` +
          (estimation
            ? ` D'après la campagne précédente, comptez${
                estimation.cout !== null ? ` environ ${usd(estimation.cout)}` : ""
              }${estimation.cout !== null && estimation.secondes !== null ? " et" : ""}${
                estimation.secondes !== null ? ` environ ${dureeApprox(estimation.secondes)}` : ""
              }.`
            : "")
        }
        confirmLabel="Relancer l'analyse"
        cancelLabel="Ne pas relancer"
        retourFocus={lancerRef}
        onConfirm={lancer}
      />

      <ConfirmDialog
        open={aSupprimer !== null}
        onOpenChange={(ouvert) => !ouvert && setASupprimer(null)}
        title="Supprimer ce CV ?"
        description="Le fichier est effacé du serveur, pas seulement de cette liste. L'action est définitive."
        preview={aSupprimer?.original_filename}
        confirmLabel="Supprimer"
        cancelLabel="Annuler"
        onConfirm={async () => {
          if (aSupprimer) await supprimer(aSupprimer);
        }}
        onCancel={() => setASupprimer(null)}
        retourFocus={retourRef}
      />
    </div>
  );
}
