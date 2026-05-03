"""
connector.py
Módulo de conectividad a bases de datos PostgreSQL.
Gestiona conexiones seguras para origen (PRODUCCIÓN) y destino (QA).
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def build_conn_string(prefix: str) -> dict:
    """
    Construye los parámetros de conexión desde variables de entorno.

    Args:
        prefix: 'SOURCE' o 'TARGET'

    Returns:
        dict con parámetros de conexión
    """
    return {
        "host":     os.environ.get(f"{prefix}_HOST",     "localhost"),
        "port":     int(os.environ.get(f"{prefix}_PORT", 5432)),
        "dbname":   os.environ.get(f"{prefix}_DB",       ""),
        "user":     os.environ.get(f"{prefix}_USER",     ""),
        "password": os.environ.get(f"{prefix}_PASSWORD", ""),
    }


@contextmanager
def get_connection(prefix: str, dict_cursor: bool = False):
    """
    Context manager que entrega una conexión PostgreSQL y la cierra al salir.

    Args:
        prefix:      'SOURCE' o 'TARGET'
        dict_cursor: Si True, retorna filas como diccionarios

    Yields:
        psycopg2 connection
    """
    params = build_conn_string(prefix)
    conn = None
    try:
        conn = psycopg2.connect(**params)
        logger.debug(
            "Conexión establecida: %s@%s:%s/%s",
            params["user"], params["host"], params["port"], params["dbname"]
        )
        yield conn
    except psycopg2.OperationalError as e:
        logger.error("Error al conectar a %s: %s", prefix, e)
        raise
    finally:
        if conn and not conn.closed:
            conn.close()
            logger.debug("Conexión cerrada: %s", prefix)


def test_connections() -> bool:
    """
    Verifica que ambas conexiones (PRODUCCIÓN y QA) estén disponibles.

    Returns:
        True si ambas conexiones son exitosas
    """
    ok = True
    for prefix in ("SOURCE", "TARGET"):
        try:
            with get_connection(prefix) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    logger.info("✓ %s conectado: %s", prefix, version[:60])
        except Exception as e:
            logger.error("✗ %s falló: %s", prefix, e)
            ok = False
    return ok


def copy_schema_to_target(source_schema_sql: str) -> None:
    """
    Aplica el schema de Northwind en la base de datos de QA (destino).
    Solo ejecuta si las tablas no existen aún.

    Args:
        source_schema_sql: Ruta al archivo SQL con el schema
    """
    with open(source_schema_sql, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
    logger.info("Schema aplicado en base de datos QA")
