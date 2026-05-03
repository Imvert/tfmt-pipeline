-- ============================================================
--  LIBRERÍA DE MÁSCARAS SQL — TFMT
--  Motor: PostgreSQL 15
--  Descripción: Procedimientos almacenados y funciones (UDFs)
--               para anonimización directamente en el motor de BD.
--               Implementa Partial Masking, Random Noise y Shuffling.
-- ============================================================

-- ──────────────────────────────────────────────────────────
--  1. PARTIAL MASKING — Enmascaramiento parcial de strings
--     Enmascara los caracteres centrales con '*'
--     Ejemplo: '1712345678' → '171****678'
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_partial_mask(
    p_value      TEXT,
    p_keep_start INT  DEFAULT 3,
    p_keep_end   INT  DEFAULT 3,
    p_mask_char  CHAR DEFAULT '*'
)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_len        INT;
    v_mask_len   INT;
BEGIN
    IF p_value IS NULL OR p_value = '' THEN
        RETURN p_value;
    END IF;

    v_len := LENGTH(p_value);

    -- Si el valor es más corto que los caracteres a preservar, enmascarar todo
    IF v_len <= (p_keep_start + p_keep_end) THEN
        RETURN REPEAT(p_mask_char, v_len);
    END IF;

    v_mask_len := v_len - p_keep_start - p_keep_end;

    RETURN SUBSTRING(p_value, 1, p_keep_start)
        || REPEAT(p_mask_char, v_mask_len)
        || SUBSTRING(p_value, v_len - p_keep_end + 1, p_keep_end);
END;
$$;

COMMENT ON FUNCTION fn_partial_mask IS
    'Enmascara caracteres centrales de un string. Usado para teléfonos y contratos.';

-- Ejemplos de uso:
-- SELECT fn_partial_mask('1712345678', 3, 3, '*');  → '171****678'
-- SELECT fn_partial_mask('022-345-6789', 3, 2, '*'); → '022-*****89'
-- SELECT fn_partial_mask('ana.alfaro@empresa.ec', 3, 5, '*'); → 'ana***************sa.ec'


-- ──────────────────────────────────────────────────────────
--  2. RANDOM NOISE — Ruido estadístico en valores numéricos
--     Aplica variación aleatoria de ±N% al valor original
--     Preserva la distribución estadística de la columna
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_random_noise(
    p_value     NUMERIC,
    p_noise_pct NUMERIC DEFAULT 10.0
)
RETURNS NUMERIC
LANGUAGE plpgsql
AS $$
DECLARE
    v_factor NUMERIC;
BEGIN
    IF p_value IS NULL THEN
        RETURN NULL;
    END IF;

    -- Factor de variación aleatoria entre (1 - pct/100) y (1 + pct/100)
    v_factor := 1.0 + (RANDOM() * 2 - 1) * (p_noise_pct / 100.0);

    RETURN ROUND((p_value * v_factor)::NUMERIC, 2);
END;
$$;

COMMENT ON FUNCTION fn_random_noise IS
    'Aplica ruido estadístico de ±N% a valores numéricos. Usado para salarios y montos.';

-- Ejemplos de uso:
-- SELECT fn_random_noise(2800.00, 15);  → valor entre 2380.00 y 3220.00
-- SELECT fn_random_noise(15000.00, 10); → valor entre 13500.00 y 16500.00


-- ──────────────────────────────────────────────────────────
--  3. SHUFFLING — Barajado de valores entre filas
--     Reasigna valores de una columna de forma aleatoria
--     entre las filas de la tabla (Fisher-Yates en SQL)
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_shuffle_column(
    p_table_name  TEXT,
    p_column_name TEXT,
    p_pk_column   TEXT DEFAULT 'id'
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_sql TEXT;
BEGIN
    -- Construye un UPDATE que reasigna valores de forma aleatoria
    -- usando ROW_NUMBER() con ORDER BY RANDOM() para el barajado
    v_sql := FORMAT('
        WITH ranked_original AS (
            SELECT %I AS pk_val,
                   %I AS original_val,
                   ROW_NUMBER() OVER (ORDER BY %I) AS rn_original
            FROM %I
        ),
        ranked_shuffled AS (
            SELECT %I AS pk_val,
                   ROW_NUMBER() OVER (ORDER BY RANDOM()) AS rn_shuffled
            FROM %I
        ),
        mapping AS (
            SELECT rs.pk_val,
                   ro.original_val AS new_val
            FROM ranked_shuffled rs
            JOIN ranked_original ro ON rs.rn_shuffled = ro.rn_original
        )
        UPDATE %I t
        SET %I = m.new_val
        FROM mapping m
        WHERE t.%I = m.pk_val
    ',
        p_pk_column, p_column_name, p_pk_column, p_table_name,
        p_pk_column, p_table_name,
        p_table_name, p_column_name, p_pk_column
    );

    EXECUTE v_sql;
END;
$$;

COMMENT ON FUNCTION fn_shuffle_column IS
    'Baraja los valores de una columna entre filas. Irreversible. Usado para nombres y direcciones.';

-- Ejemplo de uso:
-- SELECT fn_shuffle_column('customers', 'contact_name', 'customer_id');
-- SELECT fn_shuffle_column('employees', 'address',      'employee_id');


-- ──────────────────────────────────────────────────────────
--  4. SUPPRESS — Supresión de valores (NULL)
--     Elimina el valor de una columna completa
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_suppress(
    p_table_name  TEXT,
    p_column_name TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    EXECUTE FORMAT('UPDATE %I SET %I = NULL', p_table_name, p_column_name);
END;
$$;

COMMENT ON FUNCTION fn_suppress IS
    'Suprime (NULL) todos los valores de una columna. Usado para datos de muy alto riesgo.';

-- Ejemplo de uso:
-- SELECT fn_suppress('customers', 'fecha_nacimiento');


-- ──────────────────────────────────────────────────────────
--  5. GENERALIZE DATE — Generalización de fechas
--     Reduce granularidad: fecha exacta → primer día del año
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION fn_generalize_date(
    p_date      DATE,
    p_precision TEXT DEFAULT 'year'
)
RETURNS DATE
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF p_date IS NULL THEN
        RETURN NULL;
    END IF;

    IF p_precision = 'year' THEN
        -- Conserva solo el año: 1982-03-15 → 1982-01-01
        RETURN DATE_TRUNC('year', p_date)::DATE;
    ELSIF p_precision = 'month' THEN
        -- Conserva año y mes: 1982-03-15 → 1982-03-01
        RETURN DATE_TRUNC('month', p_date)::DATE;
    ELSE
        RETURN p_date;
    END IF;
END;
$$;

COMMENT ON FUNCTION fn_generalize_date IS
    'Reduce granularidad de fecha. year: conserva solo el año. month: conserva año y mes.';

-- Ejemplos de uso:
-- SELECT fn_generalize_date('1982-03-15', 'year');  → 1982-01-01
-- SELECT fn_generalize_date('1982-03-15', 'month'); → 1982-03-01


-- ──────────────────────────────────────────────────────────
--  6. STORED PROCEDURE PRINCIPAL — Anonimizar tabla customers
--     Aplica todas las transformaciones de una sola llamada
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_anonymize_customers()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Iniciando anonimización de tabla customers...';

    -- Paso 1: Tokenización FPE de cédula (ejecutada desde Python)
    -- La cédula se tokeniza desde el orquestador Python con ff3
    -- porque SQL no tiene implementación nativa de FPE/FF3-1

    -- Paso 2: Barajado de nombres (Shuffling)
    PERFORM fn_shuffle_column('customers', 'contact_name', 'customer_id');
    RAISE NOTICE '  contact_name: shuffling aplicado';

    -- Paso 3: Enmascaramiento parcial de teléfonos
    UPDATE customers
    SET phone = fn_partial_mask(phone, 3, 2, '*')
    WHERE phone IS NOT NULL;
    RAISE NOTICE '  phone: partial masking aplicado';

    -- Paso 4: Generalización de fecha de nacimiento
    UPDATE customers
    SET fecha_nacimiento = fn_generalize_date(fecha_nacimiento, 'year')
    WHERE fecha_nacimiento IS NOT NULL;
    RAISE NOTICE '  fecha_nacimiento: generalizada al año';

    -- Paso 5: Ruido estadístico en límite de crédito (±15%)
    UPDATE customers
    SET credit_limit = fn_random_noise(credit_limit, 15)
    WHERE credit_limit IS NOT NULL;
    RAISE NOTICE '  credit_limit: ruido estadístico ±15%% aplicado';

    RAISE NOTICE 'Anonimización de customers completada.';
END;
$$;

COMMENT ON PROCEDURE sp_anonymize_customers IS
    'Aplica todas las transformaciones de anonimización sobre la tabla customers en QA.';


-- ──────────────────────────────────────────────────────────
--  7. STORED PROCEDURE PRINCIPAL — Anonimizar tabla employees
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_anonymize_employees()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Iniciando anonimización de tabla employees...';

    -- Paso 1: Barajado de dirección domiciliaria
    PERFORM fn_shuffle_column('employees', 'address', 'employee_id');
    RAISE NOTICE '  address: shuffling aplicado';

    -- Paso 2: Enmascaramiento parcial de teléfono
    UPDATE employees
    SET home_phone = fn_partial_mask(home_phone, 3, 2, '*')
    WHERE home_phone IS NOT NULL;
    RAISE NOTICE '  home_phone: partial masking aplicado';

    -- Paso 3: Generalización de fecha de nacimiento
    UPDATE employees
    SET birth_date = fn_generalize_date(birth_date, 'year')
    WHERE birth_date IS NOT NULL;
    RAISE NOTICE '  birth_date: generalizada al año';

    -- Paso 4: Ruido estadístico en salario (±20%)
    UPDATE employees
    SET salary = fn_random_noise(salary, 20)
    WHERE salary IS NOT NULL;
    RAISE NOTICE '  salary: ruido estadístico ±20%% aplicado';

    RAISE NOTICE 'Anonimización de employees completada.';
END;
$$;

-- ──────────────────────────────────────────────────────────
--  8. VISTA DE AUDITORÍA — Verifica integridad post-transform
-- ──────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_audit_integrity AS
SELECT
    'orders→customers' AS relacion,
    COUNT(*) FILTER (
        WHERE c.customer_id IS NULL
    ) AS registros_huerfanos,
    COUNT(*) AS total_registros
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id

UNION ALL

SELECT
    'orders→employees',
    COUNT(*) FILTER (WHERE e.employee_id IS NULL),
    COUNT(*)
FROM orders o
LEFT JOIN employees e ON o.employee_id = e.employee_id

UNION ALL

SELECT
    'order_details→orders',
    COUNT(*) FILTER (WHERE ord.order_id IS NULL),
    COUNT(*)
FROM order_details od
LEFT JOIN orders ord ON od.order_id = ord.order_id

UNION ALL

SELECT
    'order_details→products',
    COUNT(*) FILTER (WHERE p.product_id IS NULL),
    COUNT(*)
FROM order_details od
LEFT JOIN products p ON od.product_id = p.product_id;

COMMENT ON VIEW vw_audit_integrity IS
    'Vista de auditoría: verifica integridad referencial post-transformación. IIR = 1 si huerfanos = 0.';

-- Uso: SELECT * FROM vw_audit_integrity;
