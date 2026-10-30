# CosmicStream Reader

Lector de escritorio para **mangas, manhwas y cómics** hecho con **Python + PySide6 + MySQL**.
Organiza tu biblioteca, extrae portadas automáticamente, guarda tu progreso de lectura y permite
reseñar cada obra.

---

## Índice

1. [Características](#características)
2. [Requisitos](#requisitos)
3. [Instalación](#instalación)
4. [Configurar la base de datos](#configurar-la-base-de-datos)
5. [Configurar la conexión](#configurar-la-conexión)
6. [Ejecutar la aplicación](#ejecutar-la-aplicación)
7. [Atajos del lector](#atajos-del-lector)
8. [Estructura del proyecto](#estructura-del-proyecto)
9. [ORM con SQLAlchemy](#orm-con-sqlalchemy)
10. [Solución de problemas](#solución-de-problemas)
11. [Seguridad](#seguridad)
12. [Funcionalidades (sistema, usuario y admin)](FUNCIONALIDADES.md)
13. [Ejercicios prácticos](#ejercicios-prácticos)

---

> 📄 **Documento detallado de funcionalidades:** [FUNCIONALIDADES.md](FUNCIONALIDADES.md)
> (qué hace el sistema, qué puede hacer un lector y qué puede hacer un administrador).

---

## Características

| Área | Qué hace |
|---|---|
| **Biblioteca** | Buscador por título/género, filtro por género y orden (recientes, título, mejor valorados). |
| **Formatos** | PDF, CBZ, ZIP, CBR, RAR e imágenes sueltas (JPG, PNG, WEBP, BMP, GIF, AVIF). |
| **Lector** | Zoom, ajuste al ancho o página completa (por defecto), pantalla completa, modo manga (derecha → izquierda) y guardado del progreso. |
| **Portadas** | Se extraen solas al subir el archivo y se guardan redimensionadas en `data/covers/`. |
| **Reseñas** | Una reseña por usuario y obra (calificación 1–5 + comentario). Repetir la reseña la actualiza. |
| **Calificación** | Estrellas de 1 a 5 en la ficha del libro, con promedio de la comunidad calculado en MySQL (`AVG`) y guardado por usuario. |
| **Administración** | Subida por drag & drop o sincronización de carpeta, edición de metadatos, gestión de géneros y usuarios. |
| **Contraseñas** | Hash **PBKDF2-HMAC-SHA256** con sal aleatoria. Nunca se guarda texto plano. |

---

## Requisitos

- **Python 3.10+** (probado con 3.12.3).
- **MySQL 8.0+** o **MariaDB 10.5+** en marcha.
- **`unrar`** solo si vas a leer archivos `.cbr` / `.rar`:

```bash
sudo apt install unrar
```

> ⚠️ **Aviso:** `sudo apt install` modifica el sistema. Si no necesitas CBR/RAR, sáltate este paso:
> la aplicación funciona igual con PDF, CBZ, ZIP e imágenes.

---

## Instalación

Desde la carpeta `comic/`:

```bash
# 1. Entorno virtual (aísla las dependencias del Python del sistema)
python3 -m venv .venv

# 2. Activar el entorno
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

**Por qué un entorno virtual:** evita que las librerías del proyecto choquen con las del sistema
y permite borrar todo con solo eliminar `.venv/`.

---

## Configurar la base de datos

### Opción A — Instalación nueva (recomendada)

```bash
mysql -u root -p < cosmicstream_db.sql
```

Esto crea la base `cosmicstream_db`, las tablas y los datos iniciales. El script usa
`CREATE TABLE IF NOT EXISTS`, así que **no borra nada** si lo ejecutas otra vez.

### Opción B — Ya tienes una base antigua

```bash
source .venv/bin/activate
python tools/migrar_bd.py
```

El script es **idempotente** (se puede repetir sin efectos secundarios) y:

1. Crea la base si no existe.
2. Crea las tablas que falten.
3. Añade a `libros` y `usuarios` las columnas nuevas (`ruta_portada`, `id_genero`,
   `total_paginas`, `ultimo_acceso`).
4. Elimina reseñas duplicadas y crea el índice único `(id_libro, id_usuario)`.
5. Convierte las contraseñas en texto plano a hashes PBKDF2.

> ⚠️ **Antes de migrar, haz un respaldo:**
> ```bash
> mysqldump -u root -p cosmicstream_db > respaldo_$(date +%F).sql
> ```
> La migración borra reseñas duplicadas (conserva la más reciente). Sin respaldo no hay vuelta atrás.

### Cuentas de demostración

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `12345` | administrador |
| `eliu leyton` | `123456789` | lector |

> 🔴 **Cambia estas contraseñas en cuanto empieces a usar el sistema de verdad.** Están publicadas
> en el repositorio, así que cualquiera que vea este proyecto las conoce.

---

## Configurar la conexión

La aplicación lee las credenciales en este orden (la primera que exista gana):

1. **Variables de entorno:** `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`.
2. **`config.json`** en la raíz del proyecto.
3. Valores por defecto (`root@127.0.0.1:3306`, sin contraseña).

Copia el ejemplo y edítalo:

```bash
cp config.example.json config.json
```

```json
{
  "host": "127.0.0.1",
  "port": 3306,
  "user": "root",
  "password": "TU_CONTRASEÑA",
  "database": "cosmicstream_db"
}
```

**Por qué un archivo aparte y no el código:** `config.json` está en `.gitignore`, así que tus
credenciales nunca se suben al repositorio. Si prefieres no tenerlas en disco, usa variables de
entorno:

```bash
DB_USER=cosmic DB_PASSWORD=secreto python main.py
```

> 💡 **Mejor práctica:** crea un usuario MySQL dedicado en vez de usar `root`:
> ```sql
> CREATE USER 'cosmic'@'localhost' IDENTIFIED BY 'una_clave_larga';
> GRANT SELECT, INSERT, UPDATE, DELETE ON cosmicstream_db.* TO 'cosmic'@'localhost';
> FLUSH PRIVILEGES;
> ```
> Así, si la aplicación se ve comprometida, el daño queda limitado a esa base y no al servidor entero.

---

## Ejecutar la aplicación

```bash
source .venv/bin/activate
python main.py
```

Si algo falla, el detalle se guarda en `cosmicstream_error.log` y se muestra un aviso legible.

---

## Atajos del lector

| Tecla | Acción |
|---|---|
| `→` / `↓` / `Espacio` | Página siguiente |
| `←` / `↑` | Página anterior |
| `+` / `=` | Acercar |
| `-` | Alejar |
| `0` | Ajustar al ancho |
| `Inicio` / `Fin` | Primera / última página |
| `F11` o `F` | Pantalla completa |
| `Esc` | Salir de pantalla completa |
| Clic izquierdo / derecho | Avanzar / retroceder (se invierte en modo manga) |
| `Ctrl` + rueda | Zoom |

---

## Estructura del proyecto

```
comic/
├── main.py                  # Punto de entrada
├── cosmicstream_db.sql      # Esquema de la base de datos
├── FUNCIONALIDADES.md       # Detalle de funciones (sistema, usuario, admin)
├── config.json              # Credenciales locales (no se versiona)
├── config.example.json      # Plantilla de configuración
├── requirements.txt
├── data/
│   ├── library/             # Tus archivos (no se versiona)
│   └── covers/              # Portadas extraídas (se regeneran solas)
├── src/
│   ├── app.py               # Controlador de navegación entre ventanas
│   ├── db.py                # Conexión y configuración de MySQL
│   ├── orm.py               # Mapeo ORM de las tablas (SQLAlchemy 2.x)
│   ├── security.py          # Hashing y validación de contraseñas
│   ├── auth.py              # Inicio de sesión / sesión activa
│   ├── user_manager.py      # Altas, bajas y roles de usuarios
│   ├── book_manager.py      # Consultas de libros, géneros, reseñas y progreso
│   ├── star_rating.py       # Widget de estrellas (calificación 1–5)
│   ├── library.py           # Lectura de PDF/CBZ/CBR y orden natural de páginas
│   ├── cover_extractor.py   # Extracción y redimensionado de portadas
│   ├── styles.py            # Hoja de estilos QSS global
│   └── *_window.py          # Login, registro, biblioteca, detalle, lector, admin…
└── tools/
    └── migrar_bd.py         # Migración de bases antiguas
```

---

## ORM con SQLAlchemy

`src/orm.py` traduce las seis tablas de `cosmicstream_db.sql` a clases de Python.
La aplicación **sigue usando SQL directo** (`db.py` + `book_manager.py`), así que el
ORM convive en paralelo: puedes migrar consulta por consulta sin romper lo que ya
funciona.

### Qué es un ORM y por qué está aquí

Un **ORM** (*Object-Relational Mapping*) convierte filas de MySQL en objetos y
objetos en filas. En vez de escribir SQL como texto, escribes Python:

| SQL directo (lo actual) | ORM (`src/orm.py`) |
|---|---|
| `SELECT * FROM libros WHERE id_libro = %s` | `db.get(Libro, 7)` |
| `cursor.fetchone()["titulo"]` | `libro.titulo` |
| `JOIN generos …` a mano | `libro.genero.nombre` |
| Cadena SQL concatenada (riesgo de inyección) | Consultas parametrizadas automáticamente |

### Modelos disponibles

| Clase | Tabla | Notas |
|---|---|---|
| `Rol` | `roles` | 1 = administrador, 2 = lector. |
| `Usuario` | `usuarios` | `password` guarda el hash PBKDF2; `es_admin` es una propiedad de solo lectura. |
| `Genero` | `generos` | `nombre` único. |
| `Libro` | `libros` | `ruta_archivo` única; relaciones `genero`, `subido_por_usuario`, `resenas`, `progresos`. |
| `Resena` | `resenas` | `CHECK` de 1–5 y `UNIQUE (id_libro, id_usuario)` replicados en el mapeo. |
| `ProgresoLectura` | `progreso_lectura` | Clave primaria compuesta `(id_usuario, id_libro)`. |

El mapeo respeta nombres de columnas, tamaños `VARCHAR`, `TINYINT` de `calificacion`,
índices (`idx_libros_genero`, `idx_libros_fecha`), el `ON DELETE` / `ON UPDATE` de
cada clave foránea y los nombres de las restricciones (`fk_usuarios_rol`,
`chk_calificacion`, `uq_resena_usuario_libro`…).

### Uso rápido

```python
from sqlalchemy import select
from src.orm import Libro, Genero, Resena, sesion

# Leer (con el género ya cargado como objeto)
with sesion() as db:
    libros = db.scalars(select(Libro).order_by(Libro.titulo)).all()
    for libro in libros:
        print(libro.titulo, "·", libro.genero.nombre if libro.genero else "Sin género")

# Crear
with sesion() as db:
    db.add(Libro(titulo="KO", formato="PDF", ruta_archivo="/ruta/absoluta/KO.pdf"))

# Actualizar o crear (equivale al INSERT … ON DUPLICATE KEY UPDATE)
with sesion() as db:
    resena = db.scalar(
        select(Resena).where(Resena.id_libro == 1, Resena.id_usuario == 7)
    )
    if resena is None:
        db.add(Resena(id_libro=1, id_usuario=7, calificacion=4, comentario=""))
    else:
        resena.calificacion = 4   # conserva el comentario que ya existía
```

**Por qué `with sesion():`** ese bloque hace `commit` si todo termina bien,
`rollback` si hay una excepción y `close` siempre. Es el mismo contrato que
`db_cursor()` en `src/db.py`, pero devolviendo una `Session` del ORM.

### Comprobar la conexión y ver el SQL

```bash
# ¿La base responde?
.venv/bin/python -c "from src.orm import verificar_conexion; print(verificar_conexion())"

# Ver el SQL que genera el ORM (útil para aprender)
ORM_ECHO=1 .venv/bin/python -c "from src.orm import *; print(verificar_conexion())"
```

### Advertencias

- **`crear_tablas_si_faltan()` no migra.** Solo crea tablas ausentes; no añade
  columnas ni cambia tipos. Para bases antiguas sigue usando `tools/migrar_bd.py`.
- **No mezcles ambas capas en la misma operación.** Una `Session` no ve los cambios
  que hace `db_cursor()` hasta que se confirma la otra transacción. Termina una
  antes de empezar la otra.
- **Las fechas `created_at`, `fecha_subida`, `fecha_creacion` y `actualizado_en`**
  las pone MySQL (`DEFAULT CURRENT_TIMESTAMP`). No hace falta asignarlas al crear.
- **Ojo con los nombres:** en `book_manager.py`, `Libro`, `Genero` y `Resena` son
  alias de `dict`; en `orm.py` son clases del ORM. Si usas los dos, importa
  `from src import orm` y escribe `orm.Libro`.

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Falta el paquete mysql-connector-python` | Dependencias no instaladas o entorno virtual inactivo | `source .venv/bin/activate && pip install -r requirements.txt` |
| `Conexión rehusada` / `Can't connect to MySQL server` | El servidor MySQL está apagado | `sudo systemctl start mysql` |
| `Access denied for user` | Credenciales incorrectas en `config.json` | Revisa usuario/contraseña; prueba `mysql -u USUARIO -p` |
| `Unknown database 'cosmicstream_db'` | No se ejecutó el `.sql` | `mysql -u root -p < cosmicstream_db.sql` |
| CBR/RAR no abren | Falta el binario `unrar` | `sudo apt install unrar` |
| Las portadas no aparecen | Falta Pillow o el archivo no tiene página 1 válida | `pip install Pillow`; si el PDF está dañado, sube una portada manual desde el panel admin |
| `Internal C++ object already deleted` | Ventana cerrada y reutilizada (bug antiguo) | Ya corregido: no uses `WA_DeleteOnClose` |
| La ventana no aparece en Wayland | Problema del plugin Qt | `QT_QPA_PLATFORM=xcb python main.py` |

---

## Seguridad

Lo que se corrigió respecto a la versión original:

| Antes | Ahora |
|---|---|
| Contraseñas en **texto plano** | **PBKDF2-HMAC-SHA256**, 260 000 iteraciones, sal de 16 bytes |
| Comparación con `==` (vulnerable a *timing attacks*) | `hmac.compare_digest` (tiempo constante) |
| `check_admin(password)` permitía **escalar privilegios** con una contraseña maestra | Se usa el rol del usuario autenticado (`controller.is_admin`) |
| Credenciales de MySQL **en el código** | `config.json` (ignorado por git) o variables de entorno |
| `DROP TABLE` en el `.sql` **borraba la base** al reinstalar | `CREATE TABLE IF NOT EXISTS`, sin destrucción |
| Consultas con datos posicionales (`fila[6]`) → bugs silenciosos | Diccionarios con nombre de columna |

**Buenas prácticas que siguen pendientes de tu parte:**

- No subas `config.json` ni `data/library/` a git (ya están en `.gitignore`).
- Cambia las contraseñas de demostración.
- No reutilices la contraseña de la base de datos en otros servicios.

---

## Ejercicios prácticos

**1. Inspeccionar los hashes.**
Abre MySQL y ejecuta:
```sql
SELECT username, password FROM cosmicstream_db.usuarios;
```
Observa que no se puede leer ninguna contraseña. Después prueba esto en Python:
```python
from src.security import hash_password
print(hash_password("12345"))
print(hash_password("12345"))
```
**Pregunta:** ¿por qué las dos salidas son distintas si la contraseña es la misma?
*(Pista: mira `SALT_BYTES` en `src/security.py`.)*

**2. Provocar y leer un error de conexión.**
Detén MySQL (`sudo systemctl stop mysql`), ejecuta `python main.py` e intenta iniciar sesión.
Localiza el mensaje en `cosmicstream_error.log`. Luego arréglalo cambiando `port` en `config.json`
a un puerto equivocado y compara los mensajes. **Objetivo:** aprender a distinguir "servidor apagado"
de "credenciales malas".

**3. Romper la validación de contraseñas.**
Registra usuarios con estas claves y anota qué acepta y qué rechaza:
`123`, `1234567890`, `admin`, `abc123`, `  abc123  `, `A1b2C3d4`.
Lee `validate_password()` en `src/security.py` y explica cada resultado.

**4. Consulta SQL con agregación.**
Escribe una consulta que devuelva, por género, cuántos libros hay y la calificación promedio,
ordenado de mejor a peor. Pista: `JOIN generos`, `LEFT JOIN resenas`, `GROUP BY`, `AVG`, `COUNT`.

**5. Orden natural.**
```python
from src.library import orden_natural
nombres = ["pag10.png", "pag2.png", "pag1.png"]
print(sorted(nombres, key=orden_natural))
```
**Pregunta:** ¿qué pasaría sin `orden_natural`? ¿Por qué el orden por defecto es incorrecto?

**6. Comparar SQL directo con ORM.**
La misma consulta de dos formas:
```python
# SQL directo (book_manager.py)
from src.book_manager import listar_libros
print(listar_libros()[0]["titulo"])

# ORM
from sqlalchemy import select
from src.orm import Libro, sesion
with sesion() as db:
    print(db.scalars(select(Libro)).first().titulo)
```
**Pregunta:** abre MySQL (`SET GLOBAL general_log = 'ON';` o el log de consultas) y
compara el SQL que envía cada una. ¿Cuál es más legible para ti? ¿Cuál te da menos
control sobre el `SELECT`?

**7. Navegar relaciones sin `JOIN`.**
```python
from sqlalchemy import select
from src.orm import Libro, sesion

with sesion() as db:
    libro = db.scalars(select(Libro)).first()
    print(libro.genero.nombre if libro.genero else "Sin género")
    print([(r.calificacion, r.usuario.username) for r in libro.resenas])
```
**Pregunta:** ¿cuántas consultas se ejecutan? Actívalas con `ORM_ECHO=1` y cuenta
los `SELECT`. *(Pista: se conoce como problema N+1; se resuelve con
`selectinload(Libro.resenas)`.)*

**8. Reto — primera migración.**
Elige una sola función de `book_manager.py` (por ejemplo `obtener_generos`) y
reescríbela usando el ORM en una función nueva, sin tocar la original. Compara que
devuelvan exactamente los mismos datos antes de cambiar la llamada en la ventana.

---

## Licencia

Proyecto académico. Úsalo solo con contenido del que tengas derecho de distribución.
