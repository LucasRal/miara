"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Zone à défilement horizontal, utilisable au clavier et qui dit qu'elle défile.
 *
 * Deux défauts d'accessibilité réglés ici une fois pour toutes :
 *  - axe `scrollable-region-focusable` : une zone qui déborde doit être
 *    atteignable au clavier. On n'ajoute `tabIndex` QUE quand elle déborde
 *    réellement, sinon chaque tableau tenant dans sa page coûterait un arrêt
 *    de tabulation pour rien.
 *  - rien ne signalait le débordement : une ombre de bord apparaît du côté où
 *    il reste du contenu.
 *
 * `overflow-x-auto` n'est posé, lui aussi, QUE quand la zone déborde : en CSS,
 * `overflow-x: auto` force `overflow-y: auto`, ce qui fait de la zone un
 * conteneur de défilement — et un `thead` en `position: sticky` se collerait
 * alors au haut de ce conteneur, qui sort lui-même de l'écran. Sans
 * débordement, pas de conteneur, donc un en-tête qui tient vraiment.
 */
export function ScrollX({
  label,
  className,
  children,
  ...props
}: React.ComponentProps<"div"> & { label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [bords, setBords] = useState({ deborde: false, gauche: false, droite: false });

  const mesurer = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Mesure valable même sans `overflow-x-auto` : `scrollWidth` rend
    // l'étendue du contenu, débordant ou non.
    const deborde = el.scrollWidth > el.clientWidth + 1;
    setBords({
      deborde,
      gauche: deborde && el.scrollLeft > 1,
      droite: deborde && el.scrollLeft + el.clientWidth < el.scrollWidth - 1,
    });
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    mesurer();
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(el);
    for (const enfant of Array.from(el.children)) observateur.observe(enfant);
    return () => observateur.disconnect();
  }, [mesurer]);

  return (
    <div className="relative">
      <div
        ref={ref}
        data-slot="scroll-x"
        onScroll={mesurer}
        // Une zone focusable doit avoir un rôle et un nom ; sans débordement,
        // ni l'un ni l'autre, pour ne pas polluer la navigation clavier.
        {...(bords.deborde ? { tabIndex: 0, role: "region", "aria-label": label } : {})}
        className={cn("w-full", bords.deborde && "overflow-x-auto", className)}
        {...props}
      >
        {children}
      </div>
      {bords.gauche && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-background to-transparent"
        />
      )}
      {bords.droite && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-background to-transparent"
        />
      )}
    </div>
  );
}
