import { Check, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Trace de l'agent — l'élément signature du produit.
 *
 * Le même composant rend la boucle de l'agent commercial (routage, outils,
 * synthèse) et le pipeline RH (extraction, profil, notation, classement) :
 * une seule façon de montrer « ce que la machine est en train de faire ».
 * Ne jamais la masquer : elle fait partie de ce qui est vendu (carte SALES).
 */
export type StepStatus = "done" | "active" | "todo" | "failed";

export interface TraceStep {
  key: string;
  label: string;
  /** Détail court : outil appelé, nombre d'éléments trouvés, motif d'échec. */
  detail?: string;
  status: StepStatus;
}

const DOT: Record<StepStatus, string> = {
  done: "border-step-done bg-step-done text-background",
  active: "border-step-active bg-step-active text-background animate-pulse",
  todo: "border-step-todo bg-background text-step-todo",
  failed: "border-destructive bg-destructive text-background",
};

const LABEL: Record<StepStatus, string> = {
  done: "text-foreground",
  active: "text-foreground",
  todo: "text-muted-foreground",
  failed: "text-destructive",
};

export function AgentTrace({ steps, className }: { steps: TraceStep[]; className?: string }) {
  return (
    <ol className={cn("flex flex-col gap-0.5", className)} aria-label="Étapes de l'agent">
      {steps.map((step, i) => (
        <li key={step.key} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span
              className={cn(
                "flex size-5 shrink-0 items-center justify-center rounded-4xl border text-[0.6rem]",
                DOT[step.status]
              )}
              aria-hidden
            >
              {step.status === "done" && <Check className="size-3" />}
              {step.status === "active" && <Loader2 className="size-3 animate-spin" />}
              {step.status === "failed" && "!"}
            </span>
            {i < steps.length - 1 && <span className="w-px flex-1 bg-border" aria-hidden />}
          </div>
          <div className={cn("pb-3 text-sm", LABEL[step.status])}>
            <p className="font-medium">
              {step.label}
              <span className="sr-only">
                {" "}
                {step.status === "done"
                  ? "(terminé)"
                  : step.status === "active"
                    ? "(en cours)"
                    : step.status === "failed"
                      ? "(échec)"
                      : "(à venir)"}
              </span>
            </p>
            {step.detail && <p className="text-xs text-muted-foreground">{step.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
