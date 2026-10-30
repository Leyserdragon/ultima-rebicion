-- ============================================================================
--  CosmicStream Reader · Esquema de base de datos
--  MySQL 8.0+ / MariaDB 10.5+
--
--  IMPORTANTE: este script ya NO borra tablas. Se puede ejecutar varias veces
--  sin perder datos (usa CREATE TABLE IF NOT EXISTS).
--
--  Si ya tienes una base de datos creada con la versión antigua, ejecuta
--  primero el script de migración:
--      python tools/migrar_bd.py
-- ============================================================================

CREATE DATABASE IF NOT EXISTS cosmicstream_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE cosmicstream_db;

-- ----------------------------------------------------------------------------
-- 1. Roles
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id_rol INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. Usuarios
--    `password` guarda un hash PBKDF2, nunca la contraseña en texto plano.
--    Formato: pbkdf2_sha256$iteraciones$sal$hash
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario   INT AUTO_INCREMENT PRIMARY KEY,
    username     VARCHAR(100) NOT NULL UNIQUE,
    password     VARCHAR(255) NOT NULL,
    id_rol       INT NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_usuarios_rol
        FOREIGN KEY (id_rol) REFERENCES roles(id_rol)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 3. Géneros
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS generos (
    id_genero INT AUTO_INCREMENT PRIMARY KEY,
    nombre    VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 4. Libros
--    ruta_archivo es UNIQUE: es la clave que usa el "upsert" al subir.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS libros (
    id_libro      INT AUTO_INCREMENT PRIMARY KEY,
    titulo        VARCHAR(255) NOT NULL,
    formato       VARCHAR(20)  NOT NULL,
    ruta_archivo  VARCHAR(500) NOT NULL UNIQUE,
    ruta_portada  VARCHAR(500) NULL,
    id_genero     INT NULL,
    total_paginas INT NULL,
    subido_por    INT NULL,
    fecha_subida  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_libros_genero
        FOREIGN KEY (id_genero) REFERENCES generos(id_genero)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    CONSTRAINT fk_libros_usuario
        FOREIGN KEY (subido_por) REFERENCES usuarios(id_usuario)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    INDEX idx_libros_genero (id_genero),
    INDEX idx_libros_fecha (fecha_subida)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 5. Reseñas
--    UNIQUE (id_libro, id_usuario): una reseña por usuario y obra.
--    Al volver a publicar, se actualiza en lugar de duplicarse.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resenas (
    id_resena      INT AUTO_INCREMENT PRIMARY KEY,
    id_libro       INT NOT NULL,
    id_usuario     INT NOT NULL,
    calificacion   TINYINT NOT NULL,
    comentario     TEXT NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_calificacion CHECK (calificacion BETWEEN 1 AND 5),
    CONSTRAINT fk_resenas_libro
        FOREIGN KEY (id_libro) REFERENCES libros(id_libro)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_resenas_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    UNIQUE KEY uq_resena_usuario_libro (id_libro, id_usuario)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 6. Progreso de lectura (una fila por usuario y libro)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS progreso_lectura (
    id_usuario     INT NOT NULL,
    id_libro       INT NOT NULL,
    ultima_pagina  INT NOT NULL DEFAULT 0,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id_usuario, id_libro),
    CONSTRAINT fk_progreso_usuario
        FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT fk_progreso_libro
        FOREIGN KEY (id_libro) REFERENCES libros(id_libro)
        ON DELETE CASCADE
        ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ============================================================================
--  Datos iniciales
-- ============================================================================

INSERT IGNORE INTO roles (id_rol, nombre) VALUES
    (1, 'administrador'),
    (2, 'lector');

-- Cuentas de demostración.
--   admin       / 12345      (rol administrador)
--   eliu leyton / 123456789  (rol lector)
-- Los valores son hashes PBKDF2-SHA256, no contraseñas legibles.
-- ⚠ Cámbialas en cuanto empieces a usar el sistema de verdad.
INSERT IGNORE INTO usuarios (username, password, id_rol) VALUES
    ('admin',       'pbkdf2_sha256$260000$ec6250d03992d7467d2344e7c3c09508$8923f4a4fb7c39ec6444e1680566af8073c2c4ff7bcb55af5a322ef05d6033fd', 1),
    ('eliu leyton', 'pbkdf2_sha256$260000$a87dff6c2f86c0ce7f70c7d942e60fb9$404b0f3307294fa83a7702386d53befa97a5e42c9723aa33c42e069f2d1ce8a5', 2);

INSERT IGNORE INTO generos (nombre) VALUES
    ('Acción'),
    ('Aventura'),
    ('Ciencia ficción'),
    ('Comedia'),
    ('Drama'),
    ('Fantasía'),
    ('Misterio'),
    ('Romance'),
    ('Slice of life'),
    ('Terror');
