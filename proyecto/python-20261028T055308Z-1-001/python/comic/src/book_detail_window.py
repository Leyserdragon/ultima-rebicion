"""Ficha de la obra: portada, datos, progreso y acceso al lector."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .book_manager import (
    actualizar_portada_libro,
    calificar_libro,
    obtener_calificacion_usuario,
    obtener_progreso,
    promedio_calificacion,
)
from .cover_extractor import extraer_portada
from .library import BookSource
from .review_dialog import ReviewDialog
from .star_rating import StarRatingWidget

COVER_W, COVER_H = 300, 425


class BookDetailWindow(QMainWindow):
    closed = Signal()

    def __init__(self, controller, libro: dict):
        super().__init__()
        self.controller = controller
        self.libro = libro
        self.id_libro = int(libro["id_libro"])
        self.titulo = libro.get("titulo", "Sin título")
        # La extracción de portada se intenta una sola vez por ventana: abrir
        # el PDF en cada actualizar() sería lento y generaría JPG repetidos.
        self._portada_intentada = False

        self.setWindowTitle(f"CosmicStream Reader · {self.titulo}")
        self.resize(1340, 760)

        self._construir_ui()
        self.actualizar()

    # ------------------------------------------------------------------ UI --
    def _construir_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        principal = QVBoxLayout(root)
        principal.setContentsMargins(28, 16, 28, 18)
        principal.setSpacing(14)

        # Barra superior
        top = QHBoxLayout()
        btn_back = QPushButton("← Volver a la biblioteca")
        btn_back.setObjectName("ghost_btn")
        btn_back.setFixedHeight(36)
        btn_back.clicked.connect(self.close)
        top.addWidget(btn_back)
        top.addStretch()
        logo = QLabel(
            "<span style='font-style: italic; font-weight: 900; font-size: 18px; color: #ff2a85;'>COSMIC</span>"
            "<span style='font-style: italic; font-weight: 900; font-size: 18px; color: #f8fafc;'>STREAM</span>"
        )
        logo.setTextFormat(Qt.TextFormat.RichText)
        top.addWidget(logo)
        principal.addLayout(top)

        # Contenido desplazable (por si la ventana es pequeña)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenedor = QWidget()
        scroll.setWidget(contenedor)
        principal.addWidget(scroll, 1)

        contenido = QHBoxLayout(contenedor)
        contenido.setContentsMargins(0, 8, 0, 8)
        contenido.setSpacing(36)

        # ---- columna izquierda: portada -----------------------------------
        col_izq = QVBoxLayout()
        col_izq.setSpacing(12)

        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(COVER_W, COVER_H)
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setObjectName("cover_frame")
        col_izq.addWidget(self.lbl_cover)

        self.lbl_progreso = QLabel("")
        self.lbl_progreso.setObjectName("muted")
        self.lbl_progreso.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col_izq.addWidget(self.lbl_progreso)

        self.barra_progreso = QProgressBar()
        self.barra_progreso.setFixedHeight(6)
        self.barra_progreso.setTextVisible(False)
        self.barra_progreso.setRange(0, 100)
        self.barra_progreso.setVisible(False)
        col_izq.addWidget(self.barra_progreso)

        col_izq.addStretch()
        contenido.addLayout(col_izq)

        # ---- columna derecha: información ---------------------------------
        col_der = QVBoxLayout()
        col_der.setSpacing(12)

        self.lbl_titulo = QLabel(self.titulo)
        self.lbl_titulo.setObjectName("detail_title")
        self.lbl_titulo.setWordWrap(True)
        col_der.addWidget(self.lbl_titulo)

        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("muted")
        self.lbl_meta.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_meta.setWordWrap(True)
        col_der.addWidget(self.lbl_meta)

        # Etiquetas
        self.fila_badges = QHBoxLayout()
        self.fila_badges.setSpacing(8)
        self.fila_badges.addStretch()
        col_der.addLayout(self.fila_badges)

        # Botones
        acciones = QHBoxLayout()
        acciones.setSpacing(12)

        self.btn_leer = QPushButton("▶ Comenzar a leer")
        self.btn_leer.setObjectName("primary_btn")
        self.btn_leer.setFixedHeight(46)
        self.btn_leer.setMinimumWidth(220)
        self.btn_leer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_leer.clicked.connect(self.abrir_lector)
        acciones.addWidget(self.btn_leer)

        btn_review = QPushButton("⭐ Reseñas")
        btn_review.setFixedHeight(46)
        btn_review.setMinimumWidth(150)
        btn_review.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_review.clicked.connect(self.abrir_resenas)
        acciones.addWidget(btn_review)

        acciones.addStretch()
        col_der.addLayout(acciones)

        # Calificación con estrellas (se guarda en MySQL)
        tarjeta_calif = QFrame()
        tarjeta_calif.setObjectName("card")
        fila_calif = QHBoxLayout(tarjeta_calif)
        fila_calif.setContentsMargins(18, 12, 18, 12)
        fila_calif.setSpacing(16)

        bloque_calif = QVBoxLayout()
        bloque_calif.setSpacing(2)

        lbl_tu_calif = QLabel("Tu calificación")
        lbl_tu_calif.setObjectName("form_label")
        bloque_calif.addWidget(lbl_tu_calif)

        self.lbl_estado_calif = QLabel("Haz clic en una estrella para calificar")
        self.lbl_estado_calif.setObjectName("muted_small")
        bloque_calif.addWidget(self.lbl_estado_calif)
        fila_calif.addLayout(bloque_calif)

        fila_calif.addStretch()

        self.estrellas = StarRatingWidget(5)
        self.estrellas.calificacionCambiada.connect(self._guardar_calificacion)
        fila_calif.addWidget(self.estrellas)

        col_der.addWidget(tarjeta_calif)

        self.lbl_promedio = QLabel("")
        self.lbl_promedio.setObjectName("muted")
        self.lbl_promedio.setTextFormat(Qt.TextFormat.RichText)
        col_der.addWidget(self.lbl_promedio)

        # Resumen
        lbl_resumen = QLabel("Detalles de la obra")
        lbl_resumen.setObjectName("section_title")
        col_der.addWidget(lbl_resumen)

        tarjeta = QFrame()
        tarjeta.setObjectName("card")
        tarjeta_lay = QVBoxLayout(tarjeta)
        tarjeta_lay.setContentsMargins(18, 16, 18, 16)

        self.lbl_detalles = QLabel("")
        self.lbl_detalles.setObjectName("muted")
        self.lbl_detalles.setWordWrap(True)
        self.lbl_detalles.setTextFormat(Qt.TextFormat.RichText)
        tarjeta_lay.addWidget(self.lbl_detalles)
        col_der.addWidget(tarjeta)

        col_der.addStretch()
        contenido.addLayout(col_der, 1)

    # ------------------------------------------------------------- datos ----
    @property
    def ruta_archivo(self) -> str:
        return self.libro.get("ruta_archivo") or ""

    def actualizar(self):
        """Recarga promedio de reseñas, progreso y portada."""
        promedio, votos = promedio_calificacion(self.id_libro)
        mi_calificacion = obtener_calificacion_usuario(
            self.id_libro, self.controller.current_user_id or 0
        )
        progreso = obtener_progreso(self.controller.current_user_id or 0, self.id_libro)
        total = self._total_paginas()

        # --- metadatos ---
        subido = self.libro.get("subido_por") or "Admin"
        fecha = str(self.libro.get("fecha_subida") or "")[:16]
        formato = self.libro.get("formato") or "—"
        genero = self.libro.get("genero") or "Sin género"

        paginas_txt = f"{total} páginas" if total else "páginas desconocidas"
        self.lbl_meta.setText(
            f"Añadido por <span style='color:#a78bfa'>{subido}</span> · "
            f"Formato <b>{formato}</b> · {paginas_txt}"
        )

        self._actualizar_calificacion(promedio, votos, mi_calificacion)

        # --- badges ---
        while self.fila_badges.count() > 1:
            item = self.fila_badges.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for texto in [genero, (formato or "").upper(), "Disponible"]:
            if not texto:
                continue
            chip = QLabel(texto)
            chip.setObjectName("chip")
            self.fila_badges.insertWidget(self.fila_badges.count() - 1, chip)

        # --- detalles ---
        self.lbl_detalles.setText(
            f"<b>Título:</b> {self.titulo}<br>"
            f"<b>Género:</b> {genero}<br>"
            f"<b>Archivo:</b> {Path(self.ruta_archivo).name or '—'}<br>"
            f"<b>Registrado:</b> {fecha or '—'}<br>"
            f"<b>Progreso:</b> {progreso + 1 if progreso is not None else 0} de {total or '?'}"
        )

        # --- progreso / botón ---
        if progreso is not None and total:
            porcentaje = int(((progreso + 1) / total) * 100)
            self.barra_progreso.setVisible(True)
            self.barra_progreso.setValue(porcentaje)
            self.lbl_progreso.setText(f"Vas por la página {progreso + 1} ({porcentaje}%)")
            self.btn_leer.setText(f"▶ Continuar en la página {progreso + 1}")
        else:
            self.barra_progreso.setVisible(False)
            self.lbl_progreso.setText("")
            self.btn_leer.setText("▶ Comenzar a leer")

        self._cargar_portada()

    # ------------------------------------------------------ calificaciones ----
    def _actualizar_calificacion(self, promedio: float, votos: int, mi_calificacion: int):
        """Pinta las estrellas del usuario y el promedio de la comunidad."""
        self.estrellas.set_valor(mi_calificacion)
        if mi_calificacion:
            self.lbl_estado_calif.setText(f"Tu calificación: {mi_calificacion} de 5")
        else:
            self.lbl_estado_calif.setText("Haz clic en una estrella para calificar")

        if votos:
            llenas = max(0, min(5, int(round(promedio))))
            estrellas = "★" * llenas + "☆" * (5 - llenas)
            plural = "calificación" if votos == 1 else "calificaciones"
            self.lbl_promedio.setText(
                f"Promedio: <span style='color:#fbbf24'>{estrellas}</span> "
                f"<b>{promedio:.1f}</b> / 5 · {votos} {plural}"
            )
        else:
            self.lbl_promedio.setText("Promedio: todavía sin calificaciones")

    def _guardar_calificacion(self, valor: int):
        """Guarda en MySQL la estrella pulsada y refresca el promedio."""
        usuario = self.controller.usuario
        if usuario is None or not valor:
            return

        ok, mensaje = calificar_libro(self.id_libro, usuario.id_usuario, valor)
        if not ok:
            QMessageBox.warning(self, "No se pudo calificar", mensaje)
            self.actualizar()
            return

        self.libro["mi_calificacion"] = valor
        self.actualizar()

    def _total_paginas(self) -> int:
        guardado = self.libro.get("total_paginas")
        if guardado:
            return int(guardado)
        try:
            with BookSource(self.ruta_archivo) as libro:
                total = libro.count()
        except Exception:
            return 0
        if total:
            # Se memoriza en el diccionario del libro para no abrir el archivo
            # otra vez la próxima vez que se llame a actualizar().
            self.libro["total_paginas"] = total
        return total

    def _pintar_portada(self, pixmap: QPixmap) -> bool:
        """Pinta la portada **completa** (sin recortarla) dentro de su marco."""
        if pixmap.isNull():
            return False
        self.lbl_cover.setText("")
        self.lbl_cover.setPixmap(
            pixmap.scaled(
                COVER_W,
                COVER_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        return True

    def _cargar_portada(self):
        ruta = self.libro.get("ruta_portada")
        if ruta and Path(ruta).exists():
            if self._pintar_portada(QPixmap(ruta)):
                return

        # Sin portada: se intenta extraerla de la primera página, una vez.
        if self._portada_intentada or not self.ruta_archivo:
            self._mostrar_sin_portada()
            return
        self._portada_intentada = True

        carpeta = Path(__file__).resolve().parent.parent / "data" / "covers"
        generada = extraer_portada(self.ruta_archivo, carpeta, self.titulo)
        if generada:
            self.libro["ruta_portada"] = str(generada)
            # Se guarda en MySQL para no volver a generar el JPG en cada visita
            # (si no, data/covers crecería sin límite).
            actualizar_portada_libro(self.id_libro, str(generada))
            if self._pintar_portada(QPixmap(str(generada))):
                return

        self._mostrar_sin_portada()

    def _mostrar_sin_portada(self):
        self.lbl_cover.setPixmap(QPixmap())
        self.lbl_cover.setText("Sin portada")
        self.lbl_cover.setObjectName("cover_placeholder")
        self.lbl_cover.setStyleSheet(
            "border: 2px dashed #2b3040; border-radius: 10px; color: #64748b; font-weight: 600;"
        )

    # ---------------------------------------------------------- acciones ----
    def abrir_lector(self):
        progreso = obtener_progreso(self.controller.current_user_id or 0, self.id_libro)
        self.controller.open_reader(self.libro, pagina_inicial=progreso or 0)

    def abrir_resenas(self):
        usuario = self.controller.usuario
        if usuario is None:
            return
        dialogo = ReviewDialog(self.id_libro, usuario.id_usuario, self.titulo, self)
        dialogo.exec()
        self.actualizar()

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
