import { CoachWorkspace } from "@/components/sales/coach-workspace";

export const metadata = { title: "Coach commercial · Miara" };

export default function CoachPage() {
  return (
    <div className="flex flex-1 flex-col gap-4">
      <div>
        <h1 className="font-heading text-xl font-semibold">Coach commercial</h1>
        <p className="text-sm text-muted-foreground">
          Faites relire un compte-rendu, un courriel ou un script. Chaque note est justifiée par une
          citation du texte.
        </p>
      </div>
      <CoachWorkspace />
    </div>
  );
}
