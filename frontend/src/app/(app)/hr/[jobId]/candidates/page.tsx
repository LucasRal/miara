import { CandidatesPanel } from "@/components/hr/candidates-panel";

export const metadata = { title: "Dépôt des CV · Miara" };

export default async function Page({ params }: PageProps<"/hr/[jobId]/candidates">) {
  const { jobId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <CandidatesPanel jobId={jobId} />
    </div>
  );
}
