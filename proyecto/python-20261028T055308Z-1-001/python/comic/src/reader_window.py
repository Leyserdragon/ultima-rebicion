"""Ventana de lectura con zoom, pantalla completa, modo manga y progreso.

Atajos de teclado
-----------------
``→ / ↓ / Espacio``  página siguiente      ``← / ↑``  página anterior
``+ / -``            acercar / alejar     ``0``      ajustar a la ventana
``F`` o ``F11``      pantalla completa     ``Esc``    salir
``Inicio / Fin``     primera / última página
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .book_manager import guardar_progreso
from .clickable_label import ClickablePageLabel
from .library import BookSource

ZOOM_MIN = 0.10
ZOOM_MAX = 6.0
ZOOM_PASO = 1.15
CACHE_PAGINAS = 9


class ReaderWindow(QMainWindow):
    """Visor de un libro con navegación, zoom y guardado de progreso."""

    closed = Signal()

    def __init__(self, controller, file_path, id_libro=None, titulo="", pagina_inicial=0):
        super().__init__()
        self.controller = controller
        self.id_libro = id_libro
        self.file_path = Path(file_path)
        self.titulo = titulo or self.file_path.name
        self.rtl = False
        self.modo_zoom = "fit_page"
        self.zoom_manual = 1.0
        self._source_pixmap: QPixmap | None = None
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._pantalla_completa = False
        self._guardado_pendiente = False

        self.setWindowTitle(f"CosmicStream Reader · {self.titulo}")
        self._ajustar_tamano_inicial()

        self.book = None
        self.total_pages = 0
        try:
            self.book = BookSource(self.file_path)
            self.total_pages = self.book.count()
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo abrir el archivo", f"{self.file_path.name}\n\n{exc}")

        self.current_page = max(0, min(int(pagina_inicial), max(0, self.total_pages - 1)))

        self._construir_ui()
        self._atajos()
        self.load_current_page()

        if pagina_inicial > 0 and self.total_pages:
            self.statusBar().showMessage(
                f"Continuando en la página {self.current_page + 1} de {self.total_pages}. "
                "Pulsa «Inicio» para volver al principio.",
                6000,
            )

        # Guardado con retardo: evita escribir en MySQL en cada pulsación.
        self._timer_guardado = QTimer(self)
        self._timer_guardado.setSingleShot(True)
        self._timer_guardado.setInterval(900)
        self._timer_guardado.timeout.connect(self._guardar_progreso)

    # ------------------------------------------------------------------ UI --
    def _ajustar_tamano_inicial(self):
        """Abre la ventana en un tamaño que deja ver la página completa.

        En vez de ocupar toda la pantalla se toma una fracción del área
        disponible: así la página cabe entera (modo «Página completa») sin
        tener que desplazarse, que es lo que se busca al leer.
        """
        pantalla = QGuiApplication.primaryScreen()
        if pantalla is None:
            self.resize(1000, 700)
            return

        disponible = pantalla.availableGeometry()
        ancho = min(1000, max(720, int(disponible.width() * 0.62)))
        alto = min(760, max(560, int(disponible.height() * 0.80)))
        self.resize(ancho, alto)

        marco = self.frameGeometry()
        marco.moveCenter(disponible.center())
        self.move(marco.topLeft())

    def _construir_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        barra = QHBoxLayout()
        barra.setSpacing(8)

        self.btn_back = QPushButton("← Biblioteca")
        self.btn_back.setObjectName("ghost_btn")
        self.btn_back.setFixedHeight(34)
        self.btn_back.setToolTip("Cerrar el lector y volver a la biblioteca (Esc)")
        self.btn_back.clicked.connect(self.close)
        barra.addWidget(self.btn_back)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(40, 34)
        self.btn_prev.setToolTip("Página anterior (←)")
        self.btn_prev.clicked.connect(self._entrada_anterior)
        barra.addWidget(self.btn_prev)

        self.spin_page = QSpinBox()
        self.spin_page.setObjectName("page_spin")
        self.spin_page.setFixedHeight(34)
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(max(1, self.total_pages))
        self.spin_page.setFixedWidth(78)
        self.spin_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_page.setToolTip("Ir a una página concreta")
        self.spin_page.valueChanged.connect(self._ir_a_spin)
        barra.addWidget(self.spin_page)

        self.lbl_total = QLabel(f"de {max(1, self.total_pages)}")
        self.lbl_total.setObjectName("muted")
        barra.addWidget(self.lbl_total)

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(40, 34)
        self.btn_next.setToolTip("Página siguiente (→)")
        self.btn_next.clicked.connect(self._entrada_siguiente)
        barra.addWidget(self.btn_next)

        barra.addSpacing(16)

        btn_zoom_out = QPushButton("−")
        btn_zoom_out.setFixedSize(34, 34)
        btn_zoom_out.setToolTip("Alejar (Ctrl + rueda, o tecla -)")
        btn_zoom_out.clicked.connect(self.zoom_out)
        barra.addWidget(btn_zoom_out)

        self.combo_zoom = QComboBox()
        self.combo_zoom.setFixedHeight(34)
        self.combo_zoom.setFixedWidth(140)
        self.combo_zoom.addItem("Ajustar ancho", "fit_width")
        self.combo_zoom.addItem("Página completa", "fit_page")
        self.combo_zoom.addItem("Tamaño real (100%)", "cien")
        # Arranca en «Página completa»: la imagen se ve entera de una vez.
        self.combo_zoom.setCurrentIndex(1)
        self.combo_zoom.currentIndexChanged.connect(self._cambiar_modo_zoom)
        barra.addWidget(self.combo_zoom)

        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(34, 34)
        btn_zoom_in.setToolTip("Acercar (Ctrl + rueda, o tecla +)")
        btn_zoom_in.clicked.connect(self.zoom_in)
        barra.addWidget(btn_zoom_in)

        barra.addStretch()

        self.btn_rtl = QPushButton("⇄ Modo manga")
        self.btn_rtl.setObjectName("ghost_btn")
        self.btn_rtl.setFixedHeight(34)
        self.btn_rtl.setCheckable(True)
        self.btn_rtl.setToolTip("Invertir el sentido de lectura (derecha → izquierda)")
        self.btn_rtl.toggled.connect(self._alternar_rtl)
        barra.addWidget(self.btn_rtl)

        self.btn_full = QPushButton("⛶")
        self.btn_full.setFixedSize(38, 34)
        self.btn_full.setToolTip("Pantalla completa (F11)")
        self.btn_full.clicked.connect(self.alternar_pantalla_completa)
        barra.addWidget(self.btn_full)

        layout.addLayout(barra)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("reader_area")
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # El QScrollArea consume la rueda para desplazar; se filtra aquí para
        # que Ctrl + rueda haga zoom también cuando el cursor está sobre la
        # página (antes solo funcionaba al pasar por la barra de herramientas).
        self.scroll_area.viewport().installEventFilter(self)

        self.page_label = ClickablePageLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.leftClicked.connect(self._clic_izquierdo)
        self.page_label.rightClicked.connect(self._clic_derecho)
        self.scroll_area.setWidget(self.page_label)
        layout.addWidget(self.scroll_area, 1)

        self.statusBar().showMessage("Listo")
        self._actualizar_controles()

    def _atajos(self):
        atajos = [
            ("Right", self._entrada_siguiente),
            ("Down", self._entrada_siguiente),
            ("Space", self._entrada_siguiente),
            ("Left", self._entrada_anterior),
            ("Up", self._entrada_anterior),
            ("+", self.zoom_in),
            ("=", self.zoom_in),
            ("-", self.zoom_out),
            ("0", self.ajustar_ancho),
            ("Home", self.primera_pagina),
            ("End", self.ultima_pagina),
            ("F11", self.alternar_pantalla_completa),
            ("F", self.alternar_pantalla_completa),
        ]
        for secuencia, funcion in atajos:
            QShortcut(QKeySequence(secuencia), self, activated=funcion)

    # --------------------------------------------------------------- estado --
    def _actualizar_controles(self):
        vacio = self.total_pages <= 0
        self.btn_prev.setEnabled(not vacio and self.current_page > 0)
        self.btn_next.setEnabled(not vacio and self.current_page < self.total_pages - 1)
        self.spin_page.setEnabled(not vacio)

        self.spin_page.blockSignals(True)
        self.spin_page.setValue(self.current_page + 1)
        self.spin_page.blockSignals(False)

        self.lbl_total.setText(f"de {max(1, self.total_pages)}")
        if not vacio:
            self.setWindowTitle(f"{self.titulo} · pág. {self.current_page + 1}/{self.total_pages}")

    # ------------------------------------------------------------ navegación --
    def _ir_a_spin(self, valor: int):
        self.ir_a(valor - 1)

    def ir_a(self, pagina: int):
        if self.total_pages <= 0:
            return
        pagina = max(0, min(int(pagina), self.total_pages - 1))
        if pagina == self.current_page:
            return
        self.current_page = pagina
        self.load_current_page()
        self._programar_guardado()

    def primera_pagina(self):
        self.ir_a(0)

    def ultima_pagina(self):
        self.ir_a(self.total_pages - 1)

    def _entrada_siguiente(self):
        self.ir_a(self.current_page + 1)

    def _entrada_anterior(self):
        self.ir_a(self.current_page - 1)

    def _clic_izquierdo(self):
        # En modo manga (derecha → izquierda) el clic izquierdo retrocede.
        self.ir_a(self.current_page - 1 if self.rtl else self.current_page + 1)

    def _clic_derecho(self):
        self.ir_a(self.current_page + 1 if self.rtl else self.current_page - 1)

    def _alternar_rtl(self, activo: bool):
        self.rtl = bool(activo)
        self.statusBar().showMessage(
            "Modo manga activado: se lee de derecha a izquierda." if activo else "Modo lectura occidental.",
            3000,
        )

    # ---------------------------------------------------------------- render --
    def _pagina_cruda(self, indice: int) -> bytes:
        """Lee la página con una caché pequeña para no repetir trabajo."""
        if indice in self._cache:
            self._cache.move_to_end(indice)
            return self._cache[indice]

        datos = self.book.read_image(indice)
        self._cache[indice] = datos
        if len(self._cache) > CACHE_PAGINAS:
            self._cache.popitem(last=False)
        return datos

    def load_current_page(self):
        self._actualizar_controles()

        if self.total_pages <= 0:
            self.page_label.setPixmap(QPixmap())
            self.page_label.setText(
                "No hay páginas para mostrar.\n\n"
                "El archivo puede estar dañado o en un formato no soportado."
            )
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            datos = self._pagina_cruda(self.current_page)
            imagen = QPixmap()
            if not imagen.loadFromData(datos):
                raise ValueError("La imagen de la página no se pudo decodificar.")
            self._source_pixmap = imagen
            self._repintar()
            self.scroll_area.verticalScrollBar().setValue(0)
        except Exception as exc:
            self._source_pixmap = None
            self.page_label.setPixmap(QPixmap())
            self.page_label.setText(f"Error al mostrar la página {self.current_page + 1}:\n{exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def _escala_objetivo(self) -> float:
        if self._source_pixmap is None:
            return 1.0
        ancho, alto = self._source_pixmap.width(), self._source_pixmap.height()
        if ancho <= 0 or alto <= 0:
            return 1.0

        vp = self.scroll_area.viewport()
        vw = max(200, vp.width() - 4)
        vh = max(200, vp.height() - 4)

        if self.modo_zoom == "fit_width":
            return vw / ancho
        if self.modo_zoom == "fit_page":
            return min(vw / ancho, vh / alto)
        if self.modo_zoom == "cien":
            return 1.0
        return self.zoom_manual

    def _repintar(self):
        if self._source_pixmap is None:
            return

        escala = max(ZOOM_MIN, min(self._escala_objetivo(), ZOOM_MAX))
        ancho = max(1, int(self._source_pixmap.width() * escala))
        alto = max(1, int(self._source_pixmap.height() * escala))

        self.page_label.setText("")
        self.page_label.setPixmap(
            self._source_pixmap.scaled(
                ancho,
                alto,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.page_label.resize(ancho, alto)

    # ------------------------------------------------------------------ zoom --
    def zoom_in(self):
        self._zoom_relativo(ZOOM_PASO)

    def zoom_out(self):
        self._zoom_relativo(1 / ZOOM_PASO)

    def _zoom_relativo(self, factor: float):
        if self._source_pixmap is None:
            return
        actual = self._escala_objetivo()
        self.modo_zoom = "manual"
        self.zoom_manual = max(ZOOM_MIN, min(actual * factor, ZOOM_MAX))
        self.combo_zoom.blockSignals(True)
        self.combo_zoom.setCurrentIndex(-1)
        self.combo_zoom.blockSignals(False)
        self._repintar()
        self.statusBar().showMessage(f"Zoom {int(self.zoom_manual * 100)}%", 1500)

    def ajustar_ancho(self):
        self.modo_zoom = "fit_width"
        self.combo_zoom.blockSignals(True)
        self.combo_zoom.setCurrentIndex(0)
        self.combo_zoom.blockSignals(False)
        self._repintar()

    def _cambiar_modo_zoom(self):
        self.modo_zoom = self.combo_zoom.currentData()
        self._repintar()

    # ------------------------------------------------------------- ventana ----
    def alternar_pantalla_completa(self):
        if self._pantalla_completa:
            self.showNormal()
        else:
            self.showFullScreen()
        self._pantalla_completa = not self._pantalla_completa

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.modo_zoom in {"fit_width", "fit_page"} and self._source_pixmap is not None:
            self._repintar()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, obj, event):
        """Captura Ctrl + rueda sobre el área de lectura (ver ``_construir_ui``)."""
        if (
            obj is self.scroll_area.viewport()
            and event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._pantalla_completa:
                self.alternar_pantalla_completa()
            else:
                self.close()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------- progreso ---
    def _programar_guardado(self):
        self._guardado_pendiente = True
        self._timer_guardado.start()

    def _guardar_progreso(self):
        if not self._guardado_pendiente or not self.id_libro:
            return
        usuario = getattr(self.controller, "usuario", None)
        if usuario is None:
            return
        guardar_progreso(usuario.id_usuario, self.id_libro, self.current_page)
        self._guardado_pendiente = False

    def closeEvent(self, event):
        self._guardar_progreso()
        if self.book is not None:
            self.book.close()
        self.closed.emit()
        super().closeEvent(event)
