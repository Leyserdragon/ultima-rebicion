"""Gestión de usuarios: registro, listado, roles y borrado seguro."""

from __future__ import annotations

from typing import Any, Optional

from .db import DBError, db_cursor
from .security import hash_password, validate_password, validate_username

ROL_ADMIN = 1
ROL_LECTOR = 2


def contar_admins() -> int:
    """Cantidad de usuarios con rol administrador."""
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT COUNT(*) FROM usuarios WHERE id_rol = %s", (ROL_ADMIN,))
            return int(cur.fetchone()[0])
    except DBError:
        return 0


def registrar_usuario(username: str, password: str, id_rol: int = ROL_LECTOR) -> tuple[bool, str]:
    """Registra un usuario nuevo con la contraseña hasheada."""
    username = (username or "").strip()

    ok, msg = validate_username(username)
    if not ok:
        return False, msg
    ok, msg = validate_password(password, username)
    if not ok:
        return False, msg

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT id_usuario FROM usuarios WHERE username = %s", (username,))
            if cur.fetchone():
                return False, f"El usuario «{username}» ya existe."

            cur.execute(
                "INSERT INTO usuarios (username, password, id_rol) VALUES (%s, %s, %s)",
                (username, hash_password(password), id_rol),
            )
        return True, "Cuenta creada correctamente. Ya puedes iniciar sesión."
    except DBError as exc:
        return False, f"No se pudo crear la cuenta: {exc}"


def listar_usuarios() -> list[dict[str, Any]]:
    """Usuarios con rol, fecha de registro y último acceso."""
    query = """
        SELECT u.id_usuario, u.username, u.id_rol, r.nombre AS rol,
               u.created_at, u.ultimo_acceso
        FROM usuarios u
        JOIN roles r ON r.id_rol = u.id_rol
        ORDER BY u.id_rol ASC, u.username ASC
    """
    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(query)
            return list(cur.fetchall())
    except DBError as exc:
        print(f"[!] No se pudieron listar los usuarios: {exc}")
        return []


def eliminar_usuario(id_usuario: int, id_solicitante: Optional[int] = None) -> tuple[bool, str]:
    """Elimina un usuario aplicando dos protecciones.

    * No permite borrarse a uno mismo (evita quedarse fuera del panel).
    * No permite dejar la base de datos sin ningún administrador.
    """
    if id_solicitante is not None and int(id_usuario) == int(id_solicitante):
        return False, "No puedes eliminar tu propia cuenta mientras la usas."

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT username, id_rol FROM usuarios WHERE id_usuario = %s", (id_usuario,))
            fila = cur.fetchone()
            if not fila:
                return False, "El usuario no existe."

            if int(fila["id_rol"]) == ROL_ADMIN:
                cur.execute("SELECT COUNT(*) AS total FROM usuarios WHERE id_rol = %s", (ROL_ADMIN,))
                if int(cur.fetchone()["total"]) <= 1:
                    return False, "No puedes eliminar al último administrador del sistema."

            cur.execute("DELETE FROM usuarios WHERE id_usuario = %s", (id_usuario,))
        return True, f"Usuario «{fila['username']}» eliminado."
    except DBError as exc:
        return False, f"No se pudo eliminar: {exc}"


def cambiar_rol(id_usuario: int, id_rol: int, id_solicitante: Optional[int] = None) -> tuple[bool, str]:
    """Cambia el rol de un usuario sin dejar el sistema sin administradores."""
    if id_solicitante is not None and int(id_usuario) == int(id_solicitante):
        return False, "No puedes cambiar tu propio rol."

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute("SELECT id_rol FROM usuarios WHERE id_usuario = %s", (id_usuario,))
            fila = cur.fetchone()
            if not fila:
                return False, "El usuario no existe."
            if int(fila["id_rol"]) == ROL_ADMIN and int(id_rol) != ROL_ADMIN:
                cur.execute("SELECT COUNT(*) AS total FROM usuarios WHERE id_rol = %s", (ROL_ADMIN,))
                if int(cur.fetchone()["total"]) <= 1:
                    return False, "No puedes quitar el rol al último administrador."

            cur.execute("UPDATE usuarios SET id_rol = %s WHERE id_usuario = %s", (id_rol, id_usuario))
        return True, "Rol actualizado."
    except DBError as exc:
        return False, f"No se pudo cambiar el rol: {exc}"


def cambiar_password(id_usuario: int, password_actual: str, password_nueva: str, es_admin: bool = False) -> tuple[bool, str]:
    """Cambia la contraseña verificando la actual (salvo que sea admin)."""
    ok, msg = validate_password(password_nueva)
    if not ok:
        return False, msg

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT username, password FROM usuarios WHERE id_usuario = %s",
                (id_usuario,),
            )
            fila = cur.fetchone()
            if not fila:
                return False, "El usuario no existe."

            if not es_admin:
                from .security import verify_password

                if not verify_password(password_actual, fila["password"]):
                    return False, "La contraseña actual es incorrecta."

            ok, msg = validate_password(password_nueva, fila["username"])
            if not ok:
                return False, msg

            cur.execute(
                "UPDATE usuarios SET password = %s WHERE id_usuario = %s",
                (hash_password(password_nueva), id_usuario),
            )
        return True, "Contraseña actualizada correctamente."
    except DBError as exc:
        return False, f"No se pudo cambiar la contraseña: {exc}"


def restablecer_password(id_usuario: int, password_nueva: str) -> tuple[bool, str]:
    """Restablece la contraseña de otro usuario (solo administradores)."""
    ok, msg = validate_password(password_nueva)
    if not ok:
        return False, msg
    try:
        with db_cursor() as (_, cur):
            cur.execute(
                "UPDATE usuarios SET password = %s WHERE id_usuario = %s",
                (hash_password(password_nueva), id_usuario),
            )
            if cur.rowcount == 0:
                return False, "El usuario no existe o la contraseña es la misma."
        return True, "Contraseña restablecida."
    except DBError as exc:
        return False, f"No se pudo restablecer: {exc}"
