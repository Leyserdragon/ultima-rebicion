"""Autenticación de usuarios con contraseñas hasheadas.

Puntos importantes:

* **Mensaje genérico**: nunca se revela si el usuario existe o si solo la
  contraseña estaba mal, porque eso permite enumerar cuentas.
* **Migración transparente**: si una contraseña está guardada en texto plano
  (bases de datos antiguas), se valida y se reemplaza por su hash PBKDF2 en el
  mismo inicio de sesión.
* **Bloqueo temporal**: tras varios intentos fallidos se espera un poco antes
  de volver a probar, para frenar ataques de fuerza bruta.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .db import DBError, db_cursor
from .security import hash_password, needs_rehash, verify_password

MAX_INTENTOS = 5
SEGUNDOS_BLOQUEO = 60
# Tope para el diccionario en memoria: probar nombres al azar no debe hacerlo
# crecer sin límite durante toda la sesión.
MAX_REGISTROS_INTENTOS = 1000

# Mensaje único para credenciales erróneas: no distingue entre «usuario
# inexistente» y «contraseña incorrecta» (evita enumerar cuentas).
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrecta."

# Estado en memoria: {username_normalizado: (fallos, bloqueado_hasta)}
_intentos: dict[str, tuple[int, float]] = {}


@dataclass(frozen=True)
class UsuarioSesion:
    """Usuario autenticado."""

    id_usuario: int
    username: str
    id_rol: int
    rol: str

    @property
    def es_admin(self) -> bool:
        return self.id_rol == 1


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    mensaje: str
    usuario: Optional[UsuarioSesion] = None


def _bloqueado(username: str) -> Optional[str]:
    """Devuelve un mensaje si el usuario está bloqueado temporalmente."""
    _, hasta = _intentos.get(username, (0, 0.0))
    restante = hasta - time.monotonic()
    if restante > 0:
        return f"Demasiados intentos fallidos. Espera {int(restante) + 1} segundos."
    return None


def _registrar_fallo(username: str) -> None:
    fallos, _ = _intentos.get(username, (0, 0.0))
    fallos += 1
    hasta = time.monotonic() + SEGUNDOS_BLOQUEO if fallos >= MAX_INTENTOS else 0.0
    _intentos[username] = (0 if hasta else fallos, hasta)

    if len(_intentos) > MAX_REGISTROS_INTENTOS:
        # Primero se descartan los bloqueos ya vencidos; si aun así sobra,
        # se elimina el registro más antiguo (los dict conservan el orden).
        ahora = time.monotonic()
        for clave in [c for c, (_, h) in _intentos.items() if h and h <= ahora]:
            _intentos.pop(clave, None)
        while len(_intentos) > MAX_REGISTROS_INTENTOS:
            _intentos.pop(next(iter(_intentos)))


def limpiar_intentos(username: str | None = None) -> None:
    """Reinicia el contador de intentos fallidos."""
    if username is None:
        _intentos.clear()
    else:
        _intentos.pop(username.strip().lower(), None)


def check_user(username: str, password: str) -> AuthResult:
    """Verifica credenciales y devuelve un :class:`AuthResult`."""
    username = (username or "").strip()
    if not username or not password:
        return AuthResult(False, "Completa todos los campos.")

    clave = username.lower()
    aviso = _bloqueado(clave)
    if aviso:
        return AuthResult(False, aviso)

    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                """
                SELECT u.id_usuario, u.username, u.password, u.id_rol, r.nombre AS rol
                FROM usuarios u
                JOIN roles r ON r.id_rol = u.id_rol
                WHERE u.username = %s
                """,
                (username,),
            )
            fila = cur.fetchone()

            if not fila or not verify_password(password, fila["password"]):
                _registrar_fallo(clave)
                return AuthResult(False, MENSAJE_CREDENCIALES)

            # Migración transparente de contraseñas en texto plano.
            if needs_rehash(fila["password"]):
                cur.execute(
                    "UPDATE usuarios SET password = %s WHERE id_usuario = %s",
                    (hash_password(password), fila["id_usuario"]),
                )

            cur.execute(
                "UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id_usuario = %s",
                (fila["id_usuario"],),
            )

        limpiar_intentos(clave)
        usuario = UsuarioSesion(
            id_usuario=int(fila["id_usuario"]),
            username=fila["username"],
            id_rol=int(fila["id_rol"]),
            rol=fila["rol"],
        )
        return AuthResult(True, "Sesión iniciada.", usuario)

    except DBError as exc:
        return AuthResult(False, f"No hay conexión con la base de datos.\n{exc}")
