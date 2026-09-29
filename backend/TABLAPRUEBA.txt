CREATE DATABASE aeroplate_db;
\c aeroplate_db;

-- 1. Tabla usuarios
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    email VARCHAR(150) UNIQUE,
    contrasena VARCHAR(255),
    verificacion BOOLEAN,
    rol VARCHAR(50)
);

-- 2. Tabla ubicaciones
CREATE TABLE ubicaciones (
    id SERIAL PRIMARY KEY,
    ciudad VARCHAR(100),
    pais VARCHAR(100),
    codigo_aeropuerto VARCHAR(10)
);

-- 3. Tabla vuelos
CREATE TABLE vuelos (
    id SERIAL PRIMARY KEY,
    id_origen INT REFERENCES ubicaciones(id),
    id_destino INT REFERENCES ubicaciones(id),
    fecha_partida TIMESTAMP,
    fecha_regreso TIMESTAMP,
    clase VARCHAR(50),
    precio DECIMAL(10, 2),
    idaVuelta BOOLEAN
);

-- 4. Tabla hoteles
CREATE TABLE hoteles (
    id SERIAL PRIMARY KEY,
    id_ubicacion INT REFERENCES ubicaciones(id),
    nombre_hotel VARCHAR(150),
    descripcion TEXT,
    precioPorNoche DECIMAL(10, 2)
);

-- 5. Tabla paquetesTuristicos
CREATE TABLE paquetesTuristicos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(150),
    descripcion TEXT,
    tipoPaquete VARCHAR(50),
    precioTotal DECIMAL(10, 2)
);

-- 6. Tabla compras
CREATE TABLE compras (
    id SERIAL PRIMARY KEY,
    numeroPedido VARCHAR(50) UNIQUE,
    id_usuario INT REFERENCES usuarios(id),
    fecha TIMESTAMP,
    estado VARCHAR(50),
    precioTotal DECIMAL(10, 2)
);

-- 7. Tabla detalleCompra
CREATE TABLE detalleCompra (
    id SERIAL PRIMARY KEY,
    id_compra INT REFERENCES compras(id),
    tipo_item VARCHAR(50),
    id_item_referencia INT,
    cantidad INT,
    subtotal DECIMAL(10, 2)
);

-- 8. Tabla pasajerosReserva
CREATE TABLE pasajerosReserva (
    id SERIAL PRIMARY KEY,
    id_compra INT REFERENCES compras(id),
    nombre VARCHAR(100),
    apellido VARCHAR(100),
    dni VARCHAR(20),
    tipoPasajero VARCHAR(50)
);

-- 9. Tabla historialVentas
CREATE TABLE historialVentas (
    id SERIAL PRIMARY KEY,
    id_compra INT REFERENCES compras(id),
    fechaEntrega TIMESTAMP
);

-- 10. Tabla mails
CREATE TABLE mails (
    id SERIAL PRIMARY KEY,
    id_usuario INT REFERENCES usuarios(id),
    destinatario VARCHAR(150),
    asunto VARCHAR(200),
    cuerpo TEXT,
    archivoAdjunto VARCHAR(255),
    fecha_envio TIMESTAMP
);
