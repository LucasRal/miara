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

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await api.post<Me>("/auth/login", { email, password });
      router.push("/");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Trop de tentatives. Réessayez dans quelques minutes.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("Email ou mot de passe incorrect.");
      } else {
        setError("Connexion impossible. Réessayez.");
      }
      setPending(false);
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Connexion à Miara</CardTitle>
          <CardDescription>Vos agents commerciaux et RH vous attendent.</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="grid gap-4">
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
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
          <CardFooter className="mt-6 flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Connexion…" : "Se connecter"}
            </Button>
            <p className="text-sm text-muted-foreground">
              Pas de compte ?{" "}
              <Link href="/register" className="font-medium text-foreground underline">
                Créer un compte
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
