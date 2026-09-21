from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from repositories.summary_repository import SummaryRepository


class SummaryWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, database_path, key):
        super().__init__()
        self.database_path = database_path
        self.key = key

    @pyqtSlot()
    def run(self):
        try:
            from database.connection import connection
            from repositories.daily_summary_repository import DailySummaryRepository
            with connection(self.database_path) as conn:
                conn.execute("BEGIN")
                result = SummaryRepository(self.database_path).load(*self.key[:4], conn=conn)
                if len(self.key) > 4:
                    repository = DailySummaryRepository(self.database_path)
                    date_from, date_to, tiers, models, eqp = self.key
                    args = dict(date_from=date_from, date_to=date_to, eqpid=eqp,
                                tiers=tiers, selected_models=models, connection=conn)
                    result.cum_daily = repository.get_cum_daily_summary(**args)
                    result.prime_daily = repository.get_prime_daily_summary(**args)
            # First heavy imports happen only on SEARCH, in the worker after the window is shown.
            from workers.chart_preload_worker import preload_charts
            preload_charts()
            self.succeeded.emit(result)
        except Exception as error:
            self.failed.emit(str(error) or "Không thể tải CUM Summary.")
        finally:
            self.finished.emit()
