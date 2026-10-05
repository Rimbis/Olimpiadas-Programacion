-- =====================================================================
-- AEROPLATE - Datos de ejemplo para probar, sacar capturas y grabar el video.
-- Nombres de tablas/columnas verificados contra la base real (ubicacion_aeropuerto,
-- codigo_aeropuerto). Es aditivo: se puede correr mas de una vez sin duplicar.
-- =====================================================================

-- Seed de paquetes turisticos "mas reales" para Aeroplate.
-- Es ADITIVO: no borra nada y no pisa lo que ya existe. Cada insert se saltea
-- las filas que ya estan (por codigo de aeropuerto, ciudad, nombre o titulo).
-- Como ninguna tabla tiene default en `id`, los ids se calculan como max(id)+n.
-- Se puede correr de una sola vez en el SQL Editor de Supabase.

-- 1) Aeropuertos (origen EZE, destinos y escala PTY) ---------------------------
insert into ubicacion_aeropuerto (id, ciudad, pais, codigo_aeropuerto)
select (select coalesce(max(id), 0) from ubicacion_aeropuerto) + row_number() over (),
       v.ciudad, v.pais, v.cod
from (values
  ('Buenos Aires',   'Argentina',          'EZE'),
  ('Bariloche',      'Argentina',          'BRC'),
  ('Ushuaia',        'Argentina',          'USH'),
  ('Cancún',         'México',             'CUN'),
  ('Río de Janeiro', 'Brasil',             'GIG'),
  ('Madrid',         'España',             'MAD'),
  ('Punta Cana',     'República Dominicana','PUJ'),
  ('Ciudad de Panamá','Panamá',            'PTY')
) as v(ciudad, pais, cod)
where not exists (
  select 1 from ubicacion_aeropuerto a where a.codigo_aeropuerto = v.cod
);

-- 2) Destinos -------------------------------------------------------------------
insert into ubicacion_destino (id, ciudad, pais)
select (select coalesce(max(id), 0) from ubicacion_destino) + row_number() over (),
       v.ciudad, v.pais
from (values
  ('Bariloche',      'Argentina'),
  ('Ushuaia',        'Argentina'),
  ('Cancún',         'México'),
  ('Río de Janeiro', 'Brasil'),
  ('Madrid',         'España'),
  ('Punta Cana',     'República Dominicana')
) as v(ciudad, pais)
where not exists (
  select 1 from ubicacion_destino d where d.ciudad = v.ciudad
);

-- 3) Seguros medicos --------------------------------------------------------------
insert into seguro_medico (id, nombre, empresa)
select (select coalesce(max(id), 0) from seguro_medico) + row_number() over (),
       v.nombre, v.empresa
from (values
  ('Cobertura Nacional',     'Asistencia Viajera'),
  ('Cobertura Internacional','Asistencia Viajera'),
  ('Cobertura Premium',      'Global Assist')
) as v(nombre, empresa)
where not exists (
  select 1 from seguro_medico s where s.nombre = v.nombre
);

-- 4) Hoteles -----------------------------------------------------------------------
insert into hoteles (id, id_ubicacion, nombre_hotel, descripcion, precio_noche, estrellas)
select (select coalesce(max(id), 0) from hoteles) + row_number() over (),
       (select d.id from ubicacion_destino d where d.ciudad = v.ciudad limit 1),
       v.nombre, v.descripcion, v.precio, v.estrellas
from (values
  ('Bariloche',      'Hotel Lago Nahuel',     'Hotel con vista al lago Nahuel Huapi, desayuno incluido y spa.',      95000, 4),
  ('Ushuaia',        'Hotel Canal del Beagle','Hotel frente al canal, habitaciones con vista a la montaña.',          88000, 4),
  ('Cancún',         'Resort Caribe Azul',    'Resort todo incluido frente al mar, con piscinas y club de niños.',   150000, 5),
  ('Río de Janeiro', 'Hotel Copacabana Sol',  'A metros de la playa de Copacabana, desayuno buffet incluido.',        98000, 4),
  ('Madrid',         'Hotel Gran Vía Plaza',  'Hotel céntrico sobre la Gran Vía, cerca de museos y teatros.',        120000, 4),
  ('Punta Cana',     'Resort Palmeras Dorado','Resort todo incluido en playa de arena blanca, con actividades.',     145000, 5)
) as v(ciudad, nombre, descripcion, precio, estrellas)
where not exists (
  select 1 from hoteles h where h.nombre_hotel = v.nombre
);

-- 5) Vuelos (ida y vuelta desde EZE; fechas futuras) -------------------------------
insert into vuelos (id, id_ubi_aereo_origen, id_ubi_aereo_destino, id_destino,
                    fecha_ida, fecha_vuelta, clase, cantidad_escalas)
select (select coalesce(max(id), 0) from vuelos) + row_number() over (),
       (select a.id from ubicacion_aeropuerto a where a.codigo_aeropuerto = 'EZE'),
       (select a.id from ubicacion_aeropuerto a where a.codigo_aeropuerto = v.cod),
       (select d.id from ubicacion_destino d where d.ciudad = v.ciudad limit 1),
       v.ida::timestamptz, v.vuelta::timestamptz, v.clase, v.escalas
from (values
  ('BRC', 'Bariloche',      '2027-01-10 08:00-03', '2027-01-17 18:00-03', 'Económica', 0),
  ('GIG', 'Río de Janeiro', '2027-01-24 09:30-03', '2027-01-31 20:00-03', 'Económica', 0),
  ('CUN', 'Cancún',         '2027-02-06 22:00-03', '2027-02-14 10:00-03', 'Económica', 1),
  ('PUJ', 'Punta Cana',     '2027-02-20 21:00-03', '2027-02-27 09:00-03', 'Económica', 1),
  ('USH', 'Ushuaia',        '2027-03-05 07:00-03', '2027-03-10 19:00-03', 'Económica', 0),
  ('MAD', 'Madrid',         '2027-03-12 19:30-03', '2027-03-22 11:00-03', 'Premium',   0)
) as v(cod, ciudad, ida, vuelta, clase, escalas)
where not exists (
  select 1 from vuelos f where f.id_destino = (select d.id from ubicacion_destino d where d.ciudad = v.ciudad limit 1)
                            and f.fecha_ida = v.ida::timestamptz
);

-- 6) Escalas (Cancún y Punta Cana pasan por Panamá) -------------------------------
insert into escalas_vuelo (id, id_vuelo, id_ubi_aeropuerto, orden)
select (select coalesce(max(id), 0) from escalas_vuelo) + row_number() over (),
       f.id,
       (select a.id from ubicacion_aeropuerto a where a.codigo_aeropuerto = 'PTY'),
       1
from vuelos f
join ubicacion_destino d on d.id = f.id_destino
where ((d.ciudad = 'Cancún'     and f.fecha_ida = '2027-02-06 22:00-03'::timestamptz)
    or (d.ciudad = 'Punta Cana' and f.fecha_ida = '2027-02-20 21:00-03'::timestamptz))
  and not exists (select 1 from escalas_vuelo e where e.id_vuelo = f.id);

-- 7) Paquetes -----------------------------------------------------------------------
-- precio_total = precio por pasajero. Ajustar precios a la moneda/escala del resto del catalogo.
-- tipo_paquete: valores del sistema = Familiar, Amigos, Parejas, Individual, Grupal.
insert into paquetes_turisticos
  (id, titulo, descripcion, tipo_paquete, precio_total, cantidad_noches,
   id_hotel, id_ubi_destino, id_seguro_medico, id_vuelo, codigo_paquete)
select (select coalesce(max(id), 0) from paquetes_turisticos) + row_number() over (order by v.codigo),
       v.titulo, v.descripcion, v.tipo, v.precio, v.noches,
       h.id, d.id, s.id, f.id, v.codigo
from (values
  ('Bariloche: nieve y lagos',  'Siete noches en Bariloche con vuelo, hotel con desayuno y seguro médico.',
   'Familiar',      1250000, 7, 'Bariloche',      'Hotel Lago Nahuel',     'Cobertura Nacional',      '2027-01-10 08:00-03', 1004),
  ('Río de Janeiro: playa y samba','Siete noches frente a Copacabana con vuelo directo y seguro internacional.',
   'Amigos',        1480000, 7, 'Río de Janeiro', 'Hotel Copacabana Sol',  'Cobertura Internacional', '2027-01-24 09:30-03', 1005),
  ('Cancún todo incluido',      'Ocho noches en resort todo incluido en el Caribe mexicano, con escala en Panamá.',
   'Parejas',       2650000, 8, 'Cancún',         'Resort Caribe Azul',    'Cobertura Internacional', '2027-02-06 22:00-03', 1006),
  ('Punta Cana: Caribe dominicano','Siete noches en resort todo incluido sobre playa de arena blanca.',
   'Familiar',      2480000, 7, 'Punta Cana',     'Resort Palmeras Dorado','Cobertura Internacional', '2027-02-20 21:00-03', 1007),
  ('Ushuaia: fin del mundo',    'Cinco noches en Ushuaia con excursión al Canal Beagle y seguro médico.',
   'Individual',    1180000, 5, 'Ushuaia',        'Hotel Canal del Beagle','Cobertura Nacional',      '2027-03-05 07:00-03', 1008),
  ('Madrid clásico',            'Diez noches en Madrid con vuelo premium y cobertura médica ampliada.',
   'Grupal',        3350000, 10,'Madrid',         'Hotel Gran Vía Plaza',  'Cobertura Premium',       '2027-03-12 19:30-03', 1009)
) as v(titulo, descripcion, tipo, precio, noches, ciudad, hotel, seguro, ida, codigo)
join ubicacion_destino d on d.ciudad = v.ciudad
join hoteles h on h.nombre_hotel = v.hotel
join seguro_medico s on s.nombre = v.seguro
join vuelos f on f.id_destino = d.id and f.fecha_ida = v.ida::timestamptz
where not exists (select 1 from paquetes_turisticos p where p.titulo = v.titulo)
  and not exists (select 1 from paquetes_turisticos p where p.codigo_paquete = v.codigo);

-- Mail del sector que recibe el aviso de cada venta (REEMPLAZAR por uno real).
insert into contactos_empresa (id, sector, email, activo)
select gen_random_uuid(), 'Ventas', 'ventas@ejemplo.com', true
where not exists (select 1 from contactos_empresa where sector = 'Ventas');

-- Los ids se cargaron explicitos: se avanzan las secuencias (si las hay) para que
-- las altas desde la app no choquen con ellos. Si una tabla no tiene secuencia, no hace nada.
select setval(pg_get_serial_sequence('ubicacion_aeropuerto', 'id'), (select coalesce(max(id), 1) from ubicacion_aeropuerto)) where pg_get_serial_sequence('ubicacion_aeropuerto', 'id') is not null;
select setval(pg_get_serial_sequence('ubicacion_destino', 'id'), (select coalesce(max(id), 1) from ubicacion_destino)) where pg_get_serial_sequence('ubicacion_destino', 'id') is not null;
select setval(pg_get_serial_sequence('seguro_medico', 'id'), (select coalesce(max(id), 1) from seguro_medico)) where pg_get_serial_sequence('seguro_medico', 'id') is not null;
select setval(pg_get_serial_sequence('hoteles', 'id'), (select coalesce(max(id), 1) from hoteles)) where pg_get_serial_sequence('hoteles', 'id') is not null;
select setval(pg_get_serial_sequence('vuelos', 'id'), (select coalesce(max(id), 1) from vuelos)) where pg_get_serial_sequence('vuelos', 'id') is not null;
select setval(pg_get_serial_sequence('escalas_vuelo', 'id'), (select coalesce(max(id), 1) from escalas_vuelo)) where pg_get_serial_sequence('escalas_vuelo', 'id') is not null;
select setval(pg_get_serial_sequence('paquetes_turisticos', 'id'), (select coalesce(max(id), 1) from paquetes_turisticos)) where pg_get_serial_sequence('paquetes_turisticos', 'id') is not null;

-- ---------------------------------------------------------------------
-- PRIMER JEFE DE VENTAS (hay que crearlo a mano, porque POST /admin/usuarios
-- ya exige ser jefe):
--   1. Supabase > Authentication > Users > Add user (Auto confirm activado).
--   2. Copiar su UUID y correr:
--      insert into admin (id, nombre, apellido, email, rol)
--      values ('<uuid>', 'Nombre', 'Apellido', 'jefe@ejemplo.com', 'jefe_ventas');
-- ---------------------------------------------------------------------

-- 8) Verificacion -------------------------------------------------------------------
select p.id, p.codigo_paquete, p.titulo, p.tipo_paquete, p.precio_total, p.cantidad_noches,
       d.ciudad as destino, h.nombre_hotel, f.cantidad_escalas, f.fecha_ida::date as ida
from paquetes_turisticos p
join ubicacion_destino d on d.id = p.id_ubi_destino
join hoteles h on h.id = p.id_hotel
join vuelos f on f.id = p.id_vuelo
order by p.codigo_paquete;
