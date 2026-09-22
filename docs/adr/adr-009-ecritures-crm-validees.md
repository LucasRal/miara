# ADR-009 - Outils d'écriture CRM à validation humaine

## Décision
`create_task` / `update_opportunity` → retour `NeedsConfirmation` à l'interface AVANT exécution.

## Justification
Confiance des équipes commerciales, aucune écriture non consentie.

## Alternatives écartées
Écriture directe : risque inacceptable en production.

## Extension aux créations (ajoutée le 22 septembre 2026)

Le périmètre d'écriture couvre désormais six outils : `create_task`,
`log_call_note`, `update_opportunity_stage`, `create_contact`,
`create_account` et `create_opportunity`. La règle ne change pas — aucune
exécution sans `NeedsConfirmation` — mais une création pose deux questions que
la mise à jour ne posait pas.

**Le doublon.** Créer un contact qui existe déjà est silencieux : aucune erreur
Salesforce, juste une fiche de plus, et un historique client coupé en deux.
Faire trancher le modèle (« ce contact existe-t-il ? ») reviendrait à lui
confier la décision ; refuser toute création en cas d'homonyme rendrait
l'outil inutilisable, les homonymes étant fréquents et légitimes. La
plateforme fait donc la recherche elle-même, à l'aperçu, et l'affiche dans
l'écran de confirmation : contacts portant le même nom, comptes de raison
sociale proche, opportunités déjà ouvertes sur le compte visé. L'humain voit
ce qui existe au moment de confirmer, et décide. **Un homonyme n'empêche
jamais une création.**

Conséquence technique : l'aperçu d'un outil devient asynchrone et contextuel
(`ToolPreview = (args, ctx) -> Awaitable[str]`), car il lit le CRM. Il
s'exécute avant la confirmation, donc il ne doit jamais écrire. Si la
recherche échoue, l'aperçu le dit au lieu de laisser croire qu'aucun homonyme
n'existe.

**Le montant et la date de clôture.** Le prompt les interdit depuis sa v1 :
ce sont des engagements que le modèle n'a pas à réécrire. À la création, en
revanche, ils sont légitimes — l'utilisateur vient de les énoncer, il n'y a
pas d'engagement antérieur à écraser. `create_opportunity` les accepte donc,
`update_opportunity_stage` continue de les refuser. L'étape et la date sont
validées avant tout appel au CRM : une valeur refusée revient au modèle sans
avoir rien créé à moitié.

Idempotence et audit valent pour les créations comme pour le reste : clé
`(org, trace_id, call_id)` en Redis, ligne dans `crm_writes` à chaque
tentative, y compris en erreur.
