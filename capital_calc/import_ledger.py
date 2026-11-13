"""가계부 내역 가져오기: CSV · 엑셀(.xlsx) · 메모장(텍스트) · 붙여넣은 글.

은행·카드사가 내려주는 파일은 제각각이다. 머리글 이름도 다르고, 위에 제목
줄이 몇 줄 붙어 있기도 하고, 입금/출금이 따로 있기도 하다. 그래서 여기서는
**머리글을 찾아 이름으로 짝지어** 읽고, 그마저 없으면 줄마다 날짜와 금액을
찾아내는 식으로 읽는다 (메모장에 손으로 적어 둔 것도 들어오게).

Qt 를 모르는 순수 파이썬이다. 읽기만 하고 가계부에 넣지는 않는다 —
무엇을 넣을지는 Backend 가 미리보기로 보여 주고 사용자가 정한다.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from pathlib import Path

from .ledger import (COST, INCOME, LEDGER_CATEGORIES, LEDGER_INCOME_CATEGORIES,
                     LEDGER_PAYS)

# 머리글 이름 짝짓기. 이름에 이 조각이 들어 있으면 그 칸으로 본다 (앞에 있는 것이 먼저).
HEADER_KEYS: list[tuple[str, tuple[str, ...]]] = [
    ("out", ("출금", "지출금액", "사용금액", "결제금액", "withdraw", "출금액")),
    ("inc", ("입금", "수입금액", "deposit", "입금액")),
    ("date", ("거래일", "이용일", "승인일", "사용일", "결제일", "매출일",
              "날짜", "일자", "date")),
    ("amount", ("거래금액", "이용금액", "승인금액", "금액", "amount", "price")),
    ("name", ("가맹점명", "가맹점", "적요", "내용", "거래내용", "사용처", "상호", "내역",
              "name", "description", "merchant")),
    ("category", ("분류", "카테고리", "업종", "category")),
    ("pay", ("결제수단", "결제방법", "수단", "카드명", "카드", "계좌", "은행", "pay", "method")),
    ("kind", ("구분", "입출구분", "입출금", "수입/지출", "입/출", "유형", "type", "kind")),
    ("note", ("메모", "비고", "note", "memo", "remark")),
]

# 숫자로 보이는 것 (1,234 / -1234 / 1 234원 / ₩1,234 / (1,234) = 음수)
_NUM = re.compile(r"^[\s₩\\(]*[-+]?[\d,\s]+(?:\.\d+)?[)\s원]*$")
_DATE_PATTERNS = (
    "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d",
    "%y-%m-%d", "%y.%m.%d", "%y/%m/%d",
    "%m-%d", "%m.%d", "%m/%d",
)
_INCOME_WORDS = ("수입", "입금", "income", "+")
_COST_WORDS = ("지출", "출금", "cost", "expense", "-")


def _clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def parse_amount(text: str) -> float | None:
    """'1,234원' '-1,234' '(1,234)' '₩1 234' → 숫자. 돈이 아니면 None."""
    t = _clean(text)
    if not t or not _NUM.match(t):
        return None
    neg = t.strip().startswith("(") or "-" in t
    digits = re.sub(r"[^\d.]", "", t)
    if not digits or digits == ".":
        return None
    try:
        v = float(digits)
    except ValueError:
        return None
    return -v if neg else v


def parse_date_text(text: str, default_year: int | None = None) -> str:
    """여러 모양의 날짜를 'YYYY-MM-DD' 로. 못 읽으면 빈 문자열.

    '2026-11-13 12:30:00' 처럼 시각이 붙어 있으면 앞의 날짜만 쓴다.
    '11/13' 처럼 해가 없으면 default_year (없으면 올해) 를 붙인다.
    """
    t = _clean(text)
    if not t:
        return ""
    # '2026년 11월 2일' 처럼 사이가 띄어져 있어도 한 덩이로 만든 뒤 시각을 떼어 낸다
    t = re.sub(r"\s*년\s*", "-", t)
    t = re.sub(r"\s*월\s*", "-", t)
    t = re.sub(r"\s*일(?!\d)", "", t)
    t = t.split()[0].strip().rstrip("-")
    year = default_year or date.today().year
    for fmt in _DATE_PATTERNS:
        try:
            d = datetime.strptime(t, fmt).date()
        except ValueError:
            continue
        if "%Y" not in fmt and "%y" not in fmt:
            d = d.replace(year=year)
        return d.isoformat()
    return ""


def _looks_like_date(text: str) -> bool:
    return bool(parse_date_text(text))


# ───────────────────────── 파일 읽기 (표로)

def _rows_from_csv(data: bytes) -> tuple[list[list[str]], str]:
    """구분자를 알아서 찾아 읽는다. 인코딩은 utf-8 → cp949 순서로 시도."""
    text, enc = _decode(data)
    sample = "\n".join(text.splitlines()[:20])
    delim = ","
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:
        for d in ("\t", ",", ";", "|"):
            if d in sample:
                delim = d
                break
    rows = [[_clean(c) for c in r] for r in csv.reader(io.StringIO(text), delimiter=delim)]
    name = {",": "쉼표", "\t": "탭", ";": "세미콜론", "|": "막대"}.get(delim, delim)
    return [r for r in rows if any(c for c in r)], f"{enc} · {name}로 나뉜 글"


def _decode(data: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(깨진 글자 있음)"


def _rows_from_xlsx(path: Path) -> tuple[list[list[str]], str]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [[_clean(c) for c in row] for row in ws.iter_rows(values_only=True)]
    wb.close()
    return [r for r in rows if any(c for c in r)], f"엑셀 '{ws.title}' 시트"


def read_table(path: str | Path) -> tuple[list[list[str]], str]:
    """파일을 표(문자열 2차원)로 읽는다. (표, 어떻게 읽었는지)"""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return _rows_from_xlsx(p)
    return _rows_from_csv(p.read_bytes())


# ───────────────────────── 표 → 내역

def find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """머리글 줄을 찾아 (줄 번호, {칸이름: 열 번호}). 못 찾으면 (-1, {}).

    은행 파일은 제목·계좌번호 같은 줄이 위에 붙어 있으므로 앞 15줄을 훑는다.
    """
    best: tuple[int, dict[str, int]] = (-1, {})
    for i, row in enumerate(rows[:15]):
        found: dict[str, int] = {}
        for col, cell in enumerate(row):
            label = re.sub(r"\s|_", "", cell).lower()
            if not label:
                continue
            for key, words in HEADER_KEYS:
                if key in found:
                    continue
                if any(w in label for w in words):
                    found[key] = col
                    break
        has_money = {"amount", "out", "inc"} & set(found)
        if "date" in found and has_money and len(found) > len(best[1]):
            best = (i, found)
    return best


def _kind_from(text: str, category: str) -> str:
    """'구분' 칸의 말과 분류로 수입/지출을 가린다."""
    t = _clean(text).lower()
    if any(w in t for w in _INCOME_WORDS):
        return INCOME
    if any(w in t for w in _COST_WORDS):
        return COST
    if category in LEDGER_INCOME_CATEGORIES:
        return INCOME
    return COST                      # 모르겠으면 지출 (카드 내역이 대부분 그렇다)


def rows_from_table(rows: list[list[str]], default_year: int | None = None) -> tuple[list[dict], list[str]]:
    """머리글을 찾아 표를 내역으로. (내역, 건너뛴 까닭들)"""
    head, cols = find_header(rows)
    if head < 0:
        return [], []
    out: list[dict] = []
    problems: list[str] = []

    def cell(row: list[str], key: str) -> str:
        i = cols.get(key, -1)
        return row[i] if 0 <= i < len(row) else ""

    for n, row in enumerate(rows[head + 1:], start=head + 2):
        if not any(c for c in row):
            continue
        d = parse_date_text(cell(row, "date"), default_year)
        if not d:
            problems.append(f"{n}번째 줄: 날짜를 못 읽었습니다 ('{cell(row, 'date')[:20]}')")
            continue

        kind = ""
        amount = None
        out_v = parse_amount(cell(row, "out"))
        inc_v = parse_amount(cell(row, "inc"))
        if out_v or inc_v:                       # 입금/출금 칸이 따로 있는 파일
            if inc_v:
                amount, kind = abs(inc_v), INCOME
            else:
                amount, kind = abs(out_v), COST
        else:
            v = parse_amount(cell(row, "amount"))
            if v is not None:
                amount = abs(v)
                if v < 0:
                    kind = COST
        if not amount:
            problems.append(f"{n}번째 줄: 금액을 못 읽었습니다 ('{cell(row, 'amount')[:20]}')")
            continue

        category = _clean(cell(row, "category"))
        if not kind:
            kind = _kind_from(cell(row, "kind"), category)
        out.append({
            "date": d,
            "amount": float(amount),
            "kind": kind,
            "name": _clean(cell(row, "name")),
            "category": category,
            "pay": _clean(cell(row, "pay")),
            "note": _clean(cell(row, "note")),
        })
    return out, problems


# ───────────────────────── 머리글이 없는 글 (메모장)

def rows_from_lines(text: str, default_year: int | None = None) -> tuple[list[dict], list[str]]:
    """'11/13 점심 12,000 카드' 처럼 손으로 적어 둔 줄을 읽는다.

    줄마다 **날짜로 보이는 토막**과 **금액으로 보이는 토막**을 하나씩 찾고,
    남은 말을 내용으로 삼는다. 금액 앞에 - 가 붙어 있으면 지출, + 면 수입이다.
    """
    out: list[dict] = []
    problems: list[str] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # 쉼표는 '12,000' 의 자릿점일 수 있으므로 숫자 사이의 것은 자르지 않는다
        parts = [p for p in re.split(r"(?<!\d),(?!\d)|\s+", line) if p]
        if len(parts) < 2:
            continue
        d = ""
        amount = None
        signed = None
        rest: list[str] = []
        for p in parts:
            if not d and _looks_like_date(p):
                d = parse_date_text(p, default_year)
                continue
            v = parse_amount(p) if amount is None else None
            if v is not None and abs(v) >= 1:
                amount, signed = abs(v), v
                continue
            rest.append(p)
        if not d or not amount:
            problems.append(f"{n}번째 줄: 날짜나 금액을 못 찾았습니다 ('{line[:28]}')")
            continue
        kind = INCOME if (signed is not None and signed > 0 and "+" in line) else COST
        pay = ""
        for w in rest:                           # 아는 결제수단 이름이 섞여 있으면 결제수단으로
            if w in LEDGER_PAYS:
                pay = w
                break
        if pay:
            rest = [w for w in rest if w != pay]
        name = " ".join(w for w in rest if w not in ("원", "-", "+"))
        category = ""
        for w in rest:                           # 아는 분류 이름이 섞여 있으면 분류로 본다
            if w in LEDGER_CATEGORIES:
                category = w
                name = " ".join(x for x in rest if x != w)
                break
        if category in LEDGER_INCOME_CATEGORIES:
            kind = INCOME
        out.append({"date": d, "amount": float(amount), "kind": kind, "name": name.strip(),
                    "category": category, "pay": pay, "note": ""})
    return out, problems


# ───────────────────────── 한 번에

def parse_text(text: str, default_year: int | None = None) -> tuple[list[dict], list[str], str]:
    """붙여넣은 글 → (내역, 까닭들, 어떻게 읽었는지)"""
    rows, how = _rows_from_csv(text.encode("utf-8"))
    got, problems = rows_from_table(rows, default_year)
    if got:
        return got, problems, f"머리글을 찾아 읽음 ({how})"
    got, problems = rows_from_lines(text, default_year)
    return got, problems, "줄마다 날짜와 금액을 찾아 읽음"


def parse_file(path: str | Path, default_year: int | None = None) -> tuple[list[dict], list[str], str]:
    """파일 → (내역, 까닭들, 어떻게 읽었는지). 읽을 수 없으면 예외를 낸다."""
    p = Path(path)
    rows, how = read_table(p)
    got, problems = rows_from_table(rows, default_year)
    if got:
        return got, problems, f"머리글을 찾아 읽음 ({how})"
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return [], problems, f"{how} — 날짜·금액 머리글을 찾지 못했습니다"
    text, _enc = _decode(p.read_bytes())
    got, problems = rows_from_lines(text, default_year)
    return got, problems, "줄마다 날짜와 금액을 찾아 읽음"
