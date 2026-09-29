from __future__ import annotations
import html
import math
import re
import sys
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPainterPath, QPalette, QPen,
    QPixmap, QPolygonF, QShortcut
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QScrollArea, QScroller, QSizePolicy,
    QSplashScreen, QStackedWidget, QTextBrowser, QTextEdit, QToolButton, QVBoxLayout, QWidget
)

from bible_app import db

APP_NAME = "VerseLens"
APP_VERSION = "0.1.0"  # keep in sync with buildozer.spec
APP_SUBTITLE = "Scripture Study, Notes & Strong’s"
ORG_NAME = "Gregory Whitlock"

STRONG_RE = re.compile(r'\{(\(?[HG]\d+\)?)\}')

# Below this window width, side-by-side verses are stacked instead of put in two columns.
NARROW_WIDTH = 640
GRID_COLUMNS = 5

HIGHLIGHT_COLORS = [
    ("Yellow", "#fff59d"),
    ("Green", "#c5e1a5"),
    ("Blue", "#b3e5fc"),
    ("Pink", "#f8bbd0"),
    ("Orange", "#ffcc80"),
]

VIEW_MODES = [("chapter", "Chapter"), ("verse", "Single Verse"), ("range", "Verse Range")]

# Every colour is set explicitly: Android's own dark mode otherwise leaks into Qt's
# default palette and produces unreadable mixes (light text on light bars, etc.).
THEMES = {
    "dark": dict(
        window="#0e1420", base="#141c2b", alt="#1c2638", text="#e7eaf0", sub="#98a2b3",
        button="#172031", mid="#2a3549", accent="#6b9bff", sep="#232d40", on_accent="#ffffff",
    ),
    "light": dict(
        window="#f2f4f8", base="#ffffff", alt="#e9eef7", text="#1a2130", sub="#5f6b7d",
        button="#ffffff", mid="#d4dae4", accent="#2f6be0", sep="#e6eaf0", on_accent="#ffffff",
    ),
}

STYLE = Template("""
QWidget { color: $text; }
QMainWindow, QStackedWidget > QWidget { background: $window; }
QFrame#appbar { border-bottom: 1px solid $mid; }
QFrame#bottombar { background: $base; border-top: 1px solid $mid; }
QLabel { font-size: 12pt; }
QLabel#apptitle { font-size: 18pt; font-weight: 700; }
QLabel#appsub { font-size: 9pt; color: $sub; }
QLabel#fieldcaption { font-size: 10pt; color: $sub; }
QLabel#fieldvalue { font-size: 12pt; }
QLabel#pagetitle { font-size: 14pt; font-weight: 600; padding-left: 4px; }
QLabel#section { font-size: 11pt; font-weight: 600; padding-top: 10px; color: $accent; }
QToolButton#bar {
    min-height: 44px; min-width: 44px; padding: 0 6px;
    border: none; border-radius: 8px; font-size: 13pt; background: transparent;
}
QToolButton#bar:pressed { background: $alt; }
QToolButton#nav {
    border: none; border-radius: 10px; padding: 4px 0; background: transparent;
    font-size: 10pt; color: $accent;
}
QToolButton#nav:pressed, QToolButton#nav:checked { background: $alt; }
QPushButton {
    min-height: 44px; padding: 0 14px; font-size: 12pt;
    background: $button; color: $text; border: 1px solid $mid; border-radius: 10px;
}
QPushButton:pressed { background: $alt; }
QPushButton:checked, QPushButton#gridcell[current="true"] {
    background: $accent; color: $on_accent; border-color: $accent;
}
QPushButton#gridcell { min-width: 0; padding: 0; }
QPushButton#field { padding: 0; text-align: left; }
QPushButton#setting { text-align: left; }
QLineEdit {
    min-height: 44px; font-size: 12pt; padding: 0 8px;
    background: $button; border: 1px solid $mid; border-radius: 10px;
}
QTextEdit { font-size: 12pt; background: $base; border: 1px solid $mid; border-radius: 10px; }
QCheckBox { min-height: 44px; font-size: 12pt; spacing: 12px; }
QCheckBox::indicator { width: 24px; height: 24px; }
QListWidget { font-size: 13pt; border: none; background: $window; }
QListWidget::item { padding: 10px 12px; border-bottom: 1px solid $sep; }
QListWidget::item:selected { background: $alt; color: $text; }
QFrame#sheet {
    background: $base;
    border-top-left-radius: 16px; border-top-right-radius: 16px;
}
QLabel#sheettitle { font-size: 14pt; font-weight: 600; }
QTextBrowser { border: none; background: $window; }
QTextBrowser#card { background: $base; border: 1px solid $mid; border-radius: 14px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 4px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: $mid; border-radius: 2px; min-height: 40px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    height: 0; background: transparent;
}
""")

def resource_path(*parts: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / Path(*parts)

def app_icon() -> QIcon:
    p = resource_path("verselens_icon.png")
    return QIcon(str(p)) if p.exists() else QIcon()

def system_prefers_dark():
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is not None and hasattr(Qt, "ColorScheme"):
        return scheme() == Qt.ColorScheme.Dark
    return QGuiApplication.palette().color(QPalette.Window).lightness() < 128

def draw_icon(name, color, size=24, filled=False):
    """Line icons drawn on a 24-unit grid, so no icon font or SVG plugin is needed."""
    dpr = 3.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 24, size / 24)
    c = QColor(color)
    p.setPen(QPen(c, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    line = lambda *pts: p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in pts]))

    if name == "left":
        line((15, 5), (8, 12), (15, 19))
    elif name == "right":
        line((9, 5), (16, 12), (9, 19))
    elif name == "down":
        line((7, 10), (12, 15), (17, 10))
    elif name == "search":
        p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
        line((15.5, 15.5), (20.5, 20.5))
    elif name == "note":
        doc = QPainterPath()
        doc.moveTo(6, 3); doc.lineTo(14, 3); doc.lineTo(19, 8); doc.lineTo(19, 21)
        doc.lineTo(6, 21); doc.closeSubpath()
        if filled:
            fill = QColor(c)
            fill.setAlpha(90)
            p.setBrush(fill)
        p.drawPath(doc)
        p.setBrush(Qt.NoBrush)
        line((14, 3), (14, 8), (19, 8))
        for y, x2 in ((12, 16), (15, 16), (18, 13)):
            line((9, y), (x2, y))
    elif name == "star":
        pts = []
        for i in range(10):
            r = 9 if i % 2 == 0 else 3.9
            a = math.radians(-90 + i * 36)
            pts.append(QPointF(12 + r * math.cos(a), 12.6 + r * math.sin(a)))
        if filled:
            p.setBrush(c)
        p.drawPolygon(QPolygonF(pts))
    elif name == "compare":
        line((9, 7), (9, 3), (20, 3), (20, 17), (15, 17))
        p.drawRoundedRect(QRectF(4, 7, 11, 14), 1.5, 1.5)
        for y, x2 in ((11, 12), (14, 12), (17, 10)):
            line((7, y), (x2, y))
    elif name == "link":
        p.translate(12, 12)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-9.5, -3.6, 11, 7.2), 3.6, 3.6)
        p.drawRoundedRect(QRectF(-1.5, -3.6, 11, 7.2), 3.6, 3.6)
    elif name == "more":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for y in (5, 12, 19):
            p.drawEllipse(QPointF(12, y), 2, 2)
    p.end()
    return pm

def enable_touch_scroll(area):
    # Kinetic finger scrolling; mouse and wheel input behave as before.
    QScroller.grabGesture(area.viewport(), QScroller.TouchGesture)

def bar_button(text="", tip=""):
    b = QToolButton()
    b.setObjectName("bar")
    b.setText(text)
    b.setToolTip(tip or text)
    b.setFocusPolicy(Qt.NoFocus)
    b.setIconSize(QSize(24, 24))
    return b

class IconBrowser(QTextBrowser):
    """QTextBrowser that serves <img src='icon:theme/name'> from drawn icons."""

    def __init__(self, icon_image):
        super().__init__()
        self.icon_image = icon_image
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        enable_touch_scroll(self)

    def loadResource(self, rtype, url):
        if url.scheme() == "icon":
            return self.icon_image(url.path())
        return super().loadResource(rtype, url)

class FieldButton(QPushButton):
    """Tappable dropdown-style field: small caption over a value, chevron on the right."""

    def __init__(self, caption=None):
        super().__init__()
        self.setObjectName("field")
        self.setFocusPolicy(Qt.NoFocus)
        lay = QHBoxLayout(self)
        # Let the row's stretch factors decide the width instead of the labels' text.
        lay.setSizeConstraint(QLayout.SetNoConstraint)
        lay.setContentsMargins(10, 4, 6, 4)
        lay.setSpacing(2)
        col = QVBoxLayout()
        col.setSpacing(0)
        labels = []
        if caption:
            cap = QLabel(caption)
            cap.setObjectName("fieldcaption")
            col.addWidget(cap)
            labels.append(cap)
        self.value = QLabel()
        self.value.setObjectName("fieldvalue")
        self.value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        col.addWidget(self.value)
        lay.addLayout(col, 1)
        self.chevron = QLabel()
        lay.addWidget(self.chevron)
        for w in labels + [self.value, self.chevron]:
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumHeight(58 if caption else 44)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

    def set_value(self, text):
        self.value.setText(text)

    def sizeHint(self):
        return self.layout().sizeHint().expandedTo(self.minimumSize())

class Page(QWidget):
    """Full-screen page: an app bar (back button, title, extra buttons) over a body."""

    def __init__(self, title=""):
        super().__init__()
        self.bar = QFrame()
        self.bar.setObjectName("appbar")
        self.bar_layout = QHBoxLayout(self.bar)
        self.bar_layout.setContentsMargins(4, 4, 4, 4)
        self.bar_layout.setSpacing(2)

        self.back_button = bar_button(tip="Back")
        self.bar_layout.addWidget(self.back_button)

        self.title = QLabel(title)
        self.title.setObjectName("pagetitle")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.bar_layout.addWidget(self.title, 1)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(12, 8, 12, 8)
        self.body.setSpacing(8)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.bar)
        root.addLayout(self.body, 1)

    def add_bar_widget(self, w):
        self.bar_layout.addWidget(w)

class VerseSheet(QWidget):
    """Bottom sheet of verse actions drawn over the main window."""

    chosen = Signal(str, int, str)  # action, verse, argument

    def __init__(self, parent):
        super().__init__(parent)
        self.verse = 0
        self.hide()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        self.panel = QFrame()
        self.panel.setObjectName("sheet")
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(16, 14, 16, 16)
        pl.setSpacing(8)

        self.title = QLabel()
        self.title.setObjectName("sheettitle")
        self.title.setWordWrap(True)
        pl.addWidget(self.title)

        self.note_b = QPushButton()
        self.bookmark_b = QPushButton()
        self.copy_b = QPushButton("Copy verse")
        for b, action in ((self.note_b, "note"), (self.bookmark_b, "bookmark"), (self.copy_b, "copy")):
            b.clicked.connect(lambda _=False, a=action: self._choose(a))
            pl.addWidget(b)

        section = QLabel("Highlight")
        section.setObjectName("section")
        pl.addWidget(section)
        row = QHBoxLayout()
        row.setSpacing(8)
        for name, color in HIGHLIGHT_COLORS:
            s = QPushButton()
            s.setToolTip(name)
            s.setFixedSize(44, 44)
            s.setStyleSheet(
                f"QPushButton{{background:{color};border:1px solid #888;"
                f"border-radius:22px;min-height:0;padding:0;}}"
            )
            s.clicked.connect(lambda _=False, c=color: self._choose("highlight", c))
            row.addWidget(s)
        clear = QPushButton("None")
        clear.clicked.connect(lambda: self._choose("clear"))
        row.addWidget(clear, 1)
        pl.addLayout(row)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.hide)
        pl.addWidget(cancel)
        outer.addWidget(self.panel)

    def open(self, verse, reference, has_note, bookmarked):
        self.verse = verse
        self.title.setText(reference)
        self.note_b.setText("Edit note" if has_note else "Add note")
        self.bookmark_b.setText("Remove bookmark" if bookmarked else "Bookmark")
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()

    def _choose(self, action, arg=""):
        self.hide()
        self.chosen.emit(action, self.verse, arg)

    def mousePressEvent(self, e):
        if not self.panel.geometry().contains(e.position().toPoint()):
            self.hide()

    def paintEvent(self, e):
        QPainter(self).fillRect(self.rect(), QColor(0, 0, 0, 120))

class MainWindow(QMainWindow):
    READER, BOOKS, GRID, SEARCH, STRONG, SETTINGS, PICKER, NOTE, TEXT = range(9)

    def __init__(self):
        super().__init__()
        self.translations = db.get_translations()
        codes = {t["code"] for t in self.translations}

        self.code = db.get_setting("translation_code", "KJV")
        if self.code not in codes and self.translations:
            self.code = self.translations[0]["code"]

        self.compare_code = db.get_setting("compare_translation_code", "ASV")
        if self.compare_code not in codes or self.compare_code == self.code:
            self.compare_code = next((t["code"] for t in self.translations if t["code"] != self.code), self.code)

        self.side_by_side = db.get_setting("side_by_side", "0") == "1"
        self.book_number = 1
        self.chapter = 1
        self.book_rows = []        # [(book_number, name)] for the current translation
        self.chapter_numbers = []  # chapters of the current book
        self.verse_numbers = []    # verses of the current chapter
        self.verse_start = None
        self.verse_end = None
        self.rows = []
        self.font_size = int(db.get_setting("font_size", "14"))
        saved_dark = db.get_setting("dark", None)
        self.dark = system_prefers_dark() if saved_dark is None else saved_dark == "1"
        self.show_strongs = db.get_setting("show_strongs", "0") == "1"
        self.view_mode = db.get_setting("view_mode", "chapter")
        if self.view_mode not in dict(VIEW_MODES):
            self.view_mode = "chapter"

        self.history = []
        self.list_pick = None
        self.grid_pick = None
        self.note_target = None
        self.last_narrow = None
        self.icon_cache = {}

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(430, 880)

        self._build()
        self._connect()
        self._apply_theme()
        self._init_nav()

    # ----- theme and icons -----

    @property
    def theme_name(self):
        return "dark" if self.dark else "light"

    @property
    def theme(self):
        return THEMES[self.theme_name]

    def _pixmap(self, name, color=None, filled=False, size=24):
        key = (name, color or self.theme["accent"], filled, size)
        if key not in self.icon_cache:
            self.icon_cache[key] = draw_icon(name, key[1], size, filled)
        return self.icon_cache[key]

    def _icon(self, name, color=None):
        return QIcon(self._pixmap(name, color))

    def _html_icon(self, path):
        # path is "<theme>/<name>" or "<theme>/<name>_on"
        _, _, name = path.partition("/")
        filled = name.endswith("_on")
        base = name[:-3] if filled else name
        color = self.theme["accent"] if filled else self.theme["sub"]
        return self._pixmap(base, color, filled).toImage()

    def _apply_theme(self):
        t = self.theme
        p = QPalette()
        for role, key in (
            (QPalette.Window, "window"), (QPalette.WindowText, "text"), (QPalette.Base, "base"),
            (QPalette.AlternateBase, "alt"), (QPalette.Text, "text"), (QPalette.Button, "button"),
            (QPalette.ButtonText, "text"), (QPalette.Highlight, "accent"),
            (QPalette.HighlightedText, "on_accent"), (QPalette.Mid, "mid"),
            (QPalette.Midlight, "alt"), (QPalette.Dark, "sub"), (QPalette.Shadow, "mid"), (QPalette.Link, "accent"), (QPalette.LinkVisited, "accent"),
            (QPalette.PlaceholderText, "sub"), (QPalette.ToolTipBase, "base"),
            (QPalette.ToolTipText, "text"),
        ):
            p.setColor(role, QColor(t[key]))
        for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
            p.setColor(QPalette.Disabled, role, QColor(t["sub"]))
        app = QApplication.instance()
        app.setPalette(p)
        app.setStyleSheet(STYLE.substitute(t))

        for page in (self.stack.widget(i) for i in range(self.stack.count())):
            if isinstance(page, Page):
                page.back_button.setIcon(self._icon("left", t["text"]))
        self.menu_button.setIcon(self._icon("more", t["text"]))
        self.search_icon_action.setIcon(self._icon("search", t["sub"]))
        for f in (self.tr_field, self.book_field, self.chapter_field, self.view_field, self.verse_field):
            f.chevron.setPixmap(self._pixmap("down", t["sub"], size=16))
        for b, name in self.nav_icons:
            b.setIcon(self._icon(name))
        self._apply_font()

    # ----- layout -----

    def _build(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        for build in (
            self._build_reader, self._build_books, self._build_grid, self._build_search,
            self._build_strong, self._build_settings, self._build_picker, self._build_note,
            self._build_text,
        ):
            self.stack.addWidget(build())
        self.sheet = VerseSheet(self)

    def _build_reader(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QVBoxLayout()
        top.setContentsMargins(12, 10, 8, 8)
        top.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)
        logo = QLabel()
        pix = QPixmap(str(resource_path("verselens_icon.png")))
        if not pix.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            pix = pix.scaled(int(46 * dpr), int(46 * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pix.setDevicePixelRatio(dpr)
            logo.setPixmap(pix)
        header.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("apptitle")
        title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub = QLabel(APP_SUBTITLE)
        sub.setObjectName("appsub")
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        titles.addWidget(title)
        titles.addWidget(sub)
        header.addLayout(titles, 1)
        self.tr_field = FieldButton()
        self.tr_field.setToolTip("Choose translation")
        self.tr_field.setFixedWidth(84)
        self.tr_field.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header.addWidget(self.tr_field)
        self.menu_button = bar_button(tip="Settings")
        self.menu_button.setStyleSheet("QToolButton{min-width:36px;padding:0;}")
        header.addWidget(self.menu_button)
        top.addLayout(header)

        fields = QHBoxLayout()
        fields.setSpacing(8)
        self.book_field = FieldButton("Book")
        self.chapter_field = FieldButton("Chapter")
        self.view_field = FieldButton("View")
        self.verse_field = FieldButton("Verse")
        for f, stretch in ((self.book_field, 3), (self.chapter_field, 2), (self.view_field, 3), (self.verse_field, 2)):
            fields.addWidget(f, stretch)
        top.addLayout(fields)

        self.quick_search = QLineEdit()
        self.quick_search.setPlaceholderText("Search current translation…")
        self.quick_search.setClearButtonEnabled(True)
        self.search_icon_action = self.quick_search.addAction(QIcon(), QLineEdit.LeadingPosition)
        top.addWidget(self.quick_search)
        root.addLayout(top)

        card_wrap = QVBoxLayout()
        card_wrap.setContentsMargins(12, 0, 12, 10)
        self.reader = IconBrowser(self._html_icon)
        self.reader.setObjectName("card")
        self.reader.document().setDocumentMargin(14)
        self.reader.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        card_wrap.addWidget(self.reader)
        root.addLayout(card_wrap, 1)

        bottom = QFrame()
        bottom.setObjectName("bottombar")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(6, 4, 6, 4)
        bl.setSpacing(2)
        self.prev_b = QToolButton()
        self.search_b = QToolButton()
        self.side_b = QToolButton()
        self.strong_b = QToolButton()
        self.next_b = QToolButton()
        self.nav_icons = [
            (self.prev_b, "left"), (self.search_b, "search"), (self.side_b, "compare"),
            (self.strong_b, "link"), (self.next_b, "right"),
        ]
        for b, text in zip((b for b, _ in self.nav_icons), ("Previous", "Search", "Compare", "Strong's", "Next")):
            b.setObjectName("nav")
            b.setText(text)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIconSize(QSize(26, 26))
            b.setFocusPolicy(Qt.NoFocus)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            b.setMinimumHeight(60)
            bl.addWidget(b)
        self.side_b.setCheckable(True)
        self.strong_b.setCheckable(True)
        root.addWidget(bottom)
        return page

    def _build_books(self):
        page = Page("Book")
        page.body.setContentsMargins(0, 0, 0, 0)
        self.books = QListWidget()
        self.books.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        enable_touch_scroll(self.books)
        page.body.addWidget(self.books, 1)
        return page

    def _build_grid(self):
        page = Page()
        self.grid_page = page
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFrameShape(QFrame.NoFrame)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        enable_touch_scroll(self.grid_scroll)
        page.body.addWidget(self.grid_scroll, 1)
        return page

    def _build_search(self):
        page = Page("Search")
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search current translation…")
        self.search.setClearButtonEnabled(True)
        self.search_go = QPushButton("Go")
        row.addWidget(self.search, 1)
        row.addWidget(self.search_go)
        page.body.addLayout(row)
        self.search_results = IconBrowser(self._html_icon)
        page.body.addWidget(self.search_results, 1)
        return page

    def _build_strong(self):
        page = Page("Strong's Study")
        self.strong_page = page
        page.body.setContentsMargins(0, 0, 0, 0)
        self.strong_detail = IconBrowser(self._html_icon)
        self.strong_detail.document().setDocumentMargin(12)
        page.body.addWidget(self.strong_detail, 1)
        return page

    def _build_settings(self):
        page = Page("Settings")
        page.body.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        enable_touch_scroll(scroll)
        inner = QWidget()
        l = QVBoxLayout(inner)
        l.setContentsMargins(16, 8, 16, 16)
        l.setSpacing(8)

        def section(text):
            s = QLabel(text)
            s.setObjectName("section")
            l.addWidget(s)

        def setting_button(text=""):
            b = QPushButton(text)
            b.setObjectName("setting")
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            l.addWidget(b)
            return b

        section("Translation")
        self.tr_setting_b = setting_button()
        self.info_b = setting_button("Translation info")

        section("Compare")
        self.side_box = QCheckBox("Show side by side")
        l.addWidget(self.side_box)
        self.cmp_setting_b = setting_button()

        section("Study")
        self.strong_box = QCheckBox("Show Strong's numbers")
        l.addWidget(self.strong_box)

        section("Display")
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Text size"), 1)
        self.a_minus = QPushButton("A−")
        self.size_label = QLabel()
        self.size_label.setAlignment(Qt.AlignCenter)
        self.size_label.setMinimumWidth(56)
        self.a_plus = QPushButton("A+")
        size_row.addWidget(self.a_minus)
        size_row.addWidget(self.size_label)
        size_row.addWidget(self.a_plus)
        l.addLayout(size_row)
        self.dark_box = QCheckBox("Dark theme")
        l.addWidget(self.dark_box)

        section(APP_NAME)
        self.about_b = setting_button(f"About {APP_NAME}")
        l.addStretch(1)

        scroll.setWidget(inner)
        page.body.addWidget(scroll, 1)
        return page

    def _build_picker(self):
        page = Page()
        self.picker_page = page
        page.body.setContentsMargins(0, 0, 0, 0)
        self.picker = QListWidget()
        self.picker.setWordWrap(True)
        self.picker.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        enable_touch_scroll(self.picker)
        page.body.addWidget(self.picker, 1)
        return page

    def _build_note(self):
        page = Page("Note")
        self.note_save = bar_button("Save")
        page.add_bar_widget(self.note_save)
        self.note_ref = QLabel()
        self.note_ref.setWordWrap(True)
        page.body.addWidget(self.note_ref)
        self.note_global = QCheckBox("Show this note in all translations")
        page.body.addWidget(self.note_global)
        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Write your note here…")
        page.body.addWidget(self.note_editor, 1)
        return page

    def _build_text(self):
        page = Page()
        self.text_page = page
        page.body.setContentsMargins(0, 0, 0, 0)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        self.text_browser.document().setDocumentMargin(12)
        enable_touch_scroll(self.text_browser)
        page.body.addWidget(self.text_browser, 1)
        return page

    def _connect(self):
        for i in range(self.stack.count()):
            p = self.stack.widget(i)
            if isinstance(p, Page):
                p.back_button.clicked.connect(self.go_back)
        QShortcut(QKeySequence(Qt.Key_Back), self, self.go_back)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.go_back)

        self.tr_field.clicked.connect(lambda: self.open_translation_picker("primary"))
        self.menu_button.clicked.connect(lambda: self.show_page(self.SETTINGS))
        self.book_field.clicked.connect(lambda: self.show_page(self.BOOKS))
        self.chapter_field.clicked.connect(lambda: self.open_chapter_grid(self.book_number))
        self.view_field.clicked.connect(self.open_view_picker)
        self.verse_field.clicked.connect(self.open_verse_grid)
        self.quick_search.returnPressed.connect(self._quick_search)
        self.search_icon_action.triggered.connect(self._quick_search)

        self.prev_b.clicked.connect(self.previous)
        self.next_b.clicked.connect(self.next_chapter)
        self.search_b.clicked.connect(self.open_search)
        self.side_b.toggled.connect(self._toggle_side_by_side)
        self.strong_b.toggled.connect(self._toggle_strongs)
        self.reader.anchorClicked.connect(self._link)
        self.sheet.chosen.connect(self._verse_action)

        self.books.itemClicked.connect(self._book_clicked)
        self.picker.itemClicked.connect(self._picker_clicked)

        self.search.returnPressed.connect(self.search_text)
        self.search_go.clicked.connect(self.search_text)
        self.search_results.anchorClicked.connect(self._search_link)
        self.strong_detail.anchorClicked.connect(self._strong_result_link)

        self.tr_setting_b.clicked.connect(lambda: self.open_translation_picker("primary"))
        self.cmp_setting_b.clicked.connect(lambda: self.open_translation_picker("compare"))
        self.info_b.clicked.connect(self.translation_info)
        self.about_b.clicked.connect(self.show_about)
        self.side_box.toggled.connect(self._toggle_side_by_side)
        self.strong_box.toggled.connect(self._toggle_strongs)
        self.a_minus.clicked.connect(lambda: self._font(-1))
        self.a_plus.clicked.connect(lambda: self._font(1))
        self.dark_box.toggled.connect(self._toggle_theme)
        self.note_save.clicked.connect(self._save_note)

    # ----- page navigation -----

    def show_page(self, index, reset=False):
        if reset:
            self.history.clear()
        elif self.stack.currentIndex() != index:
            self.history.append(self.stack.currentIndex())
        self.stack.setCurrentIndex(index)

    def go_back(self):
        if self.sheet.isVisible():
            self.sheet.hide()
        elif self.history:
            self.stack.setCurrentIndex(self.history.pop())
        elif self.stack.currentIndex() != self.READER:
            self.stack.setCurrentIndex(self.READER)
        else:
            self.close()

    def showEvent(self, e):
        super().showEvent(e)
        win = self.windowHandle()
        if win and not getattr(self, "_safe_area_hooked", False):
            # Android 15+ draws apps edge-to-edge; keep content clear of the system bars.
            win.safeAreaMarginsChanged.connect(self._apply_safe_area)
            self._safe_area_hooked = True
        self._apply_safe_area()

    def _apply_safe_area(self, *_):
        win = self.windowHandle()
        if win:
            m = win.safeAreaMargins()
            self.centralWidget().setContentsMargins(m.left(), m.top(), m.right(), m.bottom())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.sheet.isVisible():
            self.sheet.setGeometry(self.rect())
        narrow = self._narrow()
        if self.last_narrow is not None and narrow != self.last_narrow and self.side_by_side:
            self.show_chapter(keep_scroll=True)
        self.last_narrow = narrow

    def _narrow(self):
        return self.width() < NARROW_WIDTH

    # ----- list and grid pickers -----

    def open_list(self, title, items, current, on_pick):
        """Full-screen single-choice list; items are (label, data) pairs."""
        self.picker_page.title.setText(title)
        self.list_pick = on_pick
        self.picker.clear()
        for label, data in items:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, data)
            self.picker.addItem(it)
            if data == current:
                self.picker.setCurrentItem(it)
        self.show_page(self.PICKER)
        if self.picker.currentItem():
            self.picker.scrollToItem(self.picker.currentItem())

    def _picker_clicked(self, item):
        pick, self.list_pick = self.list_pick, None
        self.go_back()
        if pick:
            pick(item.data(Qt.UserRole))

    def open_grid(self, title, numbers, current, on_pick):
        """Full-screen grid of number buttons (chapters or verses)."""
        self.grid_page.title.setText(title)
        self.grid_pick = on_pick
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setSpacing(6)
        for i, n in enumerate(numbers):
            b = QPushButton(str(n))
            b.setObjectName("gridcell")
            b.setProperty("current", n == current)
            b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            b.setMinimumHeight(48)
            b.clicked.connect(lambda _=False, v=n: self.grid_pick and self.grid_pick(v))
            grid.addWidget(b, i // GRID_COLUMNS, i % GRID_COLUMNS)
        grid.setRowStretch(grid.rowCount(), 1)
        self.grid_scroll.setWidget(host)
        self.show_page(self.GRID)

    def open_chapter_grid(self, book):
        chapters = [int(c) for c in db.get_chapters(self.code, book)]
        current = self.chapter if book == self.book_number else None

        def pick(ch):
            self._go(book, ch)
            self.show_page(self.READER, reset=True)

        self.open_grid(f"{self._book_name(book)} · Chapter", chapters, current, pick)

    def open_view_picker(self):
        self.open_list("View", [(label, mode) for mode, label in VIEW_MODES], self.view_mode, self._set_view_mode)

    def open_verse_grid(self):
        ref = f"{self._book_name()} {self.chapter}"
        if self.view_mode == "range":
            def pick_start(v):
                self.verse_start = v
                later = [n for n in self.verse_numbers if n >= v]
                self.open_grid(f"{ref}:{v} · End verse", later, self.verse_end, pick_end)

            def pick_end(v):
                self.verse_end = v
                self.show_chapter()
                self.show_page(self.READER, reset=True)

            self.open_grid(f"{ref} · Start verse", self.verse_numbers, self.verse_start, pick_start)
        else:
            def pick(v):
                self.verse_start = self.verse_end = v
                self.show_chapter()
                self.show_page(self.READER, reset=True)

            self.open_grid(f"{ref} · Verse", self.verse_numbers, self.verse_start, pick)

    # ----- books / chapters / verses -----

    def _init_nav(self):
        self._reload_books(1)
        self._reload_chapters(1)
        self._sync_controls()
        self.show_chapter()

    def _reload_books(self, want=1):
        self.book_rows = [(int(b["book_number"]), b["name"]) for b in db.get_books(self.code)]
        numbers = [n for n, _ in self.book_rows]
        if want in numbers:
            self.book_number = want
        elif numbers:
            self.book_number = numbers[0]

        self.books.clear()
        headers = {1: "Old Testament", 40: "New Testament"}
        for n, name in self.book_rows:
            if n in headers:
                h = QListWidgetItem(headers[n])
                h.setFlags(Qt.NoItemFlags)
                f = h.font()
                f.setBold(True)
                h.setFont(f)
                h.setForeground(QColor(self.theme["accent"]))
                self.books.addItem(h)
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, n)
            self.books.addItem(it)

    def _reload_chapters(self, want=1):
        self.chapter_numbers = [int(x) for x in db.get_chapters(self.code, self.book_number)]
        if want in self.chapter_numbers:
            self.chapter = want
        elif self.chapter_numbers:
            self.chapter = self.chapter_numbers[0]
        self._reload_verses()

    def _reload_verses(self):
        rows = db.get_chapter(self.code, self.book_number, self.chapter)
        self.verse_numbers = [int(r["verse"]) for r in rows]
        if not self.verse_numbers:
            self.verse_start = self.verse_end = None
            return
        if self.verse_start not in self.verse_numbers:
            self.verse_start = self.verse_numbers[0]
        if self.verse_end not in self.verse_numbers:
            self.verse_end = self.verse_numbers[-1]
        if self.verse_end < self.verse_start:
            self.verse_end = self.verse_start

    def _book_name(self, number=None):
        number = self.book_number if number is None else number
        return next((name for n, name in self.book_rows if n == number), "")

    def _book_clicked(self, item):
        number = item.data(Qt.UserRole)
        if number is not None:
            self.open_chapter_grid(int(number))

    def _go(self, book, chapter):
        self.book_number = book
        self._reload_chapters(chapter)
        self.show_chapter()

    def _set_view_mode(self, mode):
        if mode == self.view_mode:
            return
        self.view_mode = mode
        db.set_setting("view_mode", self.view_mode)
        if mode == "verse":
            self.verse_end = self.verse_start
        elif mode == "range" and self.verse_end == self.verse_start and self.verse_numbers:
            self.verse_end = self.verse_numbers[-1]
        self.show_chapter()

    def _selected_verse_bounds(self):
        if self.view_mode == "chapter" or self.verse_start is None:
            return None, None
        start = int(self.verse_start)
        if self.view_mode == "verse":
            return start, start
        end = int(self.verse_end) if self.verse_end is not None else start
        return start, max(start, end)

    def _filter_rows_for_view(self, rows):
        start, end = self._selected_verse_bounds()
        if start is None:
            return rows
        return [r for r in rows if start <= int(r["verse"]) <= end]

    def _reference_heading(self, book_name):
        start, end = self._selected_verse_bounds()
        if start is None:
            return f"{book_name} {self.chapter}"
        if start == end:
            return f"{book_name} {self.chapter}:{start}"
        return f"{book_name} {self.chapter}:{start}-{end}"

    def _update_fields(self):
        self.tr_field.set_value(self.code)
        self.book_field.set_value(self._book_name())
        self.chapter_field.set_value(str(self.chapter))
        self.view_field.set_value(dict(VIEW_MODES)[self.view_mode])
        self.verse_field.setVisible(self.view_mode != "chapter")
        start, end = self._selected_verse_bounds()
        if start is None:
            self.verse_field.set_value("")
        else:
            self.verse_field.set_value(str(start) if start == end else f"{start}–{end}")
        self.quick_search.setPlaceholderText(f"Search {self.code}…")

    def previous(self):
        i = self.chapter_numbers.index(self.chapter) if self.chapter in self.chapter_numbers else 0
        if i > 0:
            self._go(self.book_number, self.chapter_numbers[i - 1])
            return
        numbers = [n for n, _ in self.book_rows]
        bi = numbers.index(self.book_number) if self.book_number in numbers else 0
        if bi <= 0:
            return
        ch = db.get_chapters(self.code, numbers[bi - 1])
        if ch:
            self._go(numbers[bi - 1], int(ch[-1]))

    def next_chapter(self):
        i = self.chapter_numbers.index(self.chapter) if self.chapter in self.chapter_numbers else 0
        if i < len(self.chapter_numbers) - 1:
            self._go(self.book_number, self.chapter_numbers[i + 1])
            return
        numbers = [n for n, _ in self.book_rows]
        bi = numbers.index(self.book_number) if self.book_number in numbers else 0
        if bi >= len(numbers) - 1:
            return
        self._go(numbers[bi + 1], 1)

    def _jump(self, b, c, v):
        """Open a verse from search or Strong's results and scroll to it."""
        self.book_number = b
        self._reload_chapters(c)
        if self.view_mode != "chapter":
            self.verse_start = self.verse_end = v
        self.show_chapter(verse=v)
        self.show_page(self.READER, reset=True)

    # ----- rendering -----

    def _strong_html(self, raw):
        out = []
        pos = 0
        for m in STRONG_RE.finditer(raw):
            out.append(html.escape(raw[pos:m.start()]))
            code = m.group(1)
            clean = code.strip('()')
            kind = "morph" if code.startswith("(") else "strong"
            if self.show_strongs:
                out.append(
                    f'<sup><a href="{kind}:{clean}" '
                    f'style="text-decoration:underline;font-weight:600;" '
                    f'title="Open {html.escape(clean)} in Strong\'s Study">'
                    f'{html.escape(clean)}</a></sup>'
                )
            pos = m.end()
        out.append(html.escape(raw[pos:]))
        return "".join(out)

    def _verse_text(self, r):
        return self._strong_html(r["text_raw"]) if r["edition_type"] == "strongs" else html.escape(r["text_clean"])

    def _heading_html(self, heading, subtitle):
        t = self.theme
        return (
            f"<p style='font-size:xx-large;font-weight:700;margin:0;'>{html.escape(heading)}</p>"
            f"<p style='font-style:italic;color:{t['sub']};margin-top:4px;margin-bottom:10px;'>"
            f"{subtitle}</p>"
        )

    def _verse_row(self, v, body, has_note=False, bookmarked=False, bg=None):
        """One verse as table rows: number | text | note, bookmark and more icons."""
        t = self.theme
        theme = self.theme_name

        def icon(action, name, on):
            src = f"icon:{theme}/{name}{'_on' if on else ''}"
            return f"<a href='{action}:{v}'><img src='{src}' width='22' height='22'></a>"

        icons = "&nbsp;&nbsp;&nbsp;".join((
            icon("note", "note", has_note),
            icon("bookmark", "star", bookmarked),
            icon("more", "link", False),
        ))
        row_bg = f" bgcolor='{bg}'" if bg else ""
        # Highlight colours are light, so force dark text for the dark theme.
        text_color = "color:#111;" if bg else ""
        return (
            f"<tr{row_bg}>"
            f"<td width='34' valign='top' style='padding:10px 2px 10px 0;'>"
            f"<a name='v{v}'></a><a href='verse:{v}' style='color:{t['accent']};"
            f"text-decoration:none;font-size:x-large;font-weight:700;'>{v}</a></td>"
            f"<td valign='top' style='padding:12px 6px 12px 4px;{text_color}'>{body}</td>"
            f"<td width='92' valign='top' align='right' style='padding:12px 0 12px 4px;white-space:nowrap;'>{icons}</td>"
            "</tr>"
            f"<tr><td colspan='3' bgcolor='{t['sep']}' style='font-size:1px;'></td></tr>"
        )

    def show_chapter(self, keep_scroll=False, verse=None):
        bar = self.reader.verticalScrollBar()
        pos = bar.value()
        if self.side_by_side:
            self._show_parallel()
        else:
            self._show_single()
        self._apply_font()
        self._update_fields()
        if keep_scroll:
            QTimer.singleShot(0, lambda: bar.setValue(pos))
        elif verse is not None:
            QTimer.singleShot(0, lambda: self.reader.scrollToAnchor(f"v{verse}"))

    def _show_single(self):
        chapter_rows = db.get_chapter(self.code, self.book_number, self.chapter)
        if not chapter_rows:
            self.reader.setHtml("<p>No verses found.</p>")
            self.rows = []
            return

        self.rows = self._filter_rows_for_view(chapter_rows)
        if not self.rows:
            self.reader.setHtml("<p>No verses found for the selected reference.</p>")
            return

        notes, hi, bm = db.get_annotations_for_rows(self.rows, self.code)
        tr = db.get_translation(self.code)
        parts = [
            self._heading_html(
                self._reference_heading(self.rows[0]["book"]),
                f"{html.escape(tr['name'])} ({html.escape(self.code)})",
            ),
            "<table width='100%' cellspacing='0' cellpadding='0'>",
        ]
        for r in self.rows:
            v = int(r["verse"])
            key = (int(r["book_number"]), int(r["chapter"]), v)
            parts.append(self._verse_row(v, self._verse_text(r), key in notes, key in bm, hi.get(key)))
        parts.append("</table>")
        self.reader.setHtml("".join(parts))

    def _show_parallel(self):
        rows = db.get_parallel_chapter(self.code, self.compare_code, self.book_number, self.chapter)
        start, end = self._selected_verse_bounds()
        if start is not None:
            rows = [row for row in rows if start <= int(row[0]) <= end]

        tr1 = db.get_translation(self.code)
        tr2 = db.get_translation(self.compare_code)
        self.rows = self._filter_rows_for_view(db.get_chapter(self.code, self.book_number, self.chapter))
        notes, hi, bm = db.get_annotations_for_rows(self.rows, self.code) if self.rows else ({}, {}, {})
        heading = self._reference_heading(self._book_name())
        missing = "<i>— verse not present in this edition —</i>"
        sub = self.theme["sub"]
        tag = f"<span style='color:{sub};font-size:small;font-weight:600;'>{{}}</span>&nbsp; "

        parts = [
            self._heading_html(
                heading,
                f"{html.escape(tr1['name'])} ({html.escape(self.code)})<br>"
                f"{html.escape(tr2['name'])} ({html.escape(self.compare_code)})",
            ),
            "<table width='100%' cellspacing='0' cellpadding='0'>",
        ]
        narrow = self._narrow()
        for verse_num, left, right in rows:
            v = int(verse_num)
            ltxt = self._verse_text(left) if left else missing
            rtxt = self._verse_text(right) if right else missing
            if narrow:
                # Phone width: both translations stacked in the text column.
                body = (
                    f"{tag.format(html.escape(self.code))}{ltxt}"
                    f"<br><br>{tag.format(html.escape(self.compare_code))}{rtxt}"
                )
            else:
                body = (
                    "<table width='100%' cellspacing='0' cellpadding='0'><tr>"
                    f"<td width='50%' valign='top' style='padding-right:10px;'>{ltxt}</td>"
                    f"<td width='50%' valign='top' style='padding-left:10px;'>{rtxt}</td>"
                    "</tr></table>"
                )
            key = (self.book_number, self.chapter, v)
            parts.append(self._verse_row(v, body, key in notes, key in bm, hi.get(key)))
        parts.append("</table>")
        self.reader.setHtml("".join(parts))

    # ----- verse actions -----

    def _row(self, v):
        return next((r for r in self.rows if int(r["verse"]) == v), None)

    def _link(self, url):
        value = url.toString()
        if ":" not in value:
            return
        action, arg = value.split(":", 1)

        if action in ("strong", "morph"):
            self.show_strong_study(arg, action)
            return

        try:
            v = int(arg)
        except ValueError:
            return
        r = self._row(v)
        if not r:
            return

        if action == "note":
            self._open_note(r)
        elif action == "bookmark":
            self._verse_action("bookmark", v, "")
        elif action in ("verse", "more"):
            notes, _, bm = db.get_annotations_for_rows([r], self.code)
            key = (int(r["book_number"]), int(r["chapter"]), v)
            self.sheet.open(v, f"{r['book']} {r['chapter']}:{v} ({self.code})", key in notes, key in bm)

    def _verse_action(self, action, v, arg):
        r = self._row(v)
        if not r:
            return
        b, c = int(r["book_number"]), int(r["chapter"])

        if action == "note":
            self._open_note(r)
            return
        if action == "bookmark":
            db.toggle_bookmark(b, c, v, None)
        elif action == "highlight":
            db.set_highlight(b, c, v, arg, None)
        elif action == "clear":
            db.set_highlight(b, c, v, None, None)
            db.set_highlight(b, c, v, None, self.code)
        elif action == "copy":
            QGuiApplication.clipboard().setText(f"{r['book']} {c}:{v} ({self.code}) {r['text_clean']}")
            return
        self.show_chapter(keep_scroll=True)

    def _open_note(self, r):
        b, c, v = int(r["book_number"]), int(r["chapter"]), int(r["verse"])
        global_n = db.get_note(b, c, v, None)
        local_n = db.get_note(b, c, v, self.code)
        self.note_target = (b, c, v)
        self.note_ref.setText(f"<b>{html.escape(r['book'])} {c}:{v}</b> ({html.escape(self.code)})")
        self.note_global.setChecked(not bool(local_n))
        self.note_editor.setPlainText(local_n or global_n or "")
        self.show_page(self.NOTE)
        self.note_editor.setFocus()

    def _save_note(self):
        if not self.note_target:
            return
        b, c, v = self.note_target
        scope = None if self.note_global.isChecked() else self.code
        other = self.code if scope is None else None
        db.save_note(b, c, v, "", other)
        db.save_note(b, c, v, self.note_editor.toPlainText(), scope)
        self.note_target = None
        self.go_back()
        self.show_chapter(keep_scroll=True)

    # ----- Strong's -----

    def show_strong_study(self, strong_number, kind="strong"):
        entry = db.get_strong_entry(strong_number)
        occ = db.get_strong_occurrences(strong_number, limit=250)

        self.strong_page.title.setText(f"Strong's {strong_number}")

        parts = []
        if entry:
            parts.append(f"<h2>{html.escape(entry['strong_number'])}</h2>")
            if entry["lemma"]:
                parts.append(f"<p><b>Lemma:</b> {html.escape(entry['lemma'])}</p>")
            if entry["transliteration"]:
                parts.append(f"<p><b>Transliteration:</b> {html.escape(entry['transliteration'])}</p>")
            if entry["pronunciation"]:
                parts.append(f"<p><b>Pronunciation:</b> {html.escape(entry['pronunciation'])}</p>")
            if entry["definition"]:
                parts.append(f"<p><b>Definition:</b><br>{html.escape(entry['definition'])}</p>")
            if entry["source"]:
                parts.append(f"<p><small>Source: {html.escape(entry['source'])}</small></p>")
        else:
            parts.append("<p><i>No lexicon definition has been imported yet.</i></p>")

        parts.append(f"<h3>Occurrences ({len(occ)} shown)</h3>")
        for r in occ:
            ref = f"{r['book']} {r['chapter']}:{r['verse']}"
            parts.append(
                f"<p><a href='goto:{r['book_number']}:{r['chapter']}:{r['verse']}'>"
                f"{html.escape(r['translation_code'])} — {html.escape(ref)}</a><br>"
                f"{html.escape(r['text_clean'])}</p>"
            )
        self.strong_detail.setHtml("".join(parts))
        self.show_page(self.STRONG)

    def _strong_result_link(self, url):
        value = url.toString()
        if not value.startswith("goto:"):
            return
        _, b, c, v = value.split(":")

        tr = db.get_translation(self.code)
        if tr and tr["edition_type"] != "strongs":
            strong_codes = [r["code"] for r in self.translations if r["edition_type"] == "strongs"]
            if strong_codes:
                self.code = strong_codes[0]
                db.set_setting("translation_code", self.code)
                self._reload_books(int(b))
                self._sync_controls()

        self._jump(int(b), int(c), int(v))

    # ----- search -----

    def _quick_search(self):
        q = self.quick_search.text().strip()
        if not q:
            return
        self.search.setText(q)
        self.search.setPlaceholderText(f"Search {self.code}…")
        self.search_text()
        self.show_page(self.SEARCH)

    def open_search(self):
        self.search.setPlaceholderText(f"Search {self.code}…")
        self.show_page(self.SEARCH)
        self.search.setFocus()
        self.search.selectAll()

    def search_text(self):
        q = self.search.text().strip()
        if not q:
            self.search_results.clear()
            return
        rows = db.search_verses(self.code, q)
        parts = [f"<p>{len(rows)} result(s) in {html.escape(self.code)}</p>"]
        for r in rows:
            parts.append(
                f"<p><a href='goto:{r['book_number']}:{r['chapter']}:{r['verse']}'>"
                f"<b>{html.escape(r['book'])} {r['chapter']}:{r['verse']}</b></a><br>"
                f"{html.escape(r['text_clean'])}</p>"
            )
        self.search_results.setHtml("".join(parts))
        self.search_results.setFocus()

    def _search_link(self, url):
        value = url.toString()
        if value.startswith("goto:"):
            _, b, c, v = value.split(":")
            self._jump(int(b), int(c), int(v))

    # ----- translations -----

    @staticmethod
    def _translation_label(t):
        suffix = " • Strong's" if t["edition_type"] == "strongs" else ""
        if not t["is_complete"]:
            suffix += " • partial"
        return f"{t['code']} — {t['name']}{suffix}"

    def open_translation_picker(self, which):
        items = [(self._translation_label(t), t["code"]) for t in self.translations]
        if which == "primary":
            self.open_list("Translation", items, self.code, self._set_translation)
        else:
            self.open_list("Compare with", items, self.compare_code, self._set_compare)

    def _set_translation(self, code):
        if not code or code == self.code:
            return
        oldb, oldc = self.book_number, self.chapter
        self.code = code
        db.set_setting("translation_code", self.code)

        selected_tr = db.get_translation(self.code)
        if selected_tr and selected_tr["edition_type"] != "strongs" and self.show_strongs:
            self.show_strongs = False
            db.set_setting("show_strongs", "0")

        self._reload_books(oldb)
        self._reload_chapters(oldc)
        self._sync_controls()
        self.show_chapter()

    def _set_compare(self, code):
        self.compare_code = code
        db.set_setting("compare_translation_code", self.compare_code)
        self._sync_controls()
        if self.side_by_side:
            self.show_chapter()

    def _sync_controls(self):
        """Mirror state into every widget that shows it, without re-firing handlers."""
        for w, on in (
            (self.side_b, self.side_by_side), (self.side_box, self.side_by_side),
            (self.strong_b, self.show_strongs), (self.strong_box, self.show_strongs),
            (self.dark_box, self.dark),
        ):
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
        by_code = {t["code"]: t for t in self.translations}
        if self.code in by_code:
            self.tr_setting_b.setText(self._translation_label(by_code[self.code]))
        if self.compare_code in by_code:
            self.cmp_setting_b.setText("Compare with: " + self._translation_label(by_code[self.compare_code]))
        self.cmp_setting_b.setEnabled(self.side_by_side)
        self.size_label.setText(f"{self.font_size} pt")
        self._update_fields()

    def translation_info(self):
        t = db.get_translation(self.code)
        completeness = "Complete 66-book edition" if t["is_complete"] else "Partial edition"
        redistribution = "Marked redistributable in this local database" if t["redistributable"] else "Local/private copy — do not redistribute from this build"
        e = lambda s: html.escape(str(s or ""))
        self.show_text(
            "Translation info",
            f"<h2>{e(t['name'])} ({e(t['code'])})</h2>"
            f"<p><b>Type:</b> {e(t['edition_type'])}<br>{completeness}<br>{redistribution}</p>"
            f"<h3>Rights</h3><p>{e(t['rights'])}</p>"
            f"<p><small>Source file: {e(t['source_filename'])}</small></p>"
        )

    def show_about(self):
        icon = resource_path("verselens_icon.png")
        img = f"<p><img src='{icon}' width='96' height='96'></p>" if icon.exists() else ""
        self.show_text(f"About {APP_NAME}", f"""
        {img}
        <h2>{APP_NAME}</h2>
        <p>{APP_SUBTITLE}<br>Version {APP_VERSION}</p>
        <h3>About</h3>
        <p><b>{APP_NAME}</b> is an offline Bible study application focused on:</p>
        <ul>
            <li>Scripture reading</li>
            <li>Notes, bookmarks, and highlighting</li>
            <li>Multiple translations</li>
            <li>Side-by-side comparison</li>
            <li>Strong's number study</li>
        </ul>
        <h3>Data Notes</h3>
        <p>Translations, Strong's-tagged texts, and optional lexicon imports are stored locally.
        User annotations are stored separately in the operating system's application-data directory.</p>
        """)

    def show_text(self, title, body):
        self.text_page.title.setText(title)
        self.text_browser.setHtml(body)
        self.show_page(self.TEXT)

    # ----- toggles, font, theme -----

    def _toggle_side_by_side(self, on):
        self.side_by_side = bool(on)
        db.set_setting("side_by_side", "1" if on else "0")
        self._sync_controls()
        self.show_chapter()

    def _strongs_equivalent(self, code):
        # Prefer a Strong's edition whose base_code matches the current translation.
        for t in self.translations:
            if t["edition_type"] == "strongs" and t["base_code"] == code:
                return t["code"]
        return None

    def _toggle_strongs(self, on):
        if on:
            tr = db.get_translation(self.code)
            if tr and tr["edition_type"] != "strongs":
                target = self._strongs_equivalent(self.code)
                if target:
                    # Set this before changing the translation because the
                    # translation change redraws immediately.
                    self.show_strongs = True
                    db.set_setting("show_strongs", "1")
                    self._set_translation(target)
                    return
                self.show_strongs = False
                self._sync_controls()
                self.show_text(
                    "Strong's Numbers",
                    "<p>This translation does not have a linked Strong's edition.</p>"
                    "<p>Choose <b>KJV-S</b> or <b>ASV-S</b> to display clickable Strong's numbers.</p>"
                )
                return

        self.show_strongs = bool(on)
        db.set_setting("show_strongs", "1" if on else "0")
        self._sync_controls()
        self.show_chapter(keep_scroll=True)

    def _font(self, d):
        self.font_size = max(8, min(28, self.font_size + d))
        db.set_setting("font_size", self.font_size)
        self.size_label.setText(f"{self.font_size} pt")
        self._apply_font()

    def _apply_font(self):
        css = f"QTextBrowser{{font-size:{self.font_size}pt;}}"
        for b in (self.reader, self.search_results, self.text_browser):
            b.setStyleSheet(css)
        self.strong_detail.setStyleSheet(f"QTextBrowser{{font-size:{max(9, self.font_size - 2)}pt;}}")

    def _toggle_theme(self, on):
        self.dark = bool(on)
        db.set_setting("dark", "1" if self.dark else "0")
        self._apply_theme()
        self._reload_books(self.book_number)
        self.show_chapter(keep_scroll=True)

def build_splash():
    logo = QPixmap(str(resource_path("verselens_logo_lockup.png")))
    if logo.isNull():
        pix = QPixmap(500, 260)
        pix.fill(Qt.white)
    else:
        pix = QPixmap(760, 260)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        scaled = logo.scaled(680, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (pix.width() - scaled.width()) // 2
        painter.drawPixmap(x, 20, scaled)
        painter.setPen(QColor(90, 95, 110))
        f = painter.font()
        f.setPointSize(14)
        painter.setFont(f)
        painter.drawText(pix.rect().adjusted(0, 200, 0, -20), Qt.AlignHCenter, APP_SUBTITLE)
        painter.end()

    # Fit narrow (portrait phone) screens.
    screen = QGuiApplication.primaryScreen()
    if screen:
        max_w = screen.availableGeometry().width() - 32
        if 0 < max_w < pix.width():
            pix = pix.scaledToWidth(max_w, Qt.SmoothTransformation)

    splash = QSplashScreen(pix)
    splash.setWindowFlag(Qt.WindowStaysOnTopHint)
    splash.setWindowIcon(app_icon())
    return splash

def main():
    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")

    splash = build_splash()
    splash.show()
    splash.showMessage("Loading VerseLens…", Qt.AlignBottom | Qt.AlignHCenter, QColor("#2b2f3a"))
    app.processEvents()

    w = MainWindow()
    QTimer.singleShot(900, splash.close)
    QTimer.singleShot(900, w.show)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
