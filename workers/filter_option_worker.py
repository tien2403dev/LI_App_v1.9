from threading import Event
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from repositories.filter_option_repository import FilterOptionRepository


class FilterOptionWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, database_path):
        super().__init__()
        self.database_path = database_path
        self.cancel_event = Event()

    def request_cancel(self):
        self.cancel_event.set()

    @pyqtSlot()
    def run(self):
        try:
            self.succeeded.emit(FilterOptionRepository(self.database_path).load_options(self.cancel_event))
        except Exception as error:
            if not self.cancel_event.is_set():
                self.failed.emit(str(error) or "Không thể nạp bộ lọc.")
        finally:
            self.finished.emit()
