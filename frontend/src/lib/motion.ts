/**
 * Préférence système « mouvement réduit ».
 *
 * `globals.css` neutralise déjà animations et transitions CSS sous
 * `prefers-reduced-motion: reduce`. Mais un défilement demandé en JavaScript
 * (`scrollTo({ behavior: "smooth" })`) ignore `scroll-behavior` : l'option
 * passée à l'appel l'emporte. Il faut donc lire la préférence ici aussi.
 */
export function mouvementReduit(): boolean {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** Comportement de défilement à passer à `scrollTo` / `scrollIntoView`. */
export function defilement(): ScrollBehavior {
  return mouvementReduit() ? "auto" : "smooth";
}

/**
 * Amène un bloc à l'écran s'il n'y est pas déjà entièrement.
 *
 * `scrollIntoView({ block: "start" })` le colle au bord haut de la fenêtre,
 * c'est-à-dire SOUS l'en-tête collant, qui le recouvre alors. La hauteur de
 * cet en-tête change avec la largeur de l'écran (une ligne sur mobile, deux
 * au-delà) : elle se mesure, elle ne se devine pas.
 *
 * Ne bouge rien si le DÉBUT du bloc est déjà à l'écran : ce qu'on cherche,
 * c'est que la personne voie que quelque chose est arrivé, pas qu'elle en
 * voie la fin — un bloc plus haut que la fenêtre n'y tiendra jamais, et
 * déplacer la page sous les yeux de quelqu'un qui regarde déjà la bonne chose
 * est une gêne, pas un service. Il faut toutefois qu'il en apparaisse plus
 * qu'un filet : on exige la hauteur de l'en-tête, la seule mesure de la page
 * dont on dispose sans inventer de constante.
 */
export function amenerAVue(bloc: HTMLElement): void {
  const entete = document.querySelector("header")?.getBoundingClientRect().height ?? 0;
  const cadre = bloc.getBoundingClientRect();
  if (cadre.top >= entete && cadre.top <= window.innerHeight - entete) return;
  window.scrollTo({ top: window.scrollY + cadre.top - entete, behavior: defilement() });
}
