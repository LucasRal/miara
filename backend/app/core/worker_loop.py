"""LA boucle asyncio du processus worker. Une seule, partagée par tout le monde.

Le code métier du worker est asynchrone (SQLAlchemy async, appels HTTP) alors
que Celery appelle des fonctions synchrones. Il faut donc une boucle, et c'est
le choix de cette boucle qui est délicat.

**Surtout pas `asyncio.run`** : il crée puis ferme une boucle à chaque appel,
alors que le pool de connexions SQLAlchemy est un singleton de module. Les
connexions restent attachées à la première boucle et la suivante échoue,
« attached to a different loop », puis « Event loop is closed ».

**Une seule boucle pour tout le processus**, et pas une par module. Les
signaux du worker (`app.core.task_events`) s'exécutent dans le même processus
que les tâches : deux boucles, même gardées ouvertes chacune de son côté, se
disputent le même pool et produisent exactement la même erreur. C'est ce qui
est arrivé le jour où le journal des tâches a été branché.

Le modèle prefork de Celery garantit qu'un processus ne traite qu'une tâche à
la fois : rien n'est partagé entre tâches concurrentes.
"""

import asyncio
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None


def run(coro: Any) -> Any:
    """Exécute la coroutine sur la boucle du processus, créée au premier appel."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)
