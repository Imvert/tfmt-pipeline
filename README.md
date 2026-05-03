# Pipeline de Anonimización y Tokenización — TFMT

**Maestría Tecnológica en Herramientas de Ciberseguridad**
Autor: Pilatuña López Luis Alexander

\---

## Requisitos previos

|Herramienta|Versión mínima|Verificar con|
|-|-|-|
|Docker Desktop|24.x|`docker --version`|
|Docker Compose|2.x|`docker compose version`|
|Python (opcional, local)|3.12|`python --version`|

\---

## Estructura del proyecto

```
tfmt-pipeline/
├── docker-compose.yml          # Orquestación de contenedores
├── requirements.txt            # Dependencias Python
├── docker/
│   ├── Dockerfile.pipeline     # Imagen del pipeline
│   └── pgadmin\_servers.json    # Config pgAdmin
├── sql/
│   ├── 01\_northwind\_schema.sql # Esquema de la BD
│   └── 02\_northwind\_data.sql   # Datos de demostración
├── config/
│   └── anonymization\_policy.yaml  # Política (Policy-as-Code)
├── pipeline/
│   ├── \_\_init\_\_.py
│   ├── connector.py            # Conectividad PostgreSQL
│   ├── anonymizer.py           # Técnicas de enmascaramiento
│   ├── tokenizer.py            # FPE (Format-Preserving Encryption)
│   ├── validator.py            # Validaciones post-transformación
│   └── orchestrator.py        # Orquestador principal
└── logs/                       # Logs generados automáticamente
```

\---

## Pasos de instalación y ejecución

### PASO 1 — Levantar las bases de datos

```bash
docker compose up db\_produccion db\_qa pgadmin -d
```

**Esperar \~20 segundos** hasta que los healthchecks pasen.

**▶ CAPTURA 1:** Ejecutar y capturar:

```bash
docker compose ps
```

Debe mostrar `db\_produccion`, `db\_qa` y `pgadmin` con status `healthy`.

\---

### PASO 2 — Verificar datos en PRODUCCIÓN (antes del pipeline)

Abrir pgAdmin en el navegador: **http://localhost:5050**

* Usuario: `admin@tfmt.local`
* Contraseña: `admin123`

Conectarse al servidor **PRODUCCION (northwind\_prod)** y ejecutar:

```sql
-- Ver datos sensibles ANTES de anonimizar
SELECT customer\_id, contact\_name, cedula, email, phone, credit\_limit
FROM customers
ORDER BY customer\_id;
```

\---

### PASO 3 — Ejecutar el pipeline de anonimización

```bash
docker compose --profile run up pipeline
```

O también se puede ejecutar localmente con Python:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export SOURCE\_HOST=localhost  SOURCE\_PORT=5432  SOURCE\_DB=northwind\_prod
export SOURCE\_USER=prod\_user  SOURCE\_PASSWORD=prod\_secret\_2024
export TARGET\_HOST=localhost  TARGET\_PORT=5433  TARGET\_DB=northwind\_qa
export TARGET\_USER=qa\_user    TARGET\_PASSWORD=qa\_secret\_2024
export FPE\_KEY=6f8b3d2a1e9c4f7b0d5a2e8c3f6b9d1a  FPE\_TWEAK=tfmt2024

# Ejecutar
python -m pipeline.orchestrator
```

\---

### PASO 4 — Verificar datos en QA (después del pipeline)

En pgAdmin, conectarse ahora a **QA (northwind\_qa)** y ejecutar:

```sql
-- Ver datos DESPUÉS de anonimizar (misma query)
SELECT customer\_id, contact\_name, cedula, email, phone, credit\_limit
FROM customers
ORDER BY customer\_id;
```



```sql
-- Comparar employee\_id=1 antes y después en la misma pantalla
SELECT employee\_id, first\_name, last\_name, cedula,
       salary, email, birth\_date
FROM employees
ORDER BY employee\_id;
```



\---

### PASO 5 — Verificar integridad referencial

```sql
-- En northwind\_qa: verificar que los pedidos aún apuntan a clientes válidos
SELECT o.order\_id, o.customer\_id, c.contact\_name, c.cedula,
       COUNT(od.product\_id) AS productos
FROM orders o
JOIN customers c ON o.customer\_id = c.customer\_id
JOIN order\_details od ON o.order\_id = od.order\_id
GROUP BY o.order\_id, o.customer\_id, c.contact\_name, c.cedula
ORDER BY o.order\_id;
```



\---

### PASO 6 — Demostración de consistencia del token FPE

```sql
-- Verificar que el mismo cliente tiene el MISMO token en todas las tablas
SELECT 'customers' AS tabla, customer\_id, cedula FROM customers WHERE customer\_id = 'ALFKI'
UNION ALL
SELECT 'orders\_via\_customer', o.customer\_id, c.cedula
FROM orders o JOIN customers c ON o.customer\_id = c.customer\_id
WHERE o.customer\_id = 'ALFKI'
LIMIT 5;
```



\---

### PASO 7 — Demostrar que el dato original no existe en QA

```sql
SELECT COUNT(\*) AS cedulas\_originales\_encontradas
FROM customers
WHERE cedula IN (
  '1712345678','0924567890','0102345678','1756789012',
  '1723456789','1812345678','0612345678','0934567890',
  '1045678901','1312345678','1789012345','0156789012'
);
```

\---

## Automatización con GitHub Actions (CI/CD)

El pipeline incluye un *workflow* configurado en `.github/workflows/anonymization_pipeline.yml`
que ejecuta automáticamente todo el flujo de anonimización en la nube de GitHub.

### Disparadores configurados

- **Manual** (`workflow_dispatch`): desde la pestaña Actions del repositorio
- **Automático** (`push`): al subir un nuevo backup de producción
- **Programado** (`schedule`): todos los lunes a las 02:00 UTC

### Configuración de Secrets en GitHub

En tu repositorio, ve a **Settings → Secrets and variables → Actions**
y agrega los siguientes secretos:

| Secreto | Descripción |
|---|---|
| `PROD_DB_PASSWORD` | Contraseña de la BD de producción |
| `QA_DB_PASSWORD` | Contraseña de la BD de QA |
| `FPE_KEY` | Clave hex de 32 caracteres para FPE |
| `FPE_TWEAK` | Tweak para el cifrado FPE |

### Ejecutar el workflow

1. Ve a la pestaña **Actions** del repositorio
2. Selecciona **Pipeline de Anonimización QA**
3. Clic en **Run workflow** → seleccionar ambiente → **Run workflow**

El workflow descarga el reporte de validación como artefacto descargable
durante 30 días, sirviendo como evidencia de auditoría LOPDP.

---

## Detener el entorno

```bash
docker compose down          # Detiene contenedores (datos persisten)
docker compose down -v       # Detiene Y elimina volúmenes (reset completo)
```

