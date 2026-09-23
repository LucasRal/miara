"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { cheminInterne } from "@/lib/session";

/**
 * Reprise de session, côté CLIENT.
 *
 * Le rendu serveur a refusé la session (jeton expiré ou révoqué) et nous a
 * envoyés ici plutôt que vers `/login`, qui rebouclerait tant que le cookie
 * `access` existe. Cette page est le seul endroit qui puisse trancher : c'est
 * le navigateur qui détient le cookie `refresh`, que le backend limite au
 * chemin `/api/v1/auth` et qui ne part donc jamais avec une navigation.
 *
 * Deux issues, jamais trois :
 * - la rotation passe : on repart sur la page demandée, l'utilisateur ne voit
 *   qu'un écran de chargement ;
 * - la rotation échoue : `/auth/logout` efface les deux cookies côté serveur,
 *   et la garde laisse alors `/login` s'afficher.
 *
 * Le garde-fou de récidive borne le tout : si une reprise a déjà été tentée il
 * y a moins de quinze secondes, on ne retente pas, on déconnecte. Sans lui,
 * une session refusée pour une autre raison que l'expiration (organisation
 * révoquée, par exemple) rejouerait la boucle que cette page corrige.
 */

const MARQUE = "miara.reprise";
const DELAI_RECIDIVE_MS = 15000;
const API = "/api/v1";

export default function RepriseSessionPage() {
  const [etat, setEtat] = useState("Reprise de la session…");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const vers = cheminInterne(params.get("vers"));
    const derniere = Number(window.sessionStorage.getItem(MARQUE) ?? 0);
    const recidive = Date.now() - derniere < DELAI_RECIDIVE_MS;

    async function reprendre() {
      if (!recidive) {
        window.sessionStorage.setItem(MARQUE, String(Date.now()));
        const rotation = await fetch(`${API}/auth/refresh`, { method: "POST" }).catch(() => null);
        if (rotation?.ok) {
          window.sessionStorage.removeItem(MARQUE);
          // Navigation complète : le serveur doit relire les cookies réémis.
          window.location.replace(vers);
          return;
        }
      }
      setEtat("Session expirée, retour à la connexion…");
      await fetch(`${API}/auth/logout`, { method: "POST" }).catch(() => null);
      window.sessionStorage.removeItem(MARQUE);
      window.location.replace("/login");
    }

    void reprendre();
  }, []);

  return (
    <div className="flex flex-1 items-center justify-center p-8">
      {/* Écran de transit : rien à esquisser en squelette, la page suivante
          n'est pas encore connue. Le statut change en cours de route, d'où
          `aria-live` plutôt qu'un simple `role="status"` muet. */}
      <p role="status" aria-live="polite" className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        <span className="text-sm">{etat}</span>
      </p>
    </div>
  );
}
