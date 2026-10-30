"""Gestión de usuarios desde el panel de administración."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .user_manager import (
    ROL_ADMIN,
    ROL_LECTOR,
    cambiar_rol,
    eliminar_usuario,
    listar_usuarios,
    restablecer_password,
)

ROLES = {"administrador": ROL_ADMIN, "lector": ROL_LECTOR}


class PasswordDialog(QDialog):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Restablecer contraseña · {username}")
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(QLabel(f"Nueva contraseña para «{username}»"))
        self.txt = QLineEdit()
        self.txt.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt.setPlaceholderText("Mínimo 6 caracteres")
        layout.addWidget(self.txt)

        self.txt2 = QLineEdit()
        self.txt2.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt2.setPlaceholderText("Repite la contraseña")
        layout.addWidget(self.txt2)

        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        botones.addWidget(cancelar)
        aceptar = QPushButton("Guardar")
        aceptar.setObjectName("primary_btn")
        aceptar.clicked.connect(self._validar)
        botones.addWidget(aceptar)
        layout.addLayout(botones)

    def _validar(self):
        if self.txt.text() != self.txt2.text():
            QMessageBox.warning(self, "No coinciden", "Las dos contraseñas deben ser iguales.")
            return
        if not self.txt.text():
            QMessageBox.warning(self, "Vacía", "Escribe una contraseña.")
            return
        self.accept()

    def password(self) -> str:
        return self.txt.text()


class UserAdminWindow(QMainWindow):
    closed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("CosmicStream Reader · Usuarios")
        self.resize(1000, 620)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 18, 28, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        btn_back = QPushButton("← Cerrar")
        btn_back.setObjectName("ghost_btn")
        btn_back.setFixedHeight(36)
        btn_back.clicked.connect(self.close)
        top.addWidget(btn_back)
        top.addStretch()

        self.search = QLineEdit()
        self.search.setObjectName("search_bar")
        self.search.setPlaceholderText("Buscar usuario…")
        self.search.setMinimumWidth(240)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self._aplicar_filtro)
        top.addWidget(self.search)
        layout.addLayout(top)

        titulo = QLabel("Gestión de usuarios")
        titulo.setObjectName("section_title")
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "Doble clic en una fila para cambiar su rol. "
            "No puedes eliminarte a ti mismo ni borrar al último administrador."
        )
        subtitulo.setObjectName("muted")
        subtitulo.setWordWrap(True)
        layout.addWidget(subtitulo)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Usuario", "Rol", "Registrado", "Último acceso"])
        encabezado = self.tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        encabezado.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self.cambiar_rol_seleccionado)
        layout.addWidget(self.tabla, 1)

        barra = QHBoxLayout()
        self.btn_rol = QPushButton("⇄ Cambiar rol")
        self.btn_rol.setMinimumHeight(40)
        self.btn_rol.clicked.connect(self.cambiar_rol_seleccionado)
        barra.addWidget(self.btn_rol)

        self.btn_pass = QPushButton("🔑 Restablecer contraseña")
        self.btn_pass.setMinimumHeight(40)
        self.btn_pass.clicked.connect(self.restablecer)
        barra.addWidget(self.btn_pass)

        self.btn_delete = QPushButton("🗑 Eliminar usuario")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setMinimumHeight(40)
        self.btn_delete.clicked.connect(self.eliminar)
        barra.addWidget(self.btn_delete)

        barra.addStretch()
        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.setMinimumHeight(40)
        btn_refresh.clicked.connect(self.cargar)
        barra.addWidget(btn_refresh)
        layout.addLayout(barra)

        self.estado = QLabel("")
        self.estado.setObjectName("muted_small")
        layout.addWidget(self.estado)

        self.cargar()

    # --------------------------------------------------------------- datos --
    def cargar(self):
        usuarios = listar_usuarios()
        self.tabla.setRowCount(0)

        for fila, usuario in enumerate(usuarios):
            es_yo = usuario["id_usuario"] == self.controller.current_user_id
            nombre = usuario["username"] + (" (tú)" if es_yo else "")

            valores = [
                str(usuario["id_usuario"]),
                nombre,
                str(usuario["rol"]).capitalize(),
                str(usuario["created_at"] or "")[:16],
                str(usuario["ultimo_acceso"] or "Nunca")[:16],
            ]
            self.tabla.insertRow(fila)
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if columna == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(Qt.ItemDataRole.UserRole, usuario)
                self.tabla.setItem(fila, columna, item)

        self.estado.setText(f"{len(usuarios)} usuarios registrados.")
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        consulta = self.search.text().strip().lower()
        for fila in range(self.tabla.rowCount()):
            item = self.tabla.item(fila, 1)
            texto = item.text().lower() if item else ""
            self.tabla.setRowHidden(fila, bool(consulta) and consulta not in texto)

    def _seleccionado(self) -> dict | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------ acciones --
    def cambiar_rol_seleccionado(self):
        usuario = self._seleccionado()
        if usuario is None:
            QMessageBox.warning(self, "Sin selección", "Selecciona un usuario de la tabla.")
            return

        if usuario["id_usuario"] == self.controller.current_user_id:
            QMessageBox.warning(self, "No permitido", "No puedes cambiar tu propio rol.")
            return

        actual = "administrador" if int(usuario["id_rol"]) == ROL_ADMIN else "lector"
        nuevo = "lector" if actual == "administrador" else "administrador"

        if QMessageBox.question(
            self,
            "Cambiar rol",
            f"¿Convertir a «{usuario['username']}» de {actual} a {nuevo}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = cambiar_rol(usuario["id_usuario"], ROLES[nuevo], self.controller.current_user_id)
        if ok:
            self.cargar()
        else:
            QMessageBox.warning(self, "No se pudo cambiar", mensaje)

    def restablecer(self):
        usuario = self._seleccionado()
        if usuario is None:
            QMessageBox.warning(self, "Sin selección", "Selecciona un usuario de la tabla.")
            return

        dialogo = PasswordDialog(usuario["username"], self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        ok, mensaje = restablecer_password(usuario["id_usuario"], dialogo.password())
        if ok:
            QMessageBox.information(self, "Listo", mensaje)
            self.cargar()
        else:
            QMessageBox.warning(self, "No se pudo restablecer", mensaje)

    def eliminar(self):
        usuario = self._seleccionado()
        if usuario is None:
            QMessageBox.warning(self, "Sin selección", "Selecciona un usuario de la tabla.")
            return

        if QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar la cuenta de «{usuario['username']}»?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = eliminar_usuario(usuario["id_usuario"], self.controller.current_user_id)
        if ok:
            self.cargar()
        else:
            QMessageBox.warning(self, "No se pudo eliminar", mensaje)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
