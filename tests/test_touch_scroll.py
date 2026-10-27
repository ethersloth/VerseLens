import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QListWidget, QScroller, QTextBrowser, QTextEdit

from app import IconBrowser, enable_touch_scroll


class TouchScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def make_browser(self, platform, browser_type=QTextBrowser):
        with patch("app.QGuiApplication.platformName", return_value=platform):
            if browser_type is IconBrowser:
                browser = IconBrowser(lambda name: None)
            else:
                browser = browser_type()
                enable_touch_scroll(browser)
        self.addCleanup(browser.close)
        browser.setPlainText("Scripture text for reading without accidental selection.\n" * 80)
        browser.resize(400, 300)
        browser.show()
        self.application.processEvents()
        return browser

    def drag_text(self, browser):
        QTest.mousePress(browser.viewport(), Qt.LeftButton, pos=QPoint(20, 20))
        QTest.mouseMove(browser.viewport(), QPoint(170, 80))
        QTest.mouseRelease(browser.viewport(), Qt.LeftButton, pos=QPoint(170, 80))

    def test_android_reading_views_do_not_select_on_drag(self):
        for browser_type in (QTextBrowser, IconBrowser):
            with self.subTest(browser_type=browser_type):
                browser = self.make_browser("android", browser_type)
                self.drag_text(browser)
                self.assertFalse(browser.textCursor().hasSelection())
                self.assertFalse(browser.textInteractionFlags() & Qt.TextSelectableByKeyboard)
                self.assertTrue(QScroller.hasScroller(browser.viewport()))

    def test_desktop_text_selection_is_unchanged(self):
        browser = self.make_browser("xcb")
        self.drag_text(browser)
        self.assertTrue(browser.textCursor().hasSelection())
        self.assertEqual(browser.textInteractionFlags(), Qt.TextBrowserInteraction)

    def test_android_gesture_scrolls_without_selecting(self):
        browser = self.make_browser("android")
        scroller = QScroller.scroller(browser.viewport())
        self.addCleanup(scroller.stop)
        scroller.handleInput(QScroller.InputPress, QPointF(100, 240), 0)
        scroller.handleInput(QScroller.InputMove, QPointF(100, 180), 100)
        scroller.handleInput(QScroller.InputMove, QPointF(100, 60), 200)
        QTest.qWait(50)
        scroller.handleInput(QScroller.InputRelease, QPointF(100, 60), 250)
        QTest.qWait(100)
        self.assertGreater(browser.verticalScrollBar().value(), 0)
        self.assertFalse(browser.textCursor().hasSelection())

    def test_android_links_still_activate(self):
        for browser_type in (QTextBrowser, IconBrowser):
            with self.subTest(browser_type=browser_type):
                browser = self.make_browser("android", browser_type)
                browser.setOpenLinks(False)
                browser.setHtml('<a href="verse:1">Open verse</a>')
                clicked = []
                browser.anchorClicked.connect(clicked.append)
                point = QPoint(10, 10)
                self.assertEqual(browser.anchorAt(point), "verse:1")
                QTest.mouseClick(browser.viewport(), Qt.LeftButton, pos=point)
                self.assertEqual([url.toString() for url in clicked], ["verse:1"])

    def test_android_editors_and_lists_are_unchanged(self):
        for widget_type in (QTextEdit, QListWidget):
            with self.subTest(widget_type=widget_type):
                widget = widget_type()
                self.addCleanup(widget.close)
                with patch("app.QGuiApplication.platformName", return_value="android"):
                    enable_touch_scroll(widget)
                self.assertTrue(QScroller.hasScroller(widget.viewport()))
                if isinstance(widget, QTextEdit):
                    self.assertFalse(widget.isReadOnly())
                    self.assertEqual(widget.textInteractionFlags(), Qt.TextEditorInteraction)
                else:
                    widget.addItem("Genesis")
                    widget.setCurrentRow(0)
                    self.assertTrue(widget.item(0).isSelected())

    def make_book_list(self, platform):
        books = QListWidget()
        self.addCleanup(books.close)
        books.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        with patch("app.QGuiApplication.platformName", return_value=platform):
            enable_touch_scroll(books)
        books.addItems([f"Book {n}" for n in range(1, 67)])
        books.resize(300, 300)
        books.show()
        self.application.processEvents()
        clicked = []
        books.itemClicked.connect(lambda item: clicked.append(item.text()))
        return books, clicked

    def test_android_list_drag_scrolls_without_selecting_a_book(self):
        books, clicked = self.make_book_list("android")
        viewport = books.viewport()
        self.addCleanup(QScroller.scroller(viewport).stop)

        def send(kind, y, button, buttons):
            # QTest.mouseMove does not hold the button, so build the drag by hand.
            point = QPointF(100, y)
            event = QMouseEvent(kind, point, viewport.mapToGlobal(point), button, buttons, Qt.NoModifier)
            QApplication.sendEvent(viewport, event)
            QTest.qWait(15)

        send(QEvent.MouseButtonPress, 250, Qt.LeftButton, Qt.LeftButton)
        for y in range(240, 40, -20):
            send(QEvent.MouseMove, y, Qt.NoButton, Qt.LeftButton)
        send(QEvent.MouseButtonRelease, 40, Qt.LeftButton, Qt.NoButton)
        QTest.qWait(400)
        self.assertGreater(books.verticalScrollBar().value(), 0)
        self.assertEqual(clicked, [])
        self.assertEqual(books.selectedItems(), [])

    def test_android_list_tap_still_selects_a_book(self):
        books, clicked = self.make_book_list("android")
        point = books.visualItemRect(books.item(2)).center()
        QTest.mouseClick(books.viewport(), Qt.LeftButton, pos=point)
        QTest.qWait(400)
        self.assertEqual(clicked, ["Book 3"])


if __name__ == "__main__":
    unittest.main()
