"""
FlashDock — Global QSS Stylesheets (HyperOS 2.0 / macOS Sequoia / Apple HIG Design Tokens).

Design Tokens & Ergonomic Color Palette:
-----------------------------------------
* Typography: Apple SF Pro System Stack ("-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif).
  - Scale: Title 1/Headline (20px), Title 2 (14px), Body (13px), Caption (11px-12px).
  - Tabular Numerals: "SF Pro Display", "JetBrains Mono", monospace.
* Light Mode Palette (Anti-Glare Slate-Mica & Soft Porcelain Frost):
  - Canvas / Window: #ECEFF4 / #F0F2F5 (Warm Slate-Mica — eliminates blinding pure white glare).
  - Sidebar Panel: #F5F7FA / #E9EEF5 with subtle 1px border rgba(0, 0, 0, 0.06) / #DCE1E8.
  - Cards & Group Containers: #FFFFFF / #F8F9FA with 16px radius and 1px border rgba(0, 0, 0, 0.06) / #DCE1E8.
  - Primary Text: #1C2024 (Deep slate charcoal — 100% crisp, zero glare).
  - Secondary / Muted Text: #5A6572 (High contrast, WCAG AAA compliant).
  - System Accent: #007AFF (Hover: #0062CC, Pressed: #004FB8).
  - Console Terminal: #080B10 with #E6EDF3 text.
  - Dividers / Borders: 1px solid #DCE1E8.
* Dark Mode Palette (HyperOS Deep Space Obsidian & Elevated Frosted Slate):
  - Canvas / Window: #0D1117 (Deep Space Obsidian — eliminates pitch-black void).
  - Sidebar Panel: #131822 / #141820 with 1px border rgba(255, 255, 255, 0.07) / #252D38.
  - Cards & Group Containers: #1A212E / #181E26 with 16px radius and inner border highlight rgba(255, 255, 255, 0.08) / #2C3644.
  - Primary Text: #E6EDF3 (Soft Platinum — high readability without blinding contrast).
  - Secondary / Muted Text: #8B949E (Muted Steel — crisp, readable).
  - System Accent: #0A84FF (Hover: #0071E3, Pressed: #0056B3).
  - Console Terminal: #080B10 with #E6EDF3 text.
  - Dividers / Borders: 1px solid #2C3644 / #252D38.
* Border Radii:
  - Checkbox indicators: 4px.
  - Buttons, LineEdit, ComboBox: 10px - 14px.
  - Action & Navigation Pills: 14px - 20px.
  - Cards, GroupBoxes, Tab panels: 16px.
  - Dialogs: 16px.
"""

DARK_STYLESHEET = """
/* ================================================================
   Apple HIG & HyperOS 2.0 Global Base (Dark Mode — Deep Space Obsidian)
   Tokens: #0D1117 Canvas, #181E26 Cards, #2C3644 Border, #141820 Sidebar, #252D38 Border, #E6EDF3 Text, #8B949E Muted, #0B0E14 Terminal
   ================================================================ */
QWidget {
    background-color: #0D1117;
    color: #E6EDF3;
    font-family: "-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
}

QMainWindow {
    background-color: #0D1117;
}

QDialog {
    background-color: #0D1117;
    color: #E6EDF3;
    border-radius: 16px;
}

QMainWindow::separator {
    background-color: #252D38;
    width: 1px;
    height: 1px;
}

QMenuBar {
    background-color: #131822;
    border-bottom: 1px solid #252D38;
    padding: 3px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 8px;
    color: #8B949E;
}

QMenuBar::item:selected {
    background-color: rgba(255, 255, 255, 0.08);
    color: #E6EDF3;
}

QMenu {
    background-color: #1A212E;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 8px;
    color: #E6EDF3;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #0A84FF;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #2C3644;
    margin: 4px 6px;
}

/* Base Push Buttons */
QPushButton {
    background-color: #1A212E;
    border: 1px solid #2C3644;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #E6EDF3;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #242D3D;
    border-color: #3D4B5C;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #141A24;
    border-color: #2C3644;
}

QPushButton:disabled {
    color: #484F58;
    background-color: rgba(255, 255, 255, 0.03);
    border-color: #1E2530;
}

/* Primary Action Trigger: Gradient Pill Button */
QPushButton[cssClass="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A84FF, stop:1 #0056B3);
    border: 1px solid #3399FF;
    border-radius: 20px;
    padding: 9px 20px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
}

QPushButton[cssClass="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3399FF, stop:1 #0066CC);
    border-color: #58A6FF;
}

QPushButton[cssClass="primary"]:pressed {
    background: #004FB8;
}

QPushButton[cssClass="primary"]:disabled {
    background: #16365C;
    border-color: #16365C;
    color: #484F58;
}

QPushButton[cssClass="secondary"] {
    background-color: #1A212E;
    border: 1px solid #2C3644;
    border-radius: 12px;
    color: #E6EDF3;
    font-weight: 500;
    padding: 7px 14px;
}

QPushButton[cssClass="secondary"]:hover {
    background-color: #242D3D;
    border-color: #3D4B5C;
}

QPushButton[cssClass="danger"] {
    background-color: #2D1418;
    border: 1px solid #4C1E24;
    border-radius: 12px;
    color: #FF453A;
    font-weight: 600;
}

QPushButton[cssClass="danger"]:hover {
    background-color: #FF453A;
    border-color: #FF453A;
    color: #FFFFFF;
}

QPushButton[cssClass="danger"]:pressed {
    background-color: #C92A2A;
}

QPushButton[cssClass="warning"] {
    background-color: #2E1F00;
    border: 1px solid #633C02;
    border-radius: 12px;
    color: #FF9F0A;
    font-weight: 600;
}

QPushButton[cssClass="warning"]:hover {
    background-color: #FF9F0A;
    border-color: #FF9F0A;
    color: #000000;
}

/* Floating Action Cards */
QPushButton[cssClass="action"] {
    background-color: #1A212E;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 14px 18px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    color: #E6EDF3;
    min-height: 52px;
}

QPushButton[cssClass="action"]:hover {
    background-color: #222C3D;
    border-color: #0A84FF;
    color: #FFFFFF;
}

QPushButton[cssClass="action"]:pressed {
    background-color: #161D28;
}

/* HyperOS / iOS 18 Primary Navigation Pills */
QPushButton[cssClass="nav_pill"] {
    background-color: #161D28;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 18px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    color: #E6EDF3;
    min-height: 44px;
}

QPushButton[cssClass="nav_pill"]:hover {
    background-color: #1E2736;
    border-color: #3D4B5C;
    color: #FFFFFF;
}

QPushButton[cssClass="nav_pill"][active="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #253346, stop:1 #1C2736);
    border: 1px solid #0A84FF;
    color: #FFFFFF;
    font-weight: 700;
}

/* Typography Labels */
QLabel {
    background: transparent;
    color: #E6EDF3;
}

QLabel[cssClass="heading"] {
    font-size: 20px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.4px;
}

QLabel[cssClass="subheading"] {
    font-size: 14px;
    font-weight: 500;
    color: #D0D7DE;
}

QLabel[cssClass="muted"] {
    color: #8B949E;
    font-size: 12px;
}

QLabel[cssClass="metric"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    font-weight: 500;
    color: #E6EDF3;
}

QLabel[cssClass="success"] {
    color: #30D158;
}

QLabel[cssClass="warning"] {
    color: #FF9F0A;
}

QLabel[cssClass="error"] {
    color: #FF453A;
}

QLabel[cssClass="code_text"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    color: #7EE787;
    font-size: 12px;
    font-weight: 600;
}

/* Card Containers & Group Boxes */
QGroupBox {
    background-color: #1A212E;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #8B949E;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.6px;
    font-weight: 700;
}

QFrame[cssClass="card"] {
    background-color: #1A212E;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 14px;
}

QFrame[cssClass="card_subtle"] {
    background-color: #13171F;
    border: 1px solid #252D38;
    border-radius: 12px;
    padding: 10px;
}

QFrame[cssClass="warn_banner"] {
    background-color: #2E1F00;
    border: 1px solid #633C02;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="danger_banner"] {
    background-color: #2D1418;
    border: 1px solid #4C1E24;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="info_banner"] {
    background-color: #0D2136;
    border: 1px solid #17426A;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="code_box"] {
    background-color: #080B10;
    border: 1px solid #252D38;
    border-radius: 8px;
    padding: 8px;
}

QFrame[cssClass="separator"] {
    background-color: #252D38;
    max-height: 1px;
    min-height: 1px;
}

/* Scroll Area & Bars */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 7px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2C3644;
    border-radius: 3px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #3D4B5C;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 7px;
    margin: 0;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #2C3644;
    border-radius: 3px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #3D4B5C;
}

/* Form Controls & Recessed Squircle Inputs */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #0E1218;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 8px 12px;
    color: #E6EDF3;
    font-size: 13px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #0A84FF;
    background-color: #141820;
}

QComboBox {
    background-color: #1A212E;
    border: 1px solid #2C3644;
    border-radius: 10px;
    padding: 7px 12px;
    min-height: 24px;
    color: #E6EDF3;
}

QComboBox:hover {
    border-color: #3D4B5C;
    background-color: #242D3D;
}

QComboBox:focus {
    border-color: #0A84FF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1A212E;
    border: 1px solid #2C3644;
    border-radius: 10px;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
    padding: 4px;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    background: transparent;
    color: #E6EDF3;
    font-size: 13px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3D4B5C;
    border-radius: 4px;
    background-color: #1A212E;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #0A84FF;
}

QCheckBox::indicator:checked {
    background-color: #0A84FF;
    border-color: #0A84FF;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QRadioButton::indicator:checked {
    background-color: #0A84FF;
    border-color: #0A84FF;
}

QTabWidget::pane {
    border: 1px solid #2C3644;
    border-radius: 16px;
    background-color: #1A212E;
    top: -1px;
}

QTabBar::tab {
    background-color: #131822;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 4px;
    color: #8B949E;
    font-size: 13px;
    font-weight: 500;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}

QTabBar::tab:selected {
    background-color: #1A212E;
    color: #FFFFFF;
    font-weight: 600;
    border-top: 1px solid #2C3644;
    border-left: 1px solid #2C3644;
    border-right: 1px solid #2C3644;
    border-bottom: 2px solid #0A84FF;
}

QTabBar::tab:hover:!selected {
    color: #E6EDF3;
    background-color: #1E2530;
}

QProgressBar {
    background-color: #1E2530;
    border: none;
    border-radius: 6px;
    text-align: center;
    min-height: 14px;
    max-height: 14px;
    color: #8B949E;
    font-family: "SF Pro Display", "JetBrains Mono", monospace;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 6px;
}

QStatusBar {
    background-color: #131822;
    border-top: 1px solid #252D38;
    padding: 3px 12px;
    font-size: 12px;
    color: #8B949E;
}

QStatusBar::item {
    border: none;
}

QToolTip {
    background-color: #1A212E;
    border: 1px solid #2C3644;
    border-radius: 8px;
    padding: 6px 10px;
    color: #E6EDF3;
    font-size: 12px;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #131822;
    border: 1px solid #2C3644;
    border-radius: 10px;
    gridline-color: #1A212E;
    color: #E6EDF3;
}

QTableWidget::item, QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #1A212E;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: rgba(10, 132, 255, 0.2);
    color: #58A6FF;
    font-weight: 500;
}

QHeaderView::section {
    background-color: #131822;
    border: none;
    border-bottom: 1px solid #2C3644;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #8B949E;
    text-transform: uppercase;
}

/* Sidebar & Specialized Containers (HyperOS Midnight Charcoal) */
PhoneControlPanel {
    background-color: #131822;
    border-right: 1px solid rgba(255, 255, 255, 0.07);
}

PhoneControlPanel QPushButton {
    background-color: transparent;
    border: 1px solid #252D38;
    border-radius: 14px;
    padding: 8px 12px;
    margin: 2px 2px;
    text-align: left;
    font-size: 12px;
    font-weight: 500;
    color: #E6EDF3;
}

PhoneControlPanel QPushButton:hover {
    background-color: rgba(10, 132, 255, 0.14);
    border-color: #0A84FF;
    color: #0A84FF;
}

PhoneControlPanel QPushButton:disabled {
    color: #484F58;
    border-color: transparent;
    background-color: transparent;
}

PhoneControlPanel QPushButton#refresh_btn {
    background-color: #1E2530;
    border: 1px solid #2C3644;
    border-radius: 14px;
    padding: 8px 12px;
    color: #E6EDF3;
}

PhoneControlPanel QPushButton#refresh_btn:hover {
    background-color: #252E3C;
}

DeviceSelector {
    background-color: transparent;
    border: none;
    padding: 0px;
}

StatusBarWidget {
    background-color: #0D1117;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: none;
    padding: 0 10px;
}

SideTerminalWidget {
    background-color: #131822;
    border-left: 1px solid #252D38;
}

SideTerminalWidget QPlainTextEdit {
    background-color: #080B10;
    border-left: 1px solid #252D38;
    border-top: none;
    border-right: none;
    border-bottom: none;
    color: #E6EDF3;
}

/* GSM Suite macOS Big Sur Tokens (Dark) */
QFrame[cssClass="segmented_control"] {
    background-color: #141820;
    border-bottom: 1px solid #252D38;
    border-radius: 0px;
    padding: 2px 14px;
}

QFrame[cssClass="operations_panel"] {
    background-color: #181E26;
    border: 1px solid #2C3644;
    border-radius: 16px;
}

QLabel#connection_badge {
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

/* Global ScrollBar Ergonomics */
QScrollBar:horizontal {
    height: 0px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
}
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #0A84FF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


LIGHT_STYLESHEET = """
/* ================================================================
   Apple HIG & HyperOS 2.0 Global Base (Light Mode — Anti-Glare Slate-Mica & Soft Frost)
   Tokens: #F0F2F5 Canvas, #F8F9FA Cards, #DCE1E8 Border, #E9EEF5 Sidebar, #1C2024 Text, #5A6572 Muted
   ================================================================ */
QWidget {
    background-color: #E2E6EC;
    color: #1C2024;
    font-family: "-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
}

QMainWindow {
    background-color: #E2E6EC;
}

QDialog {
    background-color: #E2E6EC;
    color: #1C2024;
    border-radius: 16px;
}

QMainWindow::separator {
    background-color: #CBD1DC;
    width: 1px;
    height: 1px;
}

QMenuBar {
    background-color: #D8DCE4;
    border-bottom: 1px solid #CBD1DC;
    padding: 3px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 8px;
    color: #1C2024;
}

QMenuBar::item:selected {
    background-color: rgba(0, 0, 0, 0.08);
    color: #1C2024;
}

QMenu {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 12px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 8px;
    color: #1C2024;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #CBD1DC;
    margin: 4px 6px;
}

/* Base Push Buttons */
QPushButton {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #1C2024;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #F4F6F9;
    border-color: #007AFF;
    color: #1C2024;
}

QPushButton:pressed {
    background-color: #D8DCE4;
    border-color: #007AFF;
}

QPushButton:disabled {
    color: #8C96A3;
    background-color: rgba(0, 0, 0, 0.04);
    border-color: #CBD1DC;
}

/* Primary Action Trigger: Gradient Pill Button */
QPushButton[cssClass="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #007AFF, stop:1 #0056B3);
    border: 1px solid #007AFF;
    border-radius: 20px;
    padding: 9px 20px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
}

QPushButton[cssClass="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0062CC, stop:1 #004FB8);
    border-color: #0062CC;
    color: #FFFFFF;
}

QPushButton[cssClass="primary"]:pressed {
    background-color: #004FB8;
}

QPushButton[cssClass="primary"]:disabled {
    background-color: #A0C8F8;
    border-color: #A0C8F8;
    color: #FFFFFF;
}

QPushButton[cssClass="secondary"] {
    background-color: #E2E6EC;
    border: 1px solid #CBD1DC;
    border-radius: 12px;
    color: #1C2024;
    font-weight: 500;
    padding: 7px 14px;
}

QPushButton[cssClass="secondary"]:hover {
    background-color: #ECEFF4;
    border-color: #9AA4B2;
}

QPushButton[cssClass="danger"] {
    background-color: #FFF0F0;
    border: 1px solid #FFD0D4;
    border-radius: 12px;
    color: #D70015;
    font-weight: 600;
}

QPushButton[cssClass="danger"]:hover {
    background-color: #D70015;
    border-color: #D70015;
    color: #FFFFFF;
}

QPushButton[cssClass="danger"]:pressed {
    background-color: #B30010;
}

QPushButton[cssClass="warning"] {
    background-color: #FFF8E6;
    border: 1px solid #F5C26B;
    border-radius: 12px;
    color: #B25000;
    font-weight: 600;
}

QPushButton[cssClass="warning"]:hover {
    background-color: #F5C26B;
    border-color: #B25000;
    color: #000000;
}

/* Floating Action Cards */
QPushButton[cssClass="action"] {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 16px;
    padding: 14px 18px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    color: #1C2024;
    min-height: 52px;
}

QPushButton[cssClass="action"]:hover {
    background-color: #F4F6F9;
    border-color: #007AFF;
    color: #1C2024;
}

QPushButton[cssClass="action"]:pressed {
    background-color: #D8DCE4;
}

/* HyperOS / iOS 18 Primary Navigation Pills */
QPushButton[cssClass="nav_pill"] {
    background-color: #E2E6EC;
    border: 1px solid #CBD1DC;
    border-radius: 18px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    color: #1C2024;
    min-height: 44px;
}

QPushButton[cssClass="nav_pill"]:hover {
    background-color: #ECEFF4;
    border-color: #9AA4B2;
    color: #1C2024;
}

QPushButton[cssClass="nav_pill"][active="true"] {
    background-color: #9AA2B0;
    border: 1px solid #828B9B;
    color: #FFFFFF;
    font-weight: 700;
}

QPushButton[cssClass="action"]:pressed {
    background-color: #F0F3F7;
}

/* Typography Labels */
QLabel {
    background: transparent;
    color: #1C2024;
}

QLabel[cssClass="heading"] {
    font-size: 20px;
    font-weight: 700;
    color: #1C2024;
    letter-spacing: -0.4px;
}

QLabel[cssClass="subheading"] {
    font-size: 14px;
    font-weight: 600;
    color: #343D46;
}

QLabel[cssClass="muted"] {
    color: #5A6572;
    font-size: 12px;
}

QLabel[cssClass="metric"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    font-weight: 500;
    color: #1C2024;
}

QLabel[cssClass="success"] {
    color: #1A7F37;
    font-weight: 600;
}

QLabel[cssClass="warning"] {
    color: #B25000;
    font-weight: 600;
}

QLabel[cssClass="error"] {
    color: #D70015;
    font-weight: 600;
}

QLabel[cssClass="code_text"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    color: #0F5132;
    font-size: 12px;
    font-weight: 600;
}

/* Card Containers & Group Boxes */
QGroupBox {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 16px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #5A6572;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.6px;
    font-weight: 700;
}

QFrame[cssClass="card"] {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 16px;
    padding: 14px;
}

QFrame[cssClass="card_subtle"] {
    background-color: #E2E6EC;
    border: 1px solid #CBD1DC;
    border-radius: 12px;
    padding: 10px;
}

QFrame[cssClass="warn_banner"] {
    background-color: #FFF8E6;
    border: 1px solid #F5C26B;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="danger_banner"] {
    background-color: #FDE8E8;
    border: 1px solid #F8B4B4;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="info_banner"] {
    background-color: #EBF5FF;
    border: 1px solid #A4CAFE;
    border-radius: 10px;
    padding: 10px;
}

QFrame[cssClass="code_box"] {
    background-color: #DDE2EB;
    border: 1px solid #CBD1DC;
    border-radius: 8px;
    padding: 8px;
}

QFrame[cssClass="separator"] {
    background-color: #CBD1DC;
    max-height: 1px;
    min-height: 1px;
}

/* Scroll Area & Bars */
QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 7px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #B8BFCB;
    border-radius: 3px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #9AA2B0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 7px;
    margin: 0;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #B8BFCB;
    border-radius: 3px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #9AA2B0;
}

/* Form Controls & Recessed Squircle Inputs */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #DDE2EB;
    border: 1px solid #CBD1DC;
    border-radius: 10px;
    padding: 8px 12px;
    color: #1C2024;
    font-size: 13px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #007AFF;
    background-color: #ECEFF4;
}

QComboBox {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 10px;
    padding: 7px 12px;
    min-height: 24px;
    color: #1C2024;
}

QComboBox:hover {
    border-color: #9AA2B0;
    background-color: #F4F6F9;
}

QComboBox:focus {
    border-color: #007AFF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 10px;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
    padding: 4px;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    background: transparent;
    color: #1C2024;
    font-size: 13px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #9AA2B0;
    border-radius: 4px;
    background-color: #ECEFF4;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #007AFF;
}

QCheckBox::indicator:checked {
    background-color: #007AFF;
    border-color: #007AFF;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QRadioButton::indicator:checked {
    background-color: #007AFF;
    border-color: #007AFF;
}

QTabWidget::pane {
    border: 1px solid #CBD1DC;
    border-radius: 16px;
    background-color: #ECEFF4;
    top: -1px;
}

QTabBar::tab {
    background-color: #D8DCE4;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 4px;
    color: #5A6572;
    font-size: 13px;
    font-weight: 500;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}

QTabBar::tab:selected {
    background-color: #ECEFF4;
    color: #1C2024;
    font-weight: 600;
    border-top: 1px solid #CBD1DC;
    border-left: 1px solid #CBD1DC;
    border-right: 1px solid #CBD1DC;
    border-bottom: 2px solid #007AFF;
}

QTabBar::tab:hover:!selected {
    color: #1C2024;
    background-color: #E2E6EC;
}

QProgressBar {
    background-color: #CBD1DC;
    border: none;
    border-radius: 6px;
    text-align: center;
    min-height: 14px;
    max-height: 14px;
    color: #5A6572;
    font-family: "SF Pro Display", "JetBrains Mono", monospace;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 6px;
}

QStatusBar {
    background-color: #D8DCE4;
    border-top: 1px solid #CBD1DC;
    padding: 3px 12px;
    font-size: 12px;
    color: #5A6572;
}

QStatusBar::item {
    border: none;
}

QToolTip {
    background-color: #1C2024;
    border: none;
    border-radius: 8px;
    padding: 6px 10px;
    color: #FFFFFF;
    font-size: 12px;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 10px;
    gridline-color: #DDE2EB;
    color: #1C2024;
}

QTableWidget::item, QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #DDE2EB;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #D0E4FF;
    color: #007AFF;
    font-weight: 600;
}

QHeaderView::section {
    background-color: #D8DCE4;
    border: none;
    border-bottom: 1px solid #CBD1DC;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #5A6572;
    text-transform: uppercase;
}

/* Sidebar & Specialized Containers (Light Soft Porcelain) */
PhoneControlPanel {
    background-color: #D8DCE4;
    border-right: 1px solid #CBD1DC;
}

PhoneControlPanel QPushButton {
    background-color: #E2E6EC;
    border: 1px solid #CBD1DC;
    border-radius: 14px;
    padding: 8px 12px;
    margin: 2px 2px;
    text-align: left;
    font-size: 12px;
    font-weight: 500;
    color: #1C2024;
}

PhoneControlPanel QPushButton:hover {
    background-color: #ECEFF4;
    border-color: #007AFF;
    color: #007AFF;
}

PhoneControlPanel QPushButton:disabled {
    color: #8C96A3;
    border-color: transparent;
    background-color: transparent;
}

PhoneControlPanel QPushButton#refresh_btn {
    background-color: #ECEFF4;
    border: 1px solid #CBD1DC;
    border-radius: 14px;
    padding: 8px 12px;
    color: #1C2024;
}

PhoneControlPanel QPushButton#refresh_btn:hover {
    background-color: #F4F6F9;
}

DeviceSelector {
    background-color: transparent;
    border: none;
    padding: 0px;
}

StatusBarWidget {
    background-color: #ECEFF4;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
    border-bottom: none;
    padding: 0 10px;
}

SideTerminalWidget {
    background-color: #D8DCE4;
    border-left: 1px solid #CBD1DC;
}

SideTerminalWidget QPlainTextEdit {
    background-color: #080B10;
    border-left: 1px solid #CBD1DC;
    border-top: none;
    border-right: none;
    border-bottom: none;
    color: #E6EDF3;
}

/* GSM Suite macOS Big Sur Tokens (Light) */
QFrame[cssClass="segmented_control"] {
    background-color: #E9EEF5;
    border-bottom: 1px solid #DCE1E8;
    border-radius: 0px;
    padding: 2px 14px;
}

QFrame[cssClass="operations_panel"] {
    background-color: #F8F9FA;
    border: 1px solid #DCE1E8;
    border-radius: 16px;
}

QLabel#connection_badge {
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

/* Global ScrollBar Ergonomics */
QScrollBar:horizontal {
    height: 0px;
    background: transparent;
}
QScrollBar::handle:horizontal {
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
}
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #007AFF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


def get_stylesheet(theme: str = "dark") -> str:
    """Return the active stylesheet based on theme selection ('dark' or 'light')."""
    if theme.lower() == "light":
        return LIGHT_STYLESHEET
    return DARK_STYLESHEET
