"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CreateOrgCard } from "@/components/auth/create-org-card";
import { OrgSwitcher } from "@/components/auth/org-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError, type Me } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  const loadMe = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/me"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/login");
      }
    }
  }, [router]);

  useEffect(() => {
    // Fetch initial : setMe n'est appelé qu'après l'await (jamais synchrone).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadMe();
  }, [loadMe]);

  async function logout() {
    await api.post("/auth/logout");
    router.push("/login");
    router.refresh();
  }

  if (!me) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        Chargement…
      </div>
    );
  }

  if (!me.org_id) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-muted/40 p-4">
        <p className="text-muted-foreground">Bienvenue {me.full_name} 👋</p>
        <CreateOrgCard onCreated={() => void loadMe()} />
        <Button variant="ghost" onClick={logout}>
          Se déconnecter
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-4">
          <span className="text-lg font-semibold">Miara</span>
          <OrgSwitcher me={me} onSwitched={setMe} />
          {me.role && <Badge variant="secondary">{me.role}</Badge>}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">{me.full_name}</span>
          <Button variant="outline" size="sm" onClick={logout}>
            Se déconnecter
          </Button>
        </div>
      </header>

      <main className="grid flex-1 content-start gap-4 p-6 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Agent commercial</CardTitle>
            <CardDescription>
              Assistant conversationnel connecté à Salesforce — cartes [SALES] à venir.
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Présélection RH</CardTitle>
            <CardDescription>Analyse de CV contre une offre — cartes [HR] à venir.</CardDescription>
          </CardHeader>
        </Card>
      </main>
    </div>
  );
}
