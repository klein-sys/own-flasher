"""Keep test-owned Qt objects within the application's lifetime."""

import gc

import pytest


@pytest.fixture(scope="session", autouse=True)
def qt_application_lifetime(request):
    gui_tests = any(
        {"qapp", "qtbot"}.intersection(item.fixturenames)
        for item in request.session.items
    )
    if not gui_tests:
        yield None
        return

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    gc.collect()


@pytest.fixture(autouse=True)
def close_test_windows(qt_application_lifetime):
    app = qt_application_lifetime
    if app is None:
        yield
        return

    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent

    existing = set(app.topLevelWidgets())
    yield
    for widget in set(app.topLevelWidgets()) - existing:
        if shiboken6.isValid(widget):
            widget.close()
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
