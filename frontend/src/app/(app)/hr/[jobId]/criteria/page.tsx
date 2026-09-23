import { CriteriaGrid } from "@/components/hr/criteria-grid";

export const metadata = { title: "Grille de critères · Miara" };

export default async function Page({ params }: PageProps<"/hr/[jobId]/criteria">) {
  const { jobId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <CriteriaGrid jobId={jobId} />
    </div>
  );
}
