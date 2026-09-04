"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Me, type MembershipInfo } from "@/lib/api";

/**
 * Sélecteur d'organisation active. Le changement passe par POST /orgs/{id}/switch :
 * le backend réémet les cookies avec le nouveau contexte (org, rôle) — le rôle
 * n'est jamais décidé côté client.
 */
export function OrgSwitcher({ me, onSwitched }: { me: Me; onSwitched: (me: Me) => void }) {
  if (me.memberships.length <= 1) {
    return (
      <span className="text-sm font-medium">
        {me.memberships[0]?.organization_name ?? "Sans organisation"}
      </span>
    );
  }

  async function handleChange(orgId: string) {
    const updated = await api.post<Me>(`/orgs/${orgId}/switch`);
    onSwitched(updated);
  }

  return (
    <Select value={me.org_id ?? undefined} onValueChange={handleChange}>
      <SelectTrigger className="w-56" aria-label="Organisation active">
        <SelectValue placeholder="Choisir une organisation" />
      </SelectTrigger>
      <SelectContent>
        {me.memberships.map((m: MembershipInfo) => (
          <SelectItem key={m.organization_id} value={m.organization_id}>
            {m.organization_name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
