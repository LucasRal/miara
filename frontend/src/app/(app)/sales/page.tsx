import { SalesWorkspace } from "@/components/sales/sales-workspace";

export const metadata = { title: "Agent commercial · Miara" };

export default function SalesPage() {
  return (
    <div className="flex flex-1 flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl font-semibold">Agent commercial</h1>
        <p className="text-sm text-muted-foreground">
          Un briefing sourcé sur vos données Salesforce. Chaque écriture passe par votre
          confirmation.
        </p>
      </div>
      <SalesWorkspace />
    </div>
  );
}
