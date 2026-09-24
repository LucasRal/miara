"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useEspace } from "@/lib/espace";
import { libelleEspace } from "@/lib/navigation";

/** Valeur envoyée à l'API : l'espace actif, ou rien quand on regarde tout. */
export const TOUT = "tout";

/**
 * Périmètre d'un écran transverse : l'espace actif, ou toute l'organisation.
 *
 * Activité, file de traitement et usage restent des écrans uniques — les
 * dupliquer par métier ferait deux journaux à tenir. Ils se cadrent donc sur
 * l'espace actif, et ce contrôle permet d'en sortir explicitement : dans
 * l'espace RH, on voit les présélections, et l'encadrement peut demander à
 * tout voir d'un geste.
 *
 * Il ne s'affiche que pour qui a deux espaces : un membre RH n'a rien à
 * débrayer, et son écran n'affiche alors aucun filtre à comprendre.
 */
export function FiltreEspace({
  valeur,
  onChange,
}: {
  valeur: string;
  onChange: (valeur: string) => void;
}) {
  const { espace, ouverts } = useEspace();
  if (ouverts.length <= 1 || !espace) return null;

  return (
    <Select value={valeur} onValueChange={onChange}>
      <SelectTrigger className="w-52" aria-label="Périmètre affiché">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={espace}>{libelleEspace(espace)}</SelectItem>
        <SelectItem value={TOUT}>Toute l&apos;organisation</SelectItem>
      </SelectContent>
    </Select>
  );
}
