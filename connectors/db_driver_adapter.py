import os
import logging
from typing import Any
from google.cloud.sql.connector import Connector

logger = logging.getLogger("Lawmadi.DB.Adapter")

_connector = None

def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if not value:
        raise RuntimeError(f"[DB ENV MISSING] {name}")
    return value

def _get_connector() -> Connector:
    global _connector
    if _connector is None:
        _connector = Connector()
    return _connector

def _build_kwargs(driver: str) -> dict[str, Any]:

    db_name = _env("DB_NAME")

    if driver == "pg8000":
        return {
            "user": _env("DB_USER"),
            "password": _env("DB_PASS"),
            "db": db_name,
        }

    if driver == "psycopg2":
        return {
            "user": _env("DB_USER"),
            "password": _env("DB_PASS"),
            "dbname": db_name,
        }

    raise RuntimeError("Unsupported DB driver")

def create_connection():

    driver = os.environ.get("DB_DRIVER", "pg8000").lower()
    instance = _env("CLOUD_SQL_INSTANCE")

    kwargs = _build_kwargs(driver)

    logger.info(f"[DB] Driver={driver}")

    if driver == "pg8000":
        connector = _get_connector()
        return connector.connect(instance, "pg8000", **kwargs)

    if driver == "psycopg2":
        import psycopg2
        return psycopg2.connect(
            host="/cloudsql/" + instance,
            **kwargs
        )

    raise RuntimeError("DB connect fail")
