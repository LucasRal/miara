import { JobsList } from "@/components/hr/jobs-list";

export const metadata = { title: "Agent RH · Miara" };

export default function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Agent RH</h1>
        <p className="text-sm text-muted-foreground">
          De l&apos;offre au classement justifié : chaque note porte une preuve tirée du CV.
        </p>
      </div>
      <JobsList />
    </div>
  );
}
