import { RunWorkspace } from "@/components/hr/run-workspace";

export const metadata = { title: "Analyse des CV · Miara" };

export default async function Page({ params }: PageProps<"/hr/[jobId]/runs/[runId]">) {
  const { jobId, runId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <RunWorkspace jobId={jobId} runId={runId} />
    </div>
  );
}
