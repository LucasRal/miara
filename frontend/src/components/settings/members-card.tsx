"use client";

import { UserMinus } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DataTable, type Colonne } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteTableau } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, ApiError, type Member, type Role } from "@/lib/api";
import { notifierErreur, notifierSucces } from "@/lib/notifications";
import { ROLE_AIDE, ROLE_LIBELLE, ROLES } from "@/lib/roles";

/**
 * Membres de l'organisation et leurs rôles (page Paramètres).
 *
 * C'est aussi l'exemple de référence du `DataTable` commun : colonnes typées
 * (`Colonne<Member>`), tri par défaut, rendu en cartes sous `sm` — la colonne
 * Email n'y est pas masquée, elle passe sous le nom.
 *
 * Les rôles ne sont modifiables que par owner/admin, et le backend le revérifie :
 * ici on ne fait que cacher des boutons. Deux gardes de plus, côté interface,
 * parce qu'elles évitent un piège plutôt qu'une faute : on ne modifie pas son
 * propre rôle (se rétrograder ferait perdre l'accès à cette page même), et on
 * ne se retire pas soi-même de l'organisation.
 */
/**
 * Sélecteur de rôle, ou le rôle en clair quand la ligne est verrouillée.
 *
 * Défini HORS de `MembersCard`, comme `BoutonRetrait` : un composant déclaré
 * dans le corps d'un autre change d'identité à chaque rendu, et React démonte
 * puis remonte tout son DOM. Le tableau entier était ainsi reconstruit à
 * chaque frappe dans le formulaire d'ajout, et le bouton mémorisé pour rendre
 * le focus après le dialogue n'existait plus au moment de le lui rendre.
 */
function CelluleRole({
  membre,
  canManage,
  meId,
  onChangerRole,
}: {
  membre: Member;
  canManage: boolean;
  meId: string;
  onChangerRole: (membre: Member, role: Role) => void;
}) {
  if (!canManage) return <span>{ROLE_LIBELLE[membre.role]}</span>;
  if (membre.user_id === meId)
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-4">
            {ROLE_LIBELLE[membre.role]}
          </span>
        </TooltipTrigger>
        <TooltipContent>
          Votre propre rôle ne se modifie pas ici : une autre personne propriétaire ou
          administratrice doit le faire.
        </TooltipContent>
      </Tooltip>
    );
  return (
    <Select value={membre.role} onValueChange={(v) => onChangerRole(membre, v as Role)}>
      <SelectTrigger className="w-44" aria-label={`Rôle de ${membre.full_name}`}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ROLES.map((r) => (
          <SelectItem key={r} value={r}>
            {ROLE_LIBELLE[r]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** Retrait, nommé pour les lecteurs d'écran (WCAG 2.4.6 : N fois « Retirer »). */
function BoutonRetrait({
  membre,
  canManage,
  meId,
  onDemander,
}: {
  membre: Member;
  canManage: boolean;
  meId: string;
  onDemander: (membre: Member, bouton: HTMLElement) => void;
}) {
  if (!canManage || membre.user_id === meId) return null;
  return (
    <Button
      variant="ghost"
      size="sm"
      className="text-destructive"
      onClick={(e) => onDemander(membre, e.currentTarget)}
    >
      <UserMinus aria-hidden />
      Retirer<span className="sr-only"> {membre.full_name} de l&apos;organisation</span>
    </Button>
  );
}

export function MembersCard({
  orgId,
  canManage,
  meId,
}: {
  orgId: string;
  canManage: boolean;
  /** Identifiant de la personne connectée : sa ligne est en lecture seule. */
  meId: string;
}) {
  const [membres, setMembres] = useState<Member[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("sales");
  const [pending, setPending] = useState(false);
  const [aRetirer, setARetirer] = useState<Member | null>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  // Le membre retiré emporte son bouton : repli sur le champ d'ajout.
  const retourRef = useRef<HTMLElement | null>(null);

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      setMembres(await api.get<Member[]>(`/orgs/${orgId}/members`));
    } catch {
      setErreur("Impossible de charger les membres.");
    }
  }, [orgId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  async function inviter(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await api.post(`/orgs/${orgId}/invite`, { email, role });
      setEmail("");
      notifierSucces("Membre ajouté à l'organisation.");
      await charger();
    } catch (err) {
      const message =
        err instanceof ApiError && err.status === 404
          ? "Aucun compte Miara avec cet email : la personne doit d'abord s'inscrire."
          : err instanceof ApiError && err.status === 409
            ? "Cette personne est déjà membre."
            : "Ajout impossible.";
      notifierErreur(message);
    } finally {
      setPending(false);
    }
  }

  async function changerRole(membre: Member, nouveau: Role) {
    try {
      await api.patch(`/orgs/${orgId}/members/${membre.user_id}`, { role: nouveau });
      notifierSucces(`${membre.full_name} est désormais ${ROLE_LIBELLE[nouveau].toLowerCase()}.`);
    } catch (err) {
      notifierErreur(err instanceof ApiError ? err.message : "Changement de rôle impossible.");
    }
    await charger();
  }

  async function retirer(membre: Member) {
    try {
      await api.delete(`/orgs/${orgId}/members/${membre.user_id}`);
      notifierSucces(`${membre.full_name} ne fait plus partie de l'organisation.`);
    } catch (err) {
      notifierErreur(
        err instanceof ApiError && err.status === 409
          ? "Impossible : une organisation garde au moins un propriétaire."
          : "Retrait impossible."
      );
    }
    // Le membre retiré emporte son bouton : repli sur le champ d'ajout.
    retourRef.current = emailRef.current;
    setARetirer(null);
    await charger();
  }

  function demanderRetrait(membre: Member, bouton: HTMLElement) {
    retourRef.current = bouton;
    setARetirer(membre);
  }

  const colonnes: Colonne<Member>[] = [
    {
      id: "nom",
      accessorKey: "full_name",
      header: "Nom",
      sortFn: "text",
      cell: ({ row }) => <span className="font-medium">{row.original.full_name}</span>,
    },
    {
      id: "email",
      accessorKey: "email",
      header: "Email",
      sortFn: "text",
      cell: ({ row }) => <span className="block max-w-56 truncate">{row.original.email}</span>,
    },
    {
      id: "role",
      accessorKey: "role",
      header: "Rôle",
      sortFn: "text",
      cell: ({ row }) => (
        <CelluleRole
          membre={row.original}
          canManage={canManage}
          meId={meId}
          onChangerRole={(m, r) => void changerRole(m, r)}
        />
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      enableSorting: false,
      cell: ({ row }) => (
        <div className="text-right">
          <BoutonRetrait
            membre={row.original}
            canManage={canManage}
            meId={meId}
            onDemander={demanderRetrait}
          />
        </div>
      ),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Membres</CardTitle>
        <CardDescription>
          Un rôle par organisation. Il est relu à chaque requête : un retrait prend effet
          immédiatement.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {erreur && <ErrorState message={erreur} onRetry={() => void charger()} />}
        {!membres && !erreur && (
          <SqueletteTableau lignes={3} colonnes={3} label="Chargement des membres…" />
        )}
        {membres && (
          <DataTable
            colonnes={colonnes}
            donnees={membres}
            caption="Membres de l'organisation"
            cleLigne={(m) => m.user_id}
            triInitial={[{ id: "nom", desc: false }]}
            carte={(m) => (
              <div className="flex flex-col gap-2 rounded-lg border p-3">
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{m.full_name}</span>
                  {/* Sous le nom, jamais masqué : c'est la seule façon de
                      distinguer deux homonymes à 390 px. */}
                  <span className="truncate text-xs text-muted-foreground">{m.email}</span>
                </div>
                <div className="flex items-center justify-between gap-2">
                  <CelluleRole
                    membre={m}
                    canManage={canManage}
                    meId={meId}
                    onChangerRole={(membre, r) => void changerRole(membre, r)}
                  />
                  <BoutonRetrait
                    membre={m}
                    canManage={canManage}
                    meId={meId}
                    onDemander={demanderRetrait}
                  />
                </div>
              </div>
            )}
          />
        )}

        {canManage && (
          <form
            onSubmit={inviter}
            className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-end"
          >
            <div className="grid flex-1 gap-2">
              <Label htmlFor="invite_email">Ajouter un membre existant</Label>
              <Input
                ref={emailRef}
                id="invite_email"
                type="email"
                required
                placeholder="collegue@entreprise.mg"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="invite_role">Rôle</Label>
              <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                <SelectTrigger id="invite_role" className="w-44" aria-describedby="invite_aide">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {ROLE_LIBELLE[r]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={pending}>
              {pending ? "Ajout…" : "Ajouter"}
            </Button>
          </form>
        )}
        {/* Le texte d'aide décrit le rôle choisi dans le formulaire : sans
            formulaire, il n'a rien à décrire. */}
        {canManage && (
          <p id="invite_aide" className="text-xs text-muted-foreground">
            {ROLE_AIDE[role]}
          </p>
        )}
      </CardContent>

      <ConfirmDialog
        open={aRetirer !== null}
        onOpenChange={(ouvert) => !ouvert && setARetirer(null)}
        title="Retirer ce membre de l'organisation ?"
        description="La personne perd immédiatement l'accès aux offres, aux conversations et aux données de l'organisation. Son compte Miara, lui, reste actif."
        preview={aRetirer ? `${aRetirer.full_name} — ${aRetirer.email}` : undefined}
        confirmLabel="Retirer"
        cancelLabel="Annuler"
        retourFocus={retourRef}
        onConfirm={() => (aRetirer ? retirer(aRetirer) : Promise.resolve())}
      />
    </Card>
  );
}
