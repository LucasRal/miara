"use client";

import { ChevronDown, LogOut, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { OrgSwitcher } from "@/components/auth/org-switcher";
import { EspaceSwitcher } from "@/components/layout/espace-switcher";
import { MainNav } from "@/components/layout/main-nav";
import { NavMobile } from "@/components/layout/nav-mobile";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { api, type Me } from "@/lib/api";
import { libelleRole } from "@/lib/roles";

/**
 * En-tête applicatif : marque, organisation active, menu compte, onglets.
 *
 * `me` est rendu côté serveur puis repris ici comme état initial : changer
 * d'organisation réémet les cookies ET met à jour les onglets visibles sans
 * rechargement, car le rôle change avec l'organisation.
 *
 * Deux navigations pour une seule source (`visibleSections`) : les onglets à
 * partir de `sm`, un tiroir sous `sm`. Les deux sont cadrées sur l'espace de
 * travail actif, que le sélecteur voisin permet de changer.
 *
 * Le rôle et le nom, autrefois en `hidden sm:inline`, vivent maintenant dans
 * le menu compte — donc visibles partout.
 */
export function AppHeader({ me: initial }: { me: Me }) {
  const router = useRouter();
  const [me, setMe] = useState(initial);

  async function seDeconnecter() {
    await api.post("/auth/logout");
    router.push("/login");
    router.refresh();
  }

  const organisation = me.memberships.find((m) => m.organization_id === me.org_id);

  return (
    <header className="sticky top-0 z-10 border-b bg-background">
      <div className="flex items-center justify-between gap-2 px-4 py-2 sm:px-6">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <NavMobile role={me.role}>
            <Button variant="ghost" size="sm" className="sm:hidden" aria-label="Ouvrir le menu">
              <Menu aria-hidden />
            </Button>
          </NavMobile>
          <span className="font-heading text-lg font-semibold text-primary">Miara</span>
          <OrgSwitcher
            me={me}
            onSwitched={(updated) => {
              setMe(updated);
              router.refresh();
            }}
          />
          {/* L'espace de travail se lit juste après l'organisation : « chez
              qui » puis « dans quel métier ». Sous `sm`, il vit dans le
              tiroir, où la place ne manque pas. */}
          <EspaceSwitcher className="hidden w-52 sm:flex" />
          {me.role && (
            <Badge variant="secondary" className="hidden lg:inline-flex">
              {libelleRole(me.role)}
            </Badge>
          )}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="max-w-44">
              <span className="truncate">{me.full_name}</span>
              <ChevronDown aria-hidden />
              <span className="sr-only">Ouvrir le menu du compte</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-64">
            <DropdownMenuLabel className="flex flex-col gap-0.5">
              <span className="truncate">{me.full_name}</span>
              <span className="truncate text-xs font-normal text-muted-foreground">{me.email}</span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {/* Rôle et organisation : consultables partout, y compris sur
                téléphone où le badge de l'en-tête ne tient pas. */}
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              {libelleRole(me.role)}
              {organisation && ` · ${organisation.organization_name}`}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => void seDeconnecter()}>
              <LogOut aria-hidden />
              Se déconnecter
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <MainNav role={me.role} />
    </header>
  );
}
