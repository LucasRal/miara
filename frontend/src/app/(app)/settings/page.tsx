import { redirect } from "next/navigation";

import { SalesforceCard } from "@/components/sales/salesforce-card";
import { MembersCard } from "@/components/settings/members-card";
import { getMe } from "@/lib/server-api";
import { reprendreSession } from "@/lib/session";

export const metadata = { title: "Paramètres · Miara" };

/** Paramètres de l'organisation : membres, rôles, connexion Salesforce. */
export default async function SettingsPage() {
  const me = await getMe();
  if (!me) reprendreSession("/settings");
  // Session valide sans organisation : la coquille propose d'en créer une.
  if (!me.org_id) redirect("/");
  const canManage = me.role === "owner" || me.role === "admin";
  const organisation =
    me.memberships.find((m) => m.organization_id === me.org_id)?.organization_name ??
    "cette organisation";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Paramètres</h1>
        <p className="text-sm text-muted-foreground">{organisation}</p>
      </div>
      <MembersCard orgId={me.org_id} canManage={canManage} meId={me.id} />
      <SalesforceCard role={me.role} orgName={organisation} />
    </div>
  );
}
