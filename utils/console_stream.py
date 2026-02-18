"""控制台重定向"""

from PySide6.QtCore import QObject, Signal


class EmittingStream(QObject):
    textWritten = Signal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass