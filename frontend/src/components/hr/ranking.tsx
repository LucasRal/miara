"use client";

import { ChevronDown, RotateCcw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScoreRing } from "@/components/ui/score-ring";
import { cn } from "@/lib/utils";
import { RECOMMENDATION_LABEL, recommendation, type RankedCandidate } from "@/lib/hr";

const VARIANTE = {
  convoquer: "default",
  examiner: "secondary",
  hors_profil: "destructive",
} as const;

/**
 * Classement justifié : une carte par CV, dépliable sur ses preuves.
 *
 * Aucune note n'est montrée sans la citation du CV qui la soutient — replier
 * la preuve est permis, la supprimer ne l'est pas (section NE PAS de la
 * carte). Les critères éliminatoires manqués sont signalés en premier, car
 * ils expliquent à eux seuls une note de zéro.
 */
export function Ranking({
  rows,
  onRetry,
}: {
  rows: RankedCandidate[];
  onRetry?: (candidateId: string) => void;
}) {
  const [ouverts, setOuverts] = useState<Set<string>>(new Set());

  function basculer(id: string) {
    setOuverts((prev) => {
      const suivant = new Set(prev);
      if (suivant.has(id)) suivant.delete(id);
      else suivant.add(id);
      return suivant;
    });
  }

  return (
    <ul className="flex flex-col gap-3">
      {rows.map((cv) => {
        const ouvert = ouverts.has(cv.candidate_id);
        const reco = recommendation(cv);
        const rates = cv.must_have_failed ?? [];
        const enEchec = cv.status !== "scored";
        // Le nom accessible doit distinguer N boutons homonymes (WCAG 2.4.6).
        // On reprend EXACTEMENT le texte déjà affiché sur la ligne — aucun
        // renseignement nouveau n'entre dans le DOM.
        const intitule = cv.original_filename ?? `CV n° ${cv.rank ?? "–"}`;
        const idDetail = `detail-${cv.candidate_id}`;
        return (
          <li key={cv.candidate_id}>
            <Card className={cn(enEchec && "border-destructive/40")}>
              <CardContent className="flex flex-col gap-3">
                {/* Sous `sm`, la rangée se replie en trois lignes : rang +
                    note + recommandation, puis le nom du fichier EN ENTIER,
                    puis les actions. En une seule rangée, un nom de CV se
                    réduisait à « C… » sur un écran de 390 px — la carte ne
                    permettait même plus de savoir de quel candidat il
                    s'agissait. Les `order` ne valent que sous `sm` : au-delà,
                    l'ordre du DOM reprend la main. */}
                <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                  <span className="font-heading text-sm text-muted-foreground tabular-nums">
                    #{cv.rank ?? "–"}
                  </span>
                  {enEchec ? (
                    <Badge variant="destructive">Non noté</Badge>
                  ) : (
                    <ScoreRing
                      value={cv.overall ?? 0}
                      label={`Note ${cv.overall ?? 0} sur 100`}
                      size="md"
                    />
                  )}
                  <div className="order-1 w-full min-w-0 sm:order-none sm:w-auto sm:flex-1">
                    <p className="font-medium break-words sm:truncate">
                      {cv.original_filename ?? "CV"}
                    </p>
                    <p className="text-sm break-words text-muted-foreground sm:truncate">
                      {cv.headline ??
                        (enEchec ? (cv.error ?? "Analyse impossible") : "Profil non résumé")}
                      {cv.years_experience != null && ` · ${cv.years_experience} ans d'expérience`}
                    </p>
                  </div>
                  {!enEchec && <Badge variant={VARIANTE[reco]}>{RECOMMENDATION_LABEL[reco]}</Badge>}
                  {enEchec && onRetry && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="order-2 sm:order-none"
                      onClick={() => onRetry(cv.candidate_id)}
                    >
                      <RotateCcw aria-hidden /> Relancer ce CV
                      <span className="sr-only"> : {intitule}</span>
                    </Button>
                  )}
                  {!enEchec && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="order-2 sm:order-none"
                      aria-expanded={ouvert}
                      aria-controls={ouvert ? idDetail : undefined}
                      onClick={() => basculer(cv.candidate_id)}
                    >
                      Détail
                      <span className="sr-only"> de {intitule}</span>
                      <ChevronDown
                        aria-hidden
                        className={cn("transition-transform", ouvert && "rotate-180")}
                      />
                    </Button>
                  )}
                </div>

                {rates.length > 0 && (
                  <p className="text-sm text-destructive">
                    Critère{rates.length > 1 ? "s" : ""} éliminatoire{rates.length > 1 ? "s" : ""}{" "}
                    non tenu{rates.length > 1 ? "s" : ""} : {rates.join(", ")}
                  </p>
                )}

                {ouvert && (
                  <div id={idDetail} className="flex flex-col gap-4 border-t pt-3">
                    <ul className="flex flex-col divide-y">
                      {(cv.criteria ?? []).map((critere) => (
                        <li key={critere.name} className="flex flex-col gap-1 py-2">
                          <div className="flex items-center justify-between gap-3">
                            <span
                              className={cn(
                                "text-sm font-medium",
                                rates.includes(critere.name) && "text-destructive"
                              )}
                            >
                              {critere.name}
                              <span className="ml-2 text-xs font-normal text-muted-foreground">
                                poids {critere.weight}
                              </span>
                            </span>
                            <span className="text-sm tabular-nums">{critere.score_0_5} / 5</span>
                          </div>
                          <p className="text-sm text-muted-foreground italic">{critere.evidence}</p>
                          {critere.missing && (
                            <p className="text-xs text-muted-foreground">
                              Il manque : {critere.missing}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                    <div className="grid gap-4 sm:grid-cols-2">
                      {(cv.strengths ?? []).length > 0 && (
                        <div>
                          <p className="text-sm font-medium">Forces</p>
                          <ul className="list-disc pl-5 text-sm text-muted-foreground">
                            {cv.strengths?.map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(cv.concerns ?? []).length > 0 && (
                        <div>
                          <p className="text-sm font-medium">Réserves</p>
                          <ul className="list-disc pl-5 text-sm text-muted-foreground">
                            {cv.concerns?.map((s) => (
                              <li key={s}>{s}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    {cv.skills.length > 0 && (
                      <p className="text-xs text-muted-foreground">
                        Compétences relevées : {cv.skills.join(", ")}
                      </p>
                    )}
                    {cv.confidence != null && (
                      <p className="text-xs text-muted-foreground">
                        Confiance du modèle : {Math.round(cv.confidence * 100)} %
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
