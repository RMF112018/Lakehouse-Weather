"""Gunicorn application factory, evaluated independently in each worker."""
from pathlib import Path
from .__main__ import application
from .server import wsgi


def create_app():
    try:
        return wsgi(application(), Path(__file__).resolve().parents[1] / 'web')
    except Exception:
        # Driver/configuration exceptions may contain credentials. Suppress context.
        raise RuntimeError('Weather startup failed; check configuration and database readiness') from None
