"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { api, ApiError, type Me } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await api.post<Me>("/auth/register", {
        email,
        password,
        full_name: fullName,
      });
      // Pas encore d'organisation : le tableau de bord enchaîne sur sa création.
      router.push("/");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Un compte existe déjà avec cet email.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError("Mot de passe trop court (8 caractères minimum).");
      } else {
        setError("Inscription impossible. Réessayez.");
      }
      setPending(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Créer un compte</CardTitle>
          <CardDescription>Puis créez ou rejoignez une organisation.</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="full_name">Nom complet</Label>
              <Input
                id="full_name"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
          <CardFooter className="mt-6 flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Création…" : "Créer mon compte"}
            </Button>
            <p className="text-sm text-muted-foreground">
              Déjà inscrit ?{" "}
              <Link href="/login" className="font-medium text-foreground underline">
                Se connecter
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
