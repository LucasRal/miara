/**
 * Outils de l'agent commercial : identifiants d'un côté, phrases de l'autre.
 *
 * `create_contact` est un nom de fonction. Il n'a rien à faire sous les yeux
 * d'un commercial, et surtout pas dans le dialogue qui lui demande d'engager
 * une écriture : « exécuter create_contact » n'engage pas de la même façon
 * que « Créer un contact dans Salesforce ».
 *
 * Une seule table, quatre consommateurs : la trace de l'agent, le dialogue de
 * confirmation, les accusés d'écriture et l'activité du tableau de bord.
 */
export interface Outil {
  /** Ce que l'outil fait, à l'infinitif — pour une proposition d'action. */
  action: string;
  /** Ce que l'outil a fait, au participe — pour un accusé ou un journal. */
  fait: string;
  /** Une écriture modifie Salesforce et passe par une confirmation humaine. */
  ecriture: boolean;
}

export const OUTILS: Record<string, Outil> = {
  // --- Écritures (ADR-009 : jamais sans confirmation) ----------------------
  create_task: { action: "Créer une tâche", fait: "Tâche créée", ecriture: true },
  log_call_note: {
    action: "Journaliser un compte-rendu d'appel",
    fait: "Compte-rendu d'appel journalisé",
    ecriture: true,
  },
  update_opportunity_stage: {
    action: "Changer l'étape d'une opportunité",
    fait: "Étape d'opportunité modifiée",
    ecriture: true,
  },
  create_contact: { action: "Créer un contact", fait: "Contact créé", ecriture: true },
  create_account: { action: "Créer un compte", fait: "Compte créé", ecriture: true },
  create_opportunity: {
    action: "Créer une opportunité",
    fait: "Opportunité créée",
    ecriture: true,
  },
  // --- Lectures ------------------------------------------------------------
  find_contact: { action: "Rechercher un contact", fait: "Contact recherché", ecriture: false },
  find_account: { action: "Rechercher un compte", fait: "Compte recherché", ecriture: false },
  get_opportunity: {
    action: "Consulter une opportunité",
    fait: "Opportunité consultée",
    ecriture: false,
  },
  search_activities: {
    action: "Parcourir l'historique d'activité",
    fait: "Historique parcouru",
    ecriture: false,
  },
  get_account_context: {
    action: "Rassembler le contexte d'un compte",
    fait: "Contexte du compte rassemblé",
    ecriture: false,
  },
};

/**
 * Repli d'un outil inconnu : une phrase lisible, jamais l'identifiant brut.
 *
 * Un outil ajouté côté backend sans sa ligne ici doit rester compréhensible —
 * « Action dans Salesforce » dit au moins de quoi il s'agit, `create_widget`
 * ne dit rien à personne.
 */
const INCONNU: Outil = {
  action: "Effectuer une action dans Salesforce",
  fait: "Action effectuée dans Salesforce",
  ecriture: true,
};

export function outil(nom: string | null | undefined): Outil {
  return (nom && OUTILS[nom]) || INCONNU;
}

/** L'action proposée, à l'infinitif : « Créer un contact ». */
export function libelleOutil(nom: string | null | undefined): string {
  return outil(nom).action;
}

/** L'action réalisée, au participe : « Contact créé ». */
export function libelleOutilFait(nom: string | null | undefined): string {
  return outil(nom).fait;
}
