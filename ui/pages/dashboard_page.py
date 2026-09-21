from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class DashboardPage(QWidget):
    """Dashboard chỉ đọc và tổng hợp snapshot đang dùng bởi tab Alarm."""

    CARD_DEFINITIONS = (
        ('total_alarm', 'Total Alarm', '#EAF2FF'),
        ('not_started', 'Chưa tiến hành', '#FDEBEC'),
        ('in_progress', 'Đang tiến hành', '#FFF4D6'),
        ('completed', 'Đã hoàn thành', '#E5F5EA'),
        ('quick_pass', 'Quick Check PASS', '#E8F4FF'),
        ('cal_pass', 'CAL Check PASS', '#EEEAFE'),
        ('monitor_day1_pass', 'Monitor Day 1 PASS', '#E9F7F5'),
        ('monitor_day2_pass', 'Monitor Day 2 PASS', '#E9F7F5'),
        ('monitor_day3_pass', 'Monitor Day 3 PASS', '#E9F7F5'),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        self.title_label = QLabel('Dashboard')
        self.title_label.setStyleSheet(
            'font-size:18px; font-weight:700; color:#163A5F;'
        )
        layout.addWidget(self.title_label)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.value_labels = {}
        for key, title, background in self.CARD_DEFINITIONS:
            card = QFrame()
            card.setObjectName(f'dashboardCard_{key}')
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card.setMinimumWidth(105)
            card.setFixedHeight(92)
            card.setStyleSheet(f'''
                QFrame#{card.objectName()} {{
                    background-color: {background};
                    border: 1px solid #B8CDE0;
                    border-radius: 9px;
                }}
                QFrame#{card.objectName()} QLabel {{
                    border: none;
                    background: transparent;
                }}
            ''')
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(3)

            label = QLabel(title)
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            label.setWordWrap(True)
            label.setStyleSheet('color:#4D6B8A; font-size:11px; font-weight:600;')
            value = QLabel('0')
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet('color:#102A43; font-size:23px; font-weight:700;')
            card_layout.addWidget(label)
            card_layout.addWidget(value, 1)
            self.value_labels[key] = value
            cards.addWidget(card, 1)

        layout.addLayout(cards)
        layout.addStretch(1)

    @staticmethod
    def _date_text(value):
        """Đưa QDate hoặc chuỗi ngày về định dạng YYYYMMDD."""
        if value is None:
            return ''
        if hasattr(value, 'toString'):
            return value.toString('yyyyMMdd')
        digits = ''.join(character for character in str(value) if character.isdigit())
        return digits if len(digits) == 8 else str(value).strip()

    def set_date_range(self, date_from=None, date_to=None):
        """Chỉ hiện khoảng ngày trên tiêu đề sau khi có đủ From và To."""
        from_text = self._date_text(date_from)
        to_text = self._date_text(date_to)
        title = f'Dashboard | {from_text} - {to_text}' if from_text and to_text else 'Dashboard'
        self.title_label.setText(title)

    @staticmethod
    def _is_pass(value):
        return str(value or '').strip().upper() == 'PASS'

    def load_rows(self, rows):
        """Tính toàn bộ chỉ số từ các dòng Alarm; Dashboard không có dữ liệu nhập tay."""
        rows = list(rows or ())
        status_counts = {
            'not_started': 0,
            'in_progress': 0,
            'completed': 0,
        }
        for row in rows:
            status = str(row.get('status') or '').strip()
            if status == 'Chưa tiến hành':
                status_counts['not_started'] += 1
            elif status in ('Đang tiến hành', 'Đang thực hiện'):
                status_counts['in_progress'] += 1
            elif status == 'Đã hoàn thành':
                status_counts['completed'] += 1

        values = {
            'total_alarm': len(rows),
            **status_counts,
            'quick_pass': sum(self._is_pass(row.get('quick_check_result')) for row in rows),
            'cal_pass': sum(self._is_pass(row.get('cal_check_result')) for row in rows),
            'monitor_day1_pass': sum(self._is_pass(row.get('monitor_day1')) for row in rows),
            'monitor_day2_pass': sum(self._is_pass(row.get('monitor_day2')) for row in rows),
            'monitor_day3_pass': sum(self._is_pass(row.get('monitor_day3')) for row in rows),
        }
        for key, value in values.items():
            self.value_labels[key].setText(str(value))
