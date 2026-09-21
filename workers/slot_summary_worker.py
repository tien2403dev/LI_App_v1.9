from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class SlotSummaryWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, database_path, key, cached_model=None):
        super().__init__()
        self.database_path = database_path
        self.key = key
        self.cached_model = cached_model

    @pyqtSlot()
    def run(self):
        try:
            from repositories.slot_summary_repository import SlotSummaryRepository
            result = SlotSummaryRepository(self.database_path).load(*self.key)
            # CUM chỉ phụ thuộc From/To/Tier; bỏ EQP, Model và SLOT khỏi cache.
            from dataclasses import replace
            from repositories.model_summary_repository import ModelSummaryRepository
            model = self.cached_model
            if model is None:
                model = ModelSummaryRepository(self.database_path).load(*self.key[:3])
            result = replace(result, cum_model=model)
            # Load heavy modules after SEARCH, outside the UI thread.
            from workers.chart_preload_worker import preload_charts
            preload_charts()
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or 'Không thể tải Yield Slot.')
        finally:
            self.finished.emit()
