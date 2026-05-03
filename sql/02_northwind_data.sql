-- ============================================================
--  DATOS DE DEMOSTRACIÓN - NORTHWIND ECUADOR
--  Datos ficticios pero con formato real ecuatoriano
--  para demostrar el pipeline de anonimización
-- ============================================================

-- ── Categorías ──────────────────────────────────────────
INSERT INTO categories (category_name, description) VALUES
('Bebidas',        'Jugos, aguas, colas y bebidas alcohólicas'),
('Lácteos',        'Quesos, yogures, mantequilla y derivados'),
('Confitería',     'Dulces, chocolates y golosinas'),
('Granos',         'Arroz, fréjol, lenteja y cereales'),
('Carnes',         'Res, cerdo, pollo y embutidos'),
('Mariscos',       'Camarón, tilapia, atún y mariscos'),
('Snacks',         'Papas fritas, chifles y aperitivos'),
('Condimentos',    'Salsas, especias y aderezos');

-- ── Proveedores ─────────────────────────────────────────
INSERT INTO suppliers (company_name, contact_name, contact_title, address, city, region, postal_code, country, phone, email) VALUES
('Alimentos del Valle S.A.',    'Carlos Andrade',    'Gerente Comercial', 'Av. De los Shyris 1200',    'Quito',       'Pichincha',  '170135', 'Ecuador', '022-345-6789', 'candrade@alivalles.com.ec'),
('Lácteos San Antonio Cía.',    'María Vásquez',     'Directora Ventas',  'Calle Bolívar 456',         'Cuenca',      'Azuay',      '010201', 'Ecuador', '074-567-8901', 'mvasquez@lacteos-sa.com.ec'),
('Empacadora del Pacífico',     'Roberto Cevallos',  'Jefe de Logística', 'Km 14 Vía a Daule',         'Guayaquil',   'Guayas',     '090512', 'Ecuador', '042-789-0123', 'rcevallos@empacadora-pac.ec'),
('Confites Finos del Ecuador',  'Ana Herrera',       'Gerente General',   'Av. 6 de Diciembre N45-78', 'Quito',       'Pichincha',  '170526', 'Ecuador', '022-456-7890', 'aherrera@confitesfinos.ec'),
('Granos & Cereales Imbabura',  'Jorge Pinto',       'Vendedor Senior',   'Calle Sucre y Bolívar',     'Ibarra',      'Imbabura',   '100201', 'Ecuador', '062-234-5678', 'jpinto@granos-imbabura.ec'),
('Mariscos Manabita Ltda.',     'Lucía Zambrano',    'Coordinadora',      'Malecón 2000 Local 45',     'Manta',       'Manabí',     '130601', 'Ecuador', '052-345-6789', 'lzambrano@mariscos-mb.ec');

-- ── Productos ────────────────────────────────────────────
INSERT INTO products (product_name, supplier_id, category_id, quantity_per_unit, unit_price, units_in_stock) VALUES
('Jugo de Naranja Natural 1L',       1, 1, '12 botellas x 1L',   2.75,  150),
('Agua Mineral Sin Gas 500ml',       1, 1, '24 unidades',         0.50,  500),
('Queso de Mesa 500g',               2, 2, '10 piezas x 500g',    4.20,   80),
('Yogurt de Frutilla 200g',          2, 2, '24 vasos x 200g',     1.10,  200),
('Chocolate Fino 100g',              4, 3, '50 tabletas x 100g',  2.30,  300),
('Arroz Seco Flor 5Kg',              5, 4, '10 sacos x 5kg',      6.50,  250),
('Lenteja Seleccionada 1kg',         5, 4, '20 fundas x 1kg',     1.80,  180),
('Chorizo Ahumado 250g',             3, 5, '30 unidades x 250g',  3.40,   90),
('Camarón Entero Congelado 1kg',     6, 6, '10 fundas x 1kg',     9.80,   60),
('Tilapia Fileteada 500g',           6, 6, '20 unidades x 500g',  5.20,   75),
('Chifles de Verde 200g',            3, 7, '40 fundas x 200g',    1.20,  400),
('Salsa de Ají Criollo 250ml',       4, 8, '24 frascos x 250ml',  2.10,  120),
('Manjar de Leche 250g',             2, 3, '30 frascos x 250g',   2.80,  160),
('Atún en Agua 180g',                3, 6, '48 latas x 180g',     1.50,  350),
('Papas Fritas Limeñas 200g',        3, 7, '36 fundas x 200g',    1.30,  280);

-- ── Transportistas ──────────────────────────────────────
INSERT INTO shippers (company_name, phone) VALUES
('Servientrega Ecuador',  '1800-737-843'),
('Laar Courier',          '1800-527-766'),
('DHL Ecuador',           '022-397-100');

-- ── Clientes (datos sensibles para demostración) ────────
INSERT INTO customers (customer_id, company_name, contact_name, contact_title, address, city, region, postal_code, country, phone, email, cedula, fecha_nacimiento, credit_limit) VALUES
('ALFKI', 'Distribuidora Alfaro S.A.',    'Ana María Alfaro Medina',    'Gerente General',     'Av. Amazonas N34-451 y Atahualpa', 'Quito',     'Pichincha', '170525', 'Ecuador', '022-345-9871', 'ana.alfaro@distribalfaro.ec',     '1712345678', '1982-03-15', 15000.00),
('BOLID', 'Comercial Bolívar Hnos.',      'Pedro Ramón Bolívar Torres', 'Director Compras',    'Calle Loja 234 y Pichincha',       'Guayaquil', 'Guayas',    '090101', 'Ecuador', '042-678-1234', 'pbolivar@comercialbolivar.ec',    '0924567890', '1975-07-22', 25000.00),
('CONSH', 'Consorcio del Sur Cía. Ltda.', 'Carla Verónica Sánchez',     'Jefa de Adquisición', 'Av. Solano 45-67',                 'Cuenca',    'Azuay',     '010201', 'Ecuador', '074-234-5678', 'csanchez@consorcio-sur.ec',       '0102345678', '1990-11-05', 10000.00),
('DRACD', 'Drácula Importaciones',        'Diego Marcelo Dávila',       'Representante',       'Calle Eloy Alfaro N22-78',         'Quito',     'Pichincha', '170136', 'Ecuador', '022-567-8901', 'ddavila@dracula-import.ec',       '1756789012', '1988-04-30', 8000.00),
('ERNSH', 'Ernst & Handels Ecuador',      'María José Herrera León',    'Gerente Ventas',      'Av. República del Salvador 1082',  'Quito',     'Pichincha', '170516', 'Ecuador', '022-789-0123', 'mherrera@ernst-handels.ec',       '1723456789', '1979-09-18', 50000.00),
('FAMIA', 'Familia Aguilar Distribuciones','Luis Alberto Aguilar',      'Propietario',         'Calle Olmedo 345 y García Moreno', 'Ambato',    'Tungurahua','180201', 'Ecuador', '032-345-6789', 'laguilar@familia-dist.ec',        '1812345678', '1965-12-01', 20000.00),
('FRANK', 'Francisco Narváez & Cía.',     'Francisco Narváez',          'Administrador',       'Av. Quito 567',                    'Riobamba',  'Chimborazo','060201', 'Ecuador', '032-456-7890', 'fnarvaez@narvaez-cia.ec',         '0612345678', '1972-06-14', 12000.00),
('GROSR', 'Grosero & Asociados',          'Verónica Grosero',           'Directora Comercial', 'Av. Las Américas 890',             'Guayaquil', 'Guayas',    '090505', 'Ecuador', '042-890-1234', 'vgrosero@grosero-asoc.ec',        '0934567890', '1984-02-28', 18000.00),
('HANAR', 'Hanar Industrias del Norte',   'Carlos Hanar Pérez',         'Gerente Operaciones', 'Av. El Retorno 1234',              'Ibarra',    'Imbabura',  '100201', 'Ecuador', '062-567-8901', 'chanar@hanar-industrias.ec',      '1045678901', '1967-08-10', 30000.00),
('ISLAT', 'Isla Tortuga Mariscos',        'Patricia Isla',              'Socia Fundadora',     'Malecón Jaime Roldós 456',         'Manta',     'Manabí',    '130601', 'Ecuador', '052-678-9012', 'pisla@islatortuga-mariscos.ec',   '1312345678', '1980-05-25', 22000.00),
('KOENE', 'Koening Representaciones',     'Marco Antonio Koening',      'Representante Legal', 'Av. Naciones Unidas 789',          'Quito',     'Pichincha', '170516', 'Ecuador', '022-901-2345', 'mkoening@koening-rep.ec',         '1789012345', '1976-03-12', 35000.00),
('LACOR', 'La Corona del Sur S.A.',       'Sofía Coronel Andrade',      'Directora Ejecutiva', 'Calle Gran Colombia 123',          'Cuenca',    'Azuay',     '010102', 'Ecuador', '074-012-3456', 'scoronel@lacorona-sur.ec',        '0156789012', '1992-10-07', 9000.00);

-- ── Empleados (datos sensibles de RRHH) ─────────────────
INSERT INTO employees (last_name, first_name, title, birth_date, hire_date, address, city, region, postal_code, country, home_phone, email, cedula, salary, reports_to) VALUES
('Davolio',    'Nancy',    'Representante Ventas',   '1968-12-08', '2018-05-01', 'Av. Shyris 456 Dep. 3B',           'Quito',     'Pichincha',  '170525', 'Ecuador', '022-345-6789', 'ndavolio@northwind.ec',    '1701234567', 2800.00, NULL),
('Fuller',     'Andrew',   'Vicepresidente Ventas',  '1952-02-19', '2015-08-14', 'Calle García Moreno 789',          'Quito',     'Pichincha',  '170136', 'Ecuador', '022-456-7890', 'afuller@northwind.ec',     '1712345678', 5500.00, 1),
('Leverling',  'Janet',    'Representante Ventas',   '1963-08-30', '2019-04-01', 'Av. América 234',                  'Quito',     'Pichincha',  '170136', 'Ecuador', '022-567-8901', 'jleverling@northwind.ec',  '1723456789', 2600.00, 2),
('Peacock',    'Margaret', 'Representante Ventas',   '1937-09-19', '2016-05-03', 'Av. 10 de Agosto 567',             'Quito',     'Pichincha',  '170525', 'Ecuador', '022-678-9012', 'mpeacock@northwind.ec',    '1734567890', 2700.00, 2),
('Buchanan',   'Steven',   'Director de Ventas',     '1955-03-04', '2017-10-17', 'Calle Veintimilla E8-134',         'Quito',     'Pichincha',  '170516', 'Ecuador', '022-789-0123', 'sbuchanan@northwind.ec',   '1745678901', 4200.00, 2),
('Suyama',     'Michael',  'Representante Ventas',   '1963-07-02', '2020-10-17', 'Av. Colón 890',                    'Quito',     'Pichincha',  '170136', 'Ecuador', '022-890-1234', 'msuyama@northwind.ec',     '1756789012', 2500.00, 5),
('King',       'Robert',   'Representante Ventas',   '1960-05-29', '2019-01-02', 'Calle Foch 123 y Juan León Mera',  'Quito',     'Pichincha',  '170525', 'Ecuador', '022-901-2345', 'rking@northwind.ec',       '1767890123', 2550.00, 5),
('Callahan',   'Laura',    'Coordinadora Interna',   '1958-01-09', '2017-03-05', 'Av. Orellana 456',                 'Quito',     'Pichincha',  '170516', 'Ecuador', '022-012-3456', 'lcallahan@northwind.ec',   '1778901234', 3100.00, 2),
('Dodsworth',  'Anne',     'Representante Ventas',   '1966-01-27', '2021-11-15', 'Av. 12 de Octubre 789',            'Quito',     'Pichincha',  '170136', 'Ecuador', '022-123-4567', 'adodsworth@northwind.ec',  '1789012345', 2450.00, 5);

-- ── Pedidos ──────────────────────────────────────────────
INSERT INTO orders (customer_id, employee_id, order_date, required_date, shipped_date, ship_via, freight, ship_name, ship_address, ship_city, ship_country) VALUES
('ALFKI', 5, '2024-01-15', '2024-01-29', '2024-01-17', 1, 32.38, 'Distribuidora Alfaro', 'Av. Amazonas N34-451', 'Quito',     'Ecuador'),
('ALFKI', 6, '2024-02-10', '2024-02-24', '2024-02-12', 2, 11.61, 'Distribuidora Alfaro', 'Av. Amazonas N34-451', 'Quito',     'Ecuador'),
('BOLID', 4, '2024-01-20', '2024-02-03', '2024-01-25', 3, 65.83, 'Comercial Bolívar',    'Calle Loja 234',       'Guayaquil', 'Ecuador'),
('ERNSH', 1, '2024-02-05', '2024-02-19', '2024-02-07', 1, 41.34, 'Ernst Handels',        'Av. República 1082',  'Quito',     'Ecuador'),
('ERNSH', 3, '2024-02-18', '2024-03-03', '2024-02-20', 2, 51.30, 'Ernst Handels',        'Av. República 1082',  'Quito',     'Ecuador'),
('CONSH', 2, '2024-03-01', '2024-03-15', '2024-03-04', 1, 22.10, 'Consorcio del Sur',    'Av. Solano 45-67',    'Cuenca',    'Ecuador'),
('HANAR', 7, '2024-03-10', '2024-03-24', '2024-03-12', 3, 78.92, 'Hanar Industrias',     'Av. El Retorno 1234', 'Ibarra',    'Ecuador'),
('FRANK', 8, '2024-03-22', '2024-04-05', '2024-03-25', 2, 15.45, 'Narváez & Cía',        'Av. Quito 567',       'Riobamba',  'Ecuador'),
('FAMIA', 9, '2024-04-01', '2024-04-15', '2024-04-03', 1, 33.20, 'Familia Aguilar',      'Calle Olmedo 345',    'Ambato',    'Ecuador'),
('ISLAT', 1, '2024-04-15', '2024-04-29', '2024-04-17', 2, 89.50, 'Isla Tortuga',         'Malecón 456',         'Manta',     'Ecuador'),
('KOENE', 3, '2024-05-02', '2024-05-16', '2024-05-04', 1, 47.80, 'Koening Rep.',         'Av. Naciones Unidas', 'Quito',     'Ecuador'),
('LACOR', 5, '2024-05-20', '2024-06-03', '2024-05-22', 3, 28.60, 'La Corona del Sur',    'Calle Gran Colombia', 'Cuenca',    'Ecuador');

-- ── Detalles de Pedidos ──────────────────────────────────
INSERT INTO order_details (order_id, product_id, unit_price, quantity, discount) VALUES
(1,  1,  2.75, 20, 0.00),
(1,  3,  4.20, 10, 0.05),
(2,  7,  1.80, 15, 0.00),
(2,  12, 2.10,  8, 0.10),
(3,  9,  9.80, 30, 0.05),
(3,  14, 1.50, 50, 0.00),
(4,  2,  0.50,100, 0.00),
(4,  6,  6.50, 20, 0.05),
(5,  5,  2.30, 25, 0.10),
(5,  11, 1.20, 40, 0.00),
(6,  4,  1.10, 30, 0.00),
(6,  13, 2.80, 15, 0.05),
(7,  10, 5.20, 20, 0.00),
(7,  9,  9.80, 10, 0.10),
(8,  15, 1.30, 50, 0.00),
(8,  8,  3.40, 12, 0.00),
(9,  6,  6.50, 25, 0.05),
(9,  7,  1.80, 30, 0.00),
(10, 9,  9.80, 40, 0.00),
(10, 14, 1.50, 60, 0.05),
(11, 1,  2.75, 35, 0.00),
(11, 3,  4.20, 20, 0.10),
(12, 4,  1.10, 45, 0.00),
(12, 13, 2.80, 10, 0.05);
