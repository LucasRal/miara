"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Unplug } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Integration, type Role } from "@/lib/api";
import { notifierErreur, notifierSucces } from "@/lib/notifications";

/**
 * Connexion Salesforce de l'organisation (carte SALES OAuth).
 * « Connecter » est une navigation complète (pas un fetch) : le backend
 * redirige vers le consentement Salesforce, qui revient sur /callback.
 */
export function SalesforceCard({ role, orgName }: { role: Role | null; orgName: string }) {
  const [integrations, setIntegrations] = useState<Integration[] | null>(null);
  const [notice, setNotice] = useState<"connected" | "error" | null>(null);
  const [aDeconnecter, setADeconnecter] = useState(false);
  const boutonRef = useRef<HTMLButtonElement>(null);

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
    // Retour du flux OAuth : /settings?salesforce=connected|error (lu hors
    // rendu pour éviter la contrainte Suspense de useSearchParams).
    const status = new URLSearchParams(window.location.search).get("salesforce");
    if (status === "connected" || status === "error") {
      setNotice(status);
      window.history.replaceState(null, "", "/settings");
    }
  }, [load]);

  const salesforce = integrations?.find((i) => i.provider === "salesforce");
  const canManage = role === "owner" || role === "admin";

  async function disconnect() {
    try {
      await api.post("/integrations/salesforce/disconnect");
      notifierSucces("Salesforce déconnecté pour l'organisation.");
    } catch {
      notifierErreur("La déconnexion n'a pas abouti. L'intégration est inchangée.");
    }
    setNotice(null);
    setADeconnecter(false);
    await load();
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Salesforce</CardTitle>
          {/* Tant que l'état n'est pas connu, on n'affirme pas « Non
              connecté » : c'est faux une fois sur deux, et le badge changeait
              sous les yeux. */}
          {integrations === null ? (
            <Skeleton className="h-6 w-28 rounded-4xl" />
          ) : salesforce ? (
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
              // Destructive, et confirmé : c'est la seule action de cet écran
              // qui coupe l'agent commercial et le coach pour TOUS les membres.
              <Button
                ref={boutonRef}
                variant="destructive"
                size="sm"
                onClick={() => setADeconnecter(true)}
              >
                <Unplug aria-hidden />
                Déconnecter Salesforce
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

      <ConfirmDialog
        open={aDeconnecter}
        onOpenChange={setADeconnecter}
        title="Déconnecter Salesforce de cette organisation ?"
        description={`L'agent commercial et le coach ne pourront plus lire ni écrire dans Salesforce pour ${orgName}, pour tous les membres. Reconnecter exige un administrateur Salesforce et un nouveau consentement.`}
        preview={salesforce?.instance_url}
        confirmLabel="Déconnecter"
        cancelLabel="Annuler"
        retourFocus={boutonRef}
        onConfirm={disconnect}
      />
    </Card>
  );
}
