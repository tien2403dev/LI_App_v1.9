from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class DatabaseInitWorker(QObject):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, database_path):
        super().__init__()
        self.database_path = Path(database_path)

    @pyqtSlot()
    def run(self):
        try:
            from database.schema import initialize_database
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            initialize_database(self.database_path)
            self.succeeded.emit()
        except Exception as error:
            self.failed.emit(str(error) or "Không thể khởi tạo database.")
        finally:
            self.finished.emit()
