"""가계부: 실제로 쓰고 번 돈을 날짜별로 적고 월별·연도별로 합산한다.

계획(Plan)이 앞으로의 예상이라면 가계부(Ledger)는 지나간 실제다.
둘은 성격이 다르므로 섞지 않고, 저장 파일에만 함께 들어간다 (Workspace).
Qt 를 전혀 모르는 순수 계산 코드다.
"""
from __future__ import annotations

import calendar
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

# 결제수단. 고르지 않으면 빈 문자열("지정 안 함")이고, 여기 없는 이름도 직접 적을 수 있다
# ('신한카드' 처럼). 직접 적은 이름은 그것을 쓰는 내역이 있는 동안 목록에 남는다.
LEDGER_PAYS: list[str] = ["카드", "현금", "계좌이체", "간편결제", "자동이체"]


def kind_of(category: str) -> str:
    """분류 이름으로 수입/지출을 판정한다. 모르는 분류는 지출로 본다."""
    return INCOME if category in LEDGER_INCOME_CATEGORIES else COST


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def prev_period(period: str) -> str:
    """'2026-03' → '2026-02', '2026' → '2025'. 그 외에는 빈 문자열."""
    if len(period) == 7:
        y, m = int(period[:4]), int(period[5:7])
        return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"
    if len(period) == 4:
        return f"{int(period) - 1:04d}"
    return ""


def shift_month(ym: str, n: int) -> str:
    """'2026-03' 에서 n개월 뒤."""
    y, m = int(ym[:4]), int(ym[5:7])
    y, m = divmod(y * 12 + (m - 1) + n, 12)
    return f"{y:04d}-{m + 1:02d}"


def same_day_in(ym: str, day: int) -> str:
    """그 달에 같은 날짜. 말일을 넘으면 말일로 맞춘다 (1/31 → 2/28)."""
    y, m = int(ym[:4]), int(ym[5:7])
    return f"{y:04d}-{m:02d}-{min(day, calendar.monthrange(y, m)[1]):02d}"


@dataclass
class Entry:
    """가계부 한 줄. 날짜·분류·금액이 전부이고 금액은 언제나 0 이상이다 (부호는 kind 가 정한다)."""

    date: str                      # 'YYYY-MM-DD'
    category: str = "기타 지출"
    amount: float = 0.0
    name: str = ""                 # 쓴 곳 / 받은 곳
    kind: str = ""                 # "income" | "cost". 비우면 분류로 자동 판정
    note: str = ""
    rule: str = ""                 # 고정 지출·수입 규칙이 만든 줄이면 그 규칙 번호
    pay: str = ""                  # 결제수단 (카드·현금·계좌이체…). 비우면 지정 안 함

    def __post_init__(self) -> None:
        if self.kind not in (INCOME, COST):
            self.kind = kind_of(self.category)
        self.amount = max(0.0, float(self.amount))
        self.pay = (self.pay or "").strip()
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
                "name": self.name, "kind": self.kind, "note": self.note, "rule": self.rule,
                "pay": self.pay}

    @classmethod
    def from_dict(cls, d: dict) -> "Entry":
        return cls(
            date=str(d.get("date") or ""),
            category=str(d.get("category") or "기타 지출"),
            amount=float(d.get("amount", 0) or 0),
            name=str(d.get("name") or ""),
            kind=str(d.get("kind") or ""),
            note=str(d.get("note") or ""),
            rule=str(d.get("rule") or ""),
            pay=str(d.get("pay") or ""),
        )


@dataclass
class Fixed:
    """고정 지출·수입 규칙. 달마다 같은 내역을 저절로 적어 준다.

    규칙은 '앞으로도 계속 나갈 돈' 이고, 그것이 실제로 적힌 줄은 보통 Entry 다.
    규칙이 만든 줄에는 rule 에 규칙 번호가 남고, 규칙은 이미 적어 준 달을 done 에
    기억한다. 그래서 적힌 줄을 지워도 다시 살아나지 않는다 (지웠다는 뜻이므로).
    """

    rid: str = ""                  # 규칙 번호
    name: str = ""                 # 내는 곳 (월세, 통신비 …)
    category: str = "기타 지출"
    amount: float = 0.0
    day: int = 1                   # 매달 며칟날. 말일을 넘으면 그 달 말일로
    kind: str = ""                 # 비우면 분류로 판정
    note: str = ""
    pay: str = ""                  # 결제수단 (적어 주는 내역에 그대로 붙는다)
    start: str = ""                # 'YYYY-MM' 부터 (비우면 만드는 달부터)
    end: str = ""                  # 'YYYY-MM' 까지 (비우면 끝없이)
    active: bool = True
    done: list[str] = field(default_factory=list)   # 이미 적어 준 달

    def __post_init__(self) -> None:
        if self.kind not in (INCOME, COST):
            self.kind = kind_of(self.category)
        self.amount = max(0.0, float(self.amount))
        self.day = max(1, min(31, int(self.day or 1)))
        self.name = (self.name or "").strip()
        self.pay = (self.pay or "").strip()
        self.start = (self.start or "")[:7]
        self.end = (self.end or "")[:7]
        self.done = sorted({str(x)[:7] for x in self.done if str(x)[:7]})

    @property
    def is_income(self) -> bool:
        return self.kind == INCOME

    @property
    def signed(self) -> float:
        return self.amount if self.is_income else -self.amount

    @property
    def label(self) -> str:
        return self.name or self.category

    def covers(self, ym: str) -> bool:
        """그 달에 적을 규칙인가 (쉬는 중이면 아니다)."""
        if not self.active or len(ym) != 7:
            return False
        if self.start and ym < self.start:
            return False
        if self.end and ym > self.end:
            return False
        return True

    def months_upto(self, upto_ym: str) -> list[str]:
        """start 부터 upto_ym 까지 (end 가 있으면 거기까지) 의 달 목록."""
        if not self.active or len(upto_ym) != 7:
            return []
        first = self.start or upto_ym
        last = min(self.end, upto_ym) if self.end else upto_ym
        if first > last:
            return []
        out, ym = [], first
        while ym <= last and len(out) < 600:          # 600달이면 50년, 그 이상은 막는다
            out.append(ym)
            ym = shift_month(ym, 1)
        return out

    def entry_for(self, ym: str) -> Entry:
        """그 달에 적을 한 줄."""
        return Entry(same_day_in(ym, self.day), self.category, self.amount,
                     self.name, kind=self.kind, note=self.note, rule=self.rid,
                     pay=self.pay)

    def to_dict(self) -> dict:
        return {"rid": self.rid, "name": self.name, "category": self.category,
                "amount": self.amount, "day": self.day, "kind": self.kind,
                "note": self.note, "pay": self.pay, "start": self.start, "end": self.end,
                "active": self.active, "done": list(self.done)}

    @classmethod
    def from_dict(cls, d: dict) -> "Fixed":
        return cls(
            rid=str(d.get("rid") or ""),
            name=str(d.get("name") or ""),
            category=str(d.get("category") or "기타 지출"),
            amount=float(d.get("amount", 0) or 0),
            day=int(d.get("day", 1) or 1),
            kind=str(d.get("kind") or ""),
            note=str(d.get("note") or ""),
            pay=str(d.get("pay") or ""),
            start=str(d.get("start") or ""),
            end=str(d.get("end") or ""),
            active=bool(d.get("active", True)),
            done=list(d.get("done") or []),
        )


def sort_key(sort: str = "date"):
    """정렬 기준. 금액순일 때는 같은 금액끼리 날짜로 한 번 더 정렬한다
    (그래야 목록이 들썩이지 않는다)."""
    if sort == "amount":
        return lambda e: (e.amount, e.date)
    return lambda e: (e.date, e.amount)


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)
    budgets: dict[str, float] = field(default_factory=dict)   # 분류 → 한 달 예산(원)
    custom: dict[str, str] = field(default_factory=dict)      # 직접 만든 분류 → "income" | "cost"
    fixed: list[Fixed] = field(default_factory=list)          # 고정 지출·수입 규칙

    # ---- 분류 (기본 + 직접 만든 것) ----
    def kind_of(self, category: str) -> str:
        """직접 만든 분류를 먼저 보고, 없으면 기본 분류표를 본다."""
        k = self.custom.get(category)
        return k if k in (INCOME, COST) else kind_of(category)

    def income_categories(self) -> list[str]:
        return LEDGER_INCOME_CATEGORIES + [c for c, k in self.custom.items() if k == INCOME]

    def cost_categories(self) -> list[str]:
        return LEDGER_COST_CATEGORIES + [c for c, k in self.custom.items() if k == COST]

    def categories(self) -> list[str]:
        return self.income_categories() + self.cost_categories()

    def add_category(self, name: str, kind: str = COST) -> str:
        """분류를 하나 만든다. 만들었으면 빈 문자열, 못 만들었으면 까닭을 돌려준다."""
        name = (name or "").strip()
        if not name:
            return "이름을 적어 주세요."
        if len(name) > 12:
            return "이름이 너무 깁니다 (12자까지)."
        if name in LEDGER_CATEGORIES:
            return f"'{name}' 은 이미 있는 분류입니다."
        if name in self.custom:
            return f"'{name}' 은 이미 만들어 둔 분류입니다."
        self.custom[name] = INCOME if kind == INCOME else COST
        return ""

    def category_in_use(self, name: str) -> int:
        """그 분류로 적어 둔 내역 수."""
        return sum(1 for e in self.entries if e.category == name)

    def remove_category(self, name: str) -> str:
        """직접 만든 분류를 지운다. 지웠으면 빈 문자열, 못 지웠으면 까닭."""
        if name not in self.custom:
            return "기본 분류는 지울 수 없습니다."
        used = self.category_in_use(name)
        if used:
            return f"'{name}' 으로 적어 둔 내역이 {used}건 있습니다."
        self.custom.pop(name, None)
        self.budgets.pop(name, None)
        return ""

    # ---- 결제수단 ----
    def pays(self) -> list[str]:
        """고를 수 있는 결제수단 — 기본 목록 + 내역에 쓰인 이름 (가나다순)."""
        used = sorted({e.pay for e in self.entries if e.pay and e.pay not in LEDGER_PAYS})
        return LEDGER_PAYS + used

    def pays_used(self, period: str = "") -> list[str]:
        """그 기간에 실제로 쓴 결제수단 (가나다순). 지정 안 한 것은 빼고."""
        return sorted({e.pay for e in self.entries if e.pay and e.in_period(period)})

    def by_pay(self, period: str = "", kind: str = COST) -> list[tuple[str, float]]:
        """결제수단별 합계, 큰 금액부터. 지정 안 한 것은 '지정 안 함' 으로 묶는다."""
        totals: dict[str, float] = {}
        for e in self.entries:
            if e.kind != kind or not e.in_period(period):
                continue
            key = e.pay or "지정 안 함"
            totals[key] = totals.get(key, 0.0) + e.amount
        return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

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

    def range_summary(self, yms: list[str]) -> dict:
        """여러 달을 한꺼번에 더한 {income, cost, net, count}."""
        want = set(yms)
        income = cost = 0.0
        count = 0
        for e in self.entries:
            if e.ym not in want:
                continue
            count += 1
            if e.is_income:
                income += e.amount
            else:
                cost += e.amount
        return {"income": income, "cost": cost, "net": income - cost, "count": count}

    def range_by_category(self, yms: list[str], kind: str = COST) -> list[tuple[str, float]]:
        """여러 달의 분류별 합계, 큰 금액부터."""
        want = set(yms)
        totals: dict[str, float] = {}
        for e in self.entries:
            if e.kind != kind or e.ym not in want:
                continue
            totals[e.category] = totals.get(e.category, 0.0) + e.amount
        return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

    def recent_months(self, n: int = 12, upto: str = "") -> list[dict]:
        """최근 n개월의 {ym, label, income, cost, net, count}. 오래된 달이 앞."""
        last = upto or month_key(date.today())
        out = []
        for i in range(n - 1, -1, -1):
            ym = shift_month(last, -i)
            out.append({"ym": ym, "label": f"{int(ym[5:7])}월", **self.summary(ym)})
        return out

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

    def matches(self, e: Entry, period: str = "", query: str = "",
                kind: str = "", category: str = "", pay: str = "",
                min_amount: float = 0.0, max_amount: float = 0.0) -> bool:
        """기간·검색어·수입지출·분류·결제수단·금액 범위에 모두 맞는가. 빈 조건은 통과.

        금액은 부호를 빼고 본다 (지출 3만원과 수입 3만원이 같은 '3만원' 이다).
        최대만 넣으면 '얼마 이하', 최소만 넣으면 '얼마 이상' 이 된다.
        """
        if not e.in_period(period):
            return False
        if min_amount > 0 and e.amount < min_amount:
            return False
        if max_amount > 0 and e.amount > max_amount:
            return False
        if kind in (INCOME, COST) and e.kind != kind:
            return False
        if category and e.category != category:
            return False
        if pay and e.pay != pay:
            return False
        if query:
            q = query.strip().lower()
            if q and q not in f"{e.name} {e.category} {e.note} {e.pay}".lower():
                return False
        return True

    def search(self, period: str = "", query: str = "", kind: str = "", category: str = "",
               pay: str = "", min_amount: float = 0.0, max_amount: float = 0.0,
               sort: str = "date", desc: bool = True) -> list[Entry]:
        rows = [e for e in self.entries
                if self.matches(e, period, query, kind, category, pay, min_amount, max_amount)]
        rows.sort(key=sort_key(sort), reverse=desc)
        return rows

    def categories_used(self, period: str = "") -> list[str]:
        """그 기간에 실제로 쓴 분류 (가나다순)."""
        return sorted({e.category for e in self.entries if e.in_period(period)})

    def has_name(self, period: str, name: str) -> bool:
        """그 기간에 같은 이름의 내역이 이미 있는가 (앞뒤 공백·대소문자 무시)."""
        key = (name or "").strip().lower()
        if not key:
            return False
        return any(e.name.strip().lower() == key for e in self.entries if e.in_period(period))

    def day_total(self, day: str) -> float:
        """그 날 하루의 수지 (수입 - 지출)."""
        return sum(e.signed for e in self.entries if e.date == day)

    # ---- 분류별 예산 ----
    def set_budget(self, category: str, amount: float) -> None:
        """한 달 예산을 정한다. 0 이하면 지운다."""
        if not category:
            return
        if amount and amount > 0:
            self.budgets[category] = float(amount)
        else:
            self.budgets.pop(category, None)

    def budget_of(self, category: str) -> float:
        return float(self.budgets.get(category, 0.0))

    def has_budgets(self) -> bool:
        return any(v > 0 for v in self.budgets.values())

    def period_months(self, period: str) -> int:
        """예산을 몇 달치로 볼지. 'YYYY-MM' 이면 1, 'YYYY' 면 12."""
        return 1 if len(period) == 7 else (12 if len(period) == 4 else 0)

    def budget_rows(self, period: str = "") -> list[dict]:
        """그 기간의 분류별 예산 현황.
        예산을 정했거나 실제로 쓴 분류만, 많이 쓴 비율 순으로.
        {category, limit, spent, left, ratio, over}"""
        months = self.period_months(period) or 1
        spent: dict[str, float] = {}
        for e in self.entries:
            if e.is_income or not e.in_period(period):
                continue
            spent[e.category] = spent.get(e.category, 0.0) + e.amount

        names = {c for c, v in self.budgets.items() if v > 0} | set(spent)
        rows = []
        for c in names:
            limit = self.budget_of(c) * months
            used = spent.get(c, 0.0)
            rows.append({
                "category": c,
                "limit": limit,
                "spent": used,
                "left": limit - used,
                "ratio": (used / limit) if limit > 0 else 0.0,
                "over": limit > 0 and used > limit,
            })
        # 예산이 있는 것 먼저, 그 안에서 많이 쓴 비율 순, 예산 없는 것은 금액 순
        rows.sort(key=lambda r: (r["limit"] <= 0, -r["ratio"], -r["spent"]))
        return rows

    def budget_totals(self, period: str = "") -> dict:
        """{limit, spent, left, ratio, over, count} — 예산을 정한 분류만 더한다."""
        months = self.period_months(period) or 1
        limit = sum(v for v in self.budgets.values() if v > 0) * months
        spent = 0.0
        count = 0
        for r in self.budget_rows(period):
            if r["limit"] > 0:
                spent += r["spent"]
                count += 1
        return {"limit": limit, "spent": spent, "left": limit - spent,
                "ratio": (spent / limit) if limit > 0 else 0.0,
                "over": limit > 0 and spent > limit, "count": count}

    def budget_from_period(self, period: str) -> int:
        """그 기간에 실제로 쓴 금액(월평균)을 예산으로 삼는다. 정한 분류 수를 돌려준다."""
        months = self.period_months(period) or 1
        spent: dict[str, float] = {}
        for e in self.entries:
            if e.is_income or not e.in_period(period):
                continue
            spent[e.category] = spent.get(e.category, 0.0) + e.amount
        for c, v in spent.items():
            self.set_budget(c, round(v / months / 1000) * 1000)     # 천원 단위로
        return len(spent)

    # ---- 고정 지출·수입 ----
    def _rids_in_use(self) -> set[str]:
        """규칙이 쓰는 번호 + 지워진 규칙이 적어 둔 내역에 남은 번호.

        번호를 다시 쓰면 옛 규칙이 적어 둔 줄이 새 규칙의 것으로 둔갑한다.
        """
        return {f.rid for f in self.fixed} | {e.rule for e in self.entries if e.rule}

    def _new_rid(self) -> str:
        used = self._rids_in_use()
        n = 1
        while f"f{n}" in used:
            n += 1
        return f"f{n}"

    def add_fixed(self, f: Fixed, today: date | None = None) -> Fixed:
        """규칙을 하나 더한다. 번호가 없으면 붙이고, 시작 달이 없으면 이번 달로 둔다."""
        if not f.rid or f.rid in self._rids_in_use():
            f.rid = self._new_rid()
        if not f.start:
            f.start = month_key(today or date.today())
        if f.kind not in (INCOME, COST):
            f.kind = self.kind_of(f.category)
        self.fixed.append(f)
        return f

    def fixed_of(self, rid: str) -> Fixed | None:
        for f in self.fixed:
            if f.rid == rid:
                return f
        return None

    def update_fixed(self, rid: str, new: Fixed) -> bool:
        """번호와 '이미 적어 준 달' 은 그대로 두고 내용만 바꾼다."""
        old = self.fixed_of(rid)
        if old is None:
            return False
        new.rid = rid
        new.done = list(old.done)
        if new.kind not in (INCOME, COST):
            new.kind = self.kind_of(new.category)
        self.fixed[self.fixed.index(old)] = new
        return True

    def set_fixed_active(self, rid: str, on: bool) -> bool:
        f = self.fixed_of(rid)
        if f is None:
            return False
        f.active = bool(on)
        return True

    def fixed_entries(self, rid: str) -> list[Entry]:
        """그 규칙이 적어 둔 내역."""
        return [e for e in self.entries if e.rule == rid]

    def remove_fixed(self, rid: str, purge: bool = False) -> int:
        """규칙을 지운다. purge 면 그 규칙이 적어 둔 내역까지 지우고, 지운 내역 수를 돌려준다."""
        f = self.fixed_of(rid)
        if f is None:
            return -1
        self.fixed.remove(f)
        if not purge:
            return 0
        gone = self.fixed_entries(rid)
        self.entries = [e for e in self.entries if e.rule != rid]
        return len(gone)

    def apply_fixed(self, upto_ym: str = "") -> list[Entry]:
        """upto_ym 까지 아직 적지 않은 달을 모두 적는다 (앱을 열 때·규칙을 만들 때 부른다)."""
        upto = upto_ym or month_key(date.today())
        made = []
        for f in self.fixed:
            for ym in f.months_upto(upto):
                if ym in f.done:
                    continue                      # 이미 적었다 (지웠더라도 되살리지 않는다)
                made.append(self.add(f.entry_for(ym)))
                f.done.append(ym)
            f.done.sort()
        return made

    def fixed_totals(self) -> dict:
        """쉬지 않는 규칙의 한 달 합계 {income, cost, net, count}."""
        income = cost = 0.0
        count = 0
        for f in self.fixed:
            if not f.active:
                continue
            count += 1
            if f.is_income:
                income += f.amount
            else:
                cost += f.amount
        return {"income": income, "cost": cost, "net": income - cost, "count": count}

    # ---- 반복 / 복사 ----
    def repeat(self, entry: Entry, months: int) -> list[Entry]:
        """같은 내역을 다음 달부터 months-1 번 더 넣는다 (entry 자신은 이미 들어있다고 본다)."""
        made = []
        for i in range(1, max(1, months)):
            ym = shift_month(entry.ym, i)
            made.append(self.add(Entry(same_day_in(ym, entry.day.day), entry.category,
                                       entry.amount, entry.name, kind=entry.kind,
                                       note=entry.note, pay=entry.pay)))
        return made

    def copy_month(self, src_ym: str, dst_ym: str) -> list[Entry]:
        """한 달치를 통째로 다른 달에 복사한다. 이미 같은 날짜·분류·금액이 있으면 건너뛴다."""
        if not src_ym or not dst_ym or src_ym == dst_ym:
            return []
        exists = {(e.date, e.category, e.amount) for e in self.entries if e.ym == dst_ym}
        made = []
        for e in sorted((x for x in self.entries if x.ym == src_ym), key=lambda x: x.date):
            d = same_day_in(dst_ym, e.day.day)
            key = (d, e.category, e.amount)
            if key in exists:
                continue
            exists.add(key)
            made.append(self.add(Entry(d, e.category, e.amount, e.name, kind=e.kind,
                                       note=e.note, pay=e.pay)))
        return made

    # ---- 저장 / 불러오기 ----
    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries],
                "budgets": {k: v for k, v in self.budgets.items() if v > 0},
                "custom": dict(self.custom),
                "fixed": [f.to_dict() for f in self.fixed]}

    @classmethod
    def from_dict(cls, d: dict | None) -> "Ledger":
        if not d:
            return cls()
        budgets = {}
        for k, v in (d.get("budgets") or {}).items():
            try:
                if float(v) > 0:
                    budgets[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        custom = {}
        for k, v in (d.get("custom") or {}).items():
            name = str(k).strip()
            if name and name not in LEDGER_CATEGORIES:
                custom[name] = INCOME if str(v) == INCOME else COST
        fixed = [Fixed.from_dict(x) for x in d.get("fixed") or [] if isinstance(x, dict)]
        return cls([Entry.from_dict(x) for x in d.get("entries", []) if isinstance(x, dict)],
                   budgets, custom, fixed)


def sample_ledger(basis: date | None = None) -> Ledger:
    """예시 데이터용 가계부 — 최근 두 달치."""
    b = basis or date.today()
    y, m = b.year, b.month
    prev_y, prev_m = (y, m - 1) if m > 1 else (y - 1, 12)
    lg = Ledger()
    for yy, mm in ((prev_y, prev_m), (y, m)):
        lg.add(Entry(f"{yy:04d}-{mm:02d}-25", "급여", 2_000_000, "회사", pay="계좌이체"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-05", "주거/관리비", 600_000, "월세·관리비", pay="자동이체"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-07", "식비", 420_000, "장보기·외식", pay="카드"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-12", "통신", 88_000, "휴대폰", pay="자동이체"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-15", "교통", 110_000, "대중교통", pay="카드"))
        lg.add(Entry(f"{yy:04d}-{mm:02d}-20", "문화/여가", 95_000, "영화·구독", pay="간편결제"))
    lg.add(Entry(f"{y:04d}-{m:02d}-10", "상여금", 500_000, "성과급"))
    for c, v in (("식비", 400_000), ("주거/관리비", 600_000), ("교통", 100_000),
                 ("통신", 90_000), ("문화/여가", 80_000)):
        lg.set_budget(c, v)
    return lg
