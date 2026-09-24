"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { EspaceSwitcher } from "@/components/layout/espace-switcher";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { Role } from "@/lib/api";
import { useEspace } from "@/lib/espace";
import { nomEspace, sectionFor, visibleSections } from "@/lib/navigation";
import { cn } from "@/lib/utils";

/**
 * Navigation sous `sm` : un tiroir, ouvert par le bouton passé en `children`.
 *
 * Une barre d'onglets à défilement horizontal cache la moitié de
 * l'application sans le dire — le défilement latéral d'une liste d'onglets
 * n'est pas un geste découvrable. Ici, toutes les sections ouvertes au rôle
 * tiennent dans une liste verticale, atteignable en un geste.
 *
 * Les sections viennent de `visibleSections`, comme les onglets et comme les
 * gardes serveur : une seule source, pas deux listes à tenir synchronisées.
 */
export function NavMobile({ role, children }: { role: Role | null; children: ReactNode }) {
  const pathname = usePathname();
  const { espace } = useEspace();
  const [ouvert, setOuvert] = useState(false);
  const active = sectionFor(pathname);

  // Naviguer ferme le tiroir : sinon il reste ouvert sur la page d'arrivée.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setOuvert(false), [pathname]);

  return (
    <Sheet open={ouvert} onOpenChange={setOuvert}>
      <SheetTrigger asChild>{children}</SheetTrigger>
      <SheetContent side="left" className="w-72">
        <SheetHeader>
          <SheetTitle>Sections</SheetTitle>
          <SheetDescription>
            Les sections ouvertes à votre rôle dans l&apos;espace {nomEspace(espace)}.
          </SheetDescription>
        </SheetHeader>
        {/* Le sélecteur vit dans le tiroir sous `sm` : la barre d'en-tête y
            porte déjà l'organisation et le menu du compte. */}
        <div className="px-4">
          <EspaceSwitcher className="w-full" />
        </div>
        <nav aria-label="Sections" className="px-4 pb-4">
          <ul className="flex flex-col gap-1">
            {visibleSections(role, espace).map((section) => {
              const courant = active?.href === section.href;
              return (
                <li key={section.href}>
                  <Link
                    href={section.href}
                    aria-current={courant ? "page" : undefined}
                    className={cn(
                      "block rounded-md px-3 py-2 text-sm",
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
      </SheetContent>
    </Sheet>
  );
}
