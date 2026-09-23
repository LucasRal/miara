"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Zone de données défilante, utilisable au clavier et qui dit qu'elle défile.
 *
 * Deux défauts d'accessibilité réglés ici une fois pour toutes :
 *  - axe `scrollable-region-focusable` : une zone qui déborde doit être
 *    atteignable au clavier. On n'ajoute `tabIndex` QUE quand elle déborde
 *    réellement, sinon chaque tableau tenant dans sa page coûterait un arrêt
 *    de tabulation pour rien.
 *  - rien ne signalait le débordement : une ombre de bord apparaît de chaque
 *    côté où il reste du contenu.
 *
 * `overflow-x-auto` n'est posé, lui, QUE quand la zone déborde horizontalement :
 * en CSS, `overflow-x: auto` force `overflow-y: auto`, ce qui fait de la zone
 * un conteneur de défilement — et sans hauteur bornée, un `thead` collant se
 * collerait au haut de ce conteneur, qui sort lui-même de l'écran.
 *
 * `borne` répond précisément à ce problème : la zone reçoit une hauteur
 * maximale (jeton `--zone-donnees`) et défile DANS son cadre à partir de `sm`.
 * L'en-tête collant redevient utile — il se colle au haut d'un cadre qui, lui,
 * ne bouge pas — et ce qui suit le tableau, sa pagination en premier, reste à
 * l'écran au lieu d'être repoussé de mille pixels vers le bas. Sous `sm`, pas
 * de cadre borné : deux défilements imbriqués sur un téléphone sont un piège
 * au pouce.
 */
export function ScrollX({
  label,
  borne = false,
  entete = false,
  sommet,
  className,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  /** Nom de la zone, annoncé quand elle devient atteignable au clavier. */
  label: string;
  /** Borner la hauteur et défiler dans le cadre à partir de `sm`. */
  borne?: boolean;
  /** Le contenu a une première ligne collante (`thead`) : l'ombre haute passe dessous. */
  entete?: boolean;
  /**
   * Valeur qui, en changeant, ramène la zone en haut — numéro de page, filtre.
   * Sans cela, on change de page et on retombe au milieu de la nouvelle : la
   * première ligne, celle qu'on venait chercher, est hors du cadre.
   */
  sommet?: unknown;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [bords, setBords] = useState({
    deborde: false,
    gauche: false,
    droite: false,
    haut: false,
    bas: false,
  });

  const mesurer = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Mesure valable même sans `overflow-x-auto` : `scrollWidth` rend
    // l'étendue du contenu, débordant ou non.
    const large = el.scrollWidth > el.clientWidth + 1;
    const haut = el.scrollHeight > el.clientHeight + 1;
    setBords({
      deborde: large || haut,
      gauche: large && el.scrollLeft > 1,
      droite: large && el.scrollLeft + el.clientWidth < el.scrollWidth - 1,
      haut: haut && el.scrollTop > 1,
      bas: haut && el.scrollTop + el.clientHeight < el.scrollHeight - 1,
    });
  }, []);

  useEffect(() => {
    if (sommet === undefined) return;
    ref.current?.scrollTo({ top: 0 });
  }, [sommet]);

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
        className={cn(
          "w-full",
          bords.gauche || bords.droite ? "overflow-x-auto" : undefined,
          // `overscroll-contain` : arrivé en bas du cadre, la molette ne
          // repart pas dans la page — on lit un tableau, on ne quitte pas
          // l'écran par accident.
          borne && "sm:max-h-(--zone-donnees) sm:overflow-y-auto sm:overscroll-contain",
          className
        )}
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
      {/* L'ombre haute part sous l'en-tête collant quand il y en a un : elle
          dit « il y a des lignes au-dessus », elle ne doit pas voiler les
          intitulés. Sur une liste sans en-tête, elle part du bord. */}
      {bords.haut && (
        <span
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-x-0 h-4 bg-gradient-to-b from-background to-transparent",
            entete ? "top-10" : "top-0"
          )}
        />
      )}
      {bords.bas && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 bottom-0 h-4 bg-gradient-to-t from-background to-transparent"
        />
      )}
    </div>
  );
}
