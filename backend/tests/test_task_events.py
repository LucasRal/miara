"""Signaux du worker : comment une exécution de tâche devient une ligne lisible.

Les fonctions testées ici sont celles qui décident l'ORGANISATION d'une ligne.
Se tromper de locataire dans un journal serait une fuite, pas un détail
d'affichage : d'où un test dédié aux cas limites plutôt qu'à l'heureux chemin.
"""

import uuid

from app.core.task_events import _serialisable, _trace_id, extract_org_id


def test_org_lue_en_derniere_position() -> None:
    """Convention du projet : (run_id, candidate_id, org_id) en positionnel.

    Lire le PREMIER identifiant venu rattacherait la ligne à la campagne : la
    base refuse la clé étrangère, et le journal reste vide sans que personne
    ne s'en aperçoive. C'est exactement ce qui est arrivé.
    """
    org, run, candidat = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert extract_org_id([str(run), str(candidat), str(org)], None) == org
    assert extract_org_id([], {"org_id": str(org)}) == org
    # L'argument nommé prime sur la position : c'est le plus explicite.
    assert extract_org_id([str(run)], {"org_id": str(org)}) == org


def test_tache_sans_org_identifiable_n_est_pas_rattachee() -> None:
    """Mieux vaut une ligne absente qu'une ligne dans la mauvaise organisation."""
    assert extract_org_id(["bonjour", 42], None) is None
    assert extract_org_id(None, None) is None
    assert extract_org_id([], {}) is None


def test_trace_et_arguments_serialisables() -> None:
    run = uuid.uuid4()
    assert _trace_id([str(run), "autre"], None) == run
    assert _trace_id([], {"run_id": str(run)}) == run
    assert _trace_id(["pas-un-uuid"], None) is None
    # Les arguments doivent repartir tels quels en cas de relance.
    assert _serialisable([str(run), 3, None, True]) == [str(run), 3, None, True]
    assert _serialisable(None) == []
