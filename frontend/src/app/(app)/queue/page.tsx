import { redirect } from "next/navigation";

import { QueueTable } from "@/components/dashboard/queue-table";
import { getMe } from "@/lib/server-api";
import { reprendreSession } from "@/lib/session";

export const metadata = { title: "File de traitement · Miara" };

export default async function Page() {
  const me = await getMe();
  if (!me) reprendreSession("/queue");
  // Session valide sans organisation : la coquille propose d'en créer une.
  if (!me.org_id) redirect("/");

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">File de traitement</h1>
        <p className="text-sm text-muted-foreground">
          Les traitements lancés par vos agents, leur durée et leur issue. La relance d&apos;une
          tâche en échec est réservée à l&apos;encadrement.
        </p>
      </div>
      <QueueTable role={me.role} />
    </div>
  );
}
