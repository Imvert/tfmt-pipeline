# Guía de Integración CI/CD — Pipeline de Anonimización
## TFMT — Maestría en Herramientas de Ciberseguridad

---

## Objetivo

Esta guía describe cómo integrar el pipeline de anonimización y tokenización
como un paso obligatorio dentro de un flujo de Integración Continua/Despliegue
Continuo (CI/CD), utilizando **GitHub Actions** como herramienta de orquestación.

El pipeline se ejecuta automáticamente cada vez que se realiza un respaldo
(*backup*) de la base de datos de producción y debe completarse exitosamente
antes de que el entorno de QA sea accesible para el equipo de pruebas.

---

## Arquitectura del flujo CI/CD

```
Backup PROD  →  Trigger GitHub Actions  →  Pipeline Anonimización
     ↓                                           ↓
Copia BD PROD                           Validación (IIR + FPE)
     ↓                                           ↓
                                        ✓ APROBADO → QA habilitado
                                        ✗ ALERTAS  → QA bloqueado
```

---

## Archivo de workflow — GitHub Actions

Crea el archivo `.github/workflows/anonymization_pipeline.yml`
en tu repositorio con el siguiente contenido:

```yaml
name: Pipeline de Anonimización QA

# ── Disparadores (triggers) ────────────────────────────────
on:
  # 1. Ejecución manual desde la interfaz de GitHub
  workflow_dispatch:
    inputs:
      environment:
        description: 'Ambiente destino'
        required: true
        default: 'qa'
        type: choice
        options: [qa, staging]

  # 2. Automático: cada vez que se sube un backup a la rama main
  push:
    branches: [main]
    paths:
      - 'backups/**.sql'
      - 'backups/**.dump'

  # 3. Programado: todos los lunes a las 02:00 UTC
  schedule:
    - cron: '0 2 * * 1'

# ── Variables de entorno globales ──────────────────────────
env:
  PYTHON_VERSION: '3.12'
  POSTGRES_VERSION: '15'

jobs:

  # ── JOB 1: Verificación previa ─────────────────────────
  pre_check:
    name: Verificación de prerequisitos
    runs-on: ubuntu-latest
    steps:
      - name: Checkout del repositorio
        uses: actions/checkout@v4

      - name: Verificar archivos de política
        run: |
          test -f config/anonymization_policy.yaml || \
            (echo "ERROR: Falta archivo de política YAML" && exit 1)
          test -f pipeline/orchestrator.py || \
            (echo "ERROR: Falta orquestador Python" && exit 1)
          echo "✓ Archivos de política verificados"

  # ── JOB 2: Ejecución del pipeline ──────────────────────
  run_pipeline:
    name: Ejecutar Pipeline de Anonimización
    runs-on: ubuntu-latest
    needs: pre_check

    # Servicios Docker para las BDs
    services:
      db_produccion:
        image: postgres:15-alpine
        env:
          POSTGRES_DB:       northwind_prod
          POSTGRES_USER:     prod_user
          POSTGRES_PASSWORD: ${{ secrets.PROD_DB_PASSWORD }}
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      db_qa:
        image: postgres:15-alpine
        env:
          POSTGRES_DB:       northwind_qa
          POSTGRES_USER:     qa_user
          POSTGRES_PASSWORD: ${{ secrets.QA_DB_PASSWORD }}
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout del repositorio
        uses: actions/checkout@v4

      - name: Configurar Python ${{ env.PYTHON_VERSION }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Cargar datos de producción
        run: |
          psql -h localhost -p 5432 -U prod_user -d northwind_prod \
            -f sql/01_northwind_schema.sql
          psql -h localhost -p 5432 -U prod_user -d northwind_prod \
            -f sql/02_northwind_data.sql
          echo "✓ Base de datos de producción cargada"
        env:
          PGPASSWORD: ${{ secrets.PROD_DB_PASSWORD }}

      - name: Ejecutar pipeline de anonimización
        run: python -m pipeline.orchestrator
        env:
          SOURCE_HOST:     localhost
          SOURCE_PORT:     5432
          SOURCE_DB:       northwind_prod
          SOURCE_USER:     prod_user
          SOURCE_PASSWORD: ${{ secrets.PROD_DB_PASSWORD }}
          TARGET_HOST:     localhost
          TARGET_PORT:     5433
          TARGET_DB:       northwind_qa
          TARGET_USER:     qa_user
          TARGET_PASSWORD: ${{ secrets.QA_DB_PASSWORD }}
          FPE_KEY:         ${{ secrets.FPE_KEY }}
          FPE_TWEAK:       ${{ secrets.FPE_TWEAK }}

      - name: Guardar reporte de validación
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pipeline-report-${{ github.run_number }}
          path: logs/
          retention-days: 30

  # ── JOB 3: Notificación de resultado ───────────────────
  notify:
    name: Notificar resultado
    runs-on: ubuntu-latest
    needs: run_pipeline
    if: always()
    steps:
      - name: Notificar éxito
        if: needs.run_pipeline.result == 'success'
        run: |
          echo "✓ Pipeline completado. Entorno QA habilitado."
          echo "El equipo de QA puede acceder al ambiente."

      - name: Bloquear QA si pipeline falló
        if: needs.run_pipeline.result == 'failure'
        run: |
          echo "✗ Pipeline falló. Entorno QA BLOQUEADO."
          echo "Revisar logs antes de autorizar acceso."
          exit 1
```

---

## Configuración de secretos en GitHub

Los valores sensibles nunca se almacenan en el código. Se configuran
como **Secrets** en GitHub:

1. Ve a tu repositorio → **Settings** → **Secrets and variables** → **Actions**
2. Agrega los siguientes secretos:

| Nombre del secreto | Descripción |
|---|---|
| `PROD_DB_PASSWORD` | Contraseña de la BD de producción |
| `QA_DB_PASSWORD` | Contraseña de la BD de QA |
| `FPE_KEY` | Clave de 32 caracteres hex para FPE |
| `FPE_TWEAK` | Tweak para el cifrado FPE |

---

## Ejecución manual del workflow

Para disparar el pipeline manualmente:

1. Ve a tu repositorio en GitHub
2. Haz clic en la pestaña **Actions**
3. Selecciona **Pipeline de Anonimización QA**
4. Haz clic en **Run workflow**
5. Selecciona el ambiente destino (`qa` o `staging`)
6. Haz clic en **Run workflow**

---

## Verificación del resultado

Después de cada ejecución puedes verificar:

- **Estado del job**: verde (✓) si el pipeline pasó todas las validaciones
- **Logs**: descargables desde la pestaña Actions → run → artefactos
- **Reporte**: archivo ZIP con los logs detallados de cada fase

Si el pipeline termina con estado **✗ CON ALERTAS**, el job falla y
GitHub bloquea automáticamente cualquier despliegue que dependa de este
workflow, evitando que el equipo de QA acceda a datos sin proteger.

---

## Integración con otros sistemas CI/CD

El mismo principio aplica para otras herramientas:

| Herramienta | Archivo de configuración |
|---|---|
| GitHub Actions | `.github/workflows/anonymization_pipeline.yml` |
| GitLab CI/CD | `.gitlab-ci.yml` |
| Jenkins | `Jenkinsfile` |
| Azure DevOps | `azure-pipelines.yml` |

En todos los casos, el pipeline de anonimización debe configurarse como
una **puerta de calidad** (*quality gate*) que bloquea el aprovisionamiento
del entorno de QA si las validaciones de seguridad no son superadas.
