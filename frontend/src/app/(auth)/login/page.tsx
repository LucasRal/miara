import { LoginForm } from "@/components/auth/login-form";

export const metadata = { title: "Connexion · Miara" };

/**
 * Page serveur, formulaire client.
 *
 * Le formulaire a besoin d'état (saisie, erreur, focus) ; `metadata` n'existe
 * que dans un composant serveur. Poser un `<title>` à la main dans le rendu ne
 * suffisait pas : celui de `metadata` racine l'emportait, et les deux pages
 * s'appelaient encore « Miara ».
 */
export default function Page() {
  return <LoginForm />;
}
