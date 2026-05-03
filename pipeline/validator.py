"""
validator.py
Módulo de validación post-transformación.

Verifica que el pipeline cumplió con sus objetivos de seguridad:
  1. Integridad referencial: no existen registros huérfanos
  2. Ausencia de originales: ningún dato sensible permanece sin transformar
  3. K-anonimato: los registros no son re-identificables individualmente
"""

import logging
from typing import Dict, Any

import psycopg2

from .connector import get_connection

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  1. INTEGRIDAD REFERENCIAL
# ────────────────────────────────────────────────────────────
def check_referential_integrity() -> Dict[str, Any]:
    """
    Verifica que no existan registros huérfanos en la BD de QA.

    Fórmula del IIR (Índice de Integridad Referencial):
        IIR = registros_válidos / total_registros

    El valor aceptable es 1.0 (100% integridad).

    Returns:
        Dict con resultados por tabla y el IIR calculado
    """
    checks = [
        {
            "name": "orders → customers",
            "sql": """
                SELECT COUNT(*) FROM orders o
                LEFT JOIN customers c ON o.customer_id = c.customer_id
                WHERE c.customer_id IS NULL
            """
        },
        {
            "name": "orders → employees",
            "sql": """
                SELECT COUNT(*) FROM orders o
                LEFT JOIN employees e ON o.employee_id = e.employee_id
                WHERE e.employee_id IS NULL
            """
        },
        {
            "name": "order_details → orders",
            "sql": """
                SELECT COUNT(*) FROM order_details od
                LEFT JOIN orders o ON od.order_id = o.order_id
                WHERE o.order_id IS NULL
            """
        },
        {
            "name": "order_details → products",
            "sql": """
                SELECT COUNT(*) FROM order_details od
                LEFT JOIN products p ON od.product_id = p.product_id
                WHERE p.product_id IS NULL
            """
        },
        {
            "name": "products → suppliers",
            "sql": """
                SELECT COUNT(*) FROM products p
                LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
                WHERE s.supplier_id IS NULL
            """
        },
    ]

    results  = {}
    total    = 0
    orphans  = 0

    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:
            for check in checks:
                cur.execute(check["sql"])
                huerfanos = cur.fetchone()[0]
                results[check["name"]] = {
                    "huerfanos": huerfanos,
                    "ok": huerfanos == 0
                }
                orphans += huerfanos
                total   += 1

    iir = 1.0 if orphans == 0 else round((total - orphans) / total, 4)

    logger.info("IIR = %.4f | Registros huérfanos totales: %d", iir, orphans)
    for name, result in results.items():
        status = "✓" if result["ok"] else "✗"
        logger.info("  %s %s — huérfanos: %d", status, name, result["huerfanos"])

    return {"iir": iir, "orphans": orphans, "details": results}


# ────────────────────────────────────────────────────────────
#  2. VERIFICACIÓN DE AUSENCIA DE DATOS ORIGINALES
# ────────────────────────────────────────────────────────────
def check_no_originals_remain(original_samples: Dict[str, list]) -> Dict[str, Any]:
    """
    Verifica que ningún valor original sensible permanezca en la BD de QA.
    Toma una muestra de valores de producción y busca si existen en QA.

    Args:
        original_samples: Dict {tabla: [lista de cédulas/emails originales]}

    Returns:
        Dict con resultados de la verificación
    """
    results  = {}
    leaks    = 0

    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:

            # Verificar cédulas de clientes
            if "cedulas_clientes" in original_samples:
                samples = original_samples["cedulas_clientes"][:10]
                placeholders = ",".join(["%s"] * len(samples))
                cur.execute(
                    f"SELECT COUNT(*) FROM customers WHERE cedula IN ({placeholders})",
                    samples
                )
                found = cur.fetchone()[0]
                results["cedulas_clientes"] = {"encontradas": found, "ok": found == 0}
                leaks += found

            # Verificar cédulas de empleados
            if "cedulas_empleados" in original_samples:
                samples = original_samples["cedulas_empleados"][:10]
                placeholders = ",".join(["%s"] * len(samples))
                cur.execute(
                    f"SELECT COUNT(*) FROM employees WHERE cedula IN ({placeholders})",
                    samples
                )
                found = cur.fetchone()[0]
                results["cedulas_empleados"] = {"encontradas": found, "ok": found == 0}
                leaks += found

            # Verificar emails de clientes
            if "emails_clientes" in original_samples:
                samples = original_samples["emails_clientes"][:10]
                placeholders = ",".join(["%s"] * len(samples))
                cur.execute(
                    f"SELECT COUNT(*) FROM customers WHERE email IN ({placeholders})",
                    samples
                )
                found = cur.fetchone()[0]
                results["emails_clientes"] = {"encontradas": found, "ok": found == 0}
                leaks += found

    tasa = round(leaks / max(sum(len(v) for v in original_samples.values()), 1), 4)
    logger.info(
        "Tasa de re-identificación = %.4f | Datos originales encontrados: %d",
        tasa, leaks
    )
    for field, result in results.items():
        status = "✓" if result["ok"] else "✗ ALERTA"
        logger.info("  %s %s — encontrados: %d", status, field, result["encontradas"])

    return {"tasa_reidentificacion": tasa, "leaks": leaks, "details": results}


# ────────────────────────────────────────────────────────────
#  3. K-ANONIMATO
# ────────────────────────────────────────────────────────────
def check_k_anonymity(k_target: int = 5) -> Dict[str, Any]:
    """
    Evalúa el nivel de k-anonimato en la tabla customers.

    Un registro cumple k-anonimato si no puede ser distinguido
    de al menos k-1 registros con los mismos quasi-identificadores.

    Quasi-identificadores usados: city, region, country
    (fecha_nacimiento ya fue generalizada a solo año)

    Args:
        k_target: Valor mínimo de k requerido (por defecto 5)

    Returns:
        Dict con k_min encontrado y si cumple el objetivo
    """
    sql = """
        SELECT city, region, country, COUNT(*) as grupo_size
        FROM customers
        GROUP BY city, region, country
        ORDER BY grupo_size ASC
        LIMIT 5
    """
    with get_connection("TARGET") as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    if not rows:
        return {"k_min": 0, "cumple": False, "grupos_pequenos": []}

    k_min = rows[0][3] if rows else 0
    cumple = k_min >= k_target
    grupos_pequenos = [
        {"city": r[0], "region": r[1], "country": r[2], "size": r[3]}
        for r in rows if r[3] < k_target
    ]

    status = "✓" if cumple else "✗"
    logger.info(
        "%s K-anonimato: k_min=%d (objetivo: k>=%d)",
        status, k_min, k_target
    )
    if grupos_pequenos:
        logger.warning(
            "  Grupos con k < %d: %s",
            k_target,
            [f"{g['city']}({g['size']})" for g in grupos_pequenos]
        )

    return {
        "k_min":           k_min,
        "k_target":        k_target,
        "cumple":          cumple,
        "grupos_pequenos": grupos_pequenos,
    }


# ────────────────────────────────────────────────────────────
#  REPORTE FINAL
# ────────────────────────────────────────────────────────────
def run_all_validations(original_samples: Dict) -> Dict[str, Any]:
    """
    Ejecuta todas las validaciones y genera el reporte final.

    Args:
        original_samples: Muestras de datos originales de producción

    Returns:
        Dict con todos los resultados de validación
    """
    logger.info("=" * 60)
    logger.info("INICIANDO VALIDACIONES POST-TRANSFORMACIÓN")
    logger.info("=" * 60)

    ri_result  = check_referential_integrity()
    no_result  = check_no_originals_remain(original_samples)
    ka_result  = check_k_anonymity(k_target=5)

    overall_ok = (
        ri_result["iir"] == 1.0
        and no_result["leaks"] == 0
        and ka_result["cumple"]
    )

    logger.info("=" * 60)
    logger.info("RESULTADO FINAL: %s", "✓ APROBADO" if overall_ok else "✗ CON ALERTAS")
    logger.info("  IIR:                   %.4f", ri_result["iir"])
    logger.info("  Tasa re-identificación:%.4f", no_result["tasa_reidentificacion"])
    logger.info("  K-anonimato:           k_min=%d", ka_result["k_min"])
    logger.info("=" * 60)

    return {
        "overall_ok":          overall_ok,
        "integridad":          ri_result,
        "no_originales":       no_result,
        "k_anonimato":         ka_result,
    }
