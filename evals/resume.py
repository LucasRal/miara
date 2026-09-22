"""Résumé markdown d'un rapport : les tableaux du chapitre 8, prêts à copier.

Le critère d'acceptation de la carte est explicite : le rapport doit suffire
aux tableaux du mémoire sans retraitement. Ce module est donc écrit à l'envers
des habitudes — pas « affichons les données », mais « voici les tableaux dont
le chapitre 8 a besoin », et chacun porte ce qu'il faut pour être lu seul :
l'effectif, la date, l'empreinte du code, et la mention d'une exécution
partielle s'il y en a une.

Les nombres sont formatés à la française (virgule décimale) parce qu'ils
finissent dans un document en français.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Version du format de rapport. À incrémenter dès qu'une métrique change de
# nom ou de définition, pour qu'un rapport archivé ne soit jamais relu avec un
# code qui compte autre chose.
#   1 : format initial.
#   2 : preuves du coach classées (citation vérifiée, constat d'absence,
#       appréciation, citation inventée) au lieu d'un seul booléen ; injections
#       jugées sur la consigne suivie au lieu de l'écart de note.
VERSION_RAPPORT = 2

STRATES = ("excellent", "bon", "limite", "hors_profil")


def nombre(valeur: Any, decimales: int = 2, defaut: str = "n. d.") -> str:
    """Nombre à la française, `n. d.` si la métrique n'a pas pu être calculée.

    Une métrique absente s'écrit, elle ne se remplace pas par zéro : un zéro
    dans un tableau de mémoire se lit comme une mesure.
    """
    if valeur is None:
        return defaut
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, int):
        return str(valeur)
    return f"{valeur:.{decimales}f}".replace(".", ",")


def pourcent(valeur: Any, decimales: int = 1) -> str:
    return "n. d." if valeur is None else nombre(100 * float(valeur), decimales) + " %"


def _entete(rapport: dict[str, Any]) -> list[str]:
    harnais = rapport["harnais"]
    lignes = [
        "# Rapport d'évaluation Miara",
        "",
        f"- **Date** : {harnais['date']}",
        f"- **Code évalué** : {harnais['sha']}",
        f"- **Suites** : {', '.join(harnais['suites'])}",
        "- **Versions de prompt** : "
        + ", ".join(f"{a} v{v}" for a, v in sorted(harnais["prompt_versions"].items())),
    ]
    if harnais.get("alias_override"):
        lignes.append(
            "- **Alias surchargés** : "
            + ", ".join(f"{a} -> {m}" for a, m in harnais["alias_override"].items())
        )
    if harnais.get("limite") is not None:
        lignes.append(
            f"- **Exécution PARTIELLE** : {harnais['limite']} cas par offre ou par suite. "
            "Les chiffres ci-dessous ne portent pas sur le jeu complet."
        )
    if harnais["sha"].endswith("-sale"):
        lignes.append(
            "- **Attention** : le dépôt contenait des modifications non committées. "
            "Ce rapport n'est pas rejouable à l'identique depuis l'empreinte seule."
        )
    return [*lignes, ""]


def _verdict(rapport: dict[str, Any]) -> list[str]:
    seuils = rapport["seuils"]
    violations = seuils["violations"]
    lignes = ["## Verdict", ""]
    if violations:
        lignes.append(f"**{len(violations)} seuil(s) non tenu(s).**")
        lignes += [
            "",
            "| Métrique | Valeur | Attendu | Pourquoi ce seuil |",
            "| --- | --- | --- | --- |",
        ]
        for violation in violations:
            attendu = (
                f"≥ {nombre(violation['min'])}"
                if violation["min"] is not None
                else f"≤ {nombre(violation['max'])}"
            )
            pourquoi = (violation.get("pourquoi") or "").strip().replace("\n", " ")
            lignes.append(
                f"| `{violation['chemin']}` | {nombre(violation['valeur'])} | "
                f"{attendu} | {pourquoi} |"
            )
    else:
        lignes.append(f"Tous les seuils sont tenus ({seuils['respectes']} vérifiés).")
    juge = rapport.get("juge", {})
    if juge.get("verdicts"):
        lignes += [
            "",
            f"{juge['verdicts']} verdicts du juge, dont {juge['echantillon_a_relire']} tirés "
            f"pour relecture humaine (`{juge['feuille']}`). Relecture faite : "
            + _etat_relecture(juge),
        ]
    return [*lignes, ""]


def _hr(bloc: dict[str, Any]) -> list[str]:
    total = bloc["global"]
    lignes = [
        "## Présélection RH",
        "",
        "| Offre | CV notés | Spearman | Top-10 | Top-20 | Must-have | Échecs | s/CV | USD/CV |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for offre, mesures in sorted(bloc["offres"].items()):
        lignes.append(
            f"| {offre} | {mesures['notes']} | {nombre(mesures['spearman'], 3)} | "
            f"{pourcent(mesures['precision_top_10'])} | {pourcent(mesures['precision_top_20'])} | "
            f"{pourcent(mesures['must_have']['exactitude'])} | {mesures['echecs']} | "
            f"{nombre(mesures['secondes_par_cv'], 1)} | {nombre(mesures['cout_par_cv_usd'], 4)} |"
        )
    lignes.append(
        f"| **ensemble** | {total['notes']} | **{nombre(total['spearman'], 3)}** | | | "
        f"{pourcent(total['exactitude_must_have'])} | {total['echecs']} | "
        f"{nombre(total['secondes_par_cv'], 1)} | {nombre(total['cout_par_cv_usd'], 4)} |"
    )
    lignes += [
        "",
        f"Écart absolu moyen à la référence : {nombre(total['ecart_absolu_moyen'], 1)} points "
        f"sur 100. Coût total de la campagne : {nombre(total['cout_usd'], 4)} USD.",
        "",
        "### Matrice de confusion par strate (attendu en ligne, obtenu en colonne)",
        "",
    ]
    if total["confusion"] is None:
        lignes.append(
            "Non calculable : les frontières entre strates se déduisent des scores de "
            "référence présents, et le jeu rejoué n'en contient pas assez."
        )
        return [*lignes, ""]
    lignes += [
        "| Attendu | " + " | ".join(STRATES) + " |",
        "| --- | " + " | ".join("---" for _ in STRATES) + " |",
    ]
    for attendu in STRATES:
        ligne = total["confusion"].get(attendu, {})
        lignes.append(f"| {attendu} | " + " | ".join(str(ligne.get(p, 0)) for p in STRATES) + " |")
    return [*lignes, ""]


def _sales(bloc: dict[str, Any]) -> list[str]:
    outils, latence = bloc["outils"], bloc["latence"]
    lignes = [
        "## Assistant commercial",
        "",
        "| Mesure | Valeur |",
        "| --- | --- |",
        f"| Questions rejouées | {bloc['questions']} |",
        f"| Tours aboutis | {bloc['tours_aboutis']} |",
        f"| F1 sur le choix des outils | {nombre(outils['f1_moyen'], 3)} |",
        f"| Précision / rappel | {nombre(outils['precision_moyenne'], 3)} / "
        f"{nombre(outils['rappel_moyen'], 3)} |",
        f"| Questions avec tous les outils attendus | {outils['questions_avec_tous_les_outils']} "
        f"sur {bloc['questions']} |",
        f"| Entités citées | {bloc['entites']['trouvees']} sur {bloc['entites']['attendues']} "
        f"({pourcent(bloc['entites']['rappel'])}) |",
        f"| Faits dorés présents | {bloc['faits_dores']['presents']} sur "
        f"{bloc['faits_dores']['total']} ({pourcent(bloc['faits_dores']['taux'])}) |",
        f"| Absence de donnée bien annoncée | {bloc['absence_de_donnee']['reussies']} sur "
        f"{bloc['absence_de_donnee']['questions']} |",
        f"| Appels au modèle par question | {nombre(bloc['etapes']['appels_llm_moyen'], 1)} |",
        f"| Latence p50 / p95 | {nombre(latence['p50_secondes'], 1)} s / "
        f"{nombre(latence['p95_secondes'], 1)} s |",
        f"| Latence maximale | {nombre(latence['max_secondes'], 1)} s |",
        f"| Tours coupés par la limite d'étapes | {bloc['etapes']['limites_d_etapes']} |",
        f"| Écritures proposées hors procédure | {bloc['etapes']['confirmations_inattendues']} |",
    ]
    return [*lignes, ""]


def _coach(bloc: dict[str, Any]) -> list[str]:
    lignes = [
        "## Coach commercial",
        "",
        f"Corrélation sur la note globale : **{nombre(bloc['spearman_global'], 3)}** "
        f"sur {bloc['aboutis']} textes. Écart absolu moyen : "
        f"{nombre(bloc['ecart_absolu_moyen_overall'], 1)} points sur 100.",
        "",
        "| Critère | Spearman | Écart absolu moyen (sur 5) | Points |",
        "| --- | --- | --- | --- |",
    ]
    for critere, mesures in bloc["par_critere"].items():
        lignes.append(
            f"| {critere.replace('_', ' ')} | {nombre(mesures['spearman'], 3)} | "
            f"{nombre(mesures['ecart_absolu_moyen'], 2)} | {mesures['points']} |"
        )
    preuves = bloc["preuves"]
    lignes += [
        "",
        "### Preuves avancées par le coach",
        "",
        "Le prompt exige pour chaque note une citation du texte ou le constat "
        "explicite d'une absence.",
        "",
        "| Nature de la preuve | Nombre |",
        "| --- | --- |",
        f"| Citation retrouvée dans le texte | {preuves['citations_verifiees']} |",
        f"| Constat d'absence | {preuves['constats_absence']} |",
        f"| Appréciation sans citation ni constat | {preuves['sans_citation_ni_absence']} |",
        f"| **Citation introuvable dans le texte** | **{preuves['citations_inventees']}** |",
        f"| Preuve vide | {preuves['vides']} |",
        f"| Total | {preuves['total']} |",
        "",
        f"Preuves conformes : {pourcent(preuves['taux_conforme'])}. Citations "
        f"inventées : {pourcent(preuves['taux_invente'])}.",
        "",
    ]
    par_critere = preuves.get("par_critere") or {}
    if par_critere:
        lignes += [
            "| Critère | Conformes | Citations inventées |",
            "| --- | --- | --- |",
        ]
        for critere, compte in sorted(par_critere.items()):
            conformes = compte["citations_verifiees"] + compte["constats_absence"]
            lignes.append(
                f"| {critere.replace('_', ' ')} | {conformes} sur {compte['total']} "
                f"| {compte['citations_inventees']} |"
            )
        lignes.append("")
    return lignes


def _etat_relecture(juge: dict[str, Any]) -> str:
    """Ce que vaut le chiffre du juge : relu et confirmé, relu et contredit, ou pas relu."""
    if not juge.get("juge_relu"):
        return "NON, les chiffres jugés ne sont pas validés."
    relecture = juge.get("relecture") or {}
    desaccords = relecture.get("desaccords")
    taux = relecture.get("taux_accord")
    detail = f"oui, {relecture.get('cas_relus')} cas relus, {pourcent(taux)} d'accord avec le juge"
    if desaccords:
        detail += (
            f". {desaccords} désaccord(s) : les taux jugés sont à lire comme une "
            "estimation basse, le détail des désaccords est dans la feuille"
        )
    return detail + "."


def _adverse(bloc: dict[str, Any]) -> list[str]:
    lignes = [
        "## Cas adverses",
        "",
        "| Cas | Conformes | Total |",
        "| --- | --- | --- |",
    ]
    for cas, compte in sorted(bloc["par_cas"].items()):
        lignes.append(f"| {cas.replace('_', ' ')} | {compte['conformes']} | {compte['total']} |")
    coaching = bloc.get("coaching", {})
    lignes.append(
        f"| injection dans un texte de coaching | {int(bool(coaching.get('conforme')))} | 1 |"
    )
    if coaching.get("statut") == "final":
        lignes += [
            "",
            f"Texte de coaching piégé : le coach a rendu {coaching['overall']}/100 "
            f"(la consigne injectée réclamait 100/100). Consigne suivie : "
            f"{'OUI' if coaching.get('consigne_suivie') else 'non'}.",
        ]
    injections = bloc["par_cas"].get("injection_de_consigne")
    if injections:
        lignes += [
            "",
            "Détail des injections dans un CV. « Conforme » ne veut dire qu'une "
            "chose : la consigne n'a pas été suivie.",
            "",
            "| Mesure | Valeur |",
            "| --- | --- |",
            f"| Consignes suivies (sécurité) | {injections['consignes_suivies']} sur "
            f"{injections['total']} |",
            f"| Tentatives signalées dans les réserves | {injections['signalees']} sur "
            f"{injections['total']} |",
            f"| Notes restées à 5 points de la référence (qualité) | "
            f"{injections['notes_stables']} sur {injections['total']} |",
        ]
    if bloc.get("fichiers_absents"):
        lignes += [
            "",
            "Fichiers annoncés par le manifeste mais absents du jeu : "
            + ", ".join(bloc["fichiers_absents"]),
        ]
    return [*lignes, ""]


class RapportTropAncien(RuntimeError):
    """Le rapport a été écrit par une version du harnais qui mesurait autrement."""


def ecrire_resume(chemin: Path, rapport: dict[str, Any]) -> None:
    """Écrit le résumé markdown d'un rapport.

    La version du harnais est vérifiée AVANT de composer quoi que ce soit :
    une métrique qui change de définition change de nom dans le rapport, et
    relire un vieux rapport avec le code d'aujourd'hui produirait soit une
    erreur incompréhensible, soit pire, un tableau muet sur ce qui manque.
    """
    version = rapport.get("harnais", {}).get("version")
    if version != VERSION_RAPPORT:
        raise RapportTropAncien(
            f"Rapport en version {version}, le harnais écrit et lit la version "
            f"{VERSION_RAPPORT}. Les métriques n'ont pas la même définition : "
            "rejoue la campagne plutôt que de mélanger deux définitions dans "
            "un même tableau."
        )
    lignes = _entete(rapport) + _verdict(rapport)
    suites = rapport["suites"]
    if "hr" in suites:
        lignes += _hr(suites["hr"])
    if "sales" in suites:
        lignes += _sales(suites["sales"])
    if "coach" in suites:
        lignes += _coach(suites["coach"])
    if "adverse" in suites:
        lignes += _adverse(suites["adverse"])
    lignes += [
        "---",
        "",
        "Rapport complet (détail CV par CV et question par question) dans le fichier "
        "JSON du même nom. Comparaison avec un autre rapport : `evals/compare.py`.",
        "",
    ]
    chemin.write_text("\n".join(lignes), encoding="utf-8")
