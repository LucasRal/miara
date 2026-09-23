import { Introuvable } from "@/components/layout/introuvable";

export const metadata = { title: "Page introuvable · Miara" };

/**
 * Ressource absente À L'INTÉRIEUR de l'application : un `notFound()` levé par
 * une page du groupe. La coquille — en-tête, onglets, menu compte — reste en
 * place, seul le contenu est remplacé.
 */
export default function NotFoundApp() {
  return (
    <div className="flex flex-1 items-center justify-center p-6">
      <Introuvable dansApplication />
    </div>
  );
}
