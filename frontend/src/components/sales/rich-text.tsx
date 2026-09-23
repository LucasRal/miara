import { Fragment, type ReactNode } from "react";

/**
 * Rendu du texte produit par l'agent : gras, listes, et surtout les
 * identifiants Salesforce cités entre parenthèses, transformés en liens vers
 * l'enregistrement (le prompt impose cette citation après chaque élément).
 *
 * Volontairement minimal et sans HTML injecté : le texte vient d'un modèle,
 * on ne lui laisse pas produire de balises.
 */
const ID_SALESFORCE = /\(([a-zA-Z0-9]{15}(?:[a-zA-Z0-9]{3})?)\)/g;
// Gras ET italique, dans la même passe : `**x**` d'abord (sinon `*x*`
// mangerait ses astérisques), puis `_x_`. Trois formes de balisage, pas une
// bibliothèque Markdown — le texte vient d'un modèle et le rendu reste
// volontairement minimal.
const EMPHASE = /\*\*([^*]+)\*\*|_([^_\n]+)_/g;

function lienSalesforce(id: string, instanceUrl: string | null): ReactNode {
  if (!instanceUrl) return <span className="font-mono text-xs">{id}</span>;
  return (
    <a
      href={`${instanceUrl}/lightning/r/${id}/view`}
      target="_blank"
      rel="noreferrer"
      className="font-mono text-xs text-primary underline underline-offset-2"
    >
      {id}
    </a>
  );
}

function ligneEnrichie(ligne: string, instanceUrl: string | null, cle: string): ReactNode {
  // 1. Emphases Markdown, 2. identifiants Salesforce dans les segments restants.
  const morceaux: ReactNode[] = [];
  let dernier = 0;
  let i = 0;
  for (const m of ligne.matchAll(EMPHASE)) {
    if (m.index > dernier)
      morceaux.push(
        <Fragment key={`t${i++}`}>
          {segmentsAvecIds(ligne.slice(dernier, m.index), instanceUrl, `${cle}-${i}`)}
        </Fragment>
      );
    morceaux.push(
      m[1] !== undefined ? (
        <strong key={`g${i++}`} className="font-heading">
          {m[1]}
        </strong>
      ) : (
        <em key={`i${i++}`}>{m[2]}</em>
      )
    );
    dernier = m.index + m[0].length;
  }
  morceaux.push(
    <Fragment key={`t${i++}`}>
      {segmentsAvecIds(ligne.slice(dernier), instanceUrl, `${cle}-fin`)}
    </Fragment>
  );
  return morceaux;
}

function segmentsAvecIds(texte: string, instanceUrl: string | null, cle: string): ReactNode {
  const sortie: ReactNode[] = [];
  let dernier = 0;
  let i = 0;
  for (const m of texte.matchAll(ID_SALESFORCE)) {
    sortie.push(<Fragment key={`${cle}-s${i++}`}>{texte.slice(dernier, m.index)}</Fragment>);
    sortie.push(<Fragment key={`${cle}-l${i++}`}>({lienSalesforce(m[1], instanceUrl)})</Fragment>);
    dernier = m.index + m[0].length;
  }
  sortie.push(<Fragment key={`${cle}-s${i++}`}>{texte.slice(dernier)}</Fragment>);
  return sortie;
}

export function RichText({
  content,
  instanceUrl = null,
  className,
}: {
  content: string;
  instanceUrl?: string | null;
  className?: string;
}) {
  const lignes = content.split("\n");
  return (
    <div className={className}>
      {lignes.map((ligne, index) => {
        // Titre : le modèle en produit, et « ### Opportunités » affiché tel
        // quel se lit comme une coquille. Pas de `<h3>` : le fil est déjà
        // sous un titre, et un niveau de titre au milieu d'une bulle
        // désorganiserait le plan de la page pour un lecteur d'écran.
        const titre = /^\s*#{1,6}\s+/.exec(ligne);
        if (titre)
          return (
            <p key={index} className="mt-2 font-heading font-medium first:mt-0">
              {ligneEnrichie(ligne.slice(titre[0].length), instanceUrl, `l${index}`)}
            </p>
          );

        // Liste à puces ou numérotée : le numéro du modèle est conservé tel
        // quel — le renuméroter changerait ce qu'il a écrit.
        const numero = /^\s*(\d{1,2})[.)]\s+/.exec(ligne);
        const puce = !numero && /^\s*[-*]\s+/.test(ligne);
        const texte = numero
          ? ligne.slice(numero[0].length)
          : puce
            ? ligne.replace(/^\s*[-*]\s+/, "")
            : ligne;
        if (!texte.trim()) return <div key={index} className="h-2" />;
        return (
          <p key={index} className={numero || puce ? "flex gap-2" : undefined}>
            {numero && <span className="tabular-nums">{numero[1]}.</span>}
            {puce && <span aria-hidden>·</span>}
            <span>{ligneEnrichie(texte, instanceUrl, `l${index}`)}</span>
          </p>
        );
      })}
    </div>
  );
}
