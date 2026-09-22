"""Point de composition du worker : tout ce qu'il doit avoir chargé.

Le worker Celery ne découvre pas les tâches tout seul : un décorateur
`@celery_app.task` n'existe que si son module a été importé. Ce fichier est le
seul nom que `app/core/celery_app.py` connaît — core continue donc de n'avoir
aucune dépendance vers un module métier, exactement comme `app/db_registry.py`
pour les modèles (dont il dépend, les tâches touchant la base).

Ajouter un domaine = ajouter une ligne ici, jamais toucher à core.
"""

import app.core.task_events  # noqa: F401  (signaux : journal des exécutions)
import app.db_registry  # noqa: F401  (tables enregistrées : FK inter-modules)
import app.hr.tasks  # noqa: F401  (présélection RH : extraction, notation, classement)
