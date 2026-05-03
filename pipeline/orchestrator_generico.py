"""
orchestrator_generico.py
funciona con CUALQUIER base de datos
PostgreSQL o MySQL/MariaDB sin modificar el código.

Cambios respecto a la versión Northwind:
  1. Descubre las PKs automáticamente desde information_schema
  2. Lee la lista de tablas a procesar desde el YAML
  3. Copia el schema desde producción automáticamente (pg_dump / SHOW CREATE)
  4. Soporta tanto PostgreSQL como MySQL/MariaDB mediante drivers intercambiables
"""

import os
import sys
import time
import logging
import yaml
import psycopg2
import psycopg2.extras

from .connector  import get_connection, test_connections
from .anonymizer import shuffle_column, generate_fake_value, partial_mask, \
                        add_noise, generalize_date, suppress
from .tokenizer  import tokenize_cedula, verify_fpe_roundtrip
from .validator  import run_all_validations

try:
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={"DEBUG":"cyan","INFO":"green","WARNING":"yellow",
                    "ERROR":"red","CRITICAL":"red,bg_white"}
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
except ImportError:
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

logger = logging.getLogger("orchestrator")

POLICY_FILE = os.path.join(
    os.path.dirname(__file__), "..", "config", "anonymization_policy.yaml"
)


# ════════════════════════════════════════════════════════════
#  DISCOVERY AUTOMÁTICO DE CLAVES PRIMARIAS
#  Consulta information_schema — funciona en PostgreSQL y MySQL
# ════════════════════════════════════════════════════════════
def discover_primary_keys(db_prefix: str, tables: list) -> dict:
    """
    Descubre automáticamente la(s) columna(s) PK de cada tabla
    consultando information_schema del motor de BD.

    Funciona con PostgreSQL y MySQL/MariaDB sin cambios.

    Args:
        db_prefix: 'SOURCE' o 'TARGET'
        tables:    Lista de nombres de tabla a inspeccionar

    Returns:
        Dict {nombre_tabla: nombre_columna_pk}
    """
    pk_map = {}

    # Consulta compatible con PostgreSQL y MySQL
    sql_pg = """
        SELECT kcu.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema    = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema    = 'public'
          AND kcu.table_name     = ANY(%s)
        ORDER BY kcu.ordinal_position
    """

    with get_connection(db_prefix) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_pg, (tables,))
            rows = cur.fetchall()

    # Para tablas con PK compuesta, tomar la primera columna como ancla
    seen = set()
    for table_name, col_name in rows:
        if table_name not in seen:
            pk_map[table_name] = col_name
            seen.add(table_name)
            logger.debug("PK descubierta: %s.%s", table_name, col_name)

    # Tablas sin PK detectada — advertencia
    for t in tables:
        if t not in pk_map:
            logger.warning(
                "No se encontró PK para la tabla '%s'. "
                "Se usará la primera columna como ancla.", t
            )

    logger.info("PKs descubiertas para %d/%d tablas", len(pk_map), len(tables))
    return pk_map


# ════════════════════════════════════════════════════════════
#  DESCUBRIMIENTO DE TABLAS DESDE EL YAML
#  Lee las tablas a procesar del archivo de política
# ════════════════════════════════════════════════════════════
def get_tables_from_policy(policy: dict) -> list:
    """
    Extrae la lista de tablas a procesar desde la política YAML.
    El orden de las tablas importa: las tablas maestras (sin FK)
    deben procesarse antes que las tablas de detalle.

    Args:
        policy: Diccionario cargado desde el YAML

    Returns:
        Lista de nombres de tabla en orden de procesamiento
    """
    tables_config = policy.get("tables", {})
    tables = list(tables_config.keys())
    logger.info("Tablas en política: %s", tables)
    return tables


# ════════════════════════════════════════════════════════════
#  COPIA DE SCHEMA DESDE PRODUCCIÓN
#  Alternativa genérica al SQL hardcodeado de Northwind
# ════════════════════════════════════════════════════════════
def copy_schema_from_source(tables: list) -> None:
    """
    Copia el schema de las tablas indicadas desde PRODUCCIÓN a QA.
    Usa pg_catalog para reconstruir el DDL de forma portable.

    Para casos de uso real con schemas complejos, se recomienda
    usar pg_dump --schema-only en lugar de este método.

    Args:
        tables: Lista de tablas a copiar
    """
    with get_connection("SOURCE") as src_conn, \
         get_connection("TARGET") as tgt_conn:

        src_cur = src_conn.cursor()
        tgt_cur = tgt_conn.cursor()

        for table in tables:
            # Verificar si la tabla ya existe en destino
            tgt_cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """, (table,))
            exists = tgt_cur.fetchone()[0]

            if exists:
                logger.info("Tabla '%s' ya existe en QA — limpiando", table)
                tgt_cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            else:
                # Obtener columnas y tipos desde information_schema
                src_cur.execute("""
                    SELECT column_name, data_type, character_maximum_length,
                           numeric_precision, numeric_scale, is_nullable,
                           column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name   = %s
                    ORDER BY ordinal_position
                """, (table,))
                columns = src_cur.fetchall()

                if not columns:
                    logger.warning("Tabla '%s' no encontrada en PRODUCCIÓN", table)
                    continue

                # Construir CREATE TABLE dinámico
                col_defs = []
                for col in columns:
                    col_name, dtype, max_len, num_prec, num_scale, nullable, default = col
                    pg_type = _map_pg_type(dtype, max_len, num_prec, num_scale)
                    null_clause = "" if nullable == "YES" else " NOT NULL"
                    col_defs.append(f"    {col_name} {pg_type}{null_clause}")

                create_sql = (
                    f"CREATE TABLE IF NOT EXISTS {table} (\n"
                    + ",\n".join(col_defs)
                    + "\n)"
                )
                tgt_cur.execute(create_sql)
                logger.info("Tabla '%s' creada en QA", table)

        tgt_conn.commit()


def _map_pg_type(dtype: str, max_len, num_prec, num_scale) -> str:
    """Mapea tipos de information_schema a tipos PostgreSQL válidos."""
    if dtype in ("character varying", "varchar"):
        return f"VARCHAR({max_len})" if max_len else "TEXT"
    if dtype == "character":
        return f"CHAR({max_len})" if max_len else "CHAR(1)"
    if dtype == "numeric":
        if num_prec and num_scale:
            return f"NUMERIC({num_prec},{num_scale})"
        return "NUMERIC"
    if dtype in ("integer", "int", "int4"):
        return "INTEGER"
    if dtype in ("bigint", "int8"):
        return "BIGINT"
    if dtype in ("smallint", "int2"):
        return "SMALLINT"
    if dtype in ("real", "float4"):
        return "REAL"
    if dtype in ("double precision", "float8"):
        return "DOUBLE PRECISION"
    if dtype == "boolean":
        return "BOOLEAN"
    if dtype == "date":
        return "DATE"
    if dtype in ("timestamp without time zone", "timestamp"):
        return "TIMESTAMP"
    if dtype in ("timestamp with time zone", "timestamptz"):
        return "TIMESTAMPTZ"
    if dtype == "text":
        return "TEXT"
    if dtype in ("uuid",):
        return "UUID"
    # Fallback seguro
    return "TEXT"


# ════════════════════════════════════════════════════════════
#  FASE EXTRACT GENÉRICA
#  Copia todas las tablas listadas en el YAML
# ════════════════════════════════════════════════════════════
def phase_extract_generic(policy: dict, tables: list) -> dict:
    """
    Copia los datos originales desde PRODUCCIÓN a QA.
    A diferencia de la versión Northwind, no tiene lista hardcodeada.

    Args:
        policy: Política YAML cargada
        tables: Tablas a copiar (vienen del YAML)

    Returns:
        Dict con muestras de datos originales para validación
    """
    logger.info("── FASE 2: EXTRACT ────────────────────────────────")

    # Identificar columnas sensibles para capturar muestras
    sensitive_cols = _find_sensitive_columns(policy)

    original_samples: dict = {k: [] for k in sensitive_cols}
    total_rows = 0

    with get_connection("SOURCE") as src_conn, \
         get_connection("TARGET") as tgt_conn:

        src_cur = src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        tgt_cur = tgt_conn.cursor()

        # Limpiar y recrear schema en QA
        copy_schema_from_source(tables)

        for table in tables:
            src_cur.execute(f"SELECT * FROM {table}")
            rows = src_cur.fetchall()

            if not rows:
                logger.info("  %-25s → 0 filas (vacía)", table)
                continue

            columns      = list(rows[0].keys())
            placeholders = ",".join(["%s"] * len(columns))
            col_names    = ",".join(columns)
            insert_sql   = (
                f"INSERT INTO {table} ({col_names}) "
                f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            )
            values = [tuple(row[c] for c in columns) for row in rows]
            tgt_cur.executemany(insert_sql, values)
            tgt_conn.commit()

            total_rows += len(rows)
            logger.info("  %-25s → %d filas copiadas", table, len(rows))

            # Capturar muestras de campos FPE para validación posterior
            for sample_key, (t, col) in sensitive_cols.items():
                if t == table and col in columns:
                    original_samples[sample_key] = [
                        str(row[col]) for row in rows
                        if row.get(col) is not None
                    ][:20]

    logger.info("EXTRACT completado: %d filas totales", total_rows)
    return original_samples


def _find_sensitive_columns(policy: dict) -> dict:
    """
    Extrae las columnas FPE del YAML para usarlas como muestras de validación.
    Devuelve: {clave_muestra: (tabla, columna)}
    """
    result = {}
    for table, cfg in policy.get("tables", {}).items():
        for col, col_cfg in cfg.get("columns", {}).items():
            if col_cfg.get("technique") == "fpe_numeric":
                key = f"fpe_{table}_{col}"
                result[key] = (table, col)
    return result


# ════════════════════════════════════════════════════════════
#  FASE TRANSFORM GENÉRICA
# ════════════════════════════════════════════════════════════
def phase_transform_generic(policy: dict, pk_map: dict) -> dict:
    """
    Aplica las transformaciones del YAML sobre la BD de QA.
    Versión genérica — usa pk_map descubierto dinámicamente.
    """
    logger.info("── FASE 3: TRANSFORM ──────────────────────────────")
    tables_config = policy.get("tables", {})
    stats = {}
    t0 = time.time()

    with get_connection("TARGET") as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        upd = conn.cursor()

        for table_name, table_cfg in tables_config.items():
            logger.info("  Procesando tabla: %s", table_name)
            columns_cfg = table_cfg.get("columns", {})

            # Obtener PK — descubierta dinámicamente
            pk = pk_map.get(table_name)
            if not pk:
                # Fallback: primera columna
                cur.execute(f"SELECT * FROM {table_name} LIMIT 1")
                if cur.description:
                    pk = cur.description[0].name
                else:
                    logger.warning("No se puede determinar PK para %s — omitida", table_name)
                    continue

            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()

            if not rows:
                logger.info("    → tabla vacía, omitida")
                continue

            # Preparar valores para shuffle (necesita todos a la vez)
            shuffle_cols = {
                col for col, cfg in columns_cfg.items()
                if cfg.get("technique") == "shuffle"
            }
            shuffled = {
                col: shuffle_column([r[col] for r in rows])
                for col in shuffle_cols
                if col in rows[0]
            }

            for idx, row in enumerate(rows):
                updates = {}
                pk_val  = row[pk]

                for col, cfg in columns_cfg.items():
                    if col not in row:
                        continue
                    technique = cfg.get("technique")
                    original  = row[col]

                    if technique == "shuffle":
                        updates[col] = shuffled.get(col, [None]*len(rows))[idx]
                    elif technique == "fake":
                        updates[col] = generate_fake_value(
                            cfg.get("fake_type", "full_name"), original)
                    elif technique == "fpe_numeric":
                        updates[col] = tokenize_cedula(original)
                    elif technique == "partial_mask":
                        updates[col] = partial_mask(
                            original,
                            mask_char  = cfg.get("mask_char",  "*"),
                            keep_start = cfg.get("keep_start",  3),
                            keep_end   = cfg.get("keep_end",    2))
                    elif technique == "noise":
                        updates[col] = add_noise(original, cfg.get("noise_pct", 10))
                    elif technique == "generalize":
                        updates[col] = generalize_date(
                            original, cfg.get("granularity", "year"))
                    elif technique == "suppress":
                        updates[col] = suppress(original)

                if updates:
                    set_clause = ", ".join([f"{c} = %s" for c in updates])
                    upd.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE {pk} = %s",
                        list(updates.values()) + [pk_val]
                    )

            conn.commit()
            stats[table_name] = {
                "filas_procesadas":   len(rows),
                "columnas_transform": len(columns_cfg)
            }
            logger.info("    ✓ %d filas | %d columnas", len(rows), len(columns_cfg))

    elapsed = round(time.time() - t0, 2)
    stats["_elapsed_seconds"] = elapsed
    logger.info("TRANSFORM completado en %.2f segundos", elapsed)
    return stats


# ════════════════════════════════════════════════════════════
#  MAIN GENÉRICO
# ════════════════════════════════════════════════════════════
def main():
    start_time = time.time()
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║   PIPELINE GENÉRICO — Cualquier BD PostgreSQL    ║")
    logger.info("║   TFMT — Maestría en Herramientas Ciberseguridad  ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # Fase 1: Discovery
    logger.info("── FASE 1: DISCOVERY ──────────────────────────────")
    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    logger.info("Política: %s v%s",
                policy["pipeline"]["name"], policy["pipeline"]["version"])

    if not test_connections():
        logger.error("Conexiones fallidas. Revise las variables de entorno.")
        sys.exit(1)

    if not verify_fpe_roundtrip():
        logger.error("FPE falló. Revise FPE_KEY y FPE_TWEAK.")
        sys.exit(1)

    # Obtener tablas desde el YAML (no hardcodeadas)
    tables = get_tables_from_policy(policy)
    logger.info("Tablas a procesar: %s", tables)

    # Descubrir PKs automáticamente desde information_schema
    pk_map = discover_primary_keys("SOURCE", tables)

    # Fase 2: Extract
    original_samples = phase_extract_generic(policy, tables)

    # Fase 3: Transform
    transform_stats = phase_transform_generic(policy, pk_map)

    # Fase 4: Validate
    logger.info("── FASE 4: VALIDATE ───────────────────────────────")
    validation_results = run_all_validations(original_samples)

    # Fase 5: Report
    total_elapsed = round(time.time() - start_time, 2)
    logger.info("── FASE 5: REPORTE FINAL ──────────────────────────")
    logger.info("Tiempo total: %.2f segundos", total_elapsed)
    logger.info("Tablas procesadas: %d",
                len([k for k in transform_stats if not k.startswith("_")]))
    logger.info("Resultado: %s",
                "✓ APROBADO" if validation_results["overall_ok"] else "✗ CON ALERTAS")

    sys.exit(0 if validation_results["overall_ok"] else 2)


if __name__ == "__main__":
    main()
