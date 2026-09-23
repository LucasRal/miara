import Link from "next/link";
import { Fragment } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Fil du parcours RH : offre, grille, CV, analyse.
 *
 * Le recruteur voit où il en est et peut revenir en arrière sans perdre son
 * travail. Une étape non atteignable (analyse avant dépôt) n'est pas un lien —
 * mais elle dit pourquoi : une étape grisée sans motif se lit comme un bug.
 */
export type JobStep = "criteria" | "candidates" | "run";

const ETAPES: { key: JobStep; label: string; motif: string }[] = [
  {
    key: "criteria",
    label: "1. Grille de critères",
    motif: "Disponible dès la création de l'offre.",
  },
  {
    key: "candidates",
    label: "2. Dépôt des CV",
    motif: "Disponible dès la création de l'offre.",
  },
  {
    key: "run",
    label: "3. Analyse et classement",
    motif: "Disponible après le dépôt des CV et le lancement d'une analyse.",
  },
];

export function JobSteps({
  jobId,
  current,
  runId,
  title,
}: {
  jobId: string;
  current: JobStep;
  /** Dernière campagne connue : sans elle, l'étape 3 n'est pas atteignable. */
  runId?: string | null;
  title?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {title && <h1 className="font-heading text-xl font-semibold">{title}</h1>}
      <Breadcrumb aria-label="Étapes de l'offre">
        <BreadcrumbList>
          {ETAPES.map((etape, i) => {
            const actif = etape.key === current;
            const href =
              etape.key === "run"
                ? runId
                  ? `/hr/${jobId}/runs/${runId}`
                  : null
                : `/hr/${jobId}/${etape.key}`;
            return (
              <Fragment key={etape.key}>
                <BreadcrumbItem>
                  {actif ? (
                    <BreadcrumbPage>{etape.label}</BreadcrumbPage>
                  ) : href ? (
                    <BreadcrumbLink asChild>
                      <Link href={href}>{etape.label}</Link>
                    </BreadcrumbLink>
                  ) : (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        {/* Focusable : le motif doit être lisible au clavier aussi. */}
                        <span
                          tabIndex={0}
                          aria-disabled
                          aria-describedby={`motif-${etape.key}`}
                          className="cursor-help underline decoration-dotted underline-offset-4"
                        >
                          {etape.label}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent id={`motif-${etape.key}`}>{etape.motif}</TooltipContent>
                    </Tooltip>
                  )}
                </BreadcrumbItem>
                {/* Pas de chevron après la dernière étape. */}
                {i < ETAPES.length - 1 && <BreadcrumbSeparator />}
              </Fragment>
            );
          })}
        </BreadcrumbList>
      </Breadcrumb>
    </div>
  );
}
