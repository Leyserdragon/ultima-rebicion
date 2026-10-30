"""Consultas de libros, géneros, reseñas y progreso de lectura.

Todas las funciones devuelven **diccionarios** (no tuplas) para que el resto de
la interfaz use nombres de columna en lugar de índices como ``fila[6]``, que se
rompen en cuanto cambia el orden de un ``SELECT``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .db import DBError, db_cursor

Libro = dict[str, Any]
Genero = dict[str, Any]
Resena = dict[str, Any]


def _normalizar_ruta(ruta: str | Path | None) -> Optional[str]:
    """Convierte una ruta a texto absoluto con separadores ``/``."""
    if not ruta:
        return None
    try:
        return str(Path(ruta).expanduser().resolve()).replace("\\", "/")
    except OSError:
        return str(ruta).replace("\\", "/")


# --------------------------------------------------------------------------- #
# Géneros
# --------------------------------------------------------------------------- #
def listar_generos() -> list[Genero]:
    """Lista los géneros con su cantidad de libros: ``{id_genero, nombre, total}``."""
    query = """
        SELECT g.id_genero, g.nombre, COUNT(l.id_libro) AS total
        FROM generos g
        LEFT JOIN libros l ON l.id_genero = g.id_genero
        GROUP BY g.id_genero, g.nombre
        ORDER BY g.nombre ASC
    """
    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(query)
            return list(cur.fetchall())
    except DBError as exc:
        print(f"[!] No se pudieron listar los géneros: {exc}")
        return []


def crear_genero(nombre: str) -> tuple[bool, str]:
    """Crea un género nuevo. Devuelve ``(ok, mensaje)``."""
    nombre = (nombre or "").strip()
    if not nombre:
        return False, "El nombre del género no puede estar vacío."
    if len(nombre) > 60:
        return False, "El nombre del género es demasiado largo (máx. 60)."

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT id_genero FROM generos WHERE nombre = %s", (nombre,))
            if cur.fetchone():
                return False, f"El género «{nombre}» ya existe."
            cur.execute("INSERT INTO generos (nombre) VALUES (%s)", (nombre,))
        return True, f"Género «{nombre}» creado."
    except DBError as exc:
        return False, f"No se pudo crear el género: {exc}"


def eliminar_genero(id_genero: int) -> tuple[bool, str]:
    """Elimina un género (los libros quedan como «Sin género»)."""
    try:
        with db_cursor() as (_, cur):
            cur.execute("DELETE FROM generos WHERE id_genero = %s", (id_genero,))
            if cur.rowcount == 0:
                return False, "El género no existe."
        return True, "Género eliminado."
    except DBError as exc:
        return False, f"No se pudo eliminar: {exc}"


# --------------------------------------------------------------------------- #
# Libros
# --------------------------------------------------------------------------- #
def listar_libros() -> list[Libro]:
    """Libros con autor, género, promedio de reseñas y progreso de lectura."""
    query = """
        SELECT
            l.id_libro,
            l.titulo,
            l.formato,
            l.ruta_archivo,
            COALESCE(u.username, 'Admin') AS subido_por,
            l.fecha_subida,
            l.ruta_portada,
            COALESCE(g.nombre, 'Sin género') AS genero,
            l.id_genero,
            l.total_paginas,
            ROUND(COALESCE(AVG(r.calificacion), 0), 1) AS promedio,
            COUNT(r.id_resena) AS total_resenas
        FROM libros l
        LEFT JOIN usuarios u ON l.subido_por = u.id_usuario
        LEFT JOIN generos  g ON l.id_genero  = g.id_genero
        LEFT JOIN resenas  r ON r.id_libro   = l.id_libro
        GROUP BY l.id_libro, u.username, g.nombre
        ORDER BY l.fecha_subida DESC, l.id_libro DESC
    """
    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(query)
            return list(cur.fetchall())
    except DBError as exc:
        print(f"[!] No se pudieron listar los libros: {exc}")
        return []


def obtener_libro(id_libro: int) -> Optional[Libro]:
    """Devuelve un libro por su id (con el mismo formato que :func:`listar_libros`)."""
    libros = [libro for libro in listar_libros() if libro["id_libro"] == id_libro]
    return libros[0] if libros else None


def registrar_libro(
    titulo: str,
    formato: str,
    ruta_archivo: str,
    id_usuario: Optional[int] = None,
    ruta_portada: Optional[str] = None,
    id_genero: Optional[int] = None,
    total_paginas: Optional[int] = None,
) -> tuple[bool, str]:
    """Inserta o actualiza un libro usando ``ruta_archivo`` como clave única."""
    titulo = (titulo or "").strip()
    if not titulo:
        return False, "El título no puede estar vacío."

    query = """
        INSERT INTO libros
            (titulo, formato, ruta_archivo, subido_por, ruta_portada, id_genero, total_paginas)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            titulo        = VALUES(titulo),
            formato       = VALUES(formato),
            subido_por    = VALUES(subido_por),
            ruta_portada  = COALESCE(VALUES(ruta_portada), ruta_portada),
            id_genero     = COALESCE(VALUES(id_genero), id_genero),
            total_paginas = COALESCE(VALUES(total_paginas), total_paginas)
    """
    try:
        with db_cursor() as (_, cur):
            if not id_usuario:
                cur.execute("SELECT id_usuario FROM usuarios WHERE id_rol = 1 ORDER BY id_usuario LIMIT 1")
                fila = cur.fetchone()
                id_usuario = fila[0] if fila else None

            cur.execute(
                query,
                (
                    titulo,
                    (formato or "").upper().strip(),
                    _normalizar_ruta(ruta_archivo),
                    id_usuario,
                    _normalizar_ruta(ruta_portada),
                    id_genero,
                    total_paginas,
                ),
            )
        return True, f"«{titulo}» registrado."
    except DBError as exc:
        return False, f"No se pudo registrar «{titulo}»: {exc}"


NO_CAMBIAR = object()
"""Centinela para distinguir «no toques este campo» de «déjalo vacío».

Con ``None`` no se puede: al editar un libro, «Sin género» también es ``None``.
"""


def actualizar_libro(
    id_libro: int,
    titulo: Optional[str] = None,
    id_genero: Any = NO_CAMBIAR,
    ruta_portada: Any = NO_CAMBIAR,
) -> tuple[bool, str]:
    """Actualiza los campos indicados de un libro.

    Solo se modifica lo que se pasa explícitamente. Para **borrar** el género
    o la portada se pasa ``None``::

        actualizar_libro(3, id_genero=None)        # quita el género
        actualizar_libro(3, ruta_portada=None)     # quita la portada
    """
    campos: list[str] = []
    valores: list[Any] = []

    if titulo is not None and titulo.strip():
        campos.append("titulo = %s")
        valores.append(titulo.strip())
    if id_genero is not NO_CAMBIAR:
        campos.append("id_genero = %s")
        valores.append(id_genero or None)
    if ruta_portada is not NO_CAMBIAR:
        campos.append("ruta_portada = %s")
        valores.append(_normalizar_ruta(ruta_portada))

    if not campos:
        return False, "No hay cambios que guardar."

    valores.append(id_libro)
    try:
        with db_cursor() as (_, cur):
            cur.execute(f"UPDATE libros SET {', '.join(campos)} WHERE id_libro = %s", tuple(valores))
        return True, "Libro actualizado."
    except DBError as exc:
        return False, f"No se pudo actualizar: {exc}"


def actualizar_portada_libro(id_libro: int, ruta_portada: str) -> bool:
    """Compatibilidad: actualiza solo la portada."""
    ok, _ = actualizar_libro(id_libro, ruta_portada=ruta_portada)
    return ok


def eliminar_libro_db(id_libro: int) -> tuple[bool, str]:
    """Borra el registro y devuelve la ruta del archivo físico para borrarlo."""
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT ruta_archivo FROM libros WHERE id_libro = %s", (id_libro,))
            fila = cur.fetchone()
            if not fila:
                return False, ""
            ruta = fila[0] or ""
            cur.execute("DELETE FROM libros WHERE id_libro = %s", (id_libro,))
        return True, ruta
    except DBError as exc:
        print(f"[!] No se pudo eliminar el libro {id_libro}: {exc}")
        return False, ""


# --------------------------------------------------------------------------- #
# Reseñas
# --------------------------------------------------------------------------- #
def agregar_resena(id_libro: int, id_usuario: int, calificacion: int, comentario: str) -> tuple[bool, str]:
    """Crea o reemplaza la reseña del usuario para ese libro (una por usuario)."""
    comentario = (comentario or "").strip()
    if not 1 <= int(calificacion) <= 5:
        return False, "La calificación debe estar entre 1 y 5."
    if not comentario:
        return False, "El comentario no puede estar vacío."

    query = """
        INSERT INTO resenas (id_libro, id_usuario, calificacion, comentario)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            calificacion    = VALUES(calificacion),
            comentario      = VALUES(comentario),
            fecha_creacion  = CURRENT_TIMESTAMP
    """
    try:
        with db_cursor() as (_, cur):
            cur.execute(query, (id_libro, id_usuario, int(calificacion), comentario))
        return True, "Reseña guardada."
    except DBError as exc:
        return False, f"No se pudo guardar la reseña: {exc}"


def listar_resenas(id_libro: int) -> list[Resena]:
    """Reseñas de un libro, la más reciente primero."""
    query = """
        SELECT r.id_usuario, u.username, r.calificacion, r.comentario, r.fecha_creacion
        FROM resenas r
        JOIN usuarios u ON r.id_usuario = u.id_usuario
        WHERE r.id_libro = %s
        ORDER BY r.fecha_creacion DESC
    """
    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(query, (id_libro,))
            return list(cur.fetchall())
    except DBError as exc:
        print(f"[!] No se pudieron listar las reseñas: {exc}")
        return []


def eliminar_resena(id_libro: int, id_usuario: int) -> tuple[bool, str]:
    """Borra la reseña del usuario para ese libro."""
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "DELETE FROM resenas WHERE id_libro = %s AND id_usuario = %s",
                (id_libro, id_usuario),
            )
            if cur.rowcount == 0:
                return False, "No tienes una reseña en esta obra."
        return True, "Reseña eliminada."
    except DBError as exc:
        return False, f"No se pudo eliminar: {exc}"


def resumen_resenas(id_libro: int) -> tuple[float, int]:
    """Devuelve ``(promedio, cantidad)`` de reseñas del libro."""
    return promedio_calificacion(id_libro)


def promedio_calificacion(id_libro: int) -> tuple[float, int]:
    """Promedio de estrellas (0.0–5.0) y cuántas calificaciones tiene la obra.

    El promedio se calcula siempre en MySQL con ``AVG``: así no hay que traer
    todas las filas a Python y el resultado es el mismo para todos los usuarios.
    """
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT COALESCE(AVG(calificacion), 0), COUNT(*) FROM resenas WHERE id_libro = %s",
                (id_libro,),
            )
            promedio, cantidad = cur.fetchone()
        return round(float(promedio or 0), 1), int(cantidad or 0)
    except DBError:
        return 0.0, 0


def obtener_calificacion_usuario(id_libro: int, id_usuario: int) -> int:
    """Estrellas que este usuario le dio a la obra (0 si aún no la calificó)."""
    if not id_usuario or not id_libro:
        return 0
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT calificacion FROM resenas WHERE id_libro = %s AND id_usuario = %s",
                (id_libro, id_usuario),
            )
            fila = cur.fetchone()
        return int(fila[0]) if fila else 0
    except DBError:
        return 0


def calificar_libro(id_libro: int, id_usuario: int, calificacion: int) -> tuple[bool, str]:
    """Guarda la calificación en estrellas del usuario (1 a 5).

    Reutiliza la tabla ``resenas``: si el usuario ya había escrito un
    comentario, se conserva y solo cambia la nota. Volver a calificar
    actualiza el valor en lugar de crear otra fila.
    """
    if not id_usuario:
        return False, "Necesitas iniciar sesión para calificar."
    try:
        valor = int(calificacion)
    except (TypeError, ValueError):
        return False, "La calificación debe ser un número entre 1 y 5."
    if not 1 <= valor <= 5:
        return False, "La calificación debe estar entre 1 y 5."

    query = """
        INSERT INTO resenas (id_libro, id_usuario, calificacion, comentario)
        VALUES (%s, %s, %s, '')
        ON DUPLICATE KEY UPDATE calificacion = VALUES(calificacion)
    """
    try:
        with db_cursor() as (_, cur):
            cur.execute(query, (id_libro, id_usuario, valor))
        return True, "Calificación guardada."
    except DBError as exc:
        return False, f"No se pudo guardar la calificación: {exc}"


# --------------------------------------------------------------------------- #
# Progreso de lectura
# --------------------------------------------------------------------------- #
def guardar_progreso(id_usuario: int, id_libro: int, pagina: int) -> None:
    """Guarda en qué página se quedó el usuario."""
    if not id_usuario or not id_libro:
        return
    query = """
        INSERT INTO progreso_lectura (id_usuario, id_libro, ultima_pagina)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            ultima_pagina  = VALUES(ultima_pagina),
            actualizado_en = CURRENT_TIMESTAMP
    """
    try:
        with db_cursor() as (_, cur):
            cur.execute(query, (id_usuario, id_libro, max(0, int(pagina))))
    except DBError as exc:
        print(f"[!] No se pudo guardar el progreso: {exc}")


def obtener_progreso(id_usuario: int, id_libro: int) -> Optional[int]:
    """Página guardada del usuario para ese libro.

    Devuelve ``None`` si nunca lo abrió. El ``0`` significa «está en la
    primera página», así que no sirve como «sin progreso».
    """
    if not id_usuario or not id_libro:
        return None
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT ultima_pagina FROM progreso_lectura WHERE id_usuario = %s AND id_libro = %s",
                (id_usuario, id_libro),
            )
            fila = cur.fetchone()
        return int(fila[0]) if fila else None
    except DBError:
        return None


def mapar_progreso(id_usuario: int) -> dict[int, int]:
    """``{id_libro: ultima_pagina}`` para pintar «Continuar» en la galería."""
    if not id_usuario:
        return {}
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "SELECT id_libro, ultima_pagina FROM progreso_lectura WHERE id_usuario = %s",
                (id_usuario,),
            )
            return {int(f[0]): int(f[1] or 0) for f in cur.fetchall()}
    except DBError:
        return {}
