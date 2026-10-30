"""Utilidades de contraseñas: hashing PBKDF2-HMAC-SHA256 y validación.

Formato almacenado en la columna ``usuarios.password``::

    pbkdf2_sha256$260000$<salt_hex>$<hash_hex>

Ventajas frente a guardar texto plano:

* La base de datos ya no contiene contraseñas legibles.
* Cada contraseña usa una *sal* aleatoria distinta, así que dos usuarios con la
  misma clave tienen hashes diferentes (no se pueden comparar entre sí).
* PBKDF2 es lento a propósito: probar millones de combinaciones cuesta caro.

El módulo también acepta contraseñas heredadas en texto plano para poder
migrarlas sin pedirle nada al usuario (ver :func:`needs_rehash`).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260_000
SALT_BYTES = 16
HASH_NAME = "sha256"
SEPARATOR = "$"

MIN_PASSWORD_LENGTH = 6
RECOMMENDED_PASSWORD_LENGTH = 10

# Un nombre de usuario solo admite letras (con acentos) y espacios: nada de
# números ni símbolos. El patrón está en sintaxis PCRE2 porque se usa también
# en un ``QRegularExpressionValidator`` para bloquear las teclas al escribir.
PATRON_USERNAME = r"^[\p{L} ]*$"
MAX_USERNAME_LENGTH = 100


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #
def _derive(password: str, salt: str, iterations: int) -> str:
    """Deriva el hash a partir de la contraseña y la sal."""
    return hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Devuelve la contraseña hasheada, lista para guardar en MySQL."""
    if not isinstance(password, str):
        raise TypeError("La contraseña debe ser una cadena de texto.")
    salt = secrets.token_hex(SALT_BYTES)
    return SEPARATOR.join((ALGORITHM, str(iterations), salt, _derive(password, salt, iterations)))


def is_hashed(stored: str | None) -> bool:
    """True si el valor guardado ya está en el formato PBKDF2."""
    if not isinstance(stored, str):
        return False
    parts = stored.split(SEPARATOR)
    return len(parts) == 4 and parts[0] == ALGORITHM


def verify_password(password: str, stored: str | None) -> bool:
    """Compara una contraseña con el valor almacenado.

    Usa comparación de tiempo constante (``hmac.compare_digest``) para no
    filtrar información por el tiempo de respuesta.
    """
    if not password or not stored:
        return False

    if not is_hashed(stored):
        # Compatibilidad con bases de datos antiguas con texto plano.
        return hmac.compare_digest(password, stored)

    try:
        _, iterations, salt, digest = stored.split(SEPARATOR)
        candidate = _derive(password, salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, digest)


def needs_rehash(stored: str | None) -> bool:
    """True si la contraseña está en texto plano o con menos iteraciones."""
    if not is_hashed(stored):
        return True
    try:
        _, iterations, _, _ = (stored or "").split(SEPARATOR)
        return int(iterations) < ITERATIONS
    except (ValueError, TypeError):
        return True


# --------------------------------------------------------------------------- #
# Política de contraseñas
# --------------------------------------------------------------------------- #
def validate_password(password: str, username: str = "") -> tuple[bool, str]:
    """Valida una contraseña nueva. Devuelve ``(es_valida, mensaje)``."""
    if not password:
        return False, "La contraseña no puede estar vacía."
    if password != password.strip():
        return False, "La contraseña no puede empezar ni terminar con espacios."
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if username and password.strip().lower() == username.strip().lower():
        return False, "La contraseña no puede ser igual al nombre de usuario."
    if password.isdigit() and len(password) < RECOMMENDED_PASSWORD_LENGTH:
        return False, (
            "Una contraseña solo numérica debe tener al menos "
            f"{RECOMMENDED_PASSWORD_LENGTH} dígitos."
        )
    return True, ""


def username_caracteres_validos(username: str) -> bool:
    """True si el nombre de usuario solo tiene letras y espacios."""
    return all(c.isalpha() or c == " " for c in (username or ""))


def validate_username(username: str) -> tuple[bool, str]:
    """Valida un nombre de usuario nuevo."""
    username = (username or "").strip()
    if not username:
        return False, "El nombre de usuario no puede estar vacío."
    if not username_caracteres_validos(username):
        return False, (
            "El nombre de usuario solo puede tener letras y espacios "
            "(sin números ni símbolos)."
        )
    if len(username) < 3:
        return False, "El nombre de usuario debe tener al menos 3 caracteres."
    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"El nombre de usuario no puede superar los {MAX_USERNAME_LENGTH} caracteres."
    return True, ""


def password_strength(password: str) -> tuple[int, str]:
    """Nivel de fuerza de 0 a 4 con una etiqueta, para mostrar en el registro."""
    if not password:
        return 0, ""
    score = 0
    if len(password) >= MIN_PASSWORD_LENGTH:
        score += 1
    if len(password) >= RECOMMENDED_PASSWORD_LENGTH:
        score += 1
    if any(c.isupper() for c in password) and any(c.islower() for c in password):
        score += 1
    if any(not c.isalnum() for c in password) or any(c.isdigit() for c in password):
        score += 1
    labels = {0: "Muy débil", 1: "Débil", 2: "Aceptable", 3: "Buena", 4: "Fuerte"}
    return score, labels[score]
