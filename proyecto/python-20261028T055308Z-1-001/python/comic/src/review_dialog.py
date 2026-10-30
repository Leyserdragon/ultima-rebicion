"""Diálogo de reseñas: lectura, publicación y edición de la propia opinión."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .book_manager import agregar_resena, eliminar_resena, listar_resenas

MAX_COMENTARIO = 600


class ReviewDialog(QDialog):
    def __init__(self, id_libro: int, id_usuario: int, titulo: str, parent=None):
        super().__init__(parent)
        self.id_libro = id_libro
        self.id_usuario = id_usuario
        self.titulo_libro = titulo

        self.setWindowTitle(f"Reseñas · {titulo}")
        self.resize(560, 620)
        self.setMinimumSize(480, 520)

        self._construir_ui()
        self.cargar_resenas()

    # ------------------------------------------------------------------ UI --
    def _construir_ui(self):
        principal = QVBoxLayout(self)
        principal.setContentsMargins(20, 18, 20, 18)
        principal.setSpacing(12)

        cabecera = QVBoxLayout()
        cabecera.setSpacing(2)

        lbl_titulo = QLabel("Reseñas de la comunidad")
        lbl_titulo.setObjectName("dialog_title")
        cabecera.addWidget(lbl_titulo)

        lbl_obra = QLabel(f"Obra: <span style='color:#a78bfa'>{self.titulo_libro}</span>")
        lbl_obra.setTextFormat(Qt.TextFormat.RichText)
        lbl_obra.setObjectName("muted")
        cabecera.addWidget(lbl_obra)
        principal.addLayout(cabecera)

        # Lista con scroll
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(200)
        self.contenedor = QWidget()
        self.lista_layout = QVBoxLayout(self.contenedor)
        self.lista_layout.setContentsMargins(10, 10, 10, 10)
        self.lista_layout.setSpacing(8)
        self.lista_layout.addStretch()
        self.scroll.setWidget(self.contenedor)
        principal.addWidget(self.scroll, 1)

        # Formulario
        tarjeta = QFrame()
        tarjeta.setObjectName("card")
        formulario = QVBoxLayout(tarjeta)
        formulario.setContentsMargins(14, 12, 14, 12)
        formulario.setSpacing(8)

        fila_nota = QHBoxLayout()
        etiqueta = QLabel("Tu puntuación:")
        etiqueta.setObjectName("muted")
        fila_nota.addWidget(etiqueta)

        self.combo_estrellas = QComboBox()
        self.combo_estrellas.setFixedHeight(32)
        self.combo_estrellas.addItem("★★★★★  Excelente", 5)
        self.combo_estrellas.addItem("★★★★☆  Muy bueno", 4)
        self.combo_estrellas.addItem("★★★☆☆  Regular", 3)
        self.combo_estrellas.addItem("★★☆☆☆  Malo", 2)
        self.combo_estrellas.addItem("★☆☆☆☆  Pésimo", 1)
        fila_nota.addWidget(self.combo_estrellas)
        fila_nota.addStretch()
        formulario.addLayout(fila_nota)

        self.txt_comentario = QTextEdit()
        self.txt_comentario.setPlaceholderText("Escribe tu opinión sobre esta obra…")
        self.txt_comentario.setFixedHeight(74)
        self.txt_comentario.textChanged.connect(self._limitar_comentario)
        formulario.addWidget(self.txt_comentario)

        self.lbl_contador = QLabel(f"0 / {MAX_COMENTARIO}")
        self.lbl_contador.setObjectName("muted")
        self.lbl_contador.setAlignment(Qt.AlignmentFlag.AlignRight)
        formulario.addWidget(self.lbl_contador)

        botones = QHBoxLayout()
        self.btn_publicar = QPushButton("⭐ Publicar opinión")
        self.btn_publicar.setObjectName("primary_btn")
        self.btn_publicar.setFixedHeight(38)
        self.btn_publicar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_publicar.clicked.connect(self.enviar_resena)
        botones.addWidget(self.btn_publicar, 1)

        self.btn_borrar = QPushButton("🗑 Eliminar la mía")
        self.btn_borrar.setObjectName("danger")
        self.btn_borrar.setFixedHeight(38)
        self.btn_borrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_borrar.setVisible(False)
        self.btn_borrar.clicked.connect(self.borrar_mi_resena)
        botones.addWidget(self.btn_borrar)

        formulario.addLayout(botones)
        principal.addWidget(tarjeta)

    # ------------------------------------------------------------- datos ----
    def cargar_resenas(self):
        # Limpiar tarjetas anteriores (el último ítem es el stretch).
        while self.lista_layout.count() > 1:
            item = self.lista_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        resenas = listar_resenas(self.id_libro)
        mia = next((r for r in resenas if int(r["id_usuario"]) == int(self.id_usuario)), None)

        if mia:
            self.btn_borrar.setVisible(True)
            self.btn_publicar.setText("💾 Actualizar mi opinión")
            self.combo_estrellas.setCurrentIndex(
                self.combo_estrellas.findData(int(mia["calificacion"]))
            )
            if not self.txt_comentario.toPlainText().strip():
                self.txt_comentario.setPlainText(mia["comentario"])
        else:
            self.btn_borrar.setVisible(False)
            self.btn_publicar.setText("⭐ Publicar opinión")

        if not resenas:
            vacio = QLabel("Todavía no hay reseñas.\n¡Sé el primero en opinar!")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vacio.setObjectName("empty_state")
            vacio.setContentsMargins(0, 24, 0, 24)
            self.lista_layout.insertWidget(0, vacio)
            return

        for resena in resenas:
            self.lista_layout.insertWidget(self.lista_layout.count() - 1, self._tarjeta(resena))

    def _tarjeta(self, resena: dict) -> QFrame:
        tarjeta = QFrame()
        tarjeta.setObjectName("review_card")
        layout = QVBoxLayout(tarjeta)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        fila = QHBoxLayout()
        usuario = resena.get("username") or "Usuario"
        avatar = QLabel((usuario[:1] or "U").upper())
        avatar.setFixedSize(22, 22)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setObjectName("avatar")
        fila.addWidget(avatar)

        nombre = QLabel(usuario)
        nombre.setObjectName("review_user")
        fila.addWidget(nombre)
        fila.addStretch()

        nota = int(resena.get("calificacion") or 0)
        lbl_nota = QLabel("★" * nota + "☆" * (5 - nota))
        lbl_nota.setStyleSheet("color:#fbbf24; font-weight:bold;")
        fila.addWidget(lbl_nota)
        layout.addLayout(fila)

        comentario = QLabel(resena.get("comentario") or "Sin comentario")
        comentario.setWordWrap(True)
        comentario.setObjectName("muted")
        layout.addWidget(comentario)

        fecha = str(resena.get("fecha_creacion") or "")[:16]
        lbl_fecha = QLabel(fecha)
        lbl_fecha.setObjectName("muted_small")
        lbl_fecha.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(lbl_fecha)
        return tarjeta

    # ---------------------------------------------------------- acciones ----
    def _limitar_comentario(self):
        texto = self.txt_comentario.toPlainText()
        if len(texto) > MAX_COMENTARIO:
            self.txt_comentario.blockSignals(True)
            self.txt_comentario.setPlainText(texto[:MAX_COMENTARIO])
            cursor = self.txt_comentario.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.txt_comentario.setTextCursor(cursor)
            self.txt_comentario.blockSignals(False)
        self.lbl_contador.setText(f"{len(self.txt_comentario.toPlainText())} / {MAX_COMENTARIO}")

    def enviar_resena(self):
        comentario = self.txt_comentario.toPlainText().strip()
        if len(comentario) < 3:
            QMessageBox.warning(self, "Comentario muy corto", "Escribe al menos 3 caracteres.")
            return

        ok, mensaje = agregar_resena(
            self.id_libro,
            self.id_usuario,
            self.combo_estrellas.currentData(),
            comentario,
        )
        if ok:
            self.cargar_resenas()
        else:
            QMessageBox.critical(self, "No se pudo guardar", mensaje)

    def borrar_mi_resena(self):
        confirmar = QMessageBox.question(
            self,
            "Eliminar reseña",
            "¿Seguro que quieres borrar tu reseña de esta obra?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmar != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = eliminar_resena(self.id_libro, self.id_usuario)
        if ok:
            self.txt_comentario.clear()
            self.cargar_resenas()
        else:
            QMessageBox.warning(self, "Aviso", mensaje)
