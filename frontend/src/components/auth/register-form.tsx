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

const ID_ERREUR = "register_erreur";
/** Même règle que le backend ; elle est dite avant la première soumission. */
const LONGUEUR_MINI = 8;

export function RegisterForm() {
  const router = useRouter();
  const emailRef = useRef<HTMLInputElement>(null);
  const motDePasseRef = useRef<HTMLInputElement>(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Quel champ est fautif : les deux erreurs possibles ne visent pas le même.
  const [champ, setChamp] = useState<"email" | "password" | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setChamp(null);
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
      let fautif: "email" | "password" | null = null;
      if (err instanceof ApiError && err.status === 409) {
        setError("Un compte existe déjà avec cet email.");
        fautif = "email";
      } else if (err instanceof ApiError && err.status === 422) {
        setError(`Mot de passe trop court (${LONGUEUR_MINI} caractères minimum).`);
        fautif = "password";
      } else {
        setError("Inscription impossible. Réessayez.");
      }
      setChamp(fautif);
      setPending(false);
      // Focus sur le champ à corriger, pas sur le haut de la page.
      (fautif === "password" ? motDePasseRef : emailRef).current?.focus();
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle asChild>
            {/* La carte EST la page : son titre est le h1 (axe
                `page-has-heading-one`). */}
            <h1>Créer un compte</h1>
          </CardTitle>
          <CardDescription>Puis créez ou rejoignez une organisation.</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit} noValidate>
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
                ref={emailRef}
                id="email"
                type="email"
                autoComplete="email"
                required
                aria-invalid={champ === "email" || undefined}
                aria-describedby={champ === "email" ? ID_ERREUR : undefined}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <PasswordField
              ref={motDePasseRef}
              id="password"
              label="Mot de passe"
              autoComplete="new-password"
              minLength={LONGUEUR_MINI}
              aide={`${LONGUEUR_MINI} caractères minimum.`}
              value={password}
              onChange={setPassword}
              invalide={champ === "password"}
              decritPar={champ === "password" ? ID_ERREUR : undefined}
            />
            <FieldError id={ID_ERREUR}>{error}</FieldError>
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
