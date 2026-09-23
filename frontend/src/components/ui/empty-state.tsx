import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * État vide standard. Chaque écran de la carte FRONT socle doit en avoir un :
 * un titre, une explication, et l'action qui sort de l'état vide.
 *
 * `titreBalise` : un état vide à l'intérieur d'une page garde un `<p>` (la
 * page a déjà son `h1`) ; un état vide QUI EST la page — 404, erreur — porte
 * le `h1`, sinon la page n'a aucun titre (axe `page-has-heading-one`).
 */
export function EmptyState({
  icon,
  title,
  titreBalise: Titre = "p",
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  titreBalise?: "p" | "h1" | "h2";
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center",
        className
      )}
    >
      {icon && <span className="text-muted-foreground [&_svg]:size-8">{icon}</span>}
      <Titre className="font-heading text-base font-medium">{title}</Titre>
      {description && <p className="max-w-prose text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}
