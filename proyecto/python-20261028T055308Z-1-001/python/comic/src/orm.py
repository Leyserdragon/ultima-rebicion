"""Mapeo ORM de CosmicStream Reader con SQLAlchemy 2.x.

Este módulo traduce las seis tablas de ``cosmicstream_db.sql`` a clases de
Python. Sirve para escribir consultas con objetos en lugar de SQL manual::

    from sqlalchemy import select
    from .orm import Libro, sesion

    with sesion() as db:
        libros = db.scalars(select(Libro).order_by(Libro.titulo)).all()
        for libro in libros:
            print(libro.titulo, libro.genero.nombre if libro.genero else "Sin género")

Ventajas del ORM
----------------
* **Relaciones navegables:** ``libro.genero.nombre`` en vez de un ``JOIN`` a mano.
* **Sesiones con transacción:** ``with sesion():`` hace ``commit`` al salir bien y
  ``rollback`` si hay una excepción, igual que ``db_cursor()`` en ``db.py``.
* **Tipos y columnas verificables:** el mapeo declara nombres, tamaños, claves y
  restricciones; si el esquema cambia, el error aparece al mapear, no en producción.
* **Consultas parametrizadas:** SQLAlchemy escapa los valores; no se concatenan
  cadenas (evita inyección SQL).

Relación con el resto del proyecto
----------------------------------
La aplicación sigue usando ``src/db.py`` + ``src/book_manager.py`` (SQL directo,
ya probado). Este archivo se añade **en paralelo** para que puedas migrar módulo
a módulo sin romper nada. Ambos usan la misma configuración (``config.json`` o
variables de entorno) y la misma base de datos.

Uso rápido
----------
Crear un libro::

    from decimal import Decimal
    from .orm import Genero, Libro, sesion

    with sesion() as db:
        genero = db.scalar(select(Genero).where(Genero.nombre == "Acción"))
        db.add(Libro(
            titulo="KO",
            formato="PDF",
            ruta_archivo="/ruta/absoluta/KO.pdf",
            genero=genero,
        ))

Calificar (equivale al ``INSERT ... ON DUPLICATE KEY UPDATE`` actual)::

    from .orm import Resena, sesion

    with sesion() as db:
        resena = db.scalar(
            select(Resena).where(
                Resena.id_libro == 1,
                Resena.id_usuario == 7,
            )
        )
        if resena is None:
            db.add(Resena(id_libro=1, id_usuario=7, calificacion=4, comentario=""))
        else:
            resena.calificacion = 4   # conserva el comentario existente
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from .db import load_config

__all__ = [
    "Base",
    "Rol",
    "Usuario",
    "Genero",
    "Libro",
    "Resena",
    "ProgresoLectura",
    "engine",
    "SessionLocal",
    "sesion",
    "construir_url",
    "crear_engine",
    "crear_tablas_si_faltan",
    "verificar_conexion",
]


# --------------------------------------------------------------------------- #
# Base declarativa
# --------------------------------------------------------------------------- #
class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #
class Rol(Base):
    """Catálogo de roles: 1 = administrador, 2 = lector."""

    __tablename__ = "roles"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id_rol: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")

    def __repr__(self) -> str:
        return f"Rol(id_rol={self.id_rol!r}, nombre={self.nombre!r})"


class Usuario(Base):
    """Cuenta de acceso. ``password`` guarda el hash PBKDF2, nunca texto plano."""

    __tablename__ = "usuarios"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    id_rol: Mapped[int] = mapped_column(
        ForeignKey(
            "roles.id_rol",
            name="fk_usuarios_rol",
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp()
    )
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
    libros_subidos: Mapped[list["Libro"]] = relationship(back_populates="subido_por_usuario")
    resenas: Mapped[list["Resena"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progresos: Mapped[list["ProgresoLectura"]] = relationship(
        back_populates="usuario",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def es_admin(self) -> bool:
        """Atajo de solo lectura, igual que ``UsuarioSesion.es_admin``."""
        return self.id_rol == 1

    def __repr__(self) -> str:
        return f"Usuario(id_usuario={self.id_usuario!r}, username={self.username!r})"


class Genero(Base):
    """Categoría de una obra (Acción, Romance, Terror…)."""

    __tablename__ = "generos"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id_genero: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)

    libros: Mapped[list["Libro"]] = relationship(back_populates="genero")

    def __repr__(self) -> str:
        return f"Genero(id_genero={self.id_genero!r}, nombre={self.nombre!r})"


class Libro(Base):
    """Obra del catálogo: PDF, CBZ, CBR o carpeta de imágenes."""

    __tablename__ = "libros"
    __table_args__ = (
        Index("idx_libros_genero", "id_genero"),
        Index("idx_libros_fecha", "fecha_subida"),
        {"mysql_engine": "InnoDB"},
    )

    id_libro: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    formato: Mapped[str] = mapped_column(String(20), nullable=False)
    # UNIQUE: es la clave que usa el "upsert" al subir un archivo.
    ruta_archivo: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    ruta_portada: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    id_genero: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "generos.id_genero",
            name="fk_libros_genero",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    total_paginas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    subido_por: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "usuarios.id_usuario",
            name="fk_libros_usuario",
            ondelete="SET NULL",
            onupdate="CASCADE",
        ),
        nullable=True,
    )
    fecha_subida: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp()
    )

    genero: Mapped[Optional["Genero"]] = relationship(back_populates="libros")
    subido_por_usuario: Mapped[Optional["Usuario"]] = relationship(
        back_populates="libros_subidos"
    )
    resenas: Mapped[list["Resena"]] = relationship(
        back_populates="libro",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progresos: Mapped[list["ProgresoLectura"]] = relationship(
        back_populates="libro",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"Libro(id_libro={self.id_libro!r}, titulo={self.titulo!r})"


class Resena(Base):
    """Calificación (1–5) y comentario de un usuario sobre una obra.

    La restricción ``UNIQUE (id_libro, id_usuario)`` garantiza una sola fila
    por usuario y libro; para "volver a calificar" se actualiza la existente.
    """

    __tablename__ = "resenas"
    __table_args__ = (
        CheckConstraint("calificacion BETWEEN 1 AND 5", name="chk_calificacion"),
        UniqueConstraint("id_libro", "id_usuario", name="uq_resena_usuario_libro"),
        {"mysql_engine": "InnoDB"},
    )

    id_resena: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_libro: Mapped[int] = mapped_column(
        ForeignKey(
            "libros.id_libro",
            name="fk_resenas_libro",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey(
            "usuarios.id_usuario",
            name="fk_resenas_usuario",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        nullable=False,
    )
    # TINYINT explícito para que coincida exactamente con el esquema SQL.
    calificacion: Mapped[int] = mapped_column(mysql.TINYINT, nullable=False)
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_creacion: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp()
    )

    libro: Mapped["Libro"] = relationship(back_populates="resenas")
    usuario: Mapped["Usuario"] = relationship(back_populates="resenas")

    def __repr__(self) -> str:
        return (
            f"Resena(id_resena={self.id_resena!r}, "
            f"id_libro={self.id_libro!r}, id_usuario={self.id_usuario!r}, "
            f"calificacion={self.calificacion!r})"
        )


class ProgresoLectura(Base):
    """Última página leída: una fila por usuario y libro (clave compuesta)."""

    __tablename__ = "progreso_lectura"
    __table_args__ = {"mysql_engine": "InnoDB"}

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey(
            "usuarios.id_usuario",
            name="fk_progreso_usuario",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    id_libro: Mapped[int] = mapped_column(
        ForeignKey(
            "libros.id_libro",
            name="fk_progreso_libro",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    ultima_pagina: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    # Equivale a TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP.
    actualizado_en: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="progresos")
    libro: Mapped["Libro"] = relationship(back_populates="progresos")

    def __repr__(self) -> str:
        return (
            f"ProgresoLectura(id_usuario={self.id_usuario!r}, "
            f"id_libro={self.id_libro!r}, ultima_pagina={self.ultima_pagina!r})"
        )


# --------------------------------------------------------------------------- #
# Motor y sesiones
# --------------------------------------------------------------------------- #
def construir_url(config: Optional[dict] = None) -> URL:
    """Construye la URL de conexión para MySQL.

    Se usa :meth:`URL.create` en lugar de concatenar texto para que una
    contraseña con ``@``, ``:`` o ``/`` no rompa la cadena de conexión.
    """
    config = config or load_config()
    return URL.create(
        "mysql+mysqlconnector",
        username=config.get("user") or "",
        password=config.get("password") or "",
        host=config.get("host") or "127.0.0.1",
        port=int(config.get("port") or 3306),
        database=config.get("database") or "cosmicstream_db",
        query={"charset": "utf8mb4"},
    )


def crear_engine(config: Optional[dict] = None, echo: bool = False) -> Engine:
    """Crea un motor de SQLAlchemy (no abre conexión hasta la primera consulta).

    ``pool_pre_ping`` comprueba la conexión antes de usarla y ``pool_recycle``
    la renueva cada hora; así MySQL no cierra conexiones inactivas por sorpresa.
    """
    return create_engine(
        construir_url(config),
        echo=echo,
        pool_pre_ping=True,
        pool_recycle=3600,
        future=True,
    )


# ``ORM_ECHO=1`` imprime el SQL generado; útil para aprender qué hace el ORM.
engine: Engine = crear_engine(echo=os.environ.get("ORM_ECHO") == "1")

# ``expire_on_commit=False`` permite seguir leyendo los atributos después del
# commit sin que SQLAlchemy vuelva a consultar la base.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def sesion() -> Iterator[Session]:
    """Sesión con transacción automática.

    ``commit`` si el bloque termina bien, ``rollback`` si lanza una excepción
    y ``close`` siempre. Equivale a ``db_cursor()`` de ``src/db.py``, pero
    devolviendo una ``Session`` del ORM::

        with sesion() as db:
            db.add(Genero(nombre="Misterio"))
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def crear_tablas_si_faltan() -> None:
    """Crea las tablas que falten según el mapeo.

    ⚠️ **No borra ni modifica tablas existentes.** Para bases nuevas es
    suficiente; para bases antiguas sigue usando ``tools/migrar_bd.py``.
    """
    Base.metadata.create_all(engine)


def verificar_conexion() -> tuple[bool, str]:
    """Devuelve ``(True, "ok")`` si la base responde, o ``(False, motivo)``."""
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        return True, "ok"
    except SQLAlchemyError as exc:
        return False, str(exc)
