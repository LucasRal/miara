"use client";

import { Check, ChevronsUpDown, X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface Compte {
  id: string;
  name: string;
  industry: string | null;
}

/**
 * Choix d'un compte Salesforce PAR SON NOM.
 *
 * L'écran demandait un identifiant de 18 caractères (`001bm000...`) tapé à la
 * main. Personne ne les connaît par cœur ; l'identifiant reste donc interne à
 * la requête, et seul le nom est montré et saisi.
 *
 * La recherche est une lecture plate côté backend (`GET /sales/accounts`) :
 * la sélection reste un geste de l'utilisateur, jamais une résolution confiée
 * au modèle.
 */
export function AccountPicker({
  valeur,
  onChange,
  labelId,
  describedBy,
}: {
  valeur: Compte | null;
  onChange: (compte: Compte | null) => void;
  labelId?: string;
  describedBy?: string;
}) {
  const [ouvert, setOuvert] = useState(false);
  const [terme, setTerme] = useState("");
  // Le résultat porte le terme qui l'a produit : c'est ce qui dit s'il est à
  // jour. Une réponse lente ne peut donc pas se faire passer pour la réponse
  // à la frappe en cours, et il n'y a pas d'état « chargement » à tenir
  // séparément de la donnée qu'il attend.
  const [dernier, setDernier] = useState<{ terme: string; comptes: Compte[] }>({
    terme: "",
    comptes: [],
  });
  const listeId = useId();

  const q = terme.trim();
  const assezLong = q.length >= 2;
  const aJour = dernier.terme === q;
  const resultats = aJour ? dernier.comptes : [];

  useEffect(() => {
    const cherche = terme.trim();
    if (cherche.length < 2) return;
    // Une requête par pause de frappe, pas par caractère : la recherche part
    // vers le CRM, dont chaque appel coûte un aller-retour réseau.
    const minuteur = setTimeout(() => {
      void api
        .get<Compte[]>(`/sales/accounts?q=${encodeURIComponent(cherche)}`)
        .then((r) => setDernier({ terme: cherche, comptes: r }))
        .catch(() => setDernier({ terme: cherche, comptes: [] }));
    }, 250);
    return () => clearTimeout(minuteur);
  }, [terme]);

  return (
    <div className="flex items-center gap-1">
      <Popover open={ouvert} onOpenChange={setOuvert}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={ouvert}
            aria-labelledby={labelId}
            aria-describedby={describedBy}
            aria-controls={ouvert ? listeId : undefined}
            className="min-w-0 flex-1 justify-between font-normal"
          >
            <span className={cn("truncate", !valeur && "text-muted-foreground")}>
              {valeur ? valeur.name : "Rechercher un compte…"}
            </span>
            <ChevronsUpDown className="opacity-50" aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-(--radix-popover-trigger-width) p-0" align="start">
          {/* `shouldFilter={false}` : c'est le CRM qui filtre, pas la liste.
              Filtrer une seconde fois côté navigateur masquerait des comptes
              que le serveur a jugés pertinents. */}
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Nom du compte…"
              value={terme}
              onValueChange={setTerme}
              aria-label="Nom du compte à rechercher"
            />
            <CommandList id={listeId}>
              <CommandEmpty>
                {!assezLong
                  ? "Saisissez au moins deux caractères."
                  : !aJour
                    ? "Recherche…"
                    : "Aucun compte de votre organisation ne porte ce nom."}
              </CommandEmpty>
              <CommandGroup>
                {resultats.map((c) => (
                  <CommandItem
                    key={c.id}
                    value={c.id}
                    onSelect={() => {
                      onChange(c);
                      setOuvert(false);
                    }}
                  >
                    <Check
                      className={cn("opacity-0", valeur?.id === c.id && "opacity-100")}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span className="block truncate">{c.name}</span>
                      {c.industry && (
                        <span className="block truncate text-xs text-muted-foreground">
                          {c.industry}
                        </span>
                      )}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {valeur && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-9 shrink-0"
          onClick={() => onChange(null)}
        >
          <X aria-hidden />
          <span className="sr-only">Retirer le compte {valeur.name}</span>
        </Button>
      )}
    </div>
  );
}
