"use client";

import { Eye, EyeOff } from "lucide-react";
import { useId, useState } from "react";

import { FieldDescription } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import { Label } from "@/components/ui/label";

/**
 * Champ mot de passe : saisie affichable, règle énoncée avant l'échec.
 *
 * Deux défauts réglés ici pour les deux écrans d'authentification :
 *  - on tapait à l'aveugle, sans moyen de relire ce qu'on avait saisi ;
 *  - la contrainte de longueur n'apparaissait qu'après un refus du serveur.
 *    Une règle que l'on découvre en échouant n'est pas une règle, c'est un
 *    piège.
 *
 * L'aide et l'erreur éventuelle sont liées au champ par `aria-describedby` :
 * un lecteur d'écran les lit à la prise de focus, pas seulement à l'échec.
 */
export function PasswordField({
  ref,
  id,
  label,
  value,
  onChange,
  autoComplete,
  aide,
  invalide = false,
  decritPar,
  minLength,
}: {
  /** Pour pouvoir y ramener le focus quand c'est ce champ qui est fautif. */
  ref?: React.Ref<HTMLInputElement>;
  id: string;
  label: string;
  value: string;
  onChange: (valeur: string) => void;
  autoComplete: "current-password" | "new-password";
  /** Règle à respecter, affichée dès le départ. */
  aide?: string;
  invalide?: boolean;
  /** Identifiant du message d'erreur de la page, s'il y en a un. */
  decritPar?: string;
  minLength?: number;
}) {
  const [visible, setVisible] = useState(false);
  const idAide = useId();
  const decrit = [aide ? idAide : null, decritPar].filter(Boolean).join(" ") || undefined;

  return (
    <div className="grid gap-2">
      <Label htmlFor={id}>{label}</Label>
      <InputGroup>
        <InputGroupInput
          ref={ref}
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          required
          minLength={minLength}
          aria-invalid={invalide || undefined}
          aria-describedby={decrit}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <InputGroupAddon align="inline-end">
          <InputGroupButton
            size="icon-xs"
            aria-pressed={visible}
            aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
          </InputGroupButton>
        </InputGroupAddon>
      </InputGroup>
      {aide && <FieldDescription id={idAide}>{aide}</FieldDescription>}
    </div>
  );
}
