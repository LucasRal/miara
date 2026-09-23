"use client";

import { useState, type ReactNode, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Dialogue de confirmation humaine (ADR-009).
 *
 * L'agent ne décide jamais seul d'une écriture : il propose un aperçu, une
 * personne confirme ou refuse. Ce composant est le SEUL chemin d'écriture CRM
 * côté interface — d'où l'aperçu obligatoire.
 *
 * Dialogue CONTRÔLÉ (`open`/`onOpenChange`), donc sans `DialogTrigger` : Radix
 * ignore d'où il a été ouvert et laisse le focus retomber sur `<body>` à la
 * fermeture. `retourFocus` lui redonne une destination — sans quoi un
 * utilisateur clavier repart du haut de la page après chaque confirmation
 * (WCAG 2.4.3).
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  preview,
  confirmLabel = "Confirmer",
  cancelLabel = "Refuser",
  onConfirm,
  onCancel,
  retourFocus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  /** Ce qui sera écrit, tel quel. Obligatoire pour une action irréversible. */
  preview?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => Promise<void> | void;
  onCancel?: () => void;
  /**
   * Où poser le focus à la fermeture, quelle qu'en soit la cause (Échap,
   * annulation, confirmation). Si la cible a disparu entre-temps — la ligne
   * qu'on vient de supprimer — le repli est le premier élément focusable
   * restant dans le même conteneur.
   */
  retourFocus?: RefObject<HTMLElement | null>;
}) {
  const [pending, setPending] = useState(false);

  async function confirmer() {
    setPending(true);
    try {
      await onConfirm();
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <DialogContent
        className="max-w-md"
        onCloseAutoFocus={(e) => {
          const cible = retourFocus?.current;
          if (!cible) return;
          // `preventDefault` avant tout : le comportement par défaut de Radix
          // sur un dialogue contrôlé est de ne rien focuser.
          e.preventDefault();
          cible.focus();
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {preview && (
          <div className="max-h-64 overflow-auto rounded-md border bg-muted/50 p-3 text-sm whitespace-pre-wrap">
            {preview}
          </div>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() => {
              onCancel?.();
              onOpenChange(false);
            }}
          >
            {cancelLabel}
          </Button>
          <Button disabled={pending} onClick={() => void confirmer()}>
            {pending ? "En cours…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
