import { AppHeader } from "@/components/layout/app-header";
import { Introuvable } from "@/components/layout/introuvable";
import { getMe } from "@/lib/server-api";

export const metadata = { title: "Page introuvable · Miara" };

/**
 * URL inconnue : la frontière que Next atteint quand aucun segment ne
 * correspond — y compris pour une URL sous l'application, car la résolution
 * échoue avant d'entrer dans le groupe `(app)` et sa coquille.
 *
 * Next rendait ici sa page par défaut : « 404 | This page could not be
 * found. », en anglais, sans en-tête ni lien de retour — le seul écran de
 * l'application à sortir de l'application. D'où la lecture de session : quand
 * elle existe, on remonte l'en-tête et les onglets nous-mêmes.
 *
 * `(app)/not-found.tsx` sert, lui, les `notFound()` levés par une page du
 * groupe (une offre supprimée, par exemple) : la coquille est déjà là.
 */
export default async function NotFound() {
  const me = await getMe();

  if (!me?.org_id) {
    return (
      <main className="flex flex-1 items-center justify-center p-6">
        <Introuvable />
      </main>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <AppHeader me={me} />
      <main className="flex flex-1 items-center justify-center p-4 sm:p-6">
        <Introuvable dansApplication />
      </main>
    </div>
  );
}
