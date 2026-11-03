"""가계부: 실제로 쓰고 번 돈을 날짜별로 적고 월별·연도별로 합산한다.

계획(Plan)이 앞으로의 예상이라면 가계부(Ledger)는 지나간 실제다.
둘은 성격이 다르므로 섞지 않고, 저장 파일에만 함께 들어간다 (Workspace).
Qt 를 전혀 모르는 순수 계산 코드다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .model import parse_date

# 가계부 분류 (계획의 분류와 별개다 — 가계부는 실제 씀씀이 기준으로 나눈다)
LEDGER_INCOME_CATEGORIES: list[str] = [
    "급여", "부업", "상여금", "이자/배당", "용돈", "기타 수입",
]
LEDGER_COST_CATEGORIES: list[str] = [
    "식비", "주거/관리비", "교통", "통신", "보험", "의료", "생활용품",
    "문화/여가", "경조사", "교육", "저축/투자", "대출 상환", "기타 지출",
]
LEDGER_CATEGORIES: list[str] = LEDGER_INCOME_CATEGORIES + LEDGER_COST_CATEGORIES

INCOME, COST = "income", "cost"


def kind_of(category: str) -> str:
    """분류 이름으로 수입/지출을 판정한다. 모르는 분류는 지출로 본다."""
    return INCOME if category in LEDGER_INCOME_CATEGORIES else COST


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


@dataclass
class Entry:
    """가계부 한 줄. 날짜·분류·금액이 전부이고 금액은 언제나 0 이상이다 (부호는 kind 가 정한다)."""

    date: str                      # 'YYYY-MM-DD'
    category: str = "기타 지출"
    amount: float = 0.0
    name: str = ""                 # 쓴 곳 / 받은 곳
    kind: str = ""                 # "income" | "cost". 비우면 분류로 자동 판정
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in (INCOME, COST):
            self.kind = kind_of(self.category)
        self.amount = max(0.0, float(self.amount))
        d = parse_date(self.date)
        self.date = d.isoformat() if d else date.today().isoformat()

    @property
    def day(self) -> date:
        return parse_date(self.date) or date.today()

    @property
    def ym(self) -> str:
        """'YYYY-MM'"""
        return self.date[:7]

    @property
    def year(self) -> str:
        return self.date[:4]

    @property
    def is_income(self) -> bool:
        return self.kind == INCOME

    @property
    def signed(self) -> float:
        """수입은 양수, 지출은 음수."""
        return self.amount if self.is_income else -self.amount

    def in_period(self, period: str) -> bool:
        """period 는 'YYYY'(한 해) 또는 'YYYY-MM'(한 달), 빈 문자열이면 전체."""
        return not period or self.date.startswith(period)

    def to_dict(self) -> dict:
        return {"date": self.date, "category": self.category, "amount": self.amount,
                "name": self.name, "kind": self.kind, "note": self.note}

    @classmethod
    def from_dict(cls, d: dict) -> "Entry":
        return cls(
            date=str(d.get("date") or ""),
            category=str(d.get("category") or "기타 지출"),
            amount=float(d.get("amount", 0) or 0),
            name=str(d.get("name") or ""),
            kind=str(d.get("kind") or ""),
            note=str(d.get("note") or ""),
        )


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)

    # ---- 목록 조작 ----
    def add(self, entry: Entry) -> Entry:
        self.entries.append(entry)
        return entry

    def remove(self, index: int) -> Entry | None:
        if 0 <= index < len(self.entries):
            return self.entries.pop(index)
        return None

    def update(self, index: int, entry: Entry) -> bool:
        if 0 <= index < len(self.entries):
            self.entries[index] = entry
            return True
        return False

    def clear(self) -> None:
        self.entries.clear()

    # ---- 기간별 조회 ----
    def in_period(self, period: str = "") -> list[Entry]:
        """최신 날짜가 위로 오도록 정렬해서 돌려준다."""
        rows = [e for e in self.entries if e.in_period(period)]
        rows.sort(key=lambda e: e.date, reverse=True)
        return rows

    def months(self) -> list[str]:
        """기록이 있는 달 ('YYYY-MM'), 최신순."""
        return sorted({e.ym for e in self.entries}, reverse=True)

    def years(self) -> list[str]:
        """기록이 있는 해, 최신순."""
        return sorted({e.year for e in self.entries}, reverse=True)

    def months_of(self, year: str) -> list[str]:
        return sorted({e.ym for e in self.entries if e.year == year}, reverse=True)

    # ---- 집계 ----
    def summary(self, period: str = "") -> dict:
        """{income, cost, net, count}"""
        income = cost = 0.0
        count = 0
        for e in self.entries:
            if not e.in_period(period):
                continue
            count += 1
            if e.is_income:
                income += e.amount
            else:
                cost += e.amount
        return {"income": income, "cost": cost, "net": income - cost, "count": count}

    def by_category(self, period: str = "", kind: str = COST) -> list[tuple[str, float]]:
        """분류별 합계, 큰 금액부터."""
        totals: dict[str, float] = {}
        for e in self.entries:
            if e.kind != kind or not e.in_period(period):
                continue
            totals[e.category] = totals.get(e.category, 0.0) + e.amount
        return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

    def year_months(self, year: str) -> list[dict]:
        """그 해 1~12월의 {month, ym, income, cost, net}. 기록이 없는 달도 0 으로 채운다."""
        out = []
        for m in range(1, 13):
            ym = f"{year}-{m:02d}"
            s = self.summary(ym)
            out.append({"month": m, "ym": ym, **s})
        return out

    def totals_by_year(self) -> list[dict]:
        """해마다 {year, income, cost, net}, 최신순."""
        return [{"year": y, **self.summary(y)} for y in self.years()]

    # ---- 저장 / 불러오기 ----
    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Ledger":
        if not d:
            return cls()
        return cls([Entry.from_dict(x) for x in d.get("entries", []) if isinstance(x, dict)])


def sample_ledger(basis: date | None = None) -> Ledger:
    """예시 데이터용 가계부 — 최근 두 달치."""
    b = basis or date.today()
    y, m = b.year, b.month
    prev_y, prev_m = (y, m - 1) if m > 1 else (y - 1, 12)
    lg = Ledger()
    for yy, mm in ((prev_y, prev_m), (y, m)):
        lg.add(Entry(f"{yy:04d}-{mm:02d}-25", "급여", 2_000_000, "회사"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-05", "주거/관리비", 600_000, "월세·관리비"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-07", "식비", 420_000, "장보기·외식"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-12", "통신", 88_000, "휴대폰"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-15", "교통", 110_000, "대중교통"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-20", "문화/여가", 95_000, "영화·구독"))
    lg.add(Entry(f"{y:04d}-{m:02d}-10", "상여금", 500_000, "성과급"))
    return lg
