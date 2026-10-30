"""Capa de acceso a MySQL.

Orden de prioridad para la configuración (de mayor a menor):

1. Variables de entorno: ``DB_HOST``, ``DB_PORT``, ``DB_USER``,
   ``DB_PASSWORD``, ``DB_NAME``.
2. Archivo ``config.json`` en la raíz del proyecto (ver ``config.example.json``).
3. Valores por defecto locales.

Así las credenciales dejan de estar escritas dentro del código fuente.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - depende del entorno
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:  # pragma: no cover
    mysql = None
    MySQLError = Exception  # type: ignore[assignment,misc]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "cosmicstream_db",
}

_ENV_MAP = {
    "DB_HOST": "host",
    "DB_PORT": "port",
    "DB_USER": "user",
    "DB_PASSWORD": "password",
    "DB_NAME": "database",
}

_last_error: str = ""
_failed_at: float = 0.0
# Si la conexión falla, no se reintenta durante estos segundos. Sin esto, una
# pantalla que hace 4 consultas seguidas con el servidor caído bloquea la
# interfaz 4 × timeout.
REINTENTO_SEGUNDOS = 3.0


class DBError(RuntimeError):
    """Error de conexión o de consulta contra MySQL."""


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """Devuelve la configuración efectiva de la base de datos."""
    config = dict(DEFAULT_CONFIG)

    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[!] No se pudo leer {CONFIG_PATH.name}: {exc}")

    for env_name, key in _ENV_MAP.items():
        value = os.environ.get(env_name)
        if value in (None, ""):
            continue
        if key == "port":
            try:
                config[key] = int(value)
            except ValueError:
                # Un DB_PORT no numérico no debe tumbar la aplicación.
                pass
        else:
            config[key] = value

    try:
        config["port"] = int(config["port"])
    except (TypeError, ValueError):
        config["port"] = DEFAULT_CONFIG["port"]

    return config


def last_error() -> str:
    """Último mensaje de error de conexión (vacío si todo fue bien)."""
    return _last_error


def is_available() -> bool:
    """Comprueba que el driver de MySQL esté instalado."""
    return mysql is not None


# --------------------------------------------------------------------------- #
# Conexión
# --------------------------------------------------------------------------- #
def get_connection():
    """Abre una conexión nueva o devuelve ``None`` si no se pudo conectar."""
    global _last_error, _failed_at

    if mysql is None:
        _last_error = (
            "Falta el paquete mysql-connector-python. "
            "Ejecuta: pip install -r requirements.txt"
        )
        return None

    # Tras un fallo reciente no se vuelve a intentar de inmediato: la pantalla
    # hace varias consultas seguidas y cada intento cuesta un timeout completo.
    if _failed_at and (time.monotonic() - _failed_at) < REINTENTO_SEGUNDOS:
        return None

    config = load_config()
    try:
        connection = mysql.connector.connect(
            host=config["host"],
            port=config["port"],
            user=config["user"],
            password=config["password"],
            database=config["database"],
            charset="utf8mb4",
            use_pure=True,
            autocommit=False,
            connection_timeout=6,
        )
        _last_error = ""
        _failed_at = 0.0
        return connection
    except MySQLError as exc:
        _last_error = str(exc)
        _failed_at = time.monotonic()
        return None


def _rollback(connection) -> None:
    """Deshace la transacción actual sin enmascarar el error original."""
    try:
        connection.rollback()
    except MySQLError:
        pass


@contextmanager
def db_cursor(dictionary: bool = False) -> Iterator[tuple]:
    """Context manager que abre conexión + cursor y limpia todo al salir.

    Hace ``commit`` si el bloque termina bien y ``rollback`` si lanza una
    excepción. Evita repetir el mismo ``try/finally`` en cada función::

        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute("SELECT ...")
            return cur.fetchall()
    """
    connection = get_connection()
    if connection is None:
        raise DBError(_last_error or "No se pudo conectar con MySQL.")

    cursor = None
    try:
        cursor = connection.cursor(dictionary=dictionary)
        yield connection, cursor
        connection.commit()
    except MySQLError as exc:
        # Cualquier error de SQL (columna inexistente, clave foránea, dato
        # demasiado largo…) sale siempre como DBError: los módulos de la app
        # capturan ese tipo y muestran un mensaje legible.
        _rollback(connection)
        raise DBError(f"Error de MySQL: {exc}") from exc
    except Exception:
        _rollback(connection)
        raise
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        try:
            if connection.is_connected():
                connection.close()
        except MySQLError:
            pass
