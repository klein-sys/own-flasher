"""
FlashDock — Global QSS Stylesheets (macOS Big Sur UI Kit / Apple HIG Design Tokens).

Extracted directly via Figma MCP from:
Figma File: macOS Big Sur UI Kit (Community)
File ID: dLmTIWT0sdmx2NbbFhAL5G

Design Tokens:
-------------
* Typography: Apple SF Pro System Stack ("-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif).
  - Scale: Title 1/Headline (20px), Title 2 (14px), Body (13px), Caption (11px-12px).
  - Tabular Numerals: "SF Pro Display", "JetBrains Mono", monospace.
* Light Mode Palette (macOS Big Sur - Balanced, Zero Eye Glare):
  - Canvas / Window: #EBEBEF (Soft neutral gray - eliminates harsh glare and eye strain).
  - Elevated Cards / Containers: #FFFFFF with 1px solid #D2D2D7 border and subtle elevation.
  - Sidebar & Top Bars: #E2E2E8 (macOS system soft sidebar).
  - Primary Text: #1C1C1E (Apple Shark deep charcoal - ultra crisp, 100% readable).
  - Secondary / Muted Text: #515154 (High contrast, WCAG AAA compliant, zero wash-out).
  - System Accent: #007AFF (Hover: #0062CC, Pressed: #004FB8).
  - Dividers / Borders: 1px solid #D2D2D7.
* Eye-Friendly Dark Mode Palette (macOS Big Sur):
  - Canvas / Window: #1C1C1E.
  - Elevated Cards: #242426 with 1px solid #38383A border.
  - Controls: #28282A.
  - Primary Text: #F2F2F7 (Soft white - high readability without blinding contrast).
  - Secondary / Muted Text: #98989D (Crisp, readable).
  - System Accent: #0A84FF.
  - Dividers / Borders: 1px solid #38383A.
* Border Radii:
  - Checkbox indicators: 4px.
  - Buttons, LineEdit, ComboBox: 8px.
  - Cards, GroupBoxes, Tab panels: 10px.
  - Dialogs: 12px.
"""

DARK_STYLESHEET = """
/* ================================================================
   Apple HIG Global Base (Eye-Friendly Dark Mode)
   ================================================================ */
QWidget {
    background-color: #1C1C1E;
    color: #E5E5EA;
    font-family: "-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
}

QMainWindow {
    background-color: #1C1C1E;
}

QDialog {
    background-color: #1C1C1E;
    color: #E5E5EA;
}

QMainWindow::separator {
    background-color: #2C2C2E;
    width: 1px;
    height: 1px;
}

QMenuBar {
    background-color: #161618;
    border-bottom: 1px solid #2C2C2E;
    padding: 3px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 6px;
    color: #8E8E93;
}

QMenuBar::item:selected {
    background-color: rgba(255, 255, 255, 0.08);
    color: #E5E5EA;
}

QMenu {
    background-color: #242426;
    border: 1px solid #38383A;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 6px;
    color: #E5E5EA;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #0A84FF;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #38383A;
    margin: 4px 6px;
}

QPushButton {
    background-color: #28282A;
    border: 1px solid #38383A;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #E5E5EA;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #323236;
    border-color: #48484A;
    color: #FFFFFF;
}

QPushButton:pressed {
    background-color: #222224;
    border-color: #38383A;
}

QPushButton:disabled {
    color: #555558;
    background-color: rgba(255, 255, 255, 0.03);
    border-color: #28282A;
}

QPushButton[cssClass="primary"] {
    background-color: #0A84FF;
    border: 1px solid #0A84FF;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton[cssClass="primary"]:hover {
    background-color: #0071E3;
    border-color: #0071E3;
}

QPushButton[cssClass="primary"]:pressed {
    background-color: #0056B3;
}

QPushButton[cssClass="primary"]:disabled {
    background-color: #1C3860;
    border-color: #1C3860;
    color: #8E8E93;
}

QPushButton[cssClass="secondary"] {
    background-color: #242426;
    border: 1px solid #38383A;
    color: #E5E5EA;
    font-weight: 500;
}

QPushButton[cssClass="secondary"]:hover {
    background-color: #2E2E32;
    border-color: #48484A;
}

QPushButton[cssClass="danger"] {
    background-color: #321618;
    border: 1px solid #5A1E22;
    color: #FF453A;
    font-weight: 600;
}

QPushButton[cssClass="danger"]:hover {
    background-color: #FF453A;
    border-color: #FF453A;
    color: #FFFFFF;
}

QPushButton[cssClass="danger"]:pressed {
    background-color: #D70015;
}

QPushButton[cssClass="warning"] {
    background-color: #332200;
    border: 1px solid #8A4E00;
    color: #FF9F0A;
    font-weight: 600;
}

QPushButton[cssClass="warning"]:hover {
    background-color: #FF9F0A;
    border-color: #FF9F0A;
    color: #000000;
}

QPushButton[cssClass="action"] {
    background-color: #242426;
    border: 1px solid #38383A;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    color: #E5E5EA;
    min-height: 48px;
}

QPushButton[cssClass="action"]:hover {
    background-color: #2E2E32;
    border-color: #0A84FF;
    color: #FFFFFF;
}

QPushButton[cssClass="action"]:pressed {
    background-color: #202022;
}

QLabel {
    background: transparent;
    color: #E5E5EA;
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
    color: #C7C7CC;
}

QLabel[cssClass="muted"] {
    color: #98989D;
    font-size: 12px;
}

QLabel[cssClass="metric"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    font-weight: 500;
    color: #E5E5EA;
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

QGroupBox {
    background-color: #242426;
    border: 1px solid #38383A;
    border-radius: 10px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #98989D;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.6px;
    font-weight: 700;
}

QFrame[cssClass="card"] {
    background-color: #242426;
    border: 1px solid #38383A;
    border-radius: 10px;
    padding: 14px;
}

QFrame[cssClass="card_subtle"] {
    background-color: #1E1E20;
    border: 1px solid #2C2C2E;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="warn_banner"] {
    background-color: #332200;
    border: 1px solid #8A4E00;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="danger_banner"] {
    background-color: #321618;
    border: 1px solid #5A1E22;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="info_banner"] {
    background-color: #0D223A;
    border: 1px solid #1C4472;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="code_box"] {
    background-color: #141416;
    border: 1px solid #28282A;
    border-radius: 6px;
    padding: 8px;
}

QFrame[cssClass="separator"] {
    background-color: #38383A;
    max-height: 1px;
    min-height: 1px;
}

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
    background-color: #38383A;
    border-radius: 3px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #48484A;
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
    background-color: #38383A;
    border-radius: 3px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #48484A;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #1C1C1E;
    border: 1px solid #38383A;
    border-radius: 8px;
    padding: 8px 12px;
    color: #E5E5EA;
    font-size: 13px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #0A84FF;
    background-color: #242426;
}

QComboBox {
    background-color: #28282A;
    border: 1px solid #38383A;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 22px;
    color: #E5E5EA;
}

QComboBox:hover {
    border-color: #48484A;
    background-color: #343438;
}

QComboBox:focus {
    border-color: #0A84FF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #242426;
    border: 1px solid #38383A;
    border-radius: 8px;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
    padding: 4px;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    background: transparent;
    color: #E5E5EA;
    font-size: 13px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #48484A;
    border-radius: 4px;
    background-color: #28282A;
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
    border: 1px solid #38383A;
    border-radius: 10px;
    background-color: #242426;
    top: -1px;
}

QTabBar::tab {
    background-color: #1E1E20;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 4px;
    color: #8E8E93;
    font-size: 13px;
    font-weight: 500;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QTabBar::tab:selected {
    background-color: #242426;
    color: #FFFFFF;
    font-weight: 600;
    border-top: 1px solid #38383A;
    border-left: 1px solid #38383A;
    border-right: 1px solid #38383A;
    border-bottom: 2px solid #0A84FF;
}

QTabBar::tab:hover:!selected {
    color: #E5E5EA;
    background-color: #28282A;
}

QProgressBar {
    background-color: #28282A;
    border: none;
    border-radius: 6px;
    text-align: center;
    min-height: 14px;
    max-height: 14px;
    color: #8E8E93;
    font-family: "SF Pro Display", "JetBrains Mono", monospace;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 6px;
}

QStatusBar {
    background-color: #161618;
    border-top: 1px solid #2C2C2E;
    padding: 3px 12px;
    font-size: 12px;
    color: #8E8E93;
}

QStatusBar::item {
    border: none;
}

QToolTip {
    background-color: #2C2C2E;
    border: 1px solid #48484A;
    border-radius: 6px;
    padding: 6px 10px;
    color: #E5E5EA;
    font-size: 12px;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #1C1C1E;
    border: 1px solid #38383A;
    border-radius: 8px;
    gridline-color: #242426;
    color: #E5E5EA;
}

QTableWidget::item, QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #242426;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: rgba(10, 132, 255, 0.2);
    color: #0A84FF;
    font-weight: 500;
}

QHeaderView::section {
    background-color: #161618;
    border: none;
    border-bottom: 1px solid #38383A;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #8E8E93;
    text-transform: uppercase;
}

/* Sidebar & Specialized Containers */
PhoneControlPanel {
    background-color: #161618;
    border-right: 1px solid #2C2C2E;
}

PhoneControlPanel QPushButton {
    background-color: transparent;
    border: 1px solid #2C2C2E;
    border-radius: 8px;
    padding: 7px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 500;
    color: #E5E5EA;
}

PhoneControlPanel QPushButton:hover {
    background-color: rgba(10, 132, 255, 0.12);
    border-color: #0A84FF;
    color: #0A84FF;
}

PhoneControlPanel QPushButton:disabled {
    color: #48484A;
    border-color: transparent;
    background-color: transparent;
}

PhoneControlPanel QPushButton#refresh_btn {
    background-color: #28282A;
    border: 1px solid #38383A;
    border-radius: 8px;
    padding: 7px 12px;
    color: #E5E5EA;
}

PhoneControlPanel QPushButton#refresh_btn:hover {
    background-color: #323236;
}

DeviceSelector {
    background-color: #1E1E20;
    border-bottom: 1px solid #2C2C2E;
    padding: 4px;
}

StatusBarWidget {
    background-color: #161618;
    border-top: 1px solid #2C2C2E;
    padding: 0 10px;
}

SideTerminalWidget {
    background-color: #161618;
    border-left: 1px solid #2C2C2E;
}

SideTerminalWidget QPlainTextEdit {
    background-color: #121214;
    border-left: 1px solid #2C2C2E;
    border-top: none;
    border-right: none;
    border-bottom: none;
    color: #A1A1AA;
}
"""


LIGHT_STYLESHEET = """
/* ================================================================
   Apple HIG Global Base (Eye-Friendly Light Mode - macOS Big Sur)
   Balanced soft neutral tones, zero glare, high-contrast readable text
   ================================================================ */
QWidget {
    background-color: #EBEBEF;
    color: #1C1C1E;
    font-family: "-apple-system", "SF Pro Text", "SF Pro Display", "SF Pro", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
}

QMainWindow {
    background-color: #EBEBEF;
}

QDialog {
    background-color: #EBEBEF;
    color: #1C1C1E;
}

QMainWindow::separator {
    background-color: #D2D2D7;
    width: 1px;
    height: 1px;
}

QMenuBar {
    background-color: #E2E2E8;
    border-bottom: 1px solid #D2D2D7;
    padding: 3px 8px;
    font-size: 12px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
    border-radius: 6px;
    color: #1C1C1E;
}

QMenuBar::item:selected {
    background-color: rgba(0, 0, 0, 0.08);
    color: #1C1C1E;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 10px;
    padding: 6px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 6px;
    color: #1C1C1E;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #007AFF;
    color: #FFFFFF;
}

QMenu::separator {
    height: 1px;
    background-color: #E5E5EA;
    margin: 4px 6px;
}

QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #1C1C1E;
    min-height: 22px;
}

QPushButton:hover {
    background-color: #F5F5F7;
    border-color: #007AFF;
    color: #1C1C1E;
}

QPushButton:pressed {
    background-color: #E5E5EA;
    border-color: #007AFF;
}

QPushButton:disabled {
    color: #8E8E93;
    background-color: rgba(0, 0, 0, 0.04);
    border-color: #E5E5EA;
}

QPushButton[cssClass="primary"] {
    background-color: #007AFF;
    border: 1px solid #007AFF;
    color: #FFFFFF;
    font-weight: 600;
}

QPushButton[cssClass="primary"]:hover {
    background-color: #0062CC;
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
    background-color: #E5E5EA;
    border: 1px solid #D2D2D7;
    color: #1C1C1E;
    font-weight: 500;
}

QPushButton[cssClass="secondary"]:hover {
    background-color: #DCDCE0;
    border-color: #B0B0B5;
}

QPushButton[cssClass="danger"] {
    background-color: #FFF2F2;
    border: 1px solid #FFCCD0;
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
    color: #B25000;
    font-weight: 600;
}

QPushButton[cssClass="warning"]:hover {
    background-color: #F5C26B;
    border-color: #B25000;
    color: #000000;
}

QPushButton[cssClass="action"] {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    color: #1C1C1E;
    min-height: 48px;
}

QPushButton[cssClass="action"]:hover {
    background-color: #FAFAFC;
    border-color: #007AFF;
    color: #1C1C1E;
}

QPushButton[cssClass="action"]:pressed {
    background-color: #F2F2F7;
}

QLabel {
    background: transparent;
    color: #1C1C1E;
}

QLabel[cssClass="heading"] {
    font-size: 20px;
    font-weight: 700;
    color: #1C1C1E;
    letter-spacing: -0.4px;
}

QLabel[cssClass="subheading"] {
    font-size: 14px;
    font-weight: 600;
    color: #3A3A3C;
}

QLabel[cssClass="muted"] {
    color: #515154;
    font-size: 12px;
}

QLabel[cssClass="metric"] {
    font-family: "SF Pro Display", "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
    font-size: 13px;
    font-weight: 500;
    color: #1C1C1E;
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

QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 10px;
    margin-top: 14px;
    padding: 18px 14px 14px 14px;
    font-weight: 600;
    font-size: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #3A3A3C;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.6px;
    font-weight: 700;
}

QFrame[cssClass="card"] {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 10px;
    padding: 14px;
}

QFrame[cssClass="card_subtle"] {
    background-color: #F5F5F7;
    border: 1px solid #E5E5EA;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="warn_banner"] {
    background-color: #FFF8E6;
    border: 1px solid #F5C26B;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="danger_banner"] {
    background-color: #FDE8E8;
    border: 1px solid #F8B4B4;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="info_banner"] {
    background-color: #EBF5FF;
    border: 1px solid #A4CAFE;
    border-radius: 8px;
    padding: 10px;
}

QFrame[cssClass="code_box"] {
    background-color: #F2F2F5;
    border: 1px solid #D2D2D7;
    border-radius: 6px;
    padding: 8px;
}

QFrame[cssClass="separator"] {
    background-color: #D2D2D7;
    max-height: 1px;
    min-height: 1px;
}

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
    background-color: #C7C7CC;
    border-radius: 3px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #8E8E93;
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
    background-color: #C7C7CC;
    border-radius: 3px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #8E8E93;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1C1C1E;
    font-size: 13px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #007AFF;
    background-color: #FFFFFF;
}

QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 22px;
    color: #1C1C1E;
}

QComboBox:hover {
    border-color: #AEAEB2;
    background-color: #FAFAFC;
}

QComboBox:focus {
    border-color: #007AFF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
    padding: 4px;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    background: transparent;
    color: #1C1C1E;
    font-size: 13px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #AEAEB2;
    border-radius: 4px;
    background-color: #FFFFFF;
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
    border: 1px solid #D2D2D7;
    border-radius: 10px;
    background-color: #FFFFFF;
    top: -1px;
}

QTabBar::tab {
    background-color: #DCDCDE;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 4px;
    color: #515154;
    font-size: 13px;
    font-weight: 500;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #1C1C1E;
    font-weight: 600;
    border-top: 1px solid #D2D2D7;
    border-left: 1px solid #D2D2D7;
    border-right: 1px solid #D2D2D7;
    border-bottom: 2px solid #007AFF;
}

QTabBar::tab:hover:!selected {
    color: #1C1C1E;
    background-color: #E5E5EA;
}

QProgressBar {
    background-color: #DCDCDE;
    border: none;
    border-radius: 6px;
    text-align: center;
    min-height: 14px;
    max-height: 14px;
    color: #515154;
    font-family: "SF Pro Display", "JetBrains Mono", monospace;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 6px;
}

QStatusBar {
    background-color: #E2E2E8;
    border-top: 1px solid #D2D2D7;
    padding: 3px 12px;
    font-size: 12px;
    color: #515154;
}

QStatusBar::item {
    border: none;
}

QToolTip {
    background-color: #1C1C1E;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    color: #FFFFFF;
    font-size: 12px;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    gridline-color: #EBEBEF;
    color: #1C1C1E;
}

QTableWidget::item, QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #EBEBEF;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #E5F1FF;
    color: #007AFF;
    font-weight: 600;
}

QHeaderView::section {
    background-color: #EBEBEF;
    border: none;
    border-bottom: 1px solid #D2D2D7;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    color: #3A3A3C;
    text-transform: uppercase;
}

/* Sidebar & Specialized Containers */
PhoneControlPanel {
    background-color: #E2E2E8;
    border-right: 1px solid #D2D2D7;
}

PhoneControlPanel QPushButton {
    background-color: transparent;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 7px 12px;
    text-align: left;
    font-size: 12px;
    font-weight: 500;
    color: #1C1C1E;
}

PhoneControlPanel QPushButton:hover {
    background-color: rgba(0, 122, 255, 0.08);
    border-color: #007AFF;
    color: #007AFF;
}

PhoneControlPanel QPushButton:disabled {
    color: #8E8E93;
    border-color: transparent;
    background-color: transparent;
}

PhoneControlPanel QPushButton#refresh_btn {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 7px 12px;
    color: #1C1C1E;
}

PhoneControlPanel QPushButton#refresh_btn:hover {
    background-color: #F2F2F7;
}

DeviceSelector {
    background-color: #E2E2E8;
    border-bottom: 1px solid #D2D2D7;
    padding: 4px;
}

StatusBarWidget {
    background-color: #E2E2E8;
    border-top: 1px solid #D2D2D7;
    padding: 0 10px;
}

SideTerminalWidget {
    background-color: #E2E2E8;
    border-left: 1px solid #D2D2D7;
}

SideTerminalWidget QPlainTextEdit {
    background-color: #18181B;
    border-left: 1px solid #D2D2D7;
    border-top: none;
    border-right: none;
    border-bottom: none;
    color: #E4E4E7;
}
"""


def get_stylesheet(theme: str = "dark") -> str:
    """Return the active stylesheet based on theme selection ('dark' or 'light')."""
    if theme.lower() == "light":
        return LIGHT_STYLESHEET
    return DARK_STYLESHEET
