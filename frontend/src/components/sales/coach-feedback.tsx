"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreRing } from "@/components/ui/score-ring";
import { cn } from "@/lib/utils";

export const LIBELLES: Record<string, string> = {
  decouverte_des_besoins: "Découverte des besoins",
  gestion_des_objections: "Gestion des objections",
  proposition_de_valeur: "Proposition de valeur",
  prochaine_etape: "Prochaine étape",
  ton_et_concision: "Ton et concision",
};

export interface CriterionScore {
  name: string;
  score_0_5: number;
  evidence: string;
  advice: string;
}

export interface Feedback {
  criteria: CriterionScore[];
  strengths: string[];
  improvements: string[];
  suggested_next_step: string;
  overall_0_100: number;
}

/**
 * Retour du coach : note globale, grille dépliable, forces et axes.
 *
 * Aucune note n'est affichée sans sa preuve : c'est la contrepartie de
 * l'explicabilité promise par la carte. La preuve est repliée par défaut pour
 * garder l'écran lisible, jamais absente.
 */
export function CoachFeedback({ feedback }: { feedback: Feedback }) {
  const [ouverts, setOuverts] = useState<Set<string>>(new Set());

  function basculer(nom: string) {
    setOuverts((prev) => {
      const suivant = new Set(prev);
      if (suivant.has(nom)) suivant.delete(nom);
      else suivant.add(nom);
      return suivant;
    });
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-4">
        <ScoreRing
          value={feedback.overall_0_100}
          size="lg"
          label={`Note globale ${feedback.overall_0_100} sur 100`}
        />
        <div>
          <CardTitle>Retour du coach</CardTitle>
          <p className="text-sm text-muted-foreground">{feedback.suggested_next_step}</p>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex flex-col divide-y">
          {feedback.criteria.map((c) => {
            const ouvert = ouverts.has(c.name);
            const idPreuve = `preuve-${c.name}`;
            return (
              <li key={c.name} className="py-2">
                <button
                  type="button"
                  onClick={() => basculer(c.name)}
                  aria-expanded={ouvert}
                  aria-controls={ouvert ? idPreuve : undefined}
                  className="flex w-full items-center justify-between gap-3 text-left text-sm"
                >
                  <span className="font-medium">{LIBELLES[c.name] ?? c.name}</span>
                  <span className="flex items-center gap-2">
                    <Badge
                      variant={
                        c.score_0_5 >= 4
                          ? "default"
                          : c.score_0_5 >= 2
                            ? "secondary"
                            : "destructive"
                      }
                    >
                      {c.score_0_5}/5
                    </Badge>
                    <ChevronDown
                      className={cn("size-4 transition-transform", ouvert && "rotate-180")}
                      aria-hidden
                    />
                  </span>
                </button>
                {ouvert && (
                  <div
                    id={idPreuve}
                    className="mt-2 flex flex-col gap-2 rounded-md bg-muted/50 p-3 text-sm"
                  >
                    <p>
                      <span className="text-muted-foreground">Preuve : </span>
                      <q>{c.evidence}</q>
                    </p>
                    <p>
                      <span className="text-muted-foreground">Conseil : </span>
                      {c.advice}
                    </p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <p className="mb-1 text-sm font-medium">Forces</p>
            <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
              {feedback.strengths.map((f) => (
                <li key={f}>· {f}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1 text-sm font-medium">Axes de progrès</p>
            <ul className="flex flex-col gap-1 text-sm text-muted-foreground">
              {feedback.improvements.map((a) => (
                <li key={a}>· {a}</li>
              ))}
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
