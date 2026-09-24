"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { ScrollX } from "@/components/ui/scroll-x";
import type { Role } from "@/lib/api";
import { useEspace } from "@/lib/espace";
import { sectionFor, visibleSections } from "@/lib/navigation";
import { cn } from "@/lib/utils";

/**
 * Onglets de navigation, à partir de `sm`. Sous `sm`, c'est `NavMobile` (un
 * tiroir) qui prend le relais : une barre d'onglets coupée au bord de l'écran
 * ne dit pas ce qu'elle cache.
 *
 * Les sections affichées viennent de `visibleSections`, la même fonction que
 * celle utilisée par les gardes serveur : un onglet masqué correspond
 * toujours à une URL interdite.
 *
 * La barre est cadrée sur l'espace actif : les sections de l'autre métier
 * n'y figurent pas. Ce n'est pas un droit — le rôle décide déjà de ce qui est
 * accessible — c'est un cadrage : huit onglets qui mélangent deux produits ne
 * disent pas dans quoi on travaille.
 */
export function MainNav({ role }: { role: Role | null }) {
  const pathname = usePathname();
  const { espace } = useEspace();
  const active = sectionFor(pathname);
  const actifRef = useRef<HTMLAnchorElement>(null);

  // L'onglet courant peut être hors champ quand la barre déborde : on l'amène
  // dans la vue en poussant le défilement de la piste, PAS avec
  // `scrollIntoView` — celui-ci déplace le « point de départ de la navigation
  // séquentielle » de Chromium, et le premier Tab de la page repartait alors
  // de l'onglet actif, sautant le lien d'évitement et une partie de l'en-tête.
  useEffect(() => {
    // Après peinture : `ScrollX` ne pose `overflow-x-auto` qu'une fois le
    // débordement mesuré, et l'effet d'un enfant s'exécute avant celui du
    // parent. Écrire `scrollLeft` tout de suite ne ferait rien — la piste
    // n'est pas encore une zone défilante.
    const image = requestAnimationFrame(() => {
      const lien = actifRef.current;
      const piste = lien?.closest<HTMLElement>('[data-slot="scroll-x"]');
      if (!lien || !piste || piste.scrollWidth <= piste.clientWidth) return;
      const MARGE = 16;
      const l = lien.getBoundingClientRect();
      const p = piste.getBoundingClientRect();
      if (l.left < p.left) piste.scrollLeft -= p.left - l.left + MARGE;
      else if (l.right > p.right) piste.scrollLeft += l.right - p.right + MARGE;
    });
    return () => cancelAnimationFrame(image);
  }, [pathname]);

  return (
    <ScrollX label="Sections" className="hidden px-2 sm:block sm:px-4">
      <nav aria-label="Sections">
        <ul className="flex min-w-max gap-1 pb-1">
          {visibleSections(role, espace).map((section) => {
            const courant = active?.href === section.href;
            return (
              <li key={section.href}>
                <Link
                  ref={courant ? actifRef : undefined}
                  href={section.href}
                  aria-current={courant ? "page" : undefined}
                  className={cn(
                    "inline-block rounded-md px-3 py-2 text-sm whitespace-nowrap transition-colors",
                    courant
                      ? "bg-secondary font-medium text-secondary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  {section.labelCourt ?? section.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </ScrollX>
  );
}
