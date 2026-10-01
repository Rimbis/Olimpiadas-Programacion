-- =====================================================================
-- AEROPLATE - Datos de ejemplo para probar, sacar capturas y grabar el video.
-- Los nombres de tablas/columnas salen del DER: si alguno no coincide con la
-- base real (ej. "ubicacion_aereopuerto"), ajustarlo antes de correr.
-- Correr UNA sola vez.
-- =====================================================================

insert into ubicacion_destino (ciudad, pais) values
    ('Bariloche', 'Argentina'),
    ('Cancún', 'México'),
    ('Río de Janeiro', 'Brasil');

insert into ubicacion_aereopuerto (ciudad, pais, codigo_aereopuerto) values
    ('Buenos Aires', 'Argentina', 'AEP'),
    ('Bariloche', 'Argentina', 'BRC'),
    ('Cancún', 'México', 'CUN'),
    ('Río de Janeiro', 'Brasil', 'GIG');

insert into hoteles (id_ubicacion, nombre_hotel, descripcion, precio_noche, estrellas) values
    ((select id from ubicacion_destino where ciudad = 'Bariloche'),
     'Hotel Lago Azul', 'Frente al lago Nahuel Huapi, desayuno incluido', 95000, 4),
    ((select id from ubicacion_destino where ciudad = 'Cancún'),
     'Resort Caribe Sol', 'Todo incluido sobre la playa', 180000, 5),
    ((select id from ubicacion_destino where ciudad = 'Río de Janeiro'),
     'Hotel Copacabana Mar', 'A una cuadra de la playa', 110000, 4);

insert into seguro_medico (nombre, empresa) values
    ('Asistencia Básica', 'Assist Viajero'),
    ('Asistencia Premium', 'Assist Viajero');

insert into vuelos
    (id_ubi_aereo_origen, id_ubi_aereo_destino, id_destino,
     fecha_ida, fecha_vuelta, clase, cantidad_escalas) values
    ((select id from ubicacion_aereopuerto where codigo_aereopuerto = 'AEP'),
     (select id from ubicacion_aereopuerto where codigo_aereopuerto = 'BRC'),
     (select id from ubicacion_destino where ciudad = 'Bariloche'),
     '2026-12-10 08:00', '2026-12-17 19:00', 'Económica', 0),
    ((select id from ubicacion_aereopuerto where codigo_aereopuerto = 'AEP'),
     (select id from ubicacion_aereopuerto where codigo_aereopuerto = 'CUN'),
     (select id from ubicacion_destino where ciudad = 'Cancún'),
     '2027-01-15 22:30', '2027-01-25 14:00', 'Económica', 1),
    ((select id from ubicacion_aereopuerto where codigo_aereopuerto = 'AEP'),
     (select id from ubicacion_aereopuerto where codigo_aereopuerto = 'GIG'),
     (select id from ubicacion_destino where ciudad = 'Río de Janeiro'),
     '2027-02-05 07:15', '2027-02-12 20:40', 'Económica', 0);

-- precio_total = precio POR PASAJERO (la compra multiplica por cantidad).
insert into paquetes_turisticos
    (codigo_paquete, titulo, descripcion, tipo_paquete, precio_total, cantidad_noches,
     id_hotel, id_ubi_destino, id_seguro_medico, id_vuelo) values
    (1001, 'Bariloche Clásico', 'Vuelo + 7 noches con desayuno y asistencia al viajero',
     'Todo incluido', 850000, 7,
     (select id from hoteles where nombre_hotel = 'Hotel Lago Azul'),
     (select id from ubicacion_destino where ciudad = 'Bariloche'),
     (select id from seguro_medico where nombre = 'Asistencia Básica'),
     (select min(id) from vuelos where id_destino = (select id from ubicacion_destino where ciudad = 'Bariloche'))),
    (1002, 'Cancún Caribe', 'Vuelo + 10 noches todo incluido en el Caribe mexicano',
     'Todo incluido', 2400000, 10,
     (select id from hoteles where nombre_hotel = 'Resort Caribe Sol'),
     (select id from ubicacion_destino where ciudad = 'Cancún'),
     (select id from seguro_medico where nombre = 'Asistencia Premium'),
     (select min(id) from vuelos where id_destino = (select id from ubicacion_destino where ciudad = 'Cancún'))),
    (1003, 'Río de Janeiro Express', 'Vuelo + 7 noches en Copacabana',
     'Estadía + pasaje', 1250000, 7,
     (select id from hoteles where nombre_hotel = 'Hotel Copacabana Mar'),
     (select id from ubicacion_destino where ciudad = 'Río de Janeiro'),
     (select id from seguro_medico where nombre = 'Asistencia Básica'),
     (select min(id) from vuelos where id_destino = (select id from ubicacion_destino where ciudad = 'Río de Janeiro')));

-- Mail del sector que recibe el aviso de cada venta (REEMPLAZAR por uno real).
insert into contactos_empresa (sector, email, activo) values
    ('Ventas', 'ventas@ejemplo.com', true);

-- ---------------------------------------------------------------------
-- PRIMER JEFE DE VENTAS (hay que crearlo a mano, porque POST /admin/usuarios
-- ya exige ser jefe):
--   1. Supabase > Authentication > Users > Add user (Auto confirm activado).
--   2. Copiar su UUID y correr:
--      insert into admin (id, nombre, apellido, email, rol)
--      values ('<uuid>', 'Nombre', 'Apellido', 'jefe@ejemplo.com', 'jefe_ventas');
-- ---------------------------------------------------------------------
