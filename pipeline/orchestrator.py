"""
orchestrator.py
Orquestador principal del Pipeline de Anonimización y Tokenización.

Flujo de ejecución:
  1. Discovery  → Lee la política YAML y valida conexiones
  2. Extract    → Copia datos de PRODUCCIÓN a QA (sin transformar)
  3. Transform  → Aplica anonimización y tokenización por tabla
  4. Validate   → Verifica integridad, ausencia de originales y k-anonimato
  5. Report     → Genera resumen de la ejecución

Autor: Pilatuña López Luis Alexander
TFMT: Implementación de un pipeline automatizado de anonimización
      y tokenización para bases de datos en entornos de QA
"""

import os
import sys
import time
import logging
import yaml

import psycopg2
import psycopg2.extras

from .connector  import get_connection, test_connections, copy_schema_to_target
from .anonymizer import shuffle_column, generate_fake_value, partial_mask, \
                        add_noise, generalize_date, suppress
from .tokenizer  import tokenize_cedula, verify_fpe_roundtrip
from .validator  import run_all_validations

# ── Configuración de logging ────────────────────────────────
try:
    import colorlog
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            "DEBUG":    "cyan",
            "INFO":     "green",
            "WARNING":  "yellow",
            "ERROR":    "red",
            "CRITICAL": "red,bg_white",
        }
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

logger = logging.getLogger("orchestrator")

# Técnicas delegadas al motor SQL (ejecutadas por Stored Procedures o UDFs)
# El resto (fpe_numeric, fake, shuffle) las ejecuta Python directamente
SQL_TECHNIQUES = {"noise", "partial_mask", "generalize", "suppress"}

# ── Ruta al archivo de política YAML ───────────────────────
POLICY_FILE = os.path.join(
    os.path.dirname(__file__), "..", "config", "anonymization_policy.yaml"
)


# ════════════════════════════════════════════════════════════
#  FASE 1: DISCOVERY — Cargar política y validar entorno
# ════════════════════════════════════════════════════════════
def phase_discovery() -> dict:
    """Carga la política YAML y valida las conexiones a BD."""
    logger.info("── FASE 1: DISCOVERY ──────────────────────────────")

    # Cargar política
    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    logger.info("Política cargada: %s v%s",
                policy["pipeline"]["name"],
                policy["pipeline"]["version"])

    # Verificar conexiones
    if not test_connections():
        logger.error("No se pudo establecer conexión con las bases de datos.")
        sys.exit(1)

    # Verificar que FPE funciona correctamente
    if not verify_fpe_roundtrip():
        logger.error("Fallo en verificación FPE. Revise FPE_KEY y FPE_TWEAK.")
        sys.exit(1)

    tables_count = len(policy.get("tables", {}))
    logger.info("Tablas a procesar: %d", tables_count)
    return policy


# ════════════════════════════════════════════════════════════
#  FASE 2: EXTRACT — Copiar datos de PROD a QA
# ════════════════════════════════════════════════════════════
def phase_extract(policy: dict) -> dict:
    """
    Copia los datos originales de PRODUCCIÓN al esquema de QA.
    También captura muestras de datos sensibles para validación posterior.
    """
    logger.info("── FASE 2: EXTRACT ────────────────────────────────")
    tables_to_copy = [
        "categories", "suppliers", "shippers",
        "products", "customers", "employees",
        "orders", "order_details"
    ]

    # Recolectar muestras de valores originales (para validar después)
    original_samples = {
        "cedulas_clientes":  [],
        "cedulas_empleados": [],
        "emails_clientes":   [],
    }

    total_rows = 0
    with get_connection("SOURCE") as src_conn, \
         get_connection("TARGET") as tgt_conn:

        src_cur = src_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        tgt_cur = tgt_conn.cursor()

        # Limpiar destino y recrear schema
        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "sql", "01_northwind_schema.sql"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            tgt_cur.execute(f.read())
        tgt_conn.commit()
        logger.info("Schema recreado en BD QA")

        # Copiar tabla por tabla
        for table in tables_to_copy:
            src_cur.execute(f"SELECT * FROM {table}")
            rows = src_cur.fetchall()

            if not rows:
                logger.info("  %-20s → 0 filas (vacía)", table)
                continue

            columns     = list(rows[0].keys())
            placeholders = ",".join(["%s"] * len(columns))
            col_names    = ",".join(columns)
            insert_sql   = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

            values = [tuple(row[c] for c in columns) for row in rows]
            tgt_cur.executemany(insert_sql, values)
            tgt_conn.commit()

            total_rows += len(rows)
            logger.info("  %-20s → %d filas copiadas", table, len(rows))

            # Capturar muestras de datos sensibles
            if table == "customers":
                original_samples["cedulas_clientes"]  = [
                    r["cedula"] for r in rows if r.get("cedula")
                ]
                original_samples["emails_clientes"] = [
                    r["email"] for r in rows if r.get("email")
                ]
            elif table == "employees":
                original_samples["cedulas_empleados"] = [
                    r["cedula"] for r in rows if r.get("cedula")
                ]

    logger.info("EXTRACT completado: %d filas totales copiadas", total_rows)
    return original_samples


# ════════════════════════════════════════════════════════════
#  FASE 3: TRANSFORM — Aplicar anonimización y tokenización
# ════════════════════════════════════════════════════════════
#  FASE 3A: CARGAR STORED PROCEDURES EN BD QA
# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
#  FASE 3a: CARGAR UDFs BASE + GENERAR SPs DINÁMICAMENTE
#
#  Las UDFs base (fn_partial_mask, fn_random_noise, etc.) se
#  cargan desde el archivo SQL. Los stored procedures por tabla
#  se GENERAN DINÁMICAMENTE desde la política YAML — esto hace
#  el pipeline compatible con cualquier base de datos sin
#  modificar el código.
# ════════════════════════════════════════════════════════════
def load_stored_procedures() -> None:
    """
    Paso 1: Carga las UDFs base desde el archivo SQL.
    Paso 2: Genera dinámicamente un stored procedure por cada
            tabla definida en el YAML que tenga técnicas SQL.

    Técnicas SQL (ejecutadas por SP):
        noise, partial_mask, generalize, suppress

    Técnicas Python (ejecutadas por el orquestador):
        fpe_numeric, fake, shuffle
    """

    # ── Paso 1: Cargar UDFs base desde archivo ──────────────
    sp_path = os.path.join(
        os.path.dirname(__file__), "..", "sql", "03_masking_procedures.sql"
    )

    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:
            if os.path.exists(sp_path):
                with open(sp_path, "r", encoding="utf-8") as f:
                    cur.execute(f.read())
                logger.info("✓ UDFs base cargadas desde 03_masking_procedures.sql")
            else:
                logger.warning("Archivo SQL no encontrado — omitiendo carga de UDFs")

        conn.commit()

    # ── Paso 2: Generar SPs dinámicamente desde el YAML ─────
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "anonymization_policy.yaml"
    )
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = yaml.safe_load(f)

    tables_config = policy.get("tables", {})
    sps_created = []

    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:
            for table_name, table_cfg in tables_config.items():
                columns_cfg = table_cfg.get("columns", {})

                # Filtrar solo columnas con técnicas SQL
                sql_steps = []
                for col, cfg in columns_cfg.items():
                    technique = cfg.get("technique")
                    if technique not in SQL_TECHNIQUES:
                        continue

                    if technique == "noise":
                        pct = cfg.get("noise_pct", 10)
                        sql_steps.append(
                            f"    UPDATE {table_name} SET {col} = "
                            f"fn_random_noise({col}, {pct}) "
                            f"WHERE {col} IS NOT NULL;\n"
                            f"    RAISE NOTICE '  {col}: ruido ±{pct}%% (fn_random_noise)';"
                        )
                    elif technique == "partial_mask":
                        ks = cfg.get("keep_start", 3)
                        ke = cfg.get("keep_end", 2)
                        mc = cfg.get("mask_char", "*")
                        sql_steps.append(
                            f"    UPDATE {table_name} SET {col} = "
                            f"fn_partial_mask({col}, {ks}, {ke}, '{mc}') "
                            f"WHERE {col} IS NOT NULL;\n"
                            f"    RAISE NOTICE '  {col}: partial mask (fn_partial_mask)';"
                        )
                    elif technique == "generalize":
                        gran = cfg.get("granularity", "year")
                        sql_steps.append(
                            f"    UPDATE {table_name} SET {col} = "
                            f"fn_generalize_date({col}, '{gran}') "
                            f"WHERE {col} IS NOT NULL;\n"
                            f"    RAISE NOTICE '  {col}: generalizado a {gran} (fn_generalize_date)';"
                        )
                    elif technique == "suppress":
                        sql_steps.append(
                            f"    UPDATE {table_name} SET {col} = NULL;\n"
                            f"    RAISE NOTICE '  {col}: suprimido (NULL)';"
                        )

                if not sql_steps:
                    continue  # Tabla sin técnicas SQL — no necesita SP

                # Generar el CREATE OR REPLACE PROCEDURE dinámicamente
                sp_name = f"sp_anon_{table_name}"
                steps_sql = "\n".join(sql_steps)
                create_sp = f"""
CREATE OR REPLACE PROCEDURE {sp_name}()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'SP {sp_name}: aplicando técnicas SQL...';
{steps_sql}
    RAISE NOTICE 'SP {sp_name} completado.';
END;
$$;
"""
                cur.execute(create_sp)
                sps_created.append(sp_name)
                logger.info(
                    "  ✓ SP generado dinámicamente: %s() | %d columnas SQL",
                    sp_name, len(sql_steps)
                )

        conn.commit()

    if sps_created:
        logger.info(
            "✓ %d stored procedures generados desde política YAML: %s",
            len(sps_created), ", ".join(sps_created)
        )
    else:
        logger.info("No se generaron SPs (ninguna tabla tiene técnicas SQL en el YAML)")


# ════════════════════════════════════════════════════════════
#  FASE 3: TRANSFORM — Arquitectura híbrida Python + SQL
#
#  Distribución de responsabilidades:
#    SQL Stored Procedures → noise, partial_mask, generalize, suppress,
#                            shuffle (cuando hay SP dedicado)
#    Python (psycopg2)     → fpe_numeric (ff3), fake (Faker),
#                            shuffle genérico, orquestación
# ════════════════════════════════════════════════════════════
def phase_transform(policy: dict) -> dict:
    """
    Aplica las transformaciones definidas en la política YAML
    sobre la copia de datos en la BD de QA.

    Arquitectura híbrida:
      1. Para tablas con SP dedicado (customers, employees):
         Python ejecuta CALL sp_anonymize_X() para las técnicas SQL
         y aplica FPE/Fake directamente para las técnicas Python.
      2. Para otras tablas (suppliers, etc.):
         Python aplica todas las transformaciones directamente.
    """
    logger.info("── FASE 3: TRANSFORM ──────────────────────────────")
    logger.info("  Arquitectura: Python (FPE/Fake) + SQL Stored Procedures "
                "(noise/mask/shuffle/generalize)")

    tables_config = policy.get("tables", {})
    stats = {}
    t0 = time.time()

    # Nombre del SP generado dinámicamente para cada tabla
    # Patrón: sp_anon_{nombre_tabla} — generado en load_stored_procedures()
    def sp_name_for(table: str) -> str:
        return f"sp_anon_{table}"

    with get_connection("TARGET") as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        upd = conn.cursor()

        for table_name, table_cfg in tables_config.items():
            logger.info("  Procesando tabla: %s", table_name)
            columns_cfg = table_cfg.get("columns", {})
            pk = _get_primary_key(table_name)

            # Obtener filas para transformaciones Python
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()

            if not rows:
                logger.info("    → tabla vacía, omitida")
                continue

            # ── PASO A: Transformaciones Python (FPE + Fake + Shuffle) ──
            # Estas técnicas requieren lógica Python y se aplican fila a fila
            python_columns = {
                col: cfg for col, cfg in columns_cfg.items()
                if cfg.get("technique") not in SQL_TECHNIQUES
            }

            # Preparar shuffle (necesita todos los valores juntos)
            shuffled_values = {}
            for col, cfg in python_columns.items():
                if cfg.get("technique") == "shuffle":
                    shuffled_values[col] = shuffle_column(
                        [r[col] for r in rows]
                    )

            # Aplicar transformaciones Python fila a fila
            python_count = 0
            for idx, row in enumerate(rows):
                updates = {}
                pk_val  = row[pk]

                for col, cfg in python_columns.items():
                    technique = cfg.get("technique")
                    original  = row.get(col)

                    if technique == "shuffle":
                        updates[col] = shuffled_values[col][idx]
                    elif technique == "fake":
                        updates[col] = generate_fake_value(
                            cfg.get("fake_type", "full_name"), original)
                    elif technique == "fpe_numeric":
                        updates[col] = tokenize_cedula(original)

                if updates:
                    set_clause = ", ".join([f"{c} = %s" for c in updates])
                    upd.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE {pk} = %s",
                        list(updates.values()) + [pk_val]
                    )
                    python_count += 1

            conn.commit()

            if python_count:
                python_techs = list({
                    cfg["technique"] for cfg in python_columns.values()
                })
                logger.info(
                    "    ✓ [Python] %d filas | técnicas: %s",
                    python_count, ", ".join(python_techs)
                )

            # ── PASO B: Stored Procedure SQL dinámico
            # El SP fue generado dinámicamente en load_stored_procedures()
            # con nombre sp_anon_{tabla}
            sp_name = sp_name_for(table_name)
            sql_cols = [
                col for col, cfg in columns_cfg.items()
                if cfg.get("technique") in SQL_TECHNIQUES
            ]

            if sql_cols:
                # Verificar que el SP existe antes de llamarlo
                upd.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_proc p
                        JOIN pg_namespace n ON p.pronamespace = n.oid
                        WHERE n.nspname = 'public' AND p.proname = %s
                    )
                """, (sp_name,))
                sp_exists = upd.fetchone()[0]

                if sp_exists:
                    upd.execute(f"CALL {sp_name}()")
                    conn.commit()
                    logger.info(
                        "    ✓ [SQL SP] CALL %s() | columnas: %s",
                        sp_name, ", ".join(sql_cols)
                    )
                else:
                    # Fallback: aplicar UDFs directamente si el SP no existe
                    logger.warning(
                        "    SP %s no encontrado — aplicando UDFs directamente",
                        sp_name
                    )
                    for col, cfg in columns_cfg.items():
                        technique = cfg.get("technique")
                        if technique not in SQL_TECHNIQUES:
                            continue
                        if technique == "noise":
                            pct = cfg.get("noise_pct", 10)
                            upd.execute(f"UPDATE {table_name} SET {col} = fn_random_noise({col}, {pct}) WHERE {col} IS NOT NULL")
                        elif technique == "partial_mask":
                            ks = cfg.get("keep_start", 3)
                            ke = cfg.get("keep_end", 2)
                            upd.execute(f"UPDATE {table_name} SET {col} = fn_partial_mask({col}, {ks}, {ke}, '*') WHERE {col} IS NOT NULL")
                        elif technique == "generalize":
                            gran = cfg.get("granularity", "year")
                            upd.execute(f"UPDATE {table_name} SET {col} = fn_generalize_date({col}, '{gran}') WHERE {col} IS NOT NULL")
                        elif technique == "suppress":
                            upd.execute(f"UPDATE {table_name} SET {col} = NULL")
                        conn.commit()
                        logger.info("    ✓ [SQL UDF] %s.%s → fn_%s()", table_name, col, technique)

            stats[table_name] = {
                "filas_procesadas":   len(rows),
                "columnas_transform": len(columns_cfg),
                "python_cols": len(python_columns),
                "sql_cols": len(columns_cfg) - len(python_columns),
            }
            logger.info(
                "    ── %d columnas total: %d Python | %d SQL",
                len(columns_cfg),
                len(python_columns),
                len(columns_cfg) - len(python_columns)
            )

    elapsed = round(time.time() - t0, 2)
    logger.info("TRANSFORM completado en %.2f segundos", elapsed)
    stats["_elapsed_seconds"] = elapsed
    return stats


# ════════════════════════════════════════════════════════════
#  HELPER: obtener clave primaria de una tabla
# ════════════════════════════════════════════════════════════
def _get_primary_key(table_name: str) -> str:
    """
    Retorna el nombre de la columna PK de una tabla.
    Hardcodeado para Northwind — en producción se consultaría
    information_schema.table_constraints.
    """
    pk_map = {
        "categories":    "category_id",
        "suppliers":     "supplier_id",
        "products":      "product_id",
        "shippers":      "shipper_id",
        "customers":     "customer_id",
        "employees":     "employee_id",
        "orders":        "order_id",
        "order_details": "order_id",
    }
    return pk_map.get(table_name, "id")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════
def main():
    start_time = time.time()
    logger.info("╔══════════════════════════════════════════════════╗")
    logger.info("║   PIPELINE DE ANONIMIZACIÓN Y TOKENIZACIÓN       ║")
    logger.info("╚══════════════════════════════════════════════════╝")

    # Fase 1: Discovery
    policy = phase_discovery()

    # Fase 2: Extract (PROD → QA sin transformar)
    original_samples = phase_extract(policy)

    # Fase 3a: Cargar Stored Procedures SQL en BD QA
    logger.info("── FASE 3a: CARGA DE STORED PROCEDURES ────────────")
    load_stored_procedures()

    # Fase 3b: Transform (Python + SQL Stored Procedures)
    transform_stats = phase_transform(policy)

    # Fase 4: Validate
    logger.info("── FASE 4: VALIDATE ───────────────────────────────")
    validation_results = run_all_validations(original_samples)

    # Fase 5: Report
    total_elapsed = round(time.time() - start_time, 2)
    logger.info("── FASE 5: REPORTE FINAL ──────────────────────────")
    logger.info("Tiempo total de ejecución: %.2f segundos", total_elapsed)
    logger.info("Tablas procesadas: %d",
                len([k for k in transform_stats if not k.startswith("_")]))
    logger.info("Resultado validación: %s",
                "✓ APROBADO" if validation_results["overall_ok"] else "✗ CON ALERTAS")

    if not validation_results["overall_ok"]:
        logger.warning(
            "El pipeline terminó con alertas. Revise los logs antes de "
            "autorizar el acceso al equipo de QA."
        )
        sys.exit(2)

    logger.info("Pipeline completado exitosamente. BD de QA lista para pruebas.")
    sys.exit(0)


if __name__ == "__main__":
    main()