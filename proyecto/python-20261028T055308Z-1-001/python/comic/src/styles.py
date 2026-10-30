"""Hoja de estilos global (QSS) de CosmicStream.

La constante ``STYLE`` se aplica a la interfaz Qt para mantener una apariencia
coherente entre ventanas y controles. Los selectores con ``#nombre`` se
corresponden con el ``objectName`` asignado a cada widget en la aplicación.

Paleta
------
Fondo        #0b0c10   Superficie  #14161f   Borde  #262b3a
Texto        #e2e8f0   Secundario  #94a3b8   Acento #ff2a85 / #7c3aed
"""

# Qt probará estas familias en orden hasta encontrar una disponible.
FUENTE = "'Inter', 'Cantarell', 'Ubuntu', 'Segoe UI', system-ui, sans-serif"

# Es una cadena f para insertar FUENTE; las llaves dobles conservan las llaves
# de bloques que requiere QSS.
STYLE = f"""
/* ---------------------------------------------------------------- base -- */
/* Valores predeterminados para los controles y ventanas de la aplicación. */
QWidget {{
    background-color: #0b0c10;
    color: #e2e8f0;
    font-family: {FUENTE};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: #0b0c10;
}}

QLabel {{
    background: transparent;
}}

QToolTip {{
    background-color: #1a1e2b;
    color: #e2e8f0;
    border: 1px solid #2f3648;
    border-radius: 6px;
    padding: 5px 8px;
}}

/* ----------------------------------------------------------- tipografía -- */
/* Estilos identificados por objectName para títulos, etiquetas y reseñas. */
#section_title {{
    font-size: 19px;
    font-weight: 800;
    color: #f8fafc;
}}

#detail_title {{
    font-size: 30px;
    font-weight: 900;
    color: #f8fafc;
}}

#dialog_title {{
    font-size: 16px;
    font-weight: 800;
    color: #f8fafc;
}}

#muted {{
    color: #94a3b8;
    font-size: 12px;
}}

#muted_small {{
    color: #64748b;
    font-size: 11px;
}}

#form_label {{
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 600;
}}

#error_label {{
    color: #fb7185;
    font-size: 12px;
    font-weight: 600;
}}

#review_user {{
    font-weight: 700;
    color: #f1f5f9;
    font-size: 12px;
}}

/* --------------------------------------------------------------- barra --- */
/* Contenedor de navegación superior. */
#top_navbar {{
    background-color: #14161f;
    border: 1px solid #232838;
    border-radius: 12px;
}}

/* -------------------------------------------------------------- botones -- */
/* Apariencia común y estados interactivos de los botones. */
QPushButton {{
    background-color: #1b1f2b;
    color: #cbd5e1;
    border: 1px solid #2a3041;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #252b3a;
    color: #ffffff;
    border-color: #3b4358;
}}
QPushButton:pressed {{
    background-color: #141821;
}}
QPushButton:disabled {{
    background-color: #14161f;
    color: #4b5563;
    border-color: #1e2330;
}}

QPushButton#primary_btn {{
    background-color: #7c3aed;
    color: #ffffff;
    border: 1px solid #7c3aed;
    border-radius: 8px;
    font-weight: 700;
}}
QPushButton#primary_btn:hover {{
    background-color: #8b5cf6;
    border-color: #8b5cf6;
}}
QPushButton#primary_btn:pressed {{
    background-color: #6d28d9;
}}
QPushButton#primary_btn:disabled {{
    background-color: #3b3363;
    border-color: #3b3363;
    color: #a5a1bd;
}}

QPushButton#ghost_btn {{
    background-color: transparent;
    border: 1px solid #2a3041;
    color: #94a3b8;
}}
QPushButton#ghost_btn:hover {{
    background-color: #1b1f2b;
    color: #ffffff;
}}

QPushButton#danger {{
    background-color: #2a1620;
    color: #fda4af;
    border: 1px solid #4c1d2b;
    font-weight: 700;
}}
QPushButton#danger:hover {{
    background-color: #8f2436;
    color: #ffffff;
    border-color: #b02a41;
}}

QPushButton#link_btn {{
    background: transparent;
    border: none;
    color: #94a3b8;
    font-weight: 500;
}}
QPushButton#link_btn:hover {{
    color: #ffffff;
    text-decoration: underline;
}}

/* ------------------------------------------------------------ entradas -- */
/* Campos de texto; el borde cambia al recibir el foco. */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: #171a24;
    border: 1px solid #2a3041;
    border-radius: 8px;
    padding: 6px 12px;
    color: #f1f5f9;
    selection-background-color: #7c3aed;
    selection-color: #ffffff;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid #8b5cf6;
    background-color: #1b1f2b;
}}
QLineEdit:read-only {{
    color: #94a3b8;
}}

QLineEdit#search_bar {{
    background-color: #171a24;
    border: 1px solid #2a3041;
    border-radius: 18px;
    padding: 6px 16px;
    color: #f1f5f9;
}}
QLineEdit#search_bar:focus {{
    border: 1px solid #8b5cf6;
    background-color: #1b1f2b;
}}

/* ----------------------------------------------------------- combos ------ */
/* Selectores desplegables y controles numéricos. */
QComboBox {{
    background-color: #1b1f2b;
    color: #e2e8f0;
    border: 1px solid #2a3041;
    border-radius: 8px;
    padding: 5px 12px;
    font-weight: 500;
}}
QComboBox:hover {{
    border-color: #475569;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: #171a24;
    border: 1px solid #2a3041;
    border-radius: 8px;
    selection-background-color: #7c3aed;
    selection-color: #ffffff;
    outline: none;
    padding: 4px;
}}

QSpinBox {{
    background-color: #1b1f2b;
    border: 1px solid #2a3041;
    border-radius: 8px;
    padding: 4px 6px;
    color: #f1f5f9;
    font-weight: 700;
}}
QSpinBox:focus {{
    border-color: #8b5cf6;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    border: none;
}}

/* ------------------------------------------------------------- tarjetas -- */
/* Superficies reutilizables para tarjetas, insignias, portadas y avisos. */
#card {{
    background-color: #13151e;
    border: 1px solid #1f2330;
    border-radius: 12px;
}}

#review_card {{
    background-color: #171a24;
    border: 1px solid #232838;
    border-radius: 10px;
}}

#auth_card {{
    background-color: #14161f;
    border: 1px solid #252936;
    border-radius: 16px;
}}

#chip {{
    background-color: #1e2230;
    color: #cbd5e1;
    border: 1px solid #2e354b;
    border-radius: 11px;
    padding: 3px 12px;
    font-size: 11px;
    font-weight: 700;
}}

#avatar {{
    background-color: #3b82f6;
    color: #ffffff;
    border-radius: 11px;
    font-weight: 700;
    font-size: 11px;
}}

#cover_frame {{
    background-color: #161922;
    border: 2px solid #232838;
    border-radius: 12px;
}}

#cover_placeholder {{
    background-color: #13151e;
    border: 2px dashed #2b3040;
    border-radius: 12px;
    color: #64748b;
    font-weight: 600;
}}

#banner_error {{
    background-color: #2b1220;
    border: 1px solid #5b1d33;
    border-left: 4px solid #f43f5e;
    border-radius: 8px;
    color: #fecdd3;
    padding: 10px 14px;
    font-size: 12px;
}}

#empty_state {{
    color: #64748b;
    font-size: 14px;
    line-height: 1.6;
}}

/* ------------------------------------------------------------- galería --- */
/* Elementos de la cuadrícula de portadas y sus estados de interacción. */
QListWidget#cover_grid {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget#cover_grid::item {{
    background-color: #14161e;
    border: 1px solid #222634;
    border-radius: 10px;
    padding: 6px;
    color: #e2e8f0;
}}
QListWidget#cover_grid::item:hover {{
    background-color: #1b1f2b;
    border: 1px solid #7c3aed;
}}
QListWidget#cover_grid::item:selected {{
    background-color: #212739;
    border: 1px solid #ff2a85;
}}

/* -------------------------------------------------------------- tablas --- */
/* Tablas, celdas y encabezados, incluidas las filas seleccionadas. */
QTableWidget, QTableView {{
    background-color: #101219;
    alternate-background-color: #14161e;
    border: 1px solid #232838;
    border-radius: 10px;
    gridline-color: #1c2130;
    color: #e2e8f0;
    selection-background-color: #2a2350;
    selection-color: #ffffff;
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: #2a2350;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: #171a24;
    color: #94a3b8;
    border: none;
    border-right: 1px solid #1c2130;
    border-bottom: 1px solid #232838;
    padding: 8px;
    font-weight: 700;
    font-size: 11px;
}}
QTableCornerButton::section {{
    background-color: #171a24;
    border: none;
}}

/* ------------------------------------------------------------ progreso --- */
/* Barra de progreso compacta con un segmento de color de acento. */
QProgressBar {{
    background-color: #1c2130;
    border: none;
    border-radius: 3px;
    height: 6px;
}}
QProgressBar::chunk {{
    background-color: #7c3aed;
    border-radius: 3px;
}}

/* --------------------------------------------------------------- lector -- */
/* Fondo del área de lectura y barra de estado de la ventana. */
QScrollArea#reader_area {{
    background-color: #08090d;
    border: 1px solid #1c2130;
    border-radius: 8px;
}}
QStatusBar {{
    background-color: #101219;
    color: #94a3b8;
    border-top: 1px solid #1c2130;
}}

/* -------------------------------------------------- barras de desplazam. -- */
/* Barras verticales y horizontales con controles de extremo ocultos. */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #2a3041;
    min-height: 28px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: #475569;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #2a3041;
    min-width: 28px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #475569;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ----------------------------------------------------- diálogos y menús --- */
/* Colores para cuadros de mensaje, casillas de verificación y menús. */
QMessageBox {{
    background-color: #14161f;
}}
QMessageBox QLabel {{
    color: #e2e8f0;
}}
QCheckBox {{
    spacing: 8px;
}}
QMenu {{
    background-color: #171a24;
    border: 1px solid #2a3041;
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: #7c3aed;
    color: #ffffff;
}}
"""
