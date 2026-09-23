"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { PasswordField } from "@/components/auth/password-field";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FieldError } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError, type Me } from "@/lib/api";

const ID_ERREUR = "login_erreur";

export function LoginForm() {
  const router = useRouter();
  const emailRef = useRef<HTMLInputElement>(null);
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
        // Volontairement indifférencié : dire « cet email est inconnu »
        // permettrait d'énumérer les comptes de la plateforme.
        setError("Email ou mot de passe incorrect.");
      } else {
        setError("Connexion impossible. Réessayez.");
      }
      setPending(false);
      // Le focus revient au premier champ concerné : sans cela il restait sur
      // le bouton, et rien n'indiquait où corriger (WCAG 3.3.1).
      emailRef.current?.focus();
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle asChild>
            {/* La carte EST la page : son titre est le h1 (axe
                `page-has-heading-one`). */}
            <h1>Connexion à Miara</h1>
          </CardTitle>
          <CardDescription>Vos agents commerciaux et RH vous attendent.</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit} noValidate>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                ref={emailRef}
                id="email"
                type="email"
                autoComplete="email"
                required
                aria-invalid={error !== null || undefined}
                aria-describedby={error ? ID_ERREUR : undefined}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <PasswordField
              id="password"
              label="Mot de passe"
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
              invalide={error !== null}
              decritPar={error ? ID_ERREUR : undefined}
            />
            {/* `FieldError` porte `role="alert"` : le message est annoncé à son
                apparition, sans quoi un formulaire qui refuse la connexion
                semble ne rien faire (WCAG 4.1.3). */}
            <FieldError id={ID_ERREUR}>{error}</FieldError>
          </CardContent>
          <CardFooter className="mt-6 flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Connexion…" : "Se connecter"}
            </Button>
            <p className="text-sm text-muted-foreground">
              <Link href="/mot-de-passe-oublie" className="font-medium text-foreground underline">
                Mot de passe oublié ?
              </Link>
            </p>
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
