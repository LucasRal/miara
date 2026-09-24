"use client";

import { Download } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Label,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { FiltreEspace, TOUT } from "@/components/layout/filtre-espace";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable, type Colonne } from "@/components/ui/data-table";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteTableau } from "@/components/ui/skeletons";
import { ErrorState } from "@/components/ui/states";
import { libelleAgent, parLibelle, type AgentAgrege } from "@/lib/agents";
import { api } from "@/lib/api";
import { useEspace } from "@/lib/espace";
import { downloadCsv } from "@/lib/hr";
import {
  duree,
  heure,
  nombre,
  usd,
  type UsageAgent,
  type UsageAgentAlias,
  type UsageCall,
  type UsageDay,
} from "@/lib/dashboard";

const FENETRES = [7, 30, 90];
const TAILLE_PAGE = 25;

/** Recharts passe une valeur non typée au formateur : on la borne ici. */
function usdTooltip(valeur: unknown): string {
  return usd(typeof valeur === "number" ? valeur : Number(valeur ?? 0));
}

const AXE = { fontSize: 12, stroke: "var(--muted-foreground)" } as const;

/**
 * Graduations d'un axe de coût, en français. Recharts formate par défaut avec
 * un point décimal : l'axe écrivait « 0.35 » à côté d'un tableau qui écrit
 * « 0,0004 USD ». Deux décimales suffisent sur une graduation.
 */
function graduationUsd(valeur: number): string {
  return nombre(valeur, valeur < 1 ? 2 : 0);
}
const INFOBULLE = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
} as const;

/**
 * Page Usage : ce que les agents consomment, par jour, par agent, par alias.
 *
 * Les graphiques sont pensés pour être repris tels quels comme figures du
 * mémoire (chap. 8) : chaque axe porte son unité, chaque série son libellé
 * métier. Le tableau des derniers appels ne montre QUE des métadonnées :
 * jamais le contenu d'un prompt, donc jamais un CV ni un compte rendu d'appel.
 */
export function UsageWorkspace() {
  const [jours, setJours] = useState(30);
  const [serie, setSerie] = useState<UsageDay[] | null>(null);
  const [agents, setAgents] = useState<AgentAgrege[]>([]);
  const [alias, setAlias] = useState<UsageAgentAlias[]>([]);
  const [appels, setAppels] = useState<{ calls: UsageCall[]; total: number } | null>(null);
  const [pageAppels, setPageAppels] = useState(0);
  const [erreur, setErreur] = useState<string | null>(null);
  const { espace } = useEspace();
  const [tout, setTout] = useState(false);
  // Les quatre vues de l'écran partagent ce périmètre : le total en haut de
  // page contredirait les lignes du bas si chacune choisissait le sien.
  const perimetre = tout || !espace ? TOUT : espace;

  const charger = useCallback(async () => {
    setErreur(null);
    try {
      const cadre = perimetre === TOUT ? "" : `&espace=${perimetre}`;
      const [daily, parAgent, derniers] = await Promise.all([
        api.get<{ series: UsageDay[] }>(`/usage/daily?days=${jours}${cadre}`),
        api.get<{ by_agent: UsageAgent[]; by_agent_alias: UsageAgentAlias[] }>(
          `/usage/by-agent?${cadre.slice(1)}`
        ),
        api.get<{ calls: UsageCall[]; total: number }>(
          `/usage/calls?limit=${TAILLE_PAGE}&offset=${pageAppels * TAILLE_PAGE}${cadre}`
        ),
      ]);
      setSerie(daily.series);
      setAgents(parLibelle(parAgent.by_agent));
      setAlias(parAgent.by_agent_alias);
      setAppels(derniers);
    } catch {
      setErreur("Impossible de charger l'usage.");
    }
  }, [jours, pageAppels, perimetre]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void charger();
  }, [charger]);

  function exporter() {
    if (!appels) return;
    const entetes = ["date", "agent", "alias", "modele", "latence_ms", "cout_usd", "statut"];
    const echapper = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lignes = appels.calls.map((a) =>
      [a.created_at, a.agent, a.alias, a.model_used, a.latency_ms, a.cost_usd ?? "", a.status]
        .map(echapper)
        .join(";")
    );
    downloadCsv("usage-derniers-appels.csv", `﻿${entetes.join(";")}\n${lignes.join("\n")}\n`);
  }

  const colonnesAlias: Colonne<UsageAgentAlias>[] = [
    {
      id: "agent",
      accessorFn: (a) => libelleAgent(a.agent),
      header: "Agent",
      sortFn: "text",
      cell: ({ row }) => libelleAgent(row.original.agent),
    },
    {
      id: "alias",
      accessorKey: "alias",
      header: "Alias de modèle",
      sortFn: "text",
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.alias}</span>,
    },
    {
      id: "appels",
      accessorKey: "calls",
      header: "Appels",
      sortFn: "basic",
      cell: ({ row }) => <span className="tabular-nums">{row.original.calls}</span>,
    },
    {
      id: "jetons",
      accessorFn: (a) => a.input_tokens + a.output_tokens,
      header: "Jetons",
      sortFn: "basic",
      cell: ({ row }) => (
        <span className="tabular-nums">
          {(row.original.input_tokens + row.original.output_tokens).toLocaleString("fr-FR")}
        </span>
      ),
    },
    {
      id: "latence",
      accessorKey: "latency_ms",
      header: "Latence moyenne",
      sortFn: "basic",
      cell: ({ row }) => <span className="tabular-nums">{duree(row.original.latency_ms)}</span>,
    },
    {
      id: "cout",
      accessorKey: "cost_usd",
      header: "Coût (USD)",
      sortFn: "basic",
      cell: ({ row }) => <span className="tabular-nums">{usd(row.original.cost_usd)}</span>,
    },
  ];

  const colonnesAppels: Colonne<UsageCall>[] = [
    {
      id: "quand",
      accessorKey: "created_at",
      header: "Quand",
      sortFn: "datetime",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{heure(row.original.created_at)}</span>
      ),
    },
    {
      id: "agent",
      accessorFn: (a) => libelleAgent(a.agent),
      header: "Agent",
      sortFn: "text",
      cell: ({ row }) => libelleAgent(row.original.agent),
    },
    {
      id: "modele",
      accessorKey: "model_used",
      header: "Modèle",
      sortFn: "text",
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.model_used}</span>,
    },
    {
      id: "latence",
      accessorKey: "latency_ms",
      header: "Latence",
      sortFn: "basic",
      cell: ({ row }) => <span className="tabular-nums">{duree(row.original.latency_ms)}</span>,
    },
    {
      id: "cout",
      accessorKey: "cost_usd",
      header: "Coût (USD)",
      sortFn: "basic",
      cell: ({ row }) => (
        <span className="tabular-nums">
          {row.original.cost_usd === null ? "–" : usd(row.original.cost_usd)}
        </span>
      ),
    },
    {
      id: "statut",
      accessorKey: "status",
      header: "Statut",
      sortFn: "text",
      cell: ({ row }) => (
        <span className={row.original.status === "ok" ? "" : "text-destructive"}>
          {row.original.status === "ok" ? "Réussi" : "En échec"}
        </span>
      ),
    },
  ];

  if (erreur) return <ErrorState message={erreur} onRetry={() => void charger()} />;
  if (serie === null || appels === null)
    return <SqueletteTableau lignes={6} colonnes={4} label="Chargement de l'usage…" />;

  const total = serie.reduce((somme, j) => somme + j.cost_usd, 0);
  const jetons = serie.reduce((somme, j) => somme + j.input_tokens + j.output_tokens, 0);
  const donneesJour = serie.map((j) => ({
    jour: new Date(j.day).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" }),
    cout: Number(j.cost_usd.toFixed(4)),
    jetons: j.input_tokens + j.output_tokens,
  }));

  // Nom accessible des graphiques : une phrase, pas la concaténation des
  // graduations (WCAG 1.1.1). Les mêmes chiffres sont dans les tableaux.
  const pic = donneesJour.reduce(
    (max, j) => (j.cout > max.cout ? j : max),
    donneesJour[0] ?? { jour: "–", cout: 0 }
  );
  const titreCourbe = `Coût quotidien en USD sur ${jours} jours`;
  const descCourbe = `Courbe du coût par jour. Total ${usd(total)} sur ${serie.length} jours avec appels ; pic le ${pic.jour} à ${usd(pic.cout)}. Les mêmes valeurs sont dans le tableau « Coût par jour ».`;
  const titreBarres = "Coût par agent, en USD";
  const descBarres = `Barres du coût cumulé par agent, sur toute l'histoire de l'organisation. ${agents
    .map((a) => `${a.libelle} : ${usd(a.cost_usd)}`)
    .join(" ; ")}. Les mêmes valeurs sont dans le tableau « Par alias de modèle ».`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Select value={String(jours)} onValueChange={(v) => setJours(Number(v))}>
            <SelectTrigger className="w-44" aria-label="Fenêtre d'observation">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FENETRES.map((f) => (
                <SelectItem key={f} value={String(f)}>
                  {f} derniers jours
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FiltreEspace
            valeur={perimetre}
            onChange={(v) => {
              setTout(v === TOUT);
              setPageAppels(0);
            }}
          />
          <p className="text-sm text-muted-foreground">
            {usd(total)} · {jetons.toLocaleString("fr-FR")} jetons
          </p>
        </div>
        <Button variant="outline" size="sm" disabled={appels.calls.length === 0} onClick={exporter}>
          <Download aria-hidden /> Exporter les appels
        </Button>
      </div>

      {serie.length === 0 ? (
        <EmptyState
          title="Aucun appel sur la période"
          description="Utilisez les agents : le coût et les jetons consommés apparaîtront ici."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Coût par jour</CardTitle>
              <CardDescription>En dollars (USD), tous agents confondus.</CardDescription>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={donneesJour} title={titreCourbe} desc={descCourbe}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="jour" {...AXE} />
                  <YAxis {...AXE} width={64} tickFormatter={graduationUsd}>
                    <Label
                      value="USD"
                      position="insideTopLeft"
                      offset={-2}
                      fill="var(--muted-foreground)"
                      fontSize={11}
                    />
                  </YAxis>
                  <Tooltip formatter={usdTooltip} contentStyle={INFOBULLE} />
                  <Line
                    type="monotone"
                    dataKey="cout"
                    name="Coût"
                    stroke="var(--chart-1)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
            {/* Alternative textuelle : la même série, en tableau, pour qui ne
                peut pas lire le graphique (WCAG 1.1.1). */}
            <table className="sr-only">
              <caption>{titreCourbe}</caption>
              <thead>
                <tr>
                  <th scope="col">Jour</th>
                  <th scope="col">Coût en USD</th>
                  <th scope="col">Jetons</th>
                </tr>
              </thead>
              <tbody>
                {donneesJour.map((j) => (
                  <tr key={j.jour}>
                    <th scope="row">{j.jour}</th>
                    <td>{usd(j.cout)}</td>
                    <td>{j.jetons.toLocaleString("fr-FR")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Coût par agent</CardTitle>
              <CardDescription>
                En dollars (USD), sur toute l&apos;histoire de l&apos;organisation. Les agents de
                test et le harnais d&apos;évaluation sont regroupés.
              </CardDescription>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={agents} title={titreBarres} desc={descBarres}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="libelle" {...AXE} interval={0} height={56} angle={-20} dy={12} />
                  <YAxis {...AXE} width={64} tickFormatter={graduationUsd}>
                    <Label
                      value="USD"
                      position="insideTopLeft"
                      offset={-2}
                      fill="var(--muted-foreground)"
                      fontSize={11}
                    />
                  </YAxis>
                  <Tooltip formatter={usdTooltip} contentStyle={INFOBULLE} />
                  <Bar dataKey="cost_usd" name="Coût" fill="var(--chart-1)" radius={4} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
            <table className="sr-only">
              <caption>{titreBarres}</caption>
              <thead>
                <tr>
                  <th scope="col">Agent</th>
                  <th scope="col">Coût en USD</th>
                  <th scope="col">Appels</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.libelle}>
                    <th scope="row">{a.libelle}</th>
                    <td>{usd(a.cost_usd)}</td>
                    <td>{a.calls}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}

      {alias.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Par alias de modèle</CardTitle>
            <CardDescription>
              Les alias de configuration (ADR-011), jamais un nom de modèle en dur.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DataTable
              colonnes={colonnesAlias}
              donnees={alias}
              caption="Consommation par agent et par alias de modèle"
              cleLigne={(a) => `${a.agent}-${a.alias}`}
              triInitial={[{ id: "cout", desc: true }]}
              carte={(a) => (
                <div className="flex flex-col gap-1 rounded-lg border p-3">
                  <span className="font-medium">{libelleAgent(a.agent)}</span>
                  <span className="font-mono text-xs text-muted-foreground">{a.alias}</span>
                  <span className="text-sm tabular-nums">
                    {usd(a.cost_usd)} · {a.calls} appels · {duree(a.latency_ms)} en moyenne
                  </span>
                </div>
              )}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Derniers appels</CardTitle>
          <CardDescription>
            Métadonnées uniquement : le contenu des prompts n&apos;est jamais exposé.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DataTable
            colonnes={colonnesAppels}
            donnees={appels.calls}
            caption="Derniers appels de modèle"
            cleLigne={(a) => a.id}
            paginationServeur={{
              page: pageAppels,
              taillePage: TAILLE_PAGE,
              total: appels.total,
              onPage: setPageAppels,
            }}
            vide={
              <EmptyState
                title="Aucun appel"
                description="Les appels de modèle de l'organisation apparaîtront ici."
              />
            }
            carte={(a) => (
              <div className="flex flex-col gap-1 rounded-lg border p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{libelleAgent(a.agent)}</span>
                  <span className={a.status === "ok" ? "text-xs" : "text-xs text-destructive"}>
                    {a.status === "ok" ? "Réussi" : "En échec"}
                  </span>
                </div>
                <span className="font-mono text-xs text-muted-foreground">{a.model_used}</span>
                <span className="text-sm tabular-nums">
                  {heure(a.created_at)} · {duree(a.latency_ms)} ·{" "}
                  {a.cost_usd === null ? "–" : usd(a.cost_usd)}
                </span>
              </div>
            )}
          />
        </CardContent>
      </Card>
    </div>
  );
}
