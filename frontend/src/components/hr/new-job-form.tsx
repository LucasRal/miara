"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Job } from "@/lib/hr";
import { notifierErreur } from "@/lib/notifications";

// Bornes reprises de backend/app/hr/jobs.py (JobIn) : mêmes règles des deux
// côtés, pour que le formulaire refuse avant l'aller-retour réseau.
const MIN_DESCRIPTION = 20;
const MAX_TITRE = 200;
const MAX_DESCRIPTION = 20000;

/** Création d'une offre : intitulé et texte. La grille vient juste après. */
export function NewJobForm() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      const job = await api.post<Job>("/hr/jobs", {
        title: title.trim(),
        description_text: description.trim(),
      });
      // On enchaîne directement sur la grille : une offre sans grille validée
      // ne peut rien analyser, autant ne pas laisser le recruteur à mi-chemin.
      // La proposition, elle, n'est PAS déclenchée ici : demander au modèle
      // sans que le recruteur l'ait décidé contredit l'ADR-007, et le bouton
      // promettait donc quelque chose qui n'arrivait pas. Il annonce
      // désormais ce qu'il fait ; c'est l'état vide de la grille qui porte
      // « Proposer une grille » en action primaire.
      router.replace(`/hr/${job.id}/criteria`);
    } catch (err) {
      notifierErreur(
        err instanceof ApiError && err.status === 422
          ? "Intitulé ou description trop court."
          : "Création impossible. Réessayez."
      );
      setPending(false);
    }
  }

  const tropCourt = description.trim().length < MIN_DESCRIPTION || title.trim().length < 3;

  return (
    <form onSubmit={onSubmit}>
      <Card>
        <CardHeader>
          <CardTitle>Nouvelle offre</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label htmlFor="title">Intitulé du poste</Label>
            <Input
              id="title"
              required
              maxLength={MAX_TITRE}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ingénieur logiciel backend"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="description">Description de l&apos;offre</Label>
            <Textarea
              id="description"
              required
              rows={12}
              maxLength={MAX_DESCRIPTION}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Missions, compétences attendues, contexte de l'équipe…"
            />
            <p className="text-xs text-muted-foreground">
              C&apos;est ce texte qui servira à proposer la grille de critères, à l&apos;étape
              suivante. Plus il est précis, plus la grille l&apos;est.
            </p>
          </div>
        </CardContent>
        <CardFooter className="mt-6 justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => router.push("/hr")}>
            Annuler
          </Button>
          <Button type="submit" disabled={pending || tropCourt}>
            {pending ? "Création…" : "Créer l'offre"}
          </Button>
        </CardFooter>
      </Card>
    </form>
  );
}
