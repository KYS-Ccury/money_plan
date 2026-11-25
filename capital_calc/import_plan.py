"""계획 항목 가져오기: CSV · 엑셀(.xlsx) · 메모장(텍스트) · 붙여넣은 글.

가계부 가져오기(`import_ledger`)와 같은 생각이다 — **머리글을 찾아 이름으로
짝지어** 읽고, 머리글이 없으면 줄마다 금액과 분류로 보이는 토막을 찾는다.
다른 점은 읽어 내는 것이 '내역' 이 아니라 '항목' 이라는 것뿐이다.

엑셀로 내보낸 '항목' 시트를 그대로 다시 읽을 수 있게 머리글 이름을 맞춰 두었다
(내보내기 → 엑셀에서 고치기 → 다시 가져오기 가 되도록).

Qt 를 모르는 순수 파이썬이다. 읽기만 하고 계획에 넣지는 않는다 —
무엇을 넣을지는 Backend 가 미리보기로 보여 주고 사용자가 정한다.
"""
from __future__ import annotations

import re
from pathlib import Path

from .import_ledger import _clean, _decode, _rows_from_csv, parse_amount, parse_date_text, read_table
from .model import (CATEGORY_ALIASES, CATEGORY_INFO, HOUSING_BUY, HOUSING_TYPE_LIST,
                    MONTHLY_SHAPES, REPAY_METHOD_LIST, REPAY_METHODS, Category)

# 머리글 이름 짝짓기. 이름에 이 조각이 들어 있으면 그 칸으로 본다.
# **순서가 중요하다**: '월 지원금' 이 '원금'(금액) 으로 잡히지 않도록 지원금을 먼저,
# '종료 날짜' 가 '날짜'(시작일) 로 잡히지 않도록 종료일을 먼저 본다.
HEADER_KEYS: list[tuple[str, tuple[str, ...]]] = [
    ("ledger_category", ("가계부분류", "가계부", "ledger")),
    ("name", ("이름", "항목명", "항목", "name", "item")),
    ("category", ("분류", "종류", "카테고리", "category")),
    ("support", ("지원금", "보조금", "support")),
    ("monthly", ("월세", "월납", "monthly", "rent")),
    ("growth", ("상승률", "인상률", "growth")),
    # '원금 자본 포함' 이 '원금'(금액) 으로, '만기까지 묶임' 이 '만기'(종료일) 로
    # 잡히지 않도록 이들을 금액·종료일보다 먼저 본다.
    ("include_principal", ("원금자본포함", "원금포함", "자본포함")),
    ("locked", ("묶임", "묶기", "locked")),
    ("as_asset", ("자산으로", "자산", "asasset")),
    ("pay_day", ("받는날", "나가는날", "결제일", "납입일", "payday")),
    ("compound", ("복리", "compound")),
    ("after_tax", ("세후", "이자소득세", "aftertax")),
    ("repayments", ("중도상환", "중도", "repayments")),
    ("repay_method", ("상환방식", "상환방법", "repaymethod")),
    ("active", ("켜짐", "사용", "active")),
    ("rate", ("연이율", "이자율", "이율", "금리", "rate")),
    ("end", ("종료일", "만기일", "반환일", "종료", "만기", "end")),
    ("start", ("시작일", "입주일", "지출일", "수입일", "시작", "날짜", "일자", "date", "start")),
    ("amount", ("금액", "원금", "보유", "잔액", "가격", "amount", "value")),
    ("every", ("되풀이", "반복", "주기", "every")),
    # '장' 한 글자는 다른 머리글에 섞여 들기 쉬워 긴 낱말로만 본다
    ("page", ("장페이지", "페이지", "시트", "page", "sheet")),
    ("note", ("메모", "비고", "note", "memo")),
]

# 분류 이름을 못 알아볼 때 쓰는 낱말. 앞에 있는 것이 먼저다
# ('반전세' 가 '전세' 보다, '일시 수입' 이 '수입' 보다 앞).
CATEGORY_WORDS: list[tuple[str, Category]] = [
    ("현금", Category.CASH), ("자산", Category.CASH), ("잔고", Category.CASH),
    ("통장", Category.CASH), ("cash", Category.CASH),
    ("적금", Category.SAVING), ("저축", Category.SAVING), ("saving", Category.SAVING),
    ("예금", Category.BANK), ("은행", Category.BANK), ("bank", Category.BANK),
    ("대출", Category.LOAN), ("융자", Category.LOAN), ("loan", Category.LOAN),
    ("일시수입", Category.INCOME_ONCE), ("상여", Category.INCOME_ONCE),
    ("보너스", Category.INCOME_ONCE), ("퇴직금", Category.INCOME_ONCE),
    ("월수입", Category.INCOME), ("급여", Category.INCOME), ("월급", Category.INCOME),
    ("소득", Category.INCOME), ("income", Category.INCOME),
    ("관리비", Category.MAINT),
    ("반전세", Category.DEPOSIT), ("전세", Category.DEPOSIT), ("매매", Category.DEPOSIT),
    ("보증금", Category.DEPOSIT), ("주거", Category.DEPOSIT),
    ("월세", Category.RENT), ("임대료", Category.RENT), ("집세", Category.RENT),
    ("고정지출", Category.FIXED), ("보험", Category.FIXED), ("통신", Category.FIXED),
    ("구독", Category.FIXED), ("식비", Category.FIXED), ("교통", Category.FIXED),
    ("일시지출", Category.EXPENSE), ("이사비", Category.EXPENSE),
    ("수수료", Category.EXPENSE), ("지출", Category.EXPENSE),
]

# 주거 형태 이름 ('반전세' 를 '전세' 보다 먼저 보도록 긴 것부터)
_HOUSING_WORDS = sorted(HOUSING_TYPE_LIST, key=lambda x: -len(x[1]))

_PCT = re.compile(r"[-+]?\d+(?:\.\d+)?")
_NOT_A_DATE = ("계속", "일시", "없음", "무기한", "-", "—")


def _norm(s: str) -> str:
    """견주기 좋게: 공백·밑줄을 빼고 소문자로."""
    return re.sub(r"[\s_]", "", _clean(s)).lower()


def parse_percent(text: str) -> float:
    """'3.5%' '3.5' '연 3.5 %' → 3.5. 못 읽으면 0."""
    t = _clean(text)
    if not t:
        return 0.0
    m = _PCT.search(t.replace(",", ""))
    if not m:
        return 0.0
    try:
        return float(m.group())
    except ValueError:
        return 0.0


def parse_count(text: str) -> int:
    """'3' '3개월' '분기' '매년' → 개월 수. 못 읽으면 0."""
    t = _norm(text)
    if not t:
        return 0
    if "분기" in t:
        return 3
    if "반년" in t or "반기" in t:
        return 6
    if "매년" in t or "연1회" in t or "1년" in t:
        return 12
    if "매달" in t or "매월" in t:
        return 1
    m = re.search(r"\d+", t)
    return int(m.group()) if m else 0


_YES = ("예", "네", "y", "yes", "o", "true", "1", "포함", "켜짐", "사용", "묶음", "묶임")
_NO = ("아니오", "아뇨", "n", "no", "x", "false", "0", "미포함", "꺼짐", "안함", "없음")


def parse_yesno(text: str) -> bool | None:
    """'예'/'아니오' → True/False. 비었거나 못 알아보면 None (= 건드리지 않음).

    None 과 False 를 가르는 것이 중요하다 — 칸이 아예 없는 표(사람이 손으로 적은
    표)에서는 Item 의 기본값을 써야 하고, '아니오' 라고 적혀 있으면 그대로 꺼야 한다.
    """
    t = _norm(text)
    if not t:
        return None
    for w in _NO:                       # '아니오' 를 '예' 보다 먼저 본다
        if t.startswith(w):
            return False
    for w in _YES:
        if t.startswith(w):
            return True
    return None


def parse_day(text: str) -> int:
    """'25일' '매달 25일' '25' → 25. 1~31 밖이거나 못 읽으면 0."""
    m = re.search(r"\d+", _norm(text))
    if not m:
        return 0
    d = int(m.group())
    return d if 1 <= d <= 31 else 0


def parse_repay_method(text: str) -> tuple[str, float]:
    """'원리금 균등' '매달 원금의 % (1.5%)' → (방식 키, 매달 상환율 %).

    내보낼 때 쓴 이름('만기 일시 상환' …) 을 그대로 되읽는다. 못 알아보면
    ("", 0.0) 을 돌려주고 Item 이 알아서 정하게 둔다.
    """
    t = _norm(text)
    if not t:
        return "", 0.0
    pct = parse_percent(text)
    for key, label in REPAY_METHOD_LIST:
        if _norm(label) in t or key in t:
            return key, (pct if key == "rate" else 0.0)
    return ("rate", pct) if pct > 0 else ("", 0.0)


def parse_repayments(text: str, default_year: int | None = None) -> list[dict]:
    """'2027-01-01 5,000,000원, 2028-01-01 3,000,000원' → [{date, amount}, …].

    금액 안에도 쉼표가 있어서 쉼표로 자를 수 없다. 날짜+금액 짝을 찾아 읽는다.
    """
    out: list[dict] = []
    for d, a in re.findall(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})\s*([\d,]+)", _clean(text)):
        day = parse_date_text(d, default_year)
        amt = parse_amount(a)
        if day and amt:
            out.append({"date": day, "amount": abs(float(amt))})
    return out


def match_category(text: str) -> tuple[Category | None, str]:
    """적힌 분류 이름 → (분류, 주거 형태). 못 알아보면 (None, "").

    '주거 (전세)' 처럼 괄호 안에 주거 형태가 적혀 있으면 그것도 같이 읽는다.
    """
    raw = _clean(text)
    if not raw:
        return None, ""

    housing = ""
    inside = re.search(r"[(（]([^)）]*)[)）]", raw)
    if inside:
        tail = _norm(inside.group(1))
        for key, label in _HOUSING_WORDS:
            if label in tail or key == tail:
                housing = key
                break
        raw = re.sub(r"[(（][^)）]*[)）]", " ", raw)

    t = _norm(raw)
    if not t:
        return (Category.DEPOSIT, housing) if housing else (None, "")

    for cat in Category:                       # 분류 이름 그대로 적힌 것이 가장 분명하다
        if _norm(cat.value) == t:
            return cat, housing
    for old, new in CATEGORY_ALIASES.items():  # 예전 이름으로 적어 둔 것
        if _norm(old) == t:
            return Category(new), housing

    for word, cat in CATEGORY_WORDS:
        if word in t:
            if cat == Category.DEPOSIT and not housing:
                for key, label in _HOUSING_WORDS:
                    if label in t:
                        housing = key
                        break
            return cat, housing
    return (Category.DEPOSIT, housing) if housing else (None, "")


def _date_or_blank(text: str, default_year: int | None = None) -> str:
    t = _clean(text)
    if not t or _norm(t) in [_norm(x) for x in _NOT_A_DATE]:
        return ""
    # '2027-05-01 반환' 처럼 뒤에 말이 붙어 있어도 날짜만 읽는다
    return parse_date_text(t, default_year)


def _row_dict(name: str, cat: Category, housing: str, amount: float, *, rate: float = 0.0,
              start: str = "", end: str = "", monthly: float = 0.0, growth: float = 0.0,
              support: float = 0.0, every: int = 0, note: str = "",
              category_text: str = "", include_principal: bool | None = None,
              locked: bool | None = None, pay_day: int = 0, compound: bool | None = None,
              after_tax: bool | None = None, repay_method: str = "", repay_rate: float = 0.0,
              repayments: list[dict] | None = None, active: bool | None = None,
              ledger_category: str = "", as_asset: bool | None = None,
              page: str = "") -> dict:
    """미리보기 한 줄. 분류에 뜻이 없는 값은 여기서 털어 낸다.

    예/아니오 설정은 **None 이면 '안 적혀 있다'** 는 뜻이라 Item 의 기본값을 쓴다
    (사람이 손으로 적은 표에는 이런 칸이 아예 없다).
    """
    info = CATEGORY_INFO[cat]
    mode = info["date_mode"]
    if cat != Category.LOAN:              # 대출에서만 뜻이 있는 것들
        include_principal, repay_method, repay_rate, repayments = None, "", 0.0, None
    elif repay_method not in REPAY_METHODS:
        repay_method = ""
    if cat != Category.SAVING:
        locked = None
    if cat != Category.DEPOSIT:
        as_asset = None
    if not info["uses_rate"]:
        compound, after_tax = None, None
    if info["shape"] not in MONTHLY_SHAPES:
        pay_day = 0
    if not info["uses_rate"]:
        rate = 0.0
    if not info.get("uses_growth"):
        growth = 0.0
    if not info.get("uses_support"):
        support = 0.0
    if cat != Category.DEPOSIT:
        housing, monthly = "", 0.0
    if mode == "":
        start, end = "", ""
    elif mode == "once" and not info.get("returnable"):
        end = ""
    if cat not in (Category.EXPENSE, Category.INCOME_ONCE):
        every = 0
    return {
        "name": (name or "").strip() or cat.value,
        "category": cat.value,
        "categoryText": (category_text or "").strip(),
        "housing": housing,
        "amount": float(max(0.0, amount)),
        "rate": max(0.0, rate),
        "start": start, "end": end,
        "monthly": float(max(0.0, monthly)),
        "growth": max(0.0, growth),
        "support": float(max(0.0, support)),
        "every": max(0, every),
        "note": (note or "").strip(),
        # 아래는 '적혀 있으면 그대로, 없으면 기본값' 인 설정들이다
        "includePrincipal": True if include_principal is None else bool(include_principal),
        "locked": bool(locked),
        "payDay": min(31, max(0, int(pay_day or 0))),
        "compound": bool(compound),
        "afterTax": bool(after_tax),
        "repayMethod": repay_method,
        "repayRate": max(0.0, repay_rate),
        "repayments": list(repayments or []),
        "active": True if active is None else bool(active),
        "ledgerCategory": (ledger_category or "").strip(),
        "asAsset": bool(as_asset),
        "page": (page or "").strip(),
    }


# ───────────────────────── 표 (머리글 있는 파일)

def find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """머리글 줄을 찾아 (줄 번호, {칸이름: 열 번호}). 못 찾으면 (-1, {})."""
    best: tuple[int, dict[str, int]] = (-1, {})
    for i, row in enumerate(rows[:15]):
        found: dict[str, int] = {}
        for col, cell in enumerate(row):
            label = _norm(cell)
            if not label:
                continue
            for key, words in HEADER_KEYS:
                if key in found:
                    continue
                if any(w in label for w in words):
                    found[key] = col
                    break
        # 금액은 꼭 있어야 하고, 이름이나 분류 중 하나는 있어야 항목이라 할 수 있다
        if "amount" in found and ({"name", "category"} & set(found)) and len(found) > len(best[1]):
            best = (i, found)
    return best


def rows_from_table(rows: list[list[str]], default_year: int | None = None) -> tuple[list[dict], list[str]]:
    """머리글을 찾아 표를 항목으로. (항목, 건너뛴 까닭들)"""
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
        name = _clean(cell(row, "name"))
        cat_text = _clean(cell(row, "category"))
        cat, housing = match_category(cat_text)
        if cat is None:                       # 분류 칸이 없거나 못 알아보면 이름에서 찾아본다
            cat, housing = match_category(name)
        if cat is None:
            label = cat_text or name
            problems.append(f"{n}번째 줄: 분류를 못 알아봤습니다 ('{label[:20]}')")
            continue

        amount = parse_amount(cell(row, "amount"))
        if amount is None:
            problems.append(f"{n}번째 줄: 금액을 못 읽었습니다 ('{cell(row, 'amount')[:20]}')")
            continue

        # 이름 뒤의 '(꺼짐)' 은 꺼진 항목을 나타내던 꼬리다. 이제는 '켜짐' 칸에
        # 적지만, 꼬리만 있는 파일도 알아보고 떼어 낸다.
        plain = re.sub(r"\s*[(（]\s*꺼짐\s*[)）]\s*$", "", name).strip()
        off_in_name = plain != name
        name = plain
        active = parse_yesno(cell(row, "active"))
        if active is None and off_in_name:
            active = False
        method, repay_rate = parse_repay_method(cell(row, "repay_method"))
        out.append(_row_dict(
            name, cat, housing, abs(amount),
            rate=parse_percent(cell(row, "rate")),
            start=_date_or_blank(cell(row, "start"), default_year),
            end=_date_or_blank(cell(row, "end"), default_year),
            monthly=abs(parse_amount(cell(row, "monthly")) or 0.0),
            growth=parse_percent(cell(row, "growth")),
            support=abs(parse_amount(cell(row, "support")) or 0.0),
            every=parse_count(cell(row, "every")),
            page=cell(row, "page"),
            note=_clean(cell(row, "note")),
            category_text=cat_text,
            include_principal=parse_yesno(cell(row, "include_principal")),
            locked=parse_yesno(cell(row, "locked")),
            pay_day=parse_day(cell(row, "pay_day")),
            compound=parse_yesno(cell(row, "compound")),
            after_tax=parse_yesno(cell(row, "after_tax")),
            repay_method=method,
            repay_rate=repay_rate,
            repayments=parse_repayments(cell(row, "repayments"), default_year),
            active=active,
            ledger_category=_clean(cell(row, "ledger_category")),
            as_asset=parse_yesno(cell(row, "as_asset")),
        ))
    return split_rent_rows(out), problems


def split_rent_rows(rows: list[dict]) -> list[dict]:
    """'주거' 줄에 월세가 함께 적혀 있으면 월세 줄을 따로 만든다.

    주거 항목에는 월세 칸이 없다 (월세는 '월세' 분류로 선다). 가져온 것도 같은
    모양이 되게 한 줄을 보증금 줄 + 월세 줄 둘로 갈라 놓는다. 미리보기도 둘로
    보이므로 '몇 개를 넣습니다' 와 실제로 들어가는 수가 어긋나지 않는다.
    """
    out: list[dict] = []
    for r in rows:
        rent = r.get("monthly") or 0.0
        if (r["category"] == Category.DEPOSIT.value and rent > 0
                and r.get("housing") != HOUSING_BUY):
            r = dict(r)
            r["monthly"] = 0.0
            out.append(r)
            out.append(_row_dict(f"{r['name']} 월세".strip(), Category.RENT, "", rent,
                                 start=r.get("start", ""), end=r.get("end", ""),
                                 category_text="월세"))
            continue
        out.append(r)
    return out


# ───────────────────────── 머리글이 없는 글 (메모장)

def rows_from_lines(text: str, default_year: int | None = None) -> tuple[list[dict], list[str]]:
    """'월세 600,000' '전세 보증금 주거 1억 5천' 처럼 적어 둔 줄을 읽는다.

    줄마다 **금액으로 보이는 토막**과 **분류로 보이는 토막**을 찾고, 남은 말을
    이름으로 삼는다. '3.5%' 가 섞여 있으면 연이율로, 날짜가 있으면 시작일로 본다.
    """
    out: list[dict] = []
    problems: list[str] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"(?<!\d),(?!\d)|\s+", line) if p]
        if len(parts) < 2:
            continue

        amount = None
        rate = 0.0
        start = ""
        rest: list[str] = []
        for p in parts:
            if "%" in p:
                rate = parse_percent(p)
                continue
            if not start and parse_date_text(p, default_year):
                start = parse_date_text(p, default_year)
                continue
            v = parse_amount(p) if amount is None else None
            if v is not None and abs(v) >= 1:
                amount = abs(v)
                continue
            rest.append(p)
        if amount is None:
            problems.append(f"{n}번째 줄: 금액을 못 찾았습니다 ('{line[:28]}')")
            continue

        cat, housing, cat_word = None, "", ""
        for w in rest:                          # 분류로 보이는 낱말을 하나 찾는다
            c, h = match_category(w)
            if c is not None:
                cat, housing, cat_word = c, h, w
                break
        if cat is None:                         # 낱말 하나로는 안 되면 줄 전체로 본다
            cat, housing = match_category(" ".join(rest))
        if cat is None:
            problems.append(f"{n}번째 줄: 분류를 못 알아봤습니다 ('{line[:28]}')")
            continue

        name = " ".join(w for w in rest if w != cat_word and w not in ("원", "-", "+"))
        out.append(_row_dict(name, cat, housing, amount, rate=rate, start=start,
                             category_text=cat_word))
    return out, problems


# ───────────────────────── 한 번에

def parse_text(text: str, default_year: int | None = None) -> tuple[list[dict], list[str], str]:
    """붙여넣은 글 → (항목, 까닭들, 어떻게 읽었는지)"""
    rows, how = _rows_from_csv((text or "").encode("utf-8"))
    got, problems = rows_from_table(rows, default_year)
    if got:
        return got, problems, f"머리글을 찾아 읽음 ({how})"
    got, problems = rows_from_lines(text or "", default_year)
    return got, problems, "줄마다 금액과 분류를 찾아 읽음"


def _sheets(path: Path) -> list[tuple[str, list[list[str]]]]:
    """엑셀의 **모든 시트**를 표로. 우리가 내보낸 파일은 첫 시트가 '요약' 이라서
    첫 시트만 보면 항목을 영영 못 찾는다. '항목' 이 이름에 든 시트를 먼저 본다."""
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    out: list[tuple[str, list[list[str]]]] = []
    for name in wb.sheetnames:
        ws = wb[name]
        rows = [[_clean(c) for c in row] for row in ws.iter_rows(values_only=True)]
        out.append((name, [r for r in rows if any(c for c in r)]))
    wb.close()
    out.sort(key=lambda s: 0 if "항목" in s[0] else 1)
    return out


def parse_file(path: str | Path, default_year: int | None = None) -> tuple[list[dict], list[str], str]:
    """파일 → (항목, 까닭들, 어떻게 읽었는지). 읽을 수 없으면 예외를 낸다."""
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        last: list[str] = []
        for name, rows in _sheets(p):
            got, problems = rows_from_table(rows, default_year)
            if got:
                return got, problems, f"머리글을 찾아 읽음 (엑셀 '{name}' 시트)"
            last = problems or last
        return [], last, "엑셀에서 이름·분류·금액 머리글을 찾지 못했습니다"

    rows, how = read_table(p)
    got, problems = rows_from_table(rows, default_year)
    if got:
        return got, problems, f"머리글을 찾아 읽음 ({how})"
    text, _enc = _decode(p.read_bytes())
    got, problems = rows_from_lines(text, default_year)
    return got, problems, "줄마다 금액과 분류를 찾아 읽음"
