"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Integration, type Role } from "@/lib/api";

/**
 * Connexion Salesforce de l'organisation (carte SALES OAuth).
 * « Connecter » est une navigation complète (pas un fetch) : le backend
 * redirige vers le consentement Salesforce, qui revient sur /callback.
 */
export function SalesforceCard({ role }: { role: Role | null }) {
  const [integrations, setIntegrations] = useState<Integration[] | null>(null);
  const [notice, setNotice] = useState<"connected" | "error" | null>(null);

  const load = useCallback(async () => {
    try {
      setIntegrations(await api.get<Integration[]>("/integrations"));
    } catch {
      setIntegrations([]);
    }
  }, []);

  useEffect(() => {
    // Fetch initial : setState seulement après l'await (jamais synchrone).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    // Retour du flux OAuth : /?salesforce=connected|error (lu hors rendu
    // pour éviter la contrainte Suspense de useSearchParams).
    const status = new URLSearchParams(window.location.search).get("salesforce");
    if (status === "connected" || status === "error") {
      setNotice(status);
      window.history.replaceState(null, "", "/");
    }
  }, [load]);

  const salesforce = integrations?.find((i) => i.provider === "salesforce");
  const canManage = role === "owner" || role === "admin";

  async function disconnect() {
    await api.post("/integrations/salesforce/disconnect");
    setNotice(null);
    await load();
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Salesforce</CardTitle>
          {salesforce ? (
            <Badge>Connecté</Badge>
          ) : (
            <Badge variant="outline">Non connecté</Badge>
          )}
        </div>
        <CardDescription>
          {salesforce
            ? salesforce.instance_url
            : "Connectez le Salesforce de votre organisation pour activer l'agent commercial."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {notice === "connected" && (
          <p className="text-sm text-primary">Salesforce connecté avec succès.</p>
        )}
        {notice === "error" && (
          <p className="text-sm text-destructive">
            La connexion Salesforce a échoué — réessayez ou vérifiez la Connected App.
          </p>
        )}
        {canManage && (
          <div className="flex gap-2">
            {salesforce ? (
              <Button variant="outline" size="sm" onClick={() => void disconnect()}>
                Déconnecter
              </Button>
            ) : (
              <Button size="sm" asChild>
                <a href="/api/v1/integrations/salesforce/connect">Connecter Salesforce</a>
              </Button>
            )}
          </div>
        )}
        {!canManage && !salesforce && (
          <p className="text-sm text-muted-foreground">
            Demandez à un administrateur de connecter Salesforce.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
