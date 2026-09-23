"use client";

import { Clock, ExternalLink, FileCheck2, Timer, Zap } from "lucide-react";
import Link from "next/link";

import { heure, libelleActivite, type ActivityEvent } from "@/lib/dashboard";

const ICONE: Record<string, typeof Clock> = {
  hr_run: FileCheck2,
  crm_write: Zap,
  coaching: Timer,
};

/**
 * Liste d'événements d'activité, partagée par l'aperçu du tableau de bord et
 * par la vue complète.
 *
 * Deux écrans qui montrent la même chose doivent la montrer pareil : le
 * libellé, l'icône et le lien vers Salesforce sont écrits une fois.
 */
export function ActivityList({
  events,
  instanceUrl,
}: {
  events: ActivityEvent[];
  instanceUrl: string | null;
}) {
  return (
    <ul className="flex flex-col divide-y rounded-lg border">
      {events.map((e, i) => {
        const Icone = ICONE[e.kind] ?? Clock;
        const lisible = libelleActivite(e);
        return (
          <li key={`${e.kind}-${e.at}-${i}`} className="flex items-center gap-2 pr-4">
            <Link
              href={e.href}
              className="flex min-w-0 flex-1 items-center gap-3 px-4 py-2 hover:bg-muted/50"
            >
              <Icone className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm">{lisible.titre}</span>
                {lisible.detail && (
                  <span className="block truncate text-xs text-muted-foreground">
                    {lisible.detail}
                  </span>
                )}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">{heure(e.at)}</span>
            </Link>
            {/* Lien vers la fiche Salesforce : hors du lien d'activité, deux
                destinations ne tiennent pas dans un seul lien. */}
            {lisible.recordId && instanceUrl && (
              <a
                href={`${instanceUrl}/lightning/r/${lisible.recordId}/view`}
                target="_blank"
                rel="noreferrer"
                className="shrink-0 text-xs text-primary underline-offset-4 hover:underline"
              >
                Voir dans Salesforce
                <span className="sr-only">
                  {" "}
                  : {lisible.titre.toLowerCase()}, enregistrement {lisible.recordId}
                </span>
                <ExternalLink className="ml-1 inline size-3" aria-hidden />
              </a>
            )}
          </li>
        );
      })}
    </ul>
  );
}
