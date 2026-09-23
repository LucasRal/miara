"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { LIBELLES } from "@/components/sales/coach-feedback";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";

export interface CoachSession {
  id: string;
  kind: string;
  overall_0_100: number;
  scores: Record<string, number>;
  created_at: string;
  logged_task_id: string | null;
}

// Les couleurs viennent des jetons de graphique de globals.css, pas d'une
// palette locale : recharts a besoin d'une valeur, on lit la variable CSS.
const SERIES = Object.keys(LIBELLES).map((nom, i) => ({
  nom,
  couleur: `var(--chart-${(i % 5) + 1})`,
}));

/** Progression du commercial, critère par critère, de la plus ancienne à la plus récente. */
export function CoachHistory({ sessions }: { sessions: CoachSession[] }) {
  if (sessions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Progression</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            title="Pas encore d'historique"
            description="Analysez quelques textes : la courbe par critère apparaîtra ici."
          />
        </CardContent>
      </Card>
    );
  }

  const donnees = [...sessions].reverse().map((s, i) => ({
    index: i + 1,
    date: new Date(s.created_at).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }),
    ...s.scores,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Progression</CardTitle>
        <CardDescription>
          Note par critère (sur 5) sur vos {sessions.length} dernières analyses.
        </CardDescription>
      </CardHeader>
      <CardContent className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={donnees} margin={{ top: 8, right: 8, bottom: 8, left: -24 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" fontSize={12} stroke="var(--muted-foreground)" />
            <YAxis
              domain={[0, 5]}
              ticks={[0, 1, 2, 3, 4, 5]}
              fontSize={12}
              stroke="var(--muted-foreground)"
            />
            <Tooltip
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                fontSize: "0.8rem",
              }}
              formatter={(valeur, nom) => [valeur, LIBELLES[String(nom)] ?? nom]}
            />
            <Legend
              formatter={(nom) => LIBELLES[String(nom)] ?? nom}
              wrapperStyle={{ fontSize: "0.75rem" }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.nom}
                type="monotone"
                dataKey={s.nom}
                stroke={s.couleur}
                strokeWidth={2}
                dot={{ r: 2 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
