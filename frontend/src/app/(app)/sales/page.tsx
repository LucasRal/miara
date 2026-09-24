import { SalesWorkspace } from "@/components/sales/sales-workspace";

export const metadata = { title: "Agent commercial · Miara" };

export default function SalesPage() {
  return (
    /* À partir de `lg`, l'écran tient dans la fenêtre : la page ne défile
       plus, ce sont la colonne des fils et le fil lui-même qui défilent,
       chacun chez soi. Sans cela, la liste des conversations imposait sa
       hauteur (près de mille pixels) et toute la page — titre, fils,
       conversation, composeur — glissait d'un bloc.
       Sous `lg`, la colonne devient un tiroir et l'écran redevient une page
       qui défile : une seule zone de défilement sous le pouce. */
    <div className="flex flex-1 flex-col gap-4 lg:h-(--zone-travail) lg:min-h-0 lg:flex-none">
      <div className="shrink-0">
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
