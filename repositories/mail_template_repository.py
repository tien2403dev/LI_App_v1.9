from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Iterable,
    Union,
)

from database.connection import create_connection

@dataclass(frozen=True)
class MailTemplate:
    """Template được người dùng lưu trong database."""

    subject: str
    heading: str
    closing: str


class MailTemplateRepository:
    """Đọc template và dữ liệu Alarm cho email."""

    TEMPLATE_ID = 1

    def __init__(
        self,
        database_path: Union[str, Path],
    ):
        self.database_path = Path(
            database_path
        )

    def get_template(self) -> MailTemplate:
        """Đọc template hiện tại từ database."""

        connection = create_connection(
            self.database_path
        )

        try:
            row = connection.execute(
                """
                SELECT
                    subject,
                    heading,
                    closing
                FROM mail_template
                WHERE id = ?
                """,
                (self.TEMPLATE_ID,),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Không tìm thấy Mail Template."
                )

            return MailTemplate(
                subject=str(
                    row["subject"] or ""
                ),
                heading=str(
                    row["heading"] or ""
                ),
                closing=str(
                    row["closing"] or ""
                ),
            )

        finally:
            connection.close()

    def save_template(
        self,
        subject: str,
        heading: str,
        closing: str,
    ) -> None:
        """Lưu template, không lưu Body Preview."""

        subject = subject.strip()

        if not subject:
            raise ValueError(
                "Subject không được để trống."
            )

        connection = create_connection(
            self.database_path
        )

        try:
            connection.execute(
                """
                INSERT INTO mail_template (
                    id,
                    subject,
                    heading,
                    closing
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(id)
                DO UPDATE SET
                    subject = excluded.subject,
                    heading = excluded.heading,
                    closing = excluded.closing
                """,
                (
                    self.TEMPLATE_ID,
                    subject,
                    heading.strip(),
                    closing.strip(),
                ),
            )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def get_alarm_previews(self, target_dates):
        """Đọc đúng Alarm Date và bằng chứng, độc lập bộ lọc trên giao diện."""
        import json
        from datetime import datetime
        dates = list(dict.fromkeys([target_dates] if isinstance(target_dates, str) else target_dates))
        for value in dates:
            datetime.strptime(value, "%Y%m%d")
        if not dates:
            return []
        conn = create_connection(self.database_path)
        try:
            conn.execute('BEGIN')
            alarms = [dict(row) for row in conn.execute(
                f"SELECT * FROM slot_fail_alarm WHERE alarm_date IN ({','.join('?' for _ in dates)}) "
                "ORDER BY alarm_date DESC,eqp,slot", dates)]
            for alarm in alarms:
                evidence = json.loads(alarm['evidence_json'])
                alarm['evidence'] = evidence
                alarm['runs'] = []
                for run in evidence.get('different_scrap', []):
                    alarm['runs'].append(dict(run, details=run['tests'],
                                             different_scrap=True))
                for run in evidence.get('1', []):
                    # Giới hạn từng chuỗi, không lấy toàn bộ FAIL trong khoảng tổng của alarm.
                    start_date, start_time = run['start'].split(' ')
                    end_date, end_time = run['end'].split(' ')
                    rows = conn.execute(
                        "SELECT DATE,TIME,MODEL,LOTNO,SCRAPCODE,QTY FROM prime_data "
                        "WHERE EQP=? AND SLOT=? AND RESULT='FAIL' "
                        "AND DATE BETWEEN ? AND ? "
                        "AND (DATE>? OR TIME>=?) AND (DATE<? OR TIME<=?) "
                        "ORDER BY DATE DESC,TIME DESC,id DESC",
                        (alarm['eqp'], alarm['slot'], start_date.replace('-',''), end_date.replace('-',''),
                         start_date.replace('-',''), start_time, end_date.replace('-',''), end_time))
                    details = [dict(row) for row in rows
                               if row['MODEL'] in run['models'] and row['SCRAPCODE'] in run['scraps']]
                    alarm['runs'].append(dict(run, details=details))
            return alarms
        finally:
            conn.close()
