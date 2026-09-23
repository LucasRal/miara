import { toast } from "sonner";

/**
 * Notifications éphémères : une durée par nature de message.
 *
 * Un toast d'erreur qui disparaît au bout de quatre secondes est, pour qui lit
 * à l'écran ou navigue au clavier, une erreur qui n'a jamais existé
 * (WCAG 2.2.1 : délai ajustable). Les erreurs restent donc jusqu'à fermeture
 * explicite ; succès et informations gardent une durée, allongée à 6 s.
 *
 * L'annonce assertive ne passe PAS par ici : cette version de sonner n'expose
 * aucune option par toast pour changer la région live, qui reste `polite`
 * (remplacer sonner est exclu par la carte). C'est la page qui porte
 * l'urgence — une erreur concernant une zone y affiche son `ErrorState`, bâti
 * sur `Alert` et donc `role="alert"`. Le toast n'est qu'un rappel pour
 * l'attention qui était ailleurs.
 */
export function notifierErreur(message: string) {
  return toast.error(message, { duration: Infinity });
}

/** Succès : se ferme seul, mais laisse le temps de lire. */
export function notifierSucces(message: string) {
  return toast.success(message);
}
