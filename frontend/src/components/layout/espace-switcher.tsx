"use client";

import { Briefcase, Users } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useEspace } from "@/lib/espace";
import { ESPACES, libelleEspace, type Espace } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const ICONE: Record<Espace, typeof Users> = { rh: Users, commercial: Briefcase };

/**
 * Sélecteur d'espace de travail.
 *
 * Il n'apparaît que pour qui a réellement les deux métiers — l'encadrement.
 * Un membre RH ou commercial est épinglé sur son espace : lui montrer un
 * sélecteur à une seule entrée lui dirait qu'il existe un ailleurs auquel il
 * n'a pas droit, et ajouterait un arrêt de tabulation pour rien.
 *
 * Ce contrôle ne donne aucun droit : il choisit parmi les espaces déjà
 * ouverts au rôle, et le serveur revérifie chaque segment (`guardSection`).
 */
export function EspaceSwitcher({ className }: { className?: string }) {
  const { espace, ouverts, changer } = useEspace();
  if (ouverts.length <= 1 || !espace) return null;

  return (
    <Select value={espace} onValueChange={(v) => changer(v as Espace)}>
      <SelectTrigger size="sm" className={cn("w-48", className)} aria-label="Espace de travail">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ESPACES.filter((e) => ouverts.includes(e.id)).map((e) => {
          const Icone = ICONE[e.id];
          return (
            <SelectItem key={e.id} value={e.id}>
              <Icone aria-hidden />
              {libelleEspace(e.id)}
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}
