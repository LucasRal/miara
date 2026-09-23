import { redirect } from "next/navigation";

import { ActivityWorkspace } from "@/components/dashboard/activity-workspace";
import { getMe } from "@/lib/server-api";
import { reprendreSession } from "@/lib/session";

export const metadata = { title: "Activité · Miara" };

export default async function Page() {
  const me = await getMe();
  if (!me) reprendreSession("/activity");
  // Session valide sans organisation : la coquille propose d'en créer une.
  if (!me.org_id) redirect("/");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Activité</h1>
        <p className="text-sm text-muted-foreground">
          Tout ce que les agents ont produit pour votre organisation : présélections de CV,
          écritures confirmées dans Salesforce, analyses du coach.
        </p>
      </div>
      <ActivityWorkspace />
    </div>
  );
}
