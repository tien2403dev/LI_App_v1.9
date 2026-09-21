"""Đọc/lưu Alarm trong QThread do PrimeController quản lý."""
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from repositories.alarm_repository import AlarmRepository


class AlarmWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, database_path, date_range=None, edit=None, history=None):
        """Chọn đọc theo ngày hoặc lưu ô; không chia sẻ SQLite connection giữa thread."""
        super().__init__()
        self.database_path = database_path
        self.date_range = date_range
        self.edit = edit
        self.history = history

    @pyqtSlot()
    def run(self):
        """Phát kết quả/lỗi, luôn kết thúc để controller dọn thread an toàn."""
        try:
            repository = AlarmRepository(self.database_path)
            if self.history is not None:
                from repositories.alarm_history_repository import AlarmHistoryRepository
                result = AlarmHistoryRepository(self.database_path).load(self.history)
                result['preferred_rule'] = self.history.get('preferred_rule')
            else:
                result = (repository.update_tracking(*self.edit) if self.edit is not None
                          else repository.load(*self.date_range, include_evidence=False))
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or 'Không thể xử lý Alarm.')
        finally:
            self.finished.emit()
