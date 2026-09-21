# import codecs
# import re
# import sqlite3
# from contextlib import closing
# from datetime import datetime
# from pathlib import Path
#
# from database.schema import PRIME_FIELDS
# from domain.prime import COLUMNS, PrimeRecord, ValidationError, check_cancel
#
# HEADERS = ("ENDTIME", "TESTER", "PARTID", "LOTID")
# VECTORS = ("PORT", "HBIN", "SCRAP_CODE", "TESTCNT", "SERIAL_NO")
# BATCH_SIZE = 5000
#
#
# def tokens(value: str) -> list[str]:
#     """Tách các vị trí trong vector và giữ nguyên vị trí trống bên trong."""
#     parts = [part.strip() for part in value.split(":")]
#     if parts and parts[-1] == "":
#         parts.pop()  # Only remove terminator, never compact interior positions.
#     return parts
#
#
# # def integer(value: str, label: str, minimum: int, maximum: int | None = None) -> int:
# #     """Kiểm tra số nguyên và giới hạn lưu trữ của SQLite."""
# #     if not re.fullmatch(r"[0-9]+", value):
# #         raise ValidationError(f"{label}: cần số nguyên, nhận {value!r}")
# #     try:
# #         result = int(value)
# #     except ValueError as error:
# #         raise ValidationError(f"{label}: số nguyên quá lớn") from error
# #     if result > 9223372036854775807:
# #         raise ValidationError(f"{label}: vượt giới hạn INTEGER của SQLite")
# #     if result < minimum or (maximum is not None and result > maximum):
# #         raise ValidationError(f"{label}: giá trị ngoài phạm vi: {value}")
# #     return result
# def integer(value: str, label: str, minimum: int,
#             maximum: int | None = None) -> int:
#     """Kiểm tra số nguyên có dấu, giới hạn SQLite và phạm vi của trường."""
#     if not re.fullmatch(r"-?[0-9]+", value):
#         raise ValidationError(f"{label}: cần số nguyên, nhận {value!r}")
#
#     try:
#         result = int(value)
#     except ValueError as error:
#         raise ValidationError(f"{label}: số nguyên quá lớn") from error
#
#     if not -9223372036854775808 <= result <= 9223372036854775807:
#         raise ValidationError(f"{label}: vượt giới hạn INTEGER của SQLite")
#
#     if result < minimum or (maximum is not None and result > maximum):
#         raise ValidationError(f"{label}: giá trị ngoài phạm vi: {value}")
#
#     return result
#
# class LiPrimeLogReader:
#     def __init__(self, encoding="utf-8-sig"):
#         """Lưu encoding mặc định dùng để đọc log PRIME."""
#         self.encoding = encoding
#
#     def read_file(self, path: Path):
#         """Đọc một file log và bổ sung đường dẫn vào lỗi kiểm tra dữ liệu."""
#         try:
#             data = path.read_bytes()
#             encoding = "utf-16" if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) else self.encoding
#             try:
#                 text = data.decode(encoding)
#             except UnicodeDecodeError as error:
#                 prefix = data[:error.start].decode(encoding, errors="ignore")
#                 line = prefix.count("\n") + 1
#                 raise ValidationError(f"Dòng {line}: không giải mã được log bằng {encoding}") from error
#             yield from self.parse_text(text)
#         except (ValueError, UnicodeError, OSError, ValidationError) as error:
#             raise ValidationError(f"{path}: {error}") from error
#
#     @staticmethod
#     def parse_text(text: str):
#         """Chuyển các thẻ log thành bản ghi và dừng ở lỗi validate đầu tiên có số dòng."""
#         def fail(message, offset=0):
#             """Báo lỗi tại dòng chứa thẻ liên quan trong file log."""
#             line = text.count("\n", 0, offset) + 1
#             raise ValidationError(f"Dòng {line}: {message}")
#
#         def checked_integer(value, label, minimum, offset, maximum=None):
#             """Kiểm tra số nguyên và gắn lỗi với dòng chứa trường dữ liệu."""
#             try:
#                 return integer(value, label, minimum, maximum)
#             except ValidationError as error:
#                 fail(str(error), offset)
#
#         # Deliberately ignore wrapper tags. Only complete required field tags matter.
#         names = HEADERS + VECTORS
#         pattern = r"<(" + "|".join(names) + r")\s*>([^<]*)</\1\s*>"
#         matches = list(re.finditer(pattern, text, flags=re.DOTALL))
#         fields = {name: [] for name in names}
#         for match in matches:
#             fields[match.group(1)].append((match.start(), match.group(2).strip()))
#         # Detect broken/duplicated opening tags for required data, not wrappers.
#         for name in names:
#             openings = list(re.finditer(r"<" + name + r"\s*>", text))
#             if len(openings) != len(fields[name]):
#                 valid_offsets = {offset for offset, _ in fields[name]}
#                 broken = next(m for m in openings if m.start() not in valid_offsets)
#                 fail(f"Thẻ {name} bị thiếu nội dung đóng hoặc sai định dạng", broken.start())
#         for name in HEADERS:
#             if len(fields[name]) != 1:
#                 offset = fields[name][1][0] if len(fields[name]) > 1 else len(text)
#                 fail(f"Cần đúng một trường {name} trong mỗi file", offset)
#         header = {name: fields[name][0][1] for name in HEADERS}
#         if not re.fullmatch(r"[0-9]{14}", header["ENDTIME"]):
#             fail("ENDTIME phải gồm 14 chữ số YYYYMMDDHHMMSS", fields["ENDTIME"][0][0])
#         try:
#             end = datetime.strptime(header["ENDTIME"], "%Y%m%d%H%M%S")
#         except ValueError:
#             fail("ENDTIME chứa ngày hoặc giờ không hợp lệ", fields["ENDTIME"][0][0])
#         for name in ("TESTER", "PARTID", "LOTID"):
#             if not header[name] or header[name].upper() == "NULL":
#                 fail(f"{name} không được rỗng/NULL", fields[name][0][0])
#         if len(header["PARTID"]) < 5:
#             fail("PARTID phải có ít nhất 5 ký tự", fields["PARTID"][0][0])
#         count = len(fields["PORT"])
#         if not count or any(len(fields[name]) != count for name in VECTORS):
#             fail("Thiếu hoặc lệch số nhóm PORT/HBIN/SCRAP_CODE/TESTCNT/SERIAL_NO (kiểm tra cuối file)", len(text))
#         for group in range(count):
#             values = {name: tokens(fields[name][group][1]) for name in VECTORS}
#             ports = values["PORT"]
#             if len(ports) != 4:
#                 fail(f"Nhóm {group+1}: PORT phải có 4 vị trí", fields["PORT"][group][0])
#             # A globally empty scrap tag means there are no scrap codes.
#             if fields["SCRAP_CODE"][group][1].upper() in ("", "NULL"):
#                 values["SCRAP_CODE"] = [""] * 4
#             for name in VECTORS:
#                 if len(values[name]) != 4:
#                     fail(f"Nhóm {group+1}: {name} phải giữ đủ 4 vị trí (dùng NULL)", fields[name][group][0])
#             slot_numbers = [checked_integer(v, "PORT", 1, fields["PORT"][group][0], 48) for v in ports]
#             if len(set(slot_numbers)) != 4:
#                 fail("PORT bị lặp slot trong cùng nhóm", fields["PORT"][group][0])
#             for index, slot in enumerate(slot_numbers):
#                 serial = values["SERIAL_NO"][index]
#                 if serial.upper() == "NULL":
#                     continue
#                 if not serial:
#                     fail(f"Slot {slot}: SERIAL_NO rỗng; vị trí không cắm phải là NULL", fields["SERIAL_NO"][group][0])
#                 # hbin = checked_integer(values["HBIN"][index], f"Slot {slot} HBIN", 0, fields["HBIN"][group][0])
#                 hbin = checked_integer(
#                     values["HBIN"][index],
#                     f"Slot {slot} HBIN",
#                     -9,
#                     fields["HBIN"][group][0],
#                 )
#                 test_count = checked_integer(values["TESTCNT"][index], f"Slot {slot} TESTCNT", 1, fields["TESTCNT"][group][0])
#                 scrap = values["SCRAP_CODE"][index]
#                 scrap = None if scrap.upper() in ("", "0", "NULL") else scrap
#                 yield PrimeRecord(
#                     end.strftime("%Y%m%d"), end.strftime("%H:%M:%S"),
#                     header["TESTER"], header["PARTID"], header["LOTID"], slot,
#                     "PASS" if hbin == 1 else "FAIL", scrap, test_count,
#                     serial, 1, header["PARTID"][:5])
#
#     @staticmethod
#     def discover(root: Path, dates: tuple[str, ...]) -> list[Path]:
#         """Tìm các file log theo folder máy và khoảng ngày đã chọn."""
#         if not root.is_dir():
#             raise ValidationError(f"Không truy cập được folder log: {root}")
#         folder_names = set()
#         for value in dates:
#             if not re.fullmatch(r"[0-9]{8}", value):
#                 raise ValidationError(f"Ngày không hợp lệ: {value}")
#             datetime.strptime(value, "%Y%m%d")
#             folder_names.add(value[2:])
#         files = []
#         # Missing day folders are skipped, but access/I/O errors are not swallowed.
#         for machine in sorted(root.iterdir()):
#             if not machine.is_dir():
#                 continue
#             for name in sorted(folder_names):
#                 folder = machine / name
#                 try:
#                     entries = list(folder.iterdir())
#                 except FileNotFoundError:
#                     continue
#                 files.extend(p for p in entries if p.is_file() and p.suffix.lower() == ".txt")
#         return sorted(files)
#
#     def stage_folder(self, root, dates, stage_path, progress, cancel=None):
#         """Đọc tuần tự các file, ghi batch vào staging và kiểm tra nguồn không thay đổi."""
#         root = Path(root)
#         files = self.discover(root, dates)
#         if not files:
#             raise ValidationError("Không tìm thấy file .txt trong các folder ngày được chọn")
#         signatures = {}
#         total = 0
#         with closing(sqlite3.connect(str(stage_path))) as conn:
#             conn.execute(f"CREATE TABLE staging_prime_data({PRIME_FIELDS})")
#             batch = []
#             sql = f"INSERT INTO staging_prime_data({','.join(COLUMNS)}) VALUES({','.join('?' for _ in COLUMNS)})"
#             for number, path in enumerate(files, 1):
#                 check_cancel(cancel)
#                 stat = path.stat()
#                 signatures[path] = (stat.st_size, stat.st_mtime_ns)
#                 for record in self.read_file(path):
#                     check_cancel(cancel)
#                     batch.append(record.values())
#                     total += 1
#                     if len(batch) >= BATCH_SIZE:
#                         conn.executemany(sql, batch)
#                         batch.clear()
#                 current = path.stat()
#                 if signatures[path] != (current.st_size, current.st_mtime_ns):
#                     raise ValidationError(f"File đang thay đổi, hãy import lại: {path}")
#                 if number == 1 or number % 50 == 0 or number == len(files):
#                     progress(f"Đã đọc {number}/{len(files)} file; {total} dòng sản phẩm")
#             if batch:
#                 conn.executemany(sql, batch)
#             if not total:
#                 raise ValidationError("Không có sản phẩm hợp lệ; không xóa dữ liệu cũ")
#             # Detect additions/removals and changed files during collection.
#             if self.discover(root, dates) != files:
#                 raise ValidationError("Danh sách file thay đổi khi đang đọc; hãy import lại")
#             for path, signature in signatures.items():
#                 current = path.stat()
#                 if signature != (current.st_size, current.st_mtime_ns):
#                     raise ValidationError(f"File thay đổi khi đang đọc: {path}")
#             conn.execute(
#                 "CREATE INDEX idx_stage_date_eqp_time_slot "
#                 "ON staging_prime_data(DATE, EQP, TIME, SLOT)")
#             conn.commit()
#         return len(files)


import codecs
import os
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from database.schema import PRIME_FIELDS
from domain.prime import COLUMNS, PrimeRecord, ValidationError, check_cancel

BATCH_SIZE = 5000
KEY_VALUE = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")
# Ngày ở đầu tên; _TCP ở cuối tên trước phần mở rộng (hoặc không có đuôi).
TCP_NAME = re.compile(r"^([0-9]{8})(?:.*)_TCP$", re.IGNORECASE)
TIME_PREFIX = re.compile(
    r"^\s*\[?(?:[0-9]{4}[-/][0-9]{2}[-/][0-9]{2}[ _T])?"
    r"([0-9]{2}:[0-9]{2}:[0-9]{2})(?:[.,][0-9]+)?(?=\]|\s|$)"
)


def integer(value: str, label: str, minimum: int,
            maximum: int | None = None) -> int:
    """Kiểm tra số nguyên có dấu, giới hạn SQLite và phạm vi của trường."""
    if not re.fullmatch(r"-?[0-9]+", value):
        raise ValidationError(f"{label}: cần số nguyên, nhận {value!r}")

    try:
        result = int(value)
    except ValueError as error:
        raise ValidationError(f"{label}: số nguyên quá lớn") from error

    if not -9223372036854775808 <= result <= 9223372036854775807:
        raise ValidationError(f"{label}: vượt giới hạn INTEGER của SQLite")

    if result < minimum or (maximum is not None and result > maximum):
        raise ValidationError(f"{label}: giá trị ngoài phạm vi: {value}")

    return result

class LiPrimeLogReader:
    def __init__(self, encoding="utf-8-sig"):
        self.encoding = encoding

    @staticmethod
    def file_date(path: Path) -> str | None:
        """Nhận YYYYMMDD..._TCP.txt hoặc YYYYMMDD..._TCP, không dùng mtime."""
        match = TCP_NAME.fullmatch(Path(path).stem)
        if match is None:
            return None
        value = match.group(1)
        try:
            datetime.strptime(value, "%Y%m%d")
        except ValueError:
            return None
        return value

    def read_file(self, path: Path):
        """Đọc log TCP; lỗi luôn có đường dẫn và số dòng nếu xác định được."""
        path = Path(path)
        try:
            day = self.file_date(path)
            if day is None:
                raise ValidationError("Tên file phải có ngày YYYYMMDD ở đầu và kết thúc bằng _TCP")
            data = path.read_bytes()
            if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
                text = data.decode("utf-16")
            else:
                # Cùng các fallback trong file mẫu. latin-1 giải mã được mọi byte.
                for encoding in dict.fromkeys((self.encoding, "utf-8-sig", "utf-8", "cp949", "iso-8859-1", "windows-1252")):
                    try:
                        text = data.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
            yield from self.parse_text(text, day)
        except (ValueError, UnicodeError, OSError, ValidationError) as error:
            raise ValidationError(f"{path}: {error}") from error

    @staticmethod
    def parse_text(text: str, business_date: str):
        """Mỗi FUNCTION=SLOT_END là một sản phẩm; giữ nguyên schema PRIME."""
        if not re.fullmatch(r"[0-9]{8}", business_date):
            raise ValidationError(f"Ngày không hợp lệ: {business_date}")
        try:
            datetime.strptime(business_date, "%Y%m%d")
        except ValueError as error:
            raise ValidationError(f"Ngày không hợp lệ: {business_date}") from error
        for line_number, line in enumerate(text.splitlines(), 1):
            data = {key.upper(): value.strip() for key, value in KEY_VALUE.findall(line)}
            if data.get("FUNCTION", "").upper() != "SLOT_END":
                continue

            def first(*keys, default=""):
                return next((data[key] for key in keys if data.get(key)), default)

            def required(*keys):
                value = first(*keys)
                if value.upper() in ("", "NULL", "-"):
                    raise ValidationError(f"{keys[0]} không được thiếu/rỗng/NULL")
                return value

            try:
                serial = first("SERIAL", "SERIALNO", "SERIAL_NO")
                if serial.upper() == "NULL":
                    continue  # Giữ quy tắc cũ: không tính vị trí không có sản phẩm.
                serial = required("SERIAL", "SERIALNO", "SERIAL_NO")
                match = TIME_PREFIX.match(line)
                if match is None:
                    raise ValidationError("Không đọc được giờ HH:MM:SS ở đầu dòng")
                time = match.group(1)
                datetime.strptime(time, "%H:%M:%S")
                eqp = required("EQPID", "EQP_ID", "EQP")
                lot = required("LOTID", "LOT_ID")
                part = required("PARTNO", "PART_NO", "MODEL")
                if len(part) < 5:
                    raise ValidationError("PARTNO phải có ít nhất 5 ký tự")
                slot = integer(required("SLOT", "SLOTNO", "SLOT_NO"), "SLOT", 1, 48)
                result = required("TESTRESULT", "TEST_RESULT", "RESULT").upper()
                if result not in ("PASS", "FAIL"):
                    raise ValidationError(f"TESTRESULT phải là PASS/FAIL, nhận {result!r}")
                count = integer(required("TEST_COUNT", "TESTCOUNT", "COUNT"), "TEST_COUNT", 0)
                scrap = first("SCRAP_CODE", "SCRAPCODE", "SCRAP")
                scrap = None if scrap.upper() in ("", "0", "NULL", "-") else scrap
                yield PrimeRecord(business_date, time, eqp, part, lot, slot,
                                  result, scrap, count, serial, 1, part[:5])
            except (ValueError, ValidationError) as error:
                raise ValidationError(f"Dòng {line_number}: {error}") from error

    @staticmethod
    def discover(root: Path, dates: tuple[str, ...]) -> list[Path]:
        """Quét mọi cấp dưới Interface; chỉ chọn _TCP có ngày trong tên phù hợp."""
        root = Path(root)
        if not root.is_dir():
            raise ValidationError(f"Không truy cập được folder log: {root}")
        selected = set(dates)
        for value in selected:
            try:
                if not re.fullmatch(r"[0-9]{8}", value):
                    raise ValueError(value)
                datetime.strptime(value, "%Y%m%d")
            except ValueError as error:
                raise ValidationError(f"Ngày không hợp lệ: {value}") from error

        def walk_error(error):
            # Không coi lỗi quyền truy cập/mạng là không có ngày cần tìm.
            raise ValidationError(f"Không đọc được folder log: {error}") from error

        files = []
        for folder, directories, names in os.walk(root, topdown=True, onerror=walk_error, followlinks=False):
            # Cắt nhánh trước khi os.walk đi vào LOT, ở mọi cấp thư mục.
            directories[:] = [name for name in directories if name.upper() != "LOT"]
            if Path(folder).name.upper() == "LOT":
                directories[:] = []
                continue
            for name in names:
                path = Path(folder) / name
                if LiPrimeLogReader.file_date(path) in selected and path.is_file():
                    files.append(path)
        return sorted(files)

    def stage_folder(self, root, dates, stage_path, progress, cancel=None):
        """Đọc tuần tự các file, ghi batch vào staging và kiểm tra nguồn không thay đổi."""
        root = Path(root)
        files = self.discover(root, dates)
        if not files:
            # Giữ thông báo này vì hai tác vụ auto-import dùng nó để nhận biết SKIPPED.
            raise ValidationError("Không tìm thấy file .txt trong các folder ngày được chọn")
        signatures = {}
        total = 0
        with closing(sqlite3.connect(str(stage_path))) as conn:
            conn.execute(f"CREATE TABLE staging_prime_data({PRIME_FIELDS})")
            batch = []
            sql = f"INSERT INTO staging_prime_data({','.join(COLUMNS)}) VALUES({','.join('?' for _ in COLUMNS)})"
            for number, path in enumerate(files, 1):
                check_cancel(cancel)
                stat = path.stat()
                signatures[path] = (stat.st_size, stat.st_mtime_ns)
                for record in self.read_file(path):
                    check_cancel(cancel)
                    batch.append(record.values())
                    total += 1
                    if len(batch) >= BATCH_SIZE:
                        conn.executemany(sql, batch)
                        batch.clear()
                current = path.stat()
                if signatures[path] != (current.st_size, current.st_mtime_ns):
                    raise ValidationError(f"File đang thay đổi, hãy import lại: {path}")
                if number == 1 or number % 50 == 0 or number == len(files):
                    progress(f"Đã đọc {number}/{len(files)} file; {total} dòng sản phẩm")
            if batch:
                conn.executemany(sql, batch)
            if not total:
                raise ValidationError("Không có sản phẩm hợp lệ; không xóa dữ liệu cũ")
            # Detect additions/removals and changed files during collection.
            if self.discover(root, dates) != files:
                raise ValidationError("Danh sách file thay đổi khi đang đọc; hãy import lại")
            for path, signature in signatures.items():
                current = path.stat()
                if signature != (current.st_size, current.st_mtime_ns):
                    raise ValidationError(f"File thay đổi khi đang đọc: {path}")
            conn.execute(
                "CREATE INDEX idx_stage_date_eqp_time_slot "
                "ON staging_prime_data(DATE, EQP, TIME, SLOT)")
            conn.commit()
        return len(files)