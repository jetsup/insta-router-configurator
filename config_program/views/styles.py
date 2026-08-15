from dataclasses import dataclass

current_theme: "Theme | None" = None


@dataclass
class Theme:
    name: str
    bg: str
    surface: str
    text_primary: str
    text_secondary: str
    text_muted: str
    border: str
    primary: str
    primary_hover: str
    primary_disabled: str
    primary_text: str
    success: str
    success_hover: str
    danger: str
    danger_hover: str
    secondary_bg: str
    secondary_text: str
    secondary_hover: str
    input_bg: str
    input_focus_bg: str
    tree_alt: str
    tree_selected_bg: str
    tree_selected_text: str
    tree_selected_hover: str
    tree_hover: str
    scroll_bg: str
    scroll_handle: str
    scroll_handle_hover: str
    header_section_bg: str
    header_section_text: str
    header_border: str
    sidebar_bg: str
    sidebar_border: str
    separator: str
    progress_bg: str
    progress_start: str
    progress_end: str
    ghost_hover_bg: str
    ghost_hover_color: str
    icon_btn_hover: str
    card_bg: str
    card_border: str
    log_bg: str
    log_border: str
    focus_ring: str

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


LIGHT = Theme(
    name="light",
    bg="#f1f5f9",
    surface="#ffffff",
    text_primary="#0f172a",
    text_secondary="#475569",
    text_muted="#94a3b8",
    border="#e2e8f0",
    primary="#1a56db",
    primary_hover="#1e40af",
    primary_disabled="#93c5fd",
    primary_text="#ffffff",
    success="#16a34a",
    success_hover="#15803d",
    danger="#dc2626",
    danger_hover="#b91c1c",
    secondary_bg="#f1f5f9",
    secondary_text="#475569",
    secondary_hover="#e2e8f0",
    input_bg="#f8fafc",
    input_focus_bg="#ffffff",
    tree_alt="#f8fafc",
    tree_selected_bg="#eff6ff",
    tree_selected_text="#1a56db",
    tree_selected_hover="#dbeafe",
    tree_hover="#f1f5f9",
    scroll_bg="#f1f5f9",
    scroll_handle="#cbd5e1",
    scroll_handle_hover="#94a3b8",
    header_section_bg="#f8fafc",
    header_section_text="#64748b",
    header_border="#e2e8f0",
    sidebar_bg="#f8fafc",
    sidebar_border="#e2e8f0",
    separator="#e2e8f0",
    progress_bg="#e2e8f0",
    progress_start="#1a56db",
    progress_end="#3b82f6",
    ghost_hover_bg="#f1f5f9",
    ghost_hover_color="#0f172a",
    icon_btn_hover="#f1f5f9",
    card_bg="#ffffff",
    card_border="#e2e8f0",
    log_bg="#f8fafc",
    log_border="#e2e8f0",
    focus_ring="#1a56db",
)

DARK = Theme(
    name="dark",
    bg="#0f172a",
    surface="#1e293b",
    text_primary="#f1f5f9",
    text_secondary="#94a3b8",
    text_muted="#64748b",
    border="#334155",
    primary="#3b82f6",
    primary_hover="#60a5fa",
    primary_disabled="#1e3a5f",
    primary_text="#ffffff",
    success="#22c55e",
    success_hover="#16a34a",
    danger="#ef4444",
    danger_hover="#dc2626",
    secondary_bg="#1e293b",
    secondary_text="#94a3b8",
    secondary_hover="#334155",
    input_bg="#1e293b",
    input_focus_bg="#1e293b",
    tree_alt="#1e293b",
    tree_selected_bg="#1e3a5f",
    tree_selected_text="#60a5fa",
    tree_selected_hover="#1e3a5f",
    tree_hover="#1e293b",
    scroll_bg="#1e293b",
    scroll_handle="#475569",
    scroll_handle_hover="#64748b",
    header_section_bg="#1e293b",
    header_section_text="#94a3b8",
    header_border="#334155",
    sidebar_bg="#1e293b",
    sidebar_border="#334155",
    separator="#334155",
    progress_bg="#334155",
    progress_start="#3b82f6",
    progress_end="#60a5fa",
    ghost_hover_bg="#334155",
    ghost_hover_color="#f1f5f9",
    icon_btn_hover="#334155",
    card_bg="#1e293b",
    card_border="#334155",
    log_bg="#1e293b",
    log_border="#334155",
    focus_ring="#3b82f6",
)


def build_qss(t: Theme) -> str:
    return f"""
QWidget {{
    font-family: -apple-system, 'Segoe UI', 'Noto Sans', system-ui, sans-serif;
    font-size: 13px;
    color: {t.text_primary};
}}

QMainWindow, QDialog {{
    background: {t.bg};
}}

QWidget#page {{
    background: {t.bg};
}}

QWidget#card {{
    background: {t.card_bg};
    border: 1px solid {t.card_border};
    border-radius: 10px;
    padding: 24px;
}}

QLabel#heading {{
    font-size: 20px;
    font-weight: 700;
    color: {t.text_primary};
}}

QLabel#subheading {{
    font-size: 13px;
    color: {t.text_secondary};
}}

QLabel#step-title {{
    font-size: 14px;
    font-weight: 600;
    color: {t.text_primary};
}}

QLabel#step-desc {{
    font-size: 12px;
    color: {t.text_muted};
}}

QLabel#status-ok {{
    color: {t.success};
    font-weight: 600;
}}

QLabel#status-fail {{
    color: {t.danger};
    font-weight: 600;
}}

QLineEdit {{
    padding: 10px 14px;
    border: 1.5px solid {t.border};
    border-radius: 8px;
    background: {t.input_bg};
    font-size: 13px;
    color: {t.text_primary};
}}

QLineEdit:focus {{
    border-color: {t.focus_ring};
    background: {t.input_focus_bg};
}}

QPushButton#primary {{
    background: {t.primary};
    color: {t.primary_text};
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background: {t.primary_hover};
}}

QPushButton#primary:disabled {{
    background: {t.primary_disabled};
}}

QPushButton#secondary {{
    background: {t.secondary_bg};
    color: {t.secondary_text};
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#secondary:hover {{
    background: {t.secondary_hover};
}}

QPushButton#success {{
    background: {t.success};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#success:hover {{
    background: {t.success_hover};
}}

QPushButton#danger {{
    background: {t.danger};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#danger:hover {{
    background: {t.danger_hover};
}}

QPushButton#ghost {{
    background: transparent;
    color: {t.text_secondary};
    border: none;
    padding: 8px 16px;
    font-size: 13px;
    border-radius: 6px;
}}

QPushButton#ghost:hover {{
    background: {t.ghost_hover_bg};
    color: {t.ghost_hover_color};
}}

QPushButton#icon-btn {{
    background: transparent;
    border: none;
    padding: 6px;
    border-radius: 6px;
    font-size: 16px;
    color: {t.text_secondary};
}}

QPushButton#icon-btn:hover {{
    background: {t.icon_btn_hover};
    color: {t.text_primary};
}}

QTreeWidget {{
    border: 1px solid {t.border};
    border-radius: 8px;
    background: {t.surface};
    alternate-background-color: {t.tree_alt};
    padding: 4px;
    outline: none;
    color: {t.text_primary};
}}

QTreeWidget::item {{
    padding: 8px 6px;
    border-radius: 4px;
}}

QTreeWidget::item:selected {{
    background: {t.tree_selected_bg};
    color: {t.tree_selected_text};
}}

QTreeWidget::item:hover {{
    background: {t.tree_hover};
}}

QTreeWidget::item:selected:hover {{
    background: {t.tree_selected_hover};
}}

QHeaderView::section {{
    background: {t.header_section_bg};
    color: {t.header_section_text};
    font-weight: 600;
    font-size: 12px;
    padding: 10px 6px;
    border: none;
    border-bottom: 1.5px solid {t.header_border};
    text-transform: uppercase;
}}

QScrollBar:vertical {{
    background: {t.scroll_bg};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {t.scroll_handle};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {t.scroll_handle_hover};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QSplitter::handle {{
    background: {t.separator};
    width: 1px;
}}

QFrame#separator {{
    background: {t.separator};
    max-height: 1px;
}}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background: {t.progress_bg};
    text-align: center;
    font-size: 11px;
    color: transparent;
    height: 8px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {t.progress_start}, stop:1 {t.progress_end});
    border-radius: 6px;
}}

QGroupBox {{
    border: 1px solid {t.border};
    border-radius: 8px;
    margin-top: 16px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    font-size: 13px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: {t.text_secondary};
}}

QLabel#card-title {{
    font-size: 15px;
    font-weight: 700;
    color: {t.text_primary};
}}

QLabel#card-value {{
    font-size: 13px;
    color: {t.text_secondary};
}}

QLabel#wifi-label {{
    font-size: 12px;
    color: {t.text_muted};
    font-style: italic;
}}

QTextEdit {{
    border: 1px solid {t.log_border};
    border-radius: 8px;
    background: {t.log_bg};
    padding: 12px;
    color: {t.text_primary};
}}

QTextEdit:focus {{
    border-color: {t.focus_ring};
}}

QWidget#sidebar {{
    background: {t.sidebar_bg};
    border-right: 1px solid {t.sidebar_border};
}}

QLabel#step-dot {{
    background: {t.secondary_bg};
    color: {t.text_muted};
    border-radius: 16px;
    font-size: 14px;
    font-weight: 600;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QLabel#step-dot-active {{
    background: {t.primary};
    color: {t.primary_text};
    border-radius: 16px;
    font-size: 14px;
    font-weight: 700;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QLabel#step-dot-done {{
    background: {t.success};
    color: white;
    border-radius: 16px;
    font-size: 14px;
    font-weight: 700;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
}}

QLabel#login-logo {{
    font-size: 24px;
    font-weight: 800;
    color: {t.primary};
    letter-spacing: -0.5px;
}}

QLabel#login-subtitle {{
    font-size: 13px;
    color: {t.text_secondary};
    margin-bottom: 8px;
}}

QFrame#login-separator {{
    background: {t.separator};
    max-height: 1px;
    margin: 16px 0;
}}

QLabel#field-label {{
    font-size: 12px;
    font-weight: 600;
    color: {t.text_secondary};
    margin-bottom: 2px;
}}

QWidget#sidebar {{
    background: {t.sidebar_bg};
    border-right: 1px solid {t.sidebar_border};
}}

QLabel#step-title {{
    font-size: 13px; font-weight: 700; color: {t.text_secondary};
}}

QLabel#step-title-active, QLabel#step-title-done {{
    font-size: 13px; font-weight: 700; color: {t.primary};
}}

QLabel#step-desc {{
    font-size: 11px; color: {t.text_muted};
}}

QLabel#step-desc-active, QLabel#step-desc-done {{
    font-size: 11px; color: {t.primary};
}}

QTextEdit#log-output {{
    border: 1px solid {t.border};
    border-radius: 8px;
    background: {t.log_bg};
    padding: 12px;
    font-family: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    color: {t.text_primary};
}}

QMenu {{
    border: 1px solid {t.border};
    border-radius: 8px;
    padding: 6px;
    background: {t.surface};
}}
QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 4px;
    font-size: 13px;
    color: {t.text_primary};
}}
QMenu::item:selected {{
    background: {t.tree_hover};
}}
QMenu::separator {{
    height: 1px;
    background: {t.separator};
    margin: 4px 8px;
}}

QPushButton#user-btn {{
    background: transparent;
    border: 1px solid {t.border};
    border-radius: 20px;
    padding: 4px 14px 4px 6px;
    font-size: 13px;
    font-weight: 600;
    color: {t.text_primary};
}}
QPushButton#user-btn:hover {{
    background: {t.icon_btn_hover};
}}
"""
