/**
 * Écrans publics (connexion, inscription) : pas d'en-tête applicatif, pas
 * d'appel réseau au rendu. La garde de navigation (src/proxy.ts) renvoie déjà
 * ici quand le cookie de session manque.
 */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  // <main> plutôt qu'un <div> : Lighthouse exige un point de repère principal
  // par page, et c'est ce qui permet le saut direct au contenu au clavier.
  return <main className="flex flex-1 flex-col bg-muted/40">{children}</main>;
}
