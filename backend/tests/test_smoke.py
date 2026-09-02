"""Tests triviaux de la carte INFRA-1 : la config se charge, les files existent."""

from app.config import settings
from app.core.celery_app import celery_app


def test_settings_load() -> None:
    assert settings.API_VERSION == "v1"
    assert settings.APP_NAME


def test_celery_queues() -> None:
    names = {q.name for q in celery_app.conf.task_queues}
    assert names == {"heavy", "light"}
