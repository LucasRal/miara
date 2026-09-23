"use client";

import { ListChecks, PencilLine, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { JobSteps } from "@/components/hr/job-steps";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteFormulaire } from "@/components/ui/skeletons";
import { ErrorState, NotFoundState } from "@/components/ui/states";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, estIntrouvable } from "@/lib/api";
import { MAX_CRITERIA, MIN_CRITERIA, statutOffre, type Criterion, type Job } from "@/lib/hr";
import { notifierErreur, notifierSucces } from "@/lib/notifications";

const CRITERE_VIDE: Criterion = { name: "", weight_1_5: 3, description: "", must_have: false };

function dateLongue(iso: string | null | undefined): string {
  if (!iso) return "date inconnue";
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

/**
 * Grille de critères : proposée par le modèle, décidée par le recruteur.
 *
 * Rien n'est analysé tant que « Valider la grille » n'a pas été cliqué
 * (ADR-007) : c'est la validation humaine qui fait du protocole d'évaluation
 * un choix du recruteur, pas du modèle. L'écran l'affiche explicitement.
 */
export function CriteriaGrid({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [lignes, setLignes] = useState<Criterion[]>([]);
  // `absente` : l'offre n'existe pas — rien à réessayer. `erreur` : panne
  // passagère, où « Réessayer » a un sens.
  const [absente, setAbsente] = useState(false);
  const [erreur, setErreur] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState(false);
  const [validation, setValidation] = useState(false);
  const [aProposer, setAProposer] = useState(false);
  // Référence = la grille telle qu'elle a été chargée. Tout écart est une
  // modification non validée, donc quelque chose à perdre en quittant.
  const [reference, setReference] = useState<string>("[]");
  const proposerRef = useRef<HTMLButtonElement>(null);

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      const data = await api.get<Job>(`/hr/jobs/${jobId}`);
      setJob(data);
      setLignes(data.criteria ?? []);
      setReference(JSON.stringify(data.criteria ?? []));
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

  /**
   * « Proposer à nouveau » remplace la grille entière par celle du modèle.
   * Tant que rien n'est saisi il n'y a rien à perdre ; dès qu'un critère est
   * renseigné, un clic effacerait le travail du recruteur — on confirme.
   */
  function demanderProposition() {
    if (lignes.some((c) => c.name.trim() || c.description.trim())) setAProposer(true);
    else void proposer();
  }

  async function proposer() {
    setAProposer(false);
    setSuggestion(true);
    try {
      const data = await api.post<{ criteria: Criterion[]; prompt_version: number }>(
        `/hr/jobs/${jobId}/criteria/suggest`
      );
      setLignes(data.criteria);
      notifierSucces("Grille proposée. À vous de l'ajuster.");
    } catch {
      notifierErreur("La proposition de grille a échoué.");
    } finally {
      setSuggestion(false);
    }
  }

  // Une grille modifiée mais non validée n'existe que dans cet onglet : rien
  // n'est enregistré avant « Valider la grille » (ADR-007). Fermer ou recharger
  // la page la perd — le navigateur demande confirmation.
  const modifiee = JSON.stringify(lignes) !== reference;
  useEffect(() => {
    if (!modifiee) return;
    const garde = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", garde);
    return () => window.removeEventListener("beforeunload", garde);
  }, [modifiee]);

  function modifier(index: number, champ: Partial<Criterion>) {
    setLignes((prev) => prev.map((c, i) => (i === index ? { ...c, ...champ } : c)));
  }

  async function valider() {
    setValidation(true);
    try {
      await api.put<Job>(`/hr/jobs/${jobId}/criteria`, { criteria: lignes });
      // Avant de naviguer : sinon `beforeunload` se déclencherait sur la
      // grille que l'on vient justement d'enregistrer.
      setReference(JSON.stringify(lignes));
      notifierSucces("Grille validée. L'analyse est désormais possible.");
      router.push(`/hr/${jobId}/candidates`);
    } catch (err) {
      notifierErreur(
        err instanceof ApiError && err.status === 422
          ? "Grille refusée : intitulés en double, ou poids hors de 1 à 5."
          : "Validation impossible. Réessayez."
      );
      setValidation(false);
    }
  }

  if (absente)
    return (
      <NotFoundState
        titre="Cette offre n'existe plus"
        description="Elle a été supprimée, ou elle appartient à une autre organisation. Le lien que vous avez suivi est périmé."
        retour={{ href: "/hr", label: "Voir les offres" }}
      />
    );
  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (job === null) return <SqueletteFormulaire champs={5} label="Chargement de l'offre…" />;

  const complet = lignes.every((c) => c.name.trim().length >= 2 && c.description.trim().length > 0);
  const taille = lignes.length >= MIN_CRITERIA && lignes.length <= MAX_CRITERIA;
  const vide = lignes.length === 0;
  const statut = statutOffre(job.status);
  // Une grille validée qui a déjà servi à noter : la rééditer ne casse rien
  // techniquement, mais rend le classement existant non comparable. On ne
  // verrouille pas (le recruteur doit pouvoir corriger) — on le dit.
  const campagne = job.status === "ready" ? job.last_run : null;

  return (
    <div className="flex flex-col gap-6">
      <JobSteps jobId={jobId} current="criteria" runId={job.last_run?.run_id} title={job.title} />

      {campagne && (
        <Alert variant="destructive">
          <AlertTitle>Cette grille a déjà servi à noter des CV</AlertTitle>
          <AlertDescription>
            <p>
              La campagne du {dateLongue(campagne.created_at)} a été notée avec la grille
              ci-dessous. La modifier et la revalider change le protocole d&apos;évaluation :{" "}
              <strong>le classement existant ne sera plus comparable</strong> aux suivants, et les
              CV déjà notés ne seront pas renotés automatiquement.
            </p>
            <p>Vous pouvez corriger la grille — relancez ensuite l&apos;analyse pour comparer.</p>
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Entre {MIN_CRITERIA} et {MAX_CRITERIA} critères. Les critères éliminatoires ramènent la
          note à zéro s&apos;ils ne sont pas tenus.
        </p>
        <div className="flex items-center gap-2">
          <Badge variant={statut.variant}>{statut.libelle}</Badge>
          {/* Caché sur une grille vide : l'état vide porte alors l'action, en
              primaire. Deux boutons « Proposer » à l'écran diraient deux fois
              la même chose, dont une en secondaire. */}
          {!vide && (
            <Button
              ref={proposerRef}
              variant="outline"
              size="sm"
              onClick={demanderProposition}
              disabled={suggestion}
            >
              <Sparkles aria-hidden />
              {suggestion ? "Proposition…" : "Proposer à nouveau"}
            </Button>
          )}
        </div>
      </div>

      {vide ? (
        <EmptyState
          icon={<ListChecks />}
          title="Aucun critère pour l'instant"
          description={`La grille est le protocole d'évaluation : chaque CV y est confronté à l'identique. Faites-la proposer à partir du texte de l'offre, puis ajustez-la — rien n'est analysé tant que vous ne l'avez pas validée.`}
          action={
            <div className="flex flex-col items-center gap-3 sm:flex-row">
              <Button ref={proposerRef} onClick={() => void proposer()} disabled={suggestion}>
                <Sparkles aria-hidden />
                {suggestion ? "Proposition en cours…" : "Proposer une grille à partir de l'offre"}
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  setLignes(Array.from({ length: MIN_CRITERIA }, () => ({ ...CRITERE_VIDE })))
                }
              >
                <PencilLine aria-hidden />
                Rédiger moi-même
              </Button>
            </div>
          }
        />
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {lignes.map((critere, index) => (
              <li key={index}>
                <Card>
                  <CardContent className="grid gap-3 md:grid-cols-[1fr_auto]">
                    <div className="grid min-w-0 gap-2">
                      <Label htmlFor={`nom-${index}`} className="sr-only">
                        Intitulé du critère {index + 1}
                      </Label>
                      <Input
                        id={`nom-${index}`}
                        value={critere.name}
                        maxLength={80}
                        placeholder="Intitulé du critère"
                        onChange={(e) => modifier(index, { name: e.target.value })}
                      />
                      <Textarea
                        aria-label={`Attendu pour le critère ${index + 1}`}
                        rows={2}
                        value={critere.description}
                        placeholder="Ce qui est attendu dans un CV pour satisfaire ce critère"
                        onChange={(e) => modifier(index, { description: e.target.value })}
                      />
                    </div>
                    <div className="flex flex-row items-start gap-4 md:flex-col md:items-end">
                      <div className="grid gap-1">
                        <Label htmlFor={`poids-${index}`} className="text-xs">
                          Poids
                        </Label>
                        <Select
                          value={String(critere.weight_1_5)}
                          onValueChange={(v) => modifier(index, { weight_1_5: Number(v) })}
                        >
                          <SelectTrigger id={`poids-${index}`} className="w-20">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {[1, 2, 3, 4, 5].map((p) => (
                              <SelectItem key={p} value={String(p)}>
                                {p}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex items-center gap-2 pt-5">
                        <Checkbox
                          id={`must-${index}`}
                          checked={critere.must_have}
                          onCheckedChange={(v) => modifier(index, { must_have: v === true })}
                        />
                        <Label htmlFor={`must-${index}`} className="text-xs">
                          Éliminatoire
                        </Label>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={`Supprimer le critère ${index + 1}`}
                        disabled={lignes.length <= MIN_CRITERIA}
                        onClick={() => setLignes((prev) => prev.filter((_, i) => i !== index))}
                      >
                        <Trash2 aria-hidden />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={lignes.length >= MAX_CRITERIA}
              onClick={() => setLignes((prev) => [...prev, { ...CRITERE_VIDE }])}
            >
              Ajouter un critère
            </Button>
            <div className="flex items-center gap-3">
              {!taille && (
                <p className="text-xs text-muted-foreground">
                  {lignes.length} critère{lignes.length > 1 ? "s" : ""} : il en faut {MIN_CRITERIA}{" "}
                  à {MAX_CRITERIA}.
                </p>
              )}
              <Button onClick={() => void valider()} disabled={validation || !taille || !complet}>
                {validation
                  ? "Validation…"
                  : campagne
                    ? "Revalider la grille"
                    : "Valider la grille"}
              </Button>
            </div>
          </div>
        </>
      )}

      <ConfirmDialog
        open={aProposer}
        onOpenChange={setAProposer}
        title="Remplacer la grille par une nouvelle proposition ?"
        description={`Les ${lignes.length} critères actuels seront effacés et remplacés par ceux que le modèle propose à partir du texte de l'offre. Vos formulations, poids et critères éliminatoires seront perdus.`}
        confirmLabel="Remplacer"
        cancelLabel="Conserver ma grille"
        retourFocus={proposerRef}
        onConfirm={proposer}
      />
    </div>
  );
}
