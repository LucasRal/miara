"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AccountPicker, type Compte } from "@/components/sales/account-picker";
import { CoachFeedback, type Feedback } from "@/components/sales/coach-feedback";
import { CoachHistory, type CoachSession } from "@/components/sales/coach-history";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SqueletteGraphique } from "@/components/ui/skeletons";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { amenerAVue } from "@/lib/motion";
import { notifierErreur, notifierSucces } from "@/lib/notifications";

const TYPES = [
  { valeur: "call_note", libelle: "Compte-rendu d'appel" },
  { valeur: "email", libelle: "Courriel" },
  { valeur: "script", libelle: "Script" },
];

interface PendingWrite {
  tool: string;
  preview: string;
  confirm_url: string;
}

interface CoachResponse {
  session_id: string;
  feedback: Feedback;
  needs_confirmation: PendingWrite | null;
}

/**
 * Coach commercial : un texte entre, une grille notée et sourcée sort.
 *
 * La journalisation dans Salesforce est proposée par la PLATEFORME (jamais
 * décidée par le modèle) et n'est exécutée qu'après confirmation explicite.
 */
export function CoachWorkspace() {
  const texteRef = useRef<HTMLTextAreaElement>(null);
  // Le retour naît sous le formulaire ; sur un écran étroit, le formulaire
  // fait plus d'une hauteur d'écran, donc le retour naît hors champ.
  const retourRef = useRef<HTMLDivElement>(null);
  const [texte, setTexte] = useState("");
  const [type, setType] = useState("call_note");
  const [compte, setCompte] = useState<Compte | null>(null);
  const [journaliser, setJournaliser] = useState(false);
  const [enCours, setEnCours] = useState(false);
  const [duree, setDuree] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingWrite | null>(null);
  const [tacheCreee, setTacheCreee] = useState<string | null>(null);
  const [sessions, setSessions] = useState<CoachSession[] | null>(null);

  const chargerHistorique = useCallback(async () => {
    const data = await api.get<{ sessions: CoachSession[] }>("/sales/coach/sessions");
    setSessions(data.sessions);
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void chargerHistorique().catch(() => setSessions([]));
  }, [chargerHistorique]);

  /**
   * Amener le retour à l'écran quand il vient de naître hors champ.
   *
   * Sur mobile la colonne de droite passe sous le formulaire : le retour
   * arrivait donc sous la ligne de flottaison, et l'écran semblait n'avoir
   * rien fait. En deux colonnes il est déjà visible, et `amenerAVue` ne
   * déplace alors rien.
   */
  useEffect(() => {
    if (feedback && retourRef.current) amenerAVue(retourRef.current);
  }, [feedback]);

  async function analyser(e: React.FormEvent) {
    e.preventDefault();
    setEnCours(true);
    setFeedback(null);
    setTacheCreee(null);
    const depart = performance.now();
    try {
      const reponse = await api.post<CoachResponse>("/sales/coach", {
        text: texte,
        kind: type,
        account_id: compte?.id ?? null,
        log_to_crm: journaliser,
      });
      setDuree(Math.round(performance.now() - depart));
      setFeedback(reponse.feedback);
      setSessionId(reponse.session_id);
      setPending(reponse.needs_confirmation);
      await chargerHistorique();
    } catch (err) {
      notifierErreur(
        err instanceof ApiError ? err.message : "Le coach n'a pas pu analyser ce texte."
      );
    } finally {
      setEnCours(false);
    }
  }

  async function confirmerJournalisation() {
    if (!sessionId) return;
    try {
      const res = await api.post<{ sf_record_id?: string; error?: string }>(
        `/sales/coach/${sessionId}/confirm`
      );
      if (res.error) {
        notifierErreur("Salesforce a refusé l'écriture.");
      } else {
        setTacheCreee(res.sf_record_id ?? null);
        notifierSucces("Compte-rendu journalisé dans Salesforce.");
      }
      setPending(null);
      await chargerHistorique();
    } catch (err) {
      notifierErreur(err instanceof ApiError ? err.message : "Journalisation impossible.");
    }
  }

  return (
    <div className="flex flex-col gap-6 lg:grid lg:grid-cols-2 lg:items-start">
      <Card>
        <CardHeader>
          <CardTitle>Texte à évaluer</CardTitle>
          <CardDescription>
            Cinq critères, une note et une preuve citée pour chacun.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={analyser} className="flex flex-col gap-4">
            <div className="grid gap-2">
              <Label htmlFor="coach_texte">Votre texte</Label>
              <Textarea
                ref={texteRef}
                id="coach_texte"
                required
                rows={10}
                maxLength={8000}
                value={texte}
                onChange={(e) => setTexte(e.target.value)}
                placeholder="Collez votre compte-rendu d'appel, votre courriel de relance ou votre script."
              />
              <p className="text-xs text-muted-foreground">{texte.length} / 8000 caractères</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="coach_type">Type</Label>
                <Select value={type} onValueChange={setType}>
                  <SelectTrigger id="coach_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {TYPES.map((t) => (
                      <SelectItem key={t.valeur} value={t.valeur}>
                        {t.libelle}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                {/* Le champ n'est pas un `<input>` mais un bouton-combobox :
                    l'intitulé lui est rattaché par `aria-labelledby`, il ne
                    peut donc pas être un `<label for>`. */}
                <Label id="coach_compte" asChild>
                  <span>Compte Salesforce (optionnel)</span>
                </Label>
                <AccountPicker
                  labelId="coach_compte"
                  describedBy="coach_compte_aide"
                  valeur={compte}
                  onChange={(c) => {
                    setCompte(c);
                    // Sans compte, il n'y a nulle part où journaliser : on ne
                    // laisse pas une case cochée promettre le contraire.
                    if (!c) setJournaliser(false);
                  }}
                />
                <p id="coach_compte_aide" className="text-xs text-muted-foreground">
                  Sert à rattacher le compte-rendu au bon compte si vous le journalisez.
                </p>
              </div>
            </div>

            {/* Une case grisée sans raison passe pour une panne. La raison est
                donc écrite à côté d'elle, et rattachée à la case. */}
            <div className="grid gap-1">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="coach_log"
                  checked={journaliser}
                  onCheckedChange={(v) => setJournaliser(v === true)}
                  disabled={compte === null}
                  aria-describedby="coach_log_aide"
                />
                {/* `peer-disabled:opacity-50` du primitif ferait tomber
                    l'intitulé sous le contraste minimal alors qu'il porte
                    justement le sens de la case. L'état désactivé reste lisible
                    dans la case elle-même et dans l'aide en dessous. */}
                <Label
                  htmlFor="coach_log"
                  className="text-sm font-normal peer-disabled:opacity-100"
                >
                  Proposer la journalisation dans Salesforce
                </Label>
              </div>
              <p id="coach_log_aide" className="text-xs text-muted-foreground">
                {compte === null
                  ? "Choisissez d'abord un compte : c'est lui qui porte le compte-rendu dans Salesforce."
                  : `Le compte-rendu sera proposé sur « ${compte.name} ». Rien n'est écrit sans votre confirmation.`}
              </p>
            </div>

            <Button type="submit" disabled={enCours || !texte.trim()}>
              {enCours ? "Analyse en cours…" : "Analyser"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div ref={retourRef} className="flex flex-col gap-6">
        {feedback && (
          <>
            <div className="flex items-center gap-2">
              {duree !== null && (
                <Badge variant="outline">Retour en {(duree / 1000).toFixed(1)} s</Badge>
              )}
              {tacheCreee && <Badge>Tâche Salesforce {tacheCreee} ✓</Badge>}
              {pending && (
                <Button size="sm" variant="outline" onClick={() => setPending({ ...pending })}>
                  Journaliser dans Salesforce
                </Button>
              )}
            </div>
            <CoachFeedback feedback={feedback} />
          </>
        )}
        {sessions === null ? (
          <SqueletteGraphique label="Chargement de la progression…" />
        ) : (
          <CoachHistory sessions={sessions} />
        )}
      </div>

      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(ouvert) => !ouvert && setPending(null)}
        title="Journaliser ce compte-rendu dans Salesforce"
        description="Le résumé est dérivé du retour du coach. Rien n'est écrit tant que vous n'avez pas confirmé."
        preview={pending?.preview}
        confirmLabel="Confirmer"
        cancelLabel="Refuser"
        retourFocus={texteRef}
        onConfirm={confirmerJournalisation}
      />
    </div>
  );
}
