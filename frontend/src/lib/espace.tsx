"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, use, useCallback, useMemo } from "react";

import type { Role } from "@/lib/api";
import { COOKIE_ESPACE, ESPACES, espaceActif, espacesFor, type Espace } from "@/lib/navigation";

const UN_AN = 60 * 60 * 24 * 365;

interface EtatEspace {
  /** Espace actif, ou `null` si le rôle n'en ouvre aucun. */
  espace: Espace | null;
  /** Espaces ouverts au rôle : deux pour l'encadrement, un pour l'équipe. */
  ouverts: Espace[];
  /** Change d'espace et ouvre son accueil. */
  changer: (espace: Espace) => void;
}

const Contexte = createContext<EtatEspace>({ espace: null, ouverts: [], changer: () => {} });

/**
 * Espace de travail actif, partagé par l'en-tête et les écrans transverses.
 *
 * Le choix est mémorisé dans un cookie plutôt que dans l'URL : les adresses
 * (/hr, /sales, /activity) ne changent pas — les figures du mémoire et le
 * script de démonstration continuent de fonctionner — et le serveur peut lire
 * la préférence au premier rendu, sans scintillement d'un espace à l'autre.
 *
 * L'URL reste prioritaire : arriver sur /sales par un lien, c'est être dans
 * l'espace commercial, quel qu'ait été le dernier choix (`espaceActif`).
 */
export function EspaceProvider({
  role,
  initial,
  children,
}: {
  role: Role | null;
  initial: Espace | null;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const espace = espaceActif(pathname, initial, role);
  const ouverts = useMemo(() => espacesFor(role), [role]);

  const changer = useCallback(
    (cible: Espace) => {
      document.cookie = `${COOKIE_ESPACE}=${cible}; path=/; max-age=${UN_AN}; samesite=lax`;
      // On va à l'accueil de l'espace : changer d'espace sans bouger
      // laisserait l'écran courant sous un en-tête qui annonce autre chose.
      router.push(ESPACES.find((e) => e.id === cible)?.accueil ?? "/");
      router.refresh();
    },
    [router]
  );

  const valeur = useMemo(() => ({ espace, ouverts, changer }), [espace, ouverts, changer]);
  return <Contexte value={valeur}>{children}</Contexte>;
}

export function useEspace(): EtatEspace {
  return use(Contexte);
}
