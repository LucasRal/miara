import { NewJobForm } from "@/components/hr/new-job-form";

export const metadata = { title: "Nouvelle offre · Miara" };

export default function Page() {
  return (
    <div className="flex flex-1 flex-col gap-6">
      <h1 className="font-heading text-xl font-semibold">Nouvelle offre</h1>
      <div className="max-w-3xl">
        <NewJobForm />
      </div>
    </div>
  );
}
