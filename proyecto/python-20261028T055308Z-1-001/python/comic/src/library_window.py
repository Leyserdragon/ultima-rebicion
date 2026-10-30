"""Galería principal: catálogo de mangas, manhwas y cómics.

Cambios clave frente a la versión anterior:

* El catálogo se descarga **una vez** y el buscador filtra en memoria (antes se
  lanzaba una consulta a MySQL por cada tecla escrita).
* La búsqueda ignora mayúsculas **y acentos**: «pokemon» encuentra «Pokémon».
* Un solo clic abre la ficha (antes clic y doble clic abrían dos ventanas).
* Cada tarjeta muestra la nota media y la página donde te quedaste.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .book_manager import listar_generos, listar_libros, mapar_progreso
from .db import is_available, last_error
from .library import Library

COVER_W, COVER_H = 168, 240
GRID_W, GRID_H = 196, 318

ORDENES = [
    ("Recientes primero", "recientes"),
    ("Título (A-Z)", "titulo"),
    ("Mejor valorados", "rating"),
    ("Más páginas", "paginas"),
]


def normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar de forma tolerante."""
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def estrellas(promedio: float) -> str:
    """Convierte 4.3 en ``★★★★☆``."""
    if not promedio:
        return ""
    llenas = int(round(promedio))
    llenas = max(0, min(5, llenas))
    return "★" * llenas + "☆" * (5 - llenas)


class LibraryWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("CosmicStream Reader · Biblioteca")
        self.resize(1340, 760)
        self.library = Library(Path(__file__).resolve().parent.parent / "data" / "library")

        self._libros: list[dict] = []
        self._progreso: dict[int, int] = {}
        # Las portadas se escalan una sola vez y se reutilizan: sin esto, cada
        # tecla del buscador volvía a leer y escalar todas las imágenes.
        self._cache_portadas: dict[str, QPixmap] = {}
        self._cache_genericas: dict[tuple[str, str], QPixmap] = {}

        self._timer_busqueda = QTimer(self)
        self._timer_busqueda.setSingleShot(True)
        self._timer_busqueda.setInterval(160)
        self._timer_busqueda.timeout.connect(self.renderizar_libros)

        self._construir_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI --
    def _construir_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(24, 14, 24, 16)
        lay.setSpacing(12)

        # ---- barra superior ------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("top_navbar")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(12, 8, 12, 8)
        top.setSpacing(12)

        logo = QLabel(
            "<span style='font-style: italic; font-weight: 900; font-size: 22px; color: #ff2a85;'>COSMIC</span>"
            "<span style='font-style: italic; font-weight: 900; font-size: 22px; color: #f8fafc;'>STREAM</span>"
        )
        logo.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(logo)

        self.search = QLineEdit()
        self.search.setObjectName("search_bar")
        self.search.setPlaceholderText("Buscar serie, tomo o género…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(lambda: self._timer_busqueda.start())
        top.addWidget(self.search, 1)

        self.genre_filter = QComboBox()
        self.genre_filter.setMinimumHeight(36)
        self.genre_filter.setMinimumWidth(170)
        self.genre_filter.currentIndexChanged.connect(self.renderizar_libros)
        top.addWidget(self.genre_filter)

        self.order_filter = QComboBox()
        self.order_filter.setMinimumHeight(36)
        self.order_filter.setMinimumWidth(160)
        for etiqueta, valor in ORDENES:
            self.order_filter.addItem(etiqueta, valor)
        self.order_filter.currentIndexChanged.connect(self.renderizar_libros)
        top.addWidget(self.order_filter)

        btn_reload = QPushButton("🔄")
        btn_reload.setFixedSize(36, 36)
        btn_reload.setToolTip("Recargar el catálogo desde MySQL")
        btn_reload.clicked.connect(self.refresh)
        top.addWidget(btn_reload)

        if self.controller.is_admin:
            btn_admin = QPushButton("⚙ Panel admin")
            btn_admin.setMinimumHeight(36)
            btn_admin.setToolTip("Administrar libros, portadas y usuarios")
            btn_admin.clicked.connect(self.controller.show_admin)
            top.addWidget(btn_admin)

        self.btn_cuenta = QPushButton("Cerrar sesión")
        self.btn_cuenta.setObjectName("primary_btn")
        self.btn_cuenta.setMinimumHeight(36)
        self.btn_cuenta.clicked.connect(self.controller.cerrar_sesion)
        top.addWidget(self.btn_cuenta)

        lay.addWidget(top_bar)

        # ---- saludo + contador --------------------------------------------
        head = QHBoxLayout()
        nombre = self.controller.current_user or "lector"
        self.lbl_hoy = QLabel(f"Bienvenido, <b>{nombre}</b>")
        self.lbl_hoy.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_hoy.setObjectName("section_title")
        head.addWidget(self.lbl_hoy)
        head.addStretch()
        self.info = QLabel("")
        self.info.setObjectName("muted")
        head.addWidget(self.info)
        lay.addLayout(head)

        # ---- aviso de error de base de datos -------------------------------
        self.banner = QLabel("")
        self.banner.setObjectName("banner_error")
        self.banner.setWordWrap(True)
        self.banner.setVisible(False)
        lay.addWidget(self.banner)

        # ---- galería -------------------------------------------------------
        self.list = QListWidget()
        self.list.setObjectName("cover_grid")
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(COVER_W, COVER_H))
        self.list.setGridSize(QSize(GRID_W, GRID_H))
        self.list.setSpacing(12)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setWrapping(True)
        self.list.setWordWrap(True)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.itemClicked.connect(self.abrir_detalle)
        self.list.itemActivated.connect(self.abrir_detalle)
        lay.addWidget(self.list, 1)

        self.lbl_vacio = QLabel("")
        self.lbl_vacio.setObjectName("empty_state")
        self.lbl_vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_vacio.setWordWrap(True)
        self.lbl_vacio.setVisible(False)
        lay.addWidget(self.lbl_vacio, 1)

    # ------------------------------------------------------------- datos ----
    def refresh(self):
        """Vuelve a leer libros, géneros y progreso desde MySQL."""
        # Las cachés se conservan (evita releer y reescalar todas las portadas
        # cada vez que se vuelve de una ficha o del lector). Solo se descartan
        # las entradas cuyo archivo ya no existe.
        self._cache_portadas = {
            ruta: pixmap
            for ruta, pixmap in self._cache_portadas.items()
            if Path(ruta).exists()
        }
        self._libros = listar_libros()
        self._progreso = mapar_progreso(self.controller.current_user_id or 0)
        self.actualizar_generos()
        self.renderizar_libros()
        self._actualizar_banner()

    def _actualizar_banner(self):
        if not is_available():
            self.banner.setText(
                "⚠ No está instalado <b>mysql-connector-python</b>. "
                "Ejecuta <code>pip install -r requirements.txt</code> y reinicia."
            )
            self.banner.setVisible(True)
        elif not self._libros and last_error():
            self.banner.setText(
                "⚠ No se pudo conectar con MySQL: "
                f"<i>{last_error()}</i><br>"
                "Revisa que el servidor esté encendido y que <code>config.json</code> "
                "tenga usuario y contraseña correctos."
            )
            self.banner.setVisible(True)
        else:
            self.banner.setVisible(False)

    def actualizar_generos(self):
        anterior = self.genre_filter.currentData()
        self.genre_filter.blockSignals(True)
        self.genre_filter.clear()
        self.genre_filter.addItem(f"📁 Todos ({len(self._libros)})", "TODOS")
        for genero in listar_generos():
            self.genre_filter.addItem(f"{genero['nombre']} ({genero['total']})", genero["nombre"])
        indice = self.genre_filter.findData(anterior)
        self.genre_filter.setCurrentIndex(indice if indice >= 0 else 0)
        self.genre_filter.blockSignals(False)

    # ------------------------------------------------------------ filtros ---
    def _libros_filtrados(self) -> list[dict]:
        consulta = normalizar(self.search.text().strip())
        terminos = [t for t in consulta.split() if t]
        genero = self.genre_filter.currentData()

        resultado = []
        for libro in self._libros:
            if genero and genero != "TODOS" and libro["genero"] != genero:
                continue
            if terminos:
                pajar = normalizar(f"{libro['titulo']} {libro['genero']} {libro['subido_por']}")
                if not all(t in pajar for t in terminos):
                    continue
            resultado.append(libro)

        orden = self.order_filter.currentData()
        if orden == "titulo":
            resultado.sort(key=lambda l: normalizar(l["titulo"]))
        elif orden == "rating":
            resultado.sort(key=lambda l: float(l["promedio"] or 0), reverse=True)
        elif orden == "paginas":
            resultado.sort(key=lambda l: int(l["total_paginas"] or 0), reverse=True)
        else:
            resultado.sort(key=lambda l: str(l["fecha_subida"] or ""), reverse=True)

        return resultado

    def renderizar_libros(self):
        libros = self._libros_filtrados()
        self.list.clear()

        for libro in libros:
            self.list.addItem(self._crear_item(libro))

        total = len(self._libros)
        mostrados = len(libros)
        if mostrados == total:
            self.info.setText(f"{total} título{'s' if total != 1 else ''}")
        else:
            self.info.setText(f"{mostrados} de {total} títulos")

        # Estado vacío
        vacio = mostrados == 0
        self.list.setVisible(not vacio)
        self.lbl_vacio.setVisible(vacio)
        if vacio:
            if total == 0:
                self.lbl_vacio.setText(
                    "Tu biblioteca está vacía.\n\n"
                    "Un administrador puede subir PDF, CBZ, CBR o imágenes\n"
                    "desde el panel de administración."
                )
            else:
                self.lbl_vacio.setText(
                    "No hay resultados para esa búsqueda.\n\nPrueba con otro título o quita los filtros."
                )

    def _crear_item(self, libro: dict) -> QListWidgetItem:
        titulo = libro["titulo"]
        genero = libro["genero"] or "Sin género"
        promedio = float(libro["promedio"] or 0)
        resenas = int(libro["total_resenas"] or 0)
        progreso = self._progreso.get(int(libro["id_libro"]))

        detalles = [genero]
        if resenas:
            detalles.append(f"{estrellas(promedio)} {promedio:.1f}")
        if progreso is not None:
            detalles.append(f"▶ pág. {progreso + 1}")

        item = QListWidgetItem(f"{titulo}\n{' · '.join(detalles)}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        item.setToolTip(f"<b>{titulo}</b><br>Categoría: {genero}")
        item.setData(Qt.ItemDataRole.UserRole, libro)
        item.setIcon(QIcon(self._portada(libro, genero)))
        return item

    def _portada(self, libro: dict, genero: str) -> QPixmap:
        ruta = libro.get("ruta_portada")
        if ruta and Path(ruta).exists():
            cache = self._cache_portadas.get(ruta)
            if cache is not None:
                return cache

            pixmap = QPixmap(ruta)
            if not pixmap.isNull():
                escalada = pixmap.scaled(
                    COVER_W,
                    COVER_H,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                ).copy(0, 0, COVER_W, COVER_H)
                self._cache_portadas[ruta] = escalada
                return escalada

        clave = (genero, (libro["titulo"][:1] or "?").upper())
        generica = self._cache_genericas.get(clave)
        if generica is None:
            generica = self._portada_generica(libro["titulo"], genero)
            self._cache_genericas[clave] = generica
        return generica

    @staticmethod
    def _portada_generica(titulo: str, genero: str) -> QPixmap:
        """Portada de relleno con el color del género y la inicial del título."""
        colores = {
            "Acción": "#ef4444",
            "Aventura": "#f59e0b",
            "Comedia": "#22c55e",
            "Drama": "#8b5cf6",
            "Fantasía": "#6366f1",
            "Romance": "#ec4899",
            "Terror": "#0ea5e9",
            "Ciencia ficción": "#14b8a6",
        }
        base = QColor(colores.get(genero, "#7c3aed"))
        pixmap = QPixmap(COVER_W, COVER_H)
        pixmap.fill(base)

        pintor = QPainter(pixmap)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        degradado = QColor(0, 0, 0, 110)
        pintor.fillRect(0, COVER_H - 70, COVER_W, 70, degradado)

        fuente = QFont()
        fuente.setPointSize(64)
        fuente.setBold(True)
        pintor.setFont(fuente)
        pintor.setPen(QColor(255, 255, 255, 220))
        pintor.drawText(pixmap.rect().adjusted(0, -20, 0, 0), Qt.AlignmentFlag.AlignCenter, (titulo[:1] or "?").upper())

        fuente.setPointSize(8)
        fuente.setBold(True)
        pintor.setFont(fuente)
        pintor.drawText(
            pixmap.rect().adjusted(8, 0, -8, -10),
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            genero.upper(),
        )
        pintor.end()
        return pixmap

    # ------------------------------------------------------------ acciones --
    def abrir_detalle(self, item: QListWidgetItem):
        libro = item.data(Qt.ItemDataRole.UserRole)
        if libro:
            self.controller.show_book_detail(libro)
