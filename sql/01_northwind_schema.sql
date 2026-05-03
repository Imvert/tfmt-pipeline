-- ============================================================
--  NORTHWIND ADAPTADO PARA TFMT
--  Motor: PostgreSQL 15
--  Descripción: Schema con campos sensibles para demostrar
--               el pipeline de anonimización y tokenización
-- ============================================================

-- Limpiar si existe
DROP TABLE IF EXISTS order_details     CASCADE;
DROP TABLE IF EXISTS orders            CASCADE;
DROP TABLE IF EXISTS customers         CASCADE;
DROP TABLE IF EXISTS employees         CASCADE;
DROP TABLE IF EXISTS products          CASCADE;
DROP TABLE IF EXISTS categories        CASCADE;
DROP TABLE IF EXISTS suppliers         CASCADE;
DROP TABLE IF EXISTS shippers          CASCADE;

-- ──────────────────────────────────────────────────────────
--  CATEGORÍAS DE PRODUCTOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE categories (
    category_id   SERIAL PRIMARY KEY,
    category_name VARCHAR(50)  NOT NULL,
    description   TEXT
);

-- ──────────────────────────────────────────────────────────
--  PROVEEDORES
-- ──────────────────────────────────────────────────────────
CREATE TABLE suppliers (
    supplier_id   SERIAL PRIMARY KEY,
    company_name  VARCHAR(80)  NOT NULL,
    contact_name  VARCHAR(60),
    contact_title VARCHAR(60),
    address       VARCHAR(120),
    city          VARCHAR(40),
    region        VARCHAR(40),
    postal_code   VARCHAR(10),
    country       VARCHAR(30),
    phone         VARCHAR(24),
    email         VARCHAR(80)   -- Campo sensible
);

-- ──────────────────────────────────────────────────────────
--  PRODUCTOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE products (
    product_id        SERIAL PRIMARY KEY,
    product_name      VARCHAR(80)    NOT NULL,
    supplier_id       INT            REFERENCES suppliers(supplier_id),
    category_id       INT            REFERENCES categories(category_id),
    quantity_per_unit VARCHAR(20),
    unit_price        NUMERIC(10,2)  DEFAULT 0,
    units_in_stock    SMALLINT       DEFAULT 0,
    discontinued      BOOLEAN        DEFAULT FALSE
);

-- ──────────────────────────────────────────────────────────
--  TRANSPORTISTAS
-- ──────────────────────────────────────────────────────────
CREATE TABLE shippers (
    shipper_id    SERIAL PRIMARY KEY,
    company_name  VARCHAR(40) NOT NULL,
    phone         VARCHAR(24)
);

-- ──────────────────────────────────────────────────────────
--  CLIENTES  ← Tabla con más datos sensibles
-- ──────────────────────────────────────────────────────────
CREATE TABLE customers (
    customer_id    CHAR(5)      PRIMARY KEY,
    company_name   VARCHAR(80)  NOT NULL,
    contact_name   VARCHAR(60),           -- SENSIBLE: nombre real
    contact_title  VARCHAR(60),
    address        VARCHAR(120),          -- SENSIBLE: dirección
    city           VARCHAR(40),
    region         VARCHAR(40),
    postal_code    VARCHAR(10),
    country        VARCHAR(30),
    phone          VARCHAR(24),           -- SENSIBLE: teléfono
    email          VARCHAR(80),           -- SENSIBLE: correo electrónico
    cedula         CHAR(10),              -- SENSIBLE: cédula ecuatoriana
    fecha_nacimiento DATE,                -- SENSIBLE: fecha de nacimiento
    credit_limit   NUMERIC(12,2)          -- SENSIBLE: límite de crédito
);

-- ──────────────────────────────────────────────────────────
--  EMPLEADOS  ← Tabla con datos sensibles de RRHH
-- ──────────────────────────────────────────────────────────
CREATE TABLE employees (
    employee_id     SERIAL       PRIMARY KEY,
    last_name       VARCHAR(20)  NOT NULL,   -- SENSIBLE
    first_name      VARCHAR(10)  NOT NULL,   -- SENSIBLE
    title           VARCHAR(30),
    birth_date      DATE,                    -- SENSIBLE
    hire_date       DATE,
    address         VARCHAR(120),            -- SENSIBLE
    city            VARCHAR(15),
    region          VARCHAR(15),
    postal_code     VARCHAR(10),
    country         VARCHAR(15),
    home_phone      VARCHAR(24),             -- SENSIBLE
    email           VARCHAR(80),             -- SENSIBLE
    cedula          CHAR(10),                -- SENSIBLE: cédula ecuatoriana
    salary          NUMERIC(10,2),           -- SENSIBLE: salario
    reports_to      INT          REFERENCES employees(employee_id)
);

-- ──────────────────────────────────────────────────────────
--  PEDIDOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE orders (
    order_id         SERIAL       PRIMARY KEY,
    customer_id      CHAR(5)      REFERENCES customers(customer_id),
    employee_id      INT          REFERENCES employees(employee_id),
    order_date       DATE,
    required_date    DATE,
    shipped_date     DATE,
    ship_via         INT          REFERENCES shippers(shipper_id),
    freight          NUMERIC(10,2) DEFAULT 0,
    ship_name        VARCHAR(40),
    ship_address     VARCHAR(120),
    ship_city        VARCHAR(15),
    ship_region      VARCHAR(15),
    ship_postal_code VARCHAR(10),
    ship_country     VARCHAR(15)
);

-- ──────────────────────────────────────────────────────────
--  DETALLES DE PEDIDOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE order_details (
    order_id    INT           REFERENCES orders(order_id),
    product_id  INT           REFERENCES products(product_id),
    unit_price  NUMERIC(10,2) NOT NULL,
    quantity    SMALLINT      NOT NULL,
    discount    REAL          DEFAULT 0,
    PRIMARY KEY (order_id, product_id)
);

-- ──────────────────────────────────────────────────────────
--  ÍNDICES para mejorar rendimiento del pipeline
-- ──────────────────────────────────────────────────────────
CREATE INDEX idx_customers_cedula   ON customers(cedula);
CREATE INDEX idx_employees_cedula   ON employees(cedula);
CREATE INDEX idx_orders_customer    ON orders(customer_id);
CREATE INDEX idx_orders_employee    ON orders(employee_id);
CREATE INDEX idx_orderdet_order     ON order_details(order_id);

-- ──────────────────────────────────────────────────────────
--  COMENTARIOS (documentación de campos sensibles)
-- ──────────────────────────────────────────────────────────
COMMENT ON COLUMN customers.cedula          IS 'DATO_SENSIBLE:ALTO - Cédula de identidad ecuatoriana (10 dígitos). Sujeto a LOPDP Art.10';
COMMENT ON COLUMN customers.contact_name    IS 'DATO_SENSIBLE:MEDIO - Nombre y apellido del contacto';
COMMENT ON COLUMN customers.phone           IS 'DATO_SENSIBLE:MEDIO - Teléfono de contacto';
COMMENT ON COLUMN customers.email           IS 'DATO_SENSIBLE:MEDIO - Correo electrónico';
COMMENT ON COLUMN customers.address         IS 'DATO_SENSIBLE:MEDIO - Dirección domiciliaria';
COMMENT ON COLUMN customers.fecha_nacimiento IS 'DATO_SENSIBLE:ALTO - Fecha de nacimiento';
COMMENT ON COLUMN customers.credit_limit    IS 'DATO_SENSIBLE:ALTO - Límite de crédito financiero';
COMMENT ON COLUMN employees.cedula          IS 'DATO_SENSIBLE:ALTO - Cédula de identidad ecuatoriana';
COMMENT ON COLUMN employees.salary          IS 'DATO_SENSIBLE:ALTO - Salario mensual del empleado';
COMMENT ON COLUMN employees.email           IS 'DATO_SENSIBLE:MEDIO - Correo corporativo/personal';
COMMENT ON COLUMN employees.home_phone      IS 'DATO_SENSIBLE:MEDIO - Teléfono domiciliario';
COMMENT ON COLUMN employees.birth_date      IS 'DATO_SENSIBLE:ALTO - Fecha de nacimiento';
