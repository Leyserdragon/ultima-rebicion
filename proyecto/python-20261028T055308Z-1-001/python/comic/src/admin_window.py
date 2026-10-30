"""Panel de administración: subir, editar y borrar libros, y gestionar géneros.

Novedades:

* **Arrastrar y soltar** archivos sobre la tabla para subirlos.
* **Portada automática**: se toma la primera página del PDF/CBZ/CBR.
* **Sincronizar carpeta**: registra los archivos que ya están en
  ``data/library`` pero no aparecen en MySQL.
* **Filtro** en la tabla y gestión de géneros sin tocar SQL.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .book_manager import (
    actualizar_libro,
    crear_genero,
    eliminar_genero,
    eliminar_libro_db,
    listar_generos,
    listar_libros,
    registrar_libro,
)
from .cover_extractor import extraer_portada
from .db import PROJECT_ROOT
from .library import ALLOWED_EXTENSIONS, BookSource
from .user_admin_window import UserAdminWindow

COVERS_DIR = PROJECT_ROOT / "data" / "covers"
FILTRO_ARCHIVOS = "Libros (*.pdf *.cbz *.zip *.cbr *.rar);;Imágenes (*.jpg *.jpeg *.png *.webp);;Todos (*)"


class GeneroDialog(QDialog):
    """Selector de género al subir archivos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asignar género")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        layout.addWidget(QLabel("¿A qué género pertenecen los archivos?"))
        self.combo = QComboBox()
        self.combo.addItem("Sin género", None)
        for genero in listar_generos():
            self.combo.addItem(genero["nombre"], genero["id_genero"])
        layout.addWidget(self.combo)

        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        botones.addWidget(cancelar)
        aceptar = QPushButton("Continuar")
        aceptar.setObjectName("primary_btn")
        aceptar.clicked.connect(self.accept)
        botones.addWidget(aceptar)
        layout.addLayout(botones)

    def genero_id(self):
        return self.combo.currentData()


class EditarLibroDialog(QDialog):
    """Edición de título, género y portada de un libro."""

    def __init__(self, libro: dict, parent=None):
        super().__init__(parent)
        self.libro = libro
        self.setWindowTitle("Editar libro")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Título"))
        self.txt_titulo = QLineEdit(libro.get("titulo", ""))
        layout.addWidget(self.txt_titulo)

        layout.addWidget(QLabel("Género"))
        self.combo = QComboBox()
        self.combo.addItem("Sin género", None)
        for genero in listar_generos():
            self.combo.addItem(genero["nombre"], genero["id_genero"])
        indice = self.combo.findData(libro.get("id_genero"))
        self.combo.setCurrentIndex(max(0, indice))
        layout.addWidget(self.combo)

        layout.addWidget(QLabel("Portada"))
        fila = QHBoxLayout()
        self.txt_portada = QLineEdit(libro.get("ruta_portada") or "")
        self.txt_portada.setReadOnly(True)
        fila.addWidget(self.txt_portada)
        btn = QPushButton("Elegir…")
        btn.clicked.connect(self._elegir_portada)
        fila.addWidget(btn)
        layout.addLayout(fila)

        botones = QHBoxLayout()
        botones.addStretch()
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        botones.addWidget(cancelar)
        guardar = QPushButton("Guardar cambios")
        guardar.setObjectName("primary_btn")
        guardar.clicked.connect(self.accept)
        botones.addWidget(guardar)
        layout.addLayout(botones)

    def _elegir_portada(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar portada", "", "Imágenes (*.png *.jpg *.jpeg *.webp)"
        )
        if ruta:
            self.txt_portada.setText(ruta)

    def datos(self) -> dict:
        return {
            "titulo": self.txt_titulo.text().strip(),
            "id_genero": self.combo.currentData(),
            "ruta_portada": self.txt_portada.text().strip() or None,
        }


class GenerosDialog(QDialog):
    """Crear y borrar géneros."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Géneros")
        self.resize(420, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Géneros disponibles"))
        self.lista = QTableWidget(0, 2)
        self.lista.setHorizontalHeaderLabels(["Género", "Libros"])
        self.lista.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lista.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lista.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.lista.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.lista)

        fila = QHBoxLayout()
        self.txt_nuevo = QLineEdit()
        self.txt_nuevo.setPlaceholderText("Nombre del nuevo género…")
        self.txt_nuevo.returnPressed.connect(self._agregar)
        fila.addWidget(self.txt_nuevo)
        btn_add = QPushButton("➕ Añadir")
        btn_add.setObjectName("primary_btn")
        btn_add.clicked.connect(self._agregar)
        fila.addWidget(btn_add)
        layout.addLayout(fila)

        fila2 = QHBoxLayout()
        btn_del = QPushButton("🗑 Eliminar seleccionado")
        btn_del.setObjectName("danger")
        btn_del.clicked.connect(self._eliminar)
        fila2.addWidget(btn_del)
        fila2.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        fila2.addWidget(cerrar)
        layout.addLayout(fila2)

        self.cargar()

    def cargar(self):
        generos = listar_generos()
        self.lista.setRowCount(0)
        for fila, genero in enumerate(generos):
            self.lista.insertRow(fila)
            item = QTableWidgetItem(genero["nombre"])
            item.setData(Qt.ItemDataRole.UserRole, genero["id_genero"])
            self.lista.setItem(fila, 0, item)
            total = QTableWidgetItem(str(genero["total"]))
            total.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.lista.setItem(fila, 1, total)

    def _agregar(self):
        nombre = self.txt_nuevo.text().strip()
        if not nombre:
            return
        ok, mensaje = crear_genero(nombre)
        if ok:
            self.txt_nuevo.clear()
            self.cargar()
        else:
            QMessageBox.warning(self, "Aviso", mensaje)

    def _eliminar(self):
        fila = self.lista.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona un género de la tabla.")
            return
        item = self.lista.item(fila, 0)
        id_genero = item.data(Qt.ItemDataRole.UserRole)
        nombre = item.text()

        if QMessageBox.question(
            self,
            "Eliminar género",
            f"¿Eliminar «{nombre}»?\nLos libros quedarán como «Sin género».",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        ok, mensaje = eliminar_genero(id_genero)
        if ok:
            self.cargar()
        else:
            QMessageBox.warning(self, "Aviso", mensaje)


class AdminWindow(QMainWindow):
    closed = Signal()

    def __init__(self, controller, library_window):
        super().__init__()
        self.controller = controller
        self.library_window = library_window
        self.library = library_window.library
        self._libros: list[dict] = []
        self.users_win = None

        self.setWindowTitle("CosmicStream Reader · Panel de administración")
        self.resize(1340, 760)
        self.setAcceptDrops(True)

        self._construir_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI --
    def _construir_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(32, 18, 32, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        btn_back = QPushButton("← Volver a la biblioteca")
        btn_back.setObjectName("ghost_btn")
        btn_back.setFixedHeight(36)
        btn_back.clicked.connect(self.close)
        top.addWidget(btn_back)
        top.addStretch()

        self.search = QLineEdit()
        self.search.setObjectName("search_bar")
        self.search.setPlaceholderText("Filtrar por título o género…")
        self.search.setMinimumWidth(280)
        self.search.setMinimumHeight(36)
        self.search.textChanged.connect(self._aplicar_filtro)
        top.addWidget(self.search)
        layout.addLayout(top)

        titulo = QLabel("Panel de administración")
        titulo.setObjectName("section_title")
        layout.addWidget(titulo)

        self.subtitulo = QLabel("")
        self.subtitulo.setObjectName("muted")
        layout.addWidget(self.subtitulo)

        barra = QHBoxLayout()
        barra.setSpacing(8)

        btn_subir = QPushButton("⬆ Subir archivos")
        btn_subir.setObjectName("primary_btn")
        btn_subir.setMinimumHeight(40)
        btn_subir.clicked.connect(self.subir_archivos)
        barra.addWidget(btn_subir)

        btn_sync = QPushButton("🔄 Sincronizar carpeta")
        btn_sync.setMinimumHeight(40)
        btn_sync.setToolTip("Registra los archivos de data/library que aún no están en MySQL")
        btn_sync.clicked.connect(self.sincronizar_carpeta)
        barra.addWidget(btn_sync)

        btn_editar = QPushButton("✏ Editar")
        btn_editar.setMinimumHeight(40)
        btn_editar.clicked.connect(self.editar_libro)
        barra.addWidget(btn_editar)

        btn_borrar = QPushButton("🗑 Eliminar")
        btn_borrar.setObjectName("danger")
        btn_borrar.setMinimumHeight(40)
        btn_borrar.clicked.connect(self.eliminar_libro)
        barra.addWidget(btn_borrar)

        btn_generos = QPushButton("🏷 Géneros")
        btn_generos.setMinimumHeight(40)
        btn_generos.clicked.connect(self.gestionar_generos)
        barra.addWidget(btn_generos)

        btn_usuarios = QPushButton("👥 Usuarios")
        btn_usuarios.setMinimumHeight(40)
        btn_usuarios.clicked.connect(self.abrir_usuarios)
        barra.addWidget(btn_usuarios)

        barra.addStretch()
        layout.addLayout(barra)

        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "Título", "Formato", "Género", "Páginas", "Portada", "Subido por", "Fecha"]
        )
        encabezado = self.tabla.horizontalHeader()
        encabezado.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for columna in (0, 2, 4, 5):
            encabezado.setSectionResizeMode(columna, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.doubleClicked.connect(self.editar_libro)
        self.tabla.setToolTip("Puedes arrastrar archivos aquí para subirlos")
        layout.addWidget(self.tabla, 1)

        self.estado = QLabel("")
        self.estado.setObjectName("muted_small")
        layout.addWidget(self.estado)

    # --------------------------------------------------------------- datos ---
    def refresh(self):
        self._libros = listar_libros()
        self.tabla.setRowCount(0)

        for fila, libro in enumerate(self._libros):
            self.tabla.insertRow(fila)
            valores = [
                str(libro["id_libro"]),
                libro["titulo"],
                libro["formato"] or "",
                libro["genero"] or "Sin género",
                str(libro["total_paginas"] or "—"),
                "✓" if libro.get("ruta_portada") else "—",
                libro["subido_por"] or "Admin",
                str(libro["fecha_subida"] or "")[:16],
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if columna in (0, 2, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tabla.setItem(fila, columna, item)

            self.tabla.item(fila, 1).setData(Qt.ItemDataRole.UserRole, libro)

        self.subtitulo.setText(f"{len(self._libros)} títulos registrados en MySQL.")
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        consulta = self.search.text().strip().lower()
        visibles = 0
        for fila in range(self.tabla.rowCount()):
            if not consulta:
                self.tabla.setRowHidden(fila, False)
                visibles += 1
                continue
            texto = " ".join(
                self.tabla.item(fila, columna).text().lower()
                for columna in (1, 3)
                if self.tabla.item(fila, columna)
            )
            coincide = consulta in texto
            self.tabla.setRowHidden(fila, not coincide)
            visibles += int(coincide)
        self.estado.setText(f"Mostrando {visibles} de {self.tabla.rowCount()} filas.")

    def _libro_seleccionado(self) -> dict | None:
        fila = self.tabla.currentRow()
        if fila < 0:
            return None
        item = self.tabla.item(fila, 1)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ------------------------------------------------------------ subir -----
    def subir_archivos(self):
        rutas, _ = QFileDialog.getOpenFileNames(self, "Subir libros", "", FILTRO_ARCHIVOS)
        if rutas:
            self._procesar_archivos([Path(r) for r in rutas], preguntar_genero=True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(Path(u.toLocalFile()).suffix.lower() in ALLOWED_EXTENSIONS for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        rutas = [
            Path(u.toLocalFile())
            for u in event.mimeData().urls()
            if Path(u.toLocalFile()).suffix.lower() in ALLOWED_EXTENSIONS
        ]
        if rutas:
            event.acceptProposedAction()
            self._procesar_archivos(rutas, preguntar_genero=True)

    def _procesar_archivos(self, rutas: list[Path], preguntar_genero: bool = True):
        if not rutas:
            return

        id_genero = None
        if preguntar_genero:
            dialogo = GeneroDialog(self)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            id_genero = dialogo.genero_id()

        progreso = QProgressDialog("Preparando…", "Cancelar", 0, len(rutas), self)
        progreso.setWindowTitle("Subiendo archivos")
        progreso.setWindowModality(Qt.WindowModality.WindowModal)

        registrados, fallidos, errores = 0, 0, []

        for indice, origen in enumerate(rutas):
            if progreso.wasCanceled():
                break
            progreso.setValue(indice)
            progreso.setLabelText(f"Procesando {origen.name}…")
            QApplication.processEvents()

            try:
                destino = self.library.add_file(origen)
                with BookSource(destino) as libro:
                    total_paginas = libro.count()
                portada = extraer_portada(destino, COVERS_DIR, origen.stem)

                ok, mensaje = registrar_libro(
                    titulo=origen.stem,
                    formato=origen.suffix.replace(".", ""),
                    ruta_archivo=str(destino),
                    id_usuario=self.controller.current_user_id,
                    ruta_portada=str(portada) if portada else None,
                    id_genero=id_genero,
                    total_paginas=total_paginas,
                )
                if ok:
                    registrados += 1
                else:
                    fallidos += 1
                    errores.append(mensaje)
            except Exception as exc:
                fallidos += 1
                errores.append(f"{origen.name}: {exc}")

        progreso.setValue(len(rutas))
        progreso.close()

        self.refresh()
        if self.library_window is not None:
            self.library_window.refresh()

        if fallidos:
            detalle = "\n".join(errores[:5])
            QMessageBox.warning(
                self,
                "Subida con incidencias",
                f"Se registraron {registrados} archivo(s) y fallaron {fallidos}.\n\n{detalle}",
            )
        else:
            QMessageBox.information(self, "Subida completada", f"Se registraron {registrados} archivo(s).")

    def sincronizar_carpeta(self):
        """Registra los archivos de data/library que no están en la base."""
        existentes = {
            str(Path(libro["ruta_archivo"]).resolve()).replace("\\", "/")
            for libro in self._libros
            if libro.get("ruta_archivo")
        }
        pendientes = [
            archivo
            for archivo in self.library.files()
            if str(archivo.resolve()).replace("\\", "/") not in existentes
        ]

        if not pendientes:
            QMessageBox.information(
                self,
                "Todo al día",
                f"Los {len(existentes)} archivos de la carpeta ya están registrados.",
            )
            return

        if QMessageBox.question(
            self,
            "Sincronizar carpeta",
            f"Se encontraron {len(pendientes)} archivo(s) sin registrar.\n¿Añadirlos al catálogo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        self._procesar_archivos(pendientes, preguntar_genero=True)

    # ------------------------------------------------------------ editar ----
    def editar_libro(self):
        libro = self._libro_seleccionado()
        if libro is None:
            QMessageBox.warning(self, "Aviso", "Selecciona un libro de la tabla.")
            return

        dialogo = EditarLibroDialog(libro, self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        datos = dialogo.datos()
        if not datos["titulo"]:
            QMessageBox.warning(self, "Aviso", "El título no puede quedar vacío.")
            return

        ok, mensaje = actualizar_libro(
            libro["id_libro"],
            titulo=datos["titulo"],
            id_genero=datos["id_genero"],
            ruta_portada=datos["ruta_portada"],
        )
        if ok:
            self.refresh()
            if self.library_window is not None:
                self.library_window.refresh()
        else:
            QMessageBox.critical(self, "Error", mensaje)

    def eliminar_libro(self):
        libro = self._libro_seleccionado()
        if libro is None:
            QMessageBox.warning(self, "Aviso", "Selecciona el libro que quieres eliminar.")
            return

        if QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar «{libro['titulo']}»?\n\n"
            "Se borrarán también sus reseñas y el archivo de la carpeta de la biblioteca.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

        ok, ruta = eliminar_libro_db(libro["id_libro"])
        if not ok:
            QMessageBox.critical(self, "Error", "No se pudo eliminar el registro de la base de datos.")
            return

        if ruta and self._dentro_de(ruta, self.library.folder):
            self.library.delete_file(ruta)
        portada = libro.get("ruta_portada")
        if portada and self._dentro_de(portada, COVERS_DIR):
            self.library.delete_file(portada)

        self.refresh()
        if self.library_window is not None:
            self.library_window.refresh()

    @staticmethod
    def _dentro_de(ruta: str | Path, carpeta: str | Path) -> bool:
        """True si ``ruta`` está dentro de ``carpeta``.

        Se comprueba antes de borrar archivos: si una fila antigua de MySQL
        apunta al archivo original del usuario (fuera de ``data/library``),
        borrarlo destruiría su copia sin avisar.
        """
        try:
            Path(ruta).resolve().relative_to(Path(carpeta).resolve())
            return True
        except (ValueError, OSError):
            return False

    # ------------------------------------------------------------ otros -----
    def gestionar_generos(self):
        GenerosDialog(self).exec()
        self.refresh()
        if self.library_window is not None:
            self.library_window.actualizar_generos()

    def abrir_usuarios(self):
        # Una sola ventana de usuarios: si ya está abierta se trae al frente.
        if self.users_win is not None:
            self.users_win.show()
            self.users_win.raise_()
            self.users_win.activateWindow()
            return
        self.users_win = UserAdminWindow(self.controller, self)
        self.users_win.closed.connect(self._usuarios_cerrados)
        self.users_win.show()

    def _usuarios_cerrados(self):
        self.users_win = None

    def closeEvent(self, event):
        if self.users_win is not None:
            self.users_win.close()
            self.users_win = None
        self.closed.emit()
        super().closeEvent(event)
