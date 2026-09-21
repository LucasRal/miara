"""Registre des modèles : importe TOUS les modules de modèles du monolithe.

Les FK inter-modules sont déclarées par chaîne (ex. le mixin TenantScoped
référence "organizations.id", table définie dans app.auth.models). SQLAlchemy
ne peut les résoudre que si toutes les tables sont enregistrées dans
Base.metadata. Tout point d'entrée qui touche la BDD doit donc importer ce
module : app.main l'obtient via ses routers, le worker Celery via `imports`
(app/core/celery_app.py), alembic/env.py et les scripts l'importent
explicitement.

Ce module vit HORS de core/ : c'est un point de composition (comme main.py),
core ne doit jamais importer un module métier.
"""

import app.auth.models  # noqa: F401
import app.core.models  # noqa: F401
import app.hr.models  # noqa: F401
import app.sales.models  # noqa: F401

# Cartes à venir : ajouter ici les modèles des nouveaux modules métier.
