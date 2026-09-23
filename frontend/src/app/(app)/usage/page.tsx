import { UsageWorkspace } from "@/components/dashboard/usage-workspace";
import { guardSection } from "@/lib/guard";

export const metadata = { title: "Usage · Miara" };

/** Réservée à l'encadrement : la garde de section double celle du backend. */
export default async function Page() {
  const { denied } = await guardSection("/usage");
  if (denied) return denied;

  return (
    <div className="flex flex-1 flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Usage</h1>
        <p className="text-sm text-muted-foreground">
          Jetons, coût et latence des appels de modèle de votre organisation.
        </p>
      </div>
      <UsageWorkspace />
    </div>
  );
}
