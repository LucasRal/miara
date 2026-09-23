import { cn } from "@/lib/utils";

/**
 * Anneau de score 0-100 (élément signature de la maquette).
 *
 * Trois paliers, trois jetons : convoquer (succès), examiner (ambre),
 * hors profil (destructif). Aucune couleur en dur — voir globals.css.
 */
export type ScoreBand = "fort" | "moyen" | "faible";

export function scoreBand(value: number): ScoreBand {
  if (value >= 70) return "fort";
  if (value >= 40) return "moyen";
  return "faible";
}

const BAND_CLASS: Record<ScoreBand, string> = {
  fort: "text-success",
  // `--amber-text`, pas `--amber` : la teinte de marque ne fait que 2,6:1 sur
  // blanc, et c'est précisément la bande où le chiffre doit être lu pour
  // trancher (WCAG 1.4.3).
  moyen: "text-amber-text",
  faible: "text-destructive",
};

const SIZES = {
  sm: { box: "size-10", text: "text-xs", stroke: 4 },
  md: { box: "size-14", text: "text-sm", stroke: 5 },
  lg: { box: "size-20", text: "text-lg", stroke: 6 },
} as const;

export function ScoreRing({
  value,
  size = "md",
  label,
  className,
}: {
  value: number;
  size?: keyof typeof SIZES;
  /** Lu par les lecteurs d'écran à la place du nombre nu. */
  label?: string;
  className?: string;
}) {
  const borne = Math.max(0, Math.min(100, Math.round(value)));
  const { box, text, stroke } = SIZES[size];
  const rayon = 50 - stroke;
  const circonference = 2 * Math.PI * rayon;

  return (
    <div
      className={cn("relative shrink-0", box, BAND_CLASS[scoreBand(borne)], className)}
      role="img"
      aria-label={label ?? `Score ${borne} sur 100`}
    >
      <svg viewBox="0 0 100 100" className="size-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r={rayon}
          fill="none"
          strokeWidth={stroke}
          className="stroke-border"
        />
        <circle
          cx="50"
          cy="50"
          r={rayon}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          stroke="currentColor"
          strokeDasharray={circonference}
          strokeDashoffset={circonference * (1 - borne / 100)}
        />
      </svg>
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 flex items-center justify-center font-heading font-semibold",
          text
        )}
      >
        {borne}
      </span>
    </div>
  );
}
