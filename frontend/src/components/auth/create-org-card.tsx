"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, type Org } from "@/lib/api";

/** Onboarding : l'utilisateur sans organisation en crée une (il en devient owner). */
export function CreateOrgCard({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await api.post<Org>("/orgs", { name });
      onCreated();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "Ce nom d'organisation est déjà pris."
          : "Création impossible. Réessayez."
      );
      setPending(false);
    }
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>Créer votre organisation</CardTitle>
        <CardDescription>
          Vous en serez propriétaire et pourrez inviter votre équipe.
        </CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit}>
        <CardContent className="grid gap-2">
          <Label htmlFor="org_name">Nom de l&apos;organisation</Label>
          <Input
            id="org_name"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
        <CardFooter className="mt-6">
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? "Création…" : "Créer l'organisation"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
