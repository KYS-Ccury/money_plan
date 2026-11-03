"""자본금 계산기 데이터 모델.

항목(Item)을 리스트로 관리하고, 기준일·기간(개월)·목표 자본금을 기준으로
보유 자금 / 필요 자금 / 순 자본 / 목표 달성률을 계산한다.
UI(QML)와 분리되어 있어 단독으로 테스트할 수 있다.

시간 축: 기준일(Plan.start_date)을 0개월로 놓고, m개월 시점의 순 자본을 계산한다.
대출처럼 날짜 범위가 있는 항목은 그 범위에 해당하는 달에만 효과가 난다.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    DEPOSIT = "보증금"          # 일시 지출 (지출일 지정 가능)
    RENT = "월세"               # 월 지출 (적용 기간)
    MAINT = "관리비"            # 월 지출 (적용 기간)
    FIXED = "고정 지출(월)"     # 월 지출 (적용 기간) — 보험료·통신비·식비처럼 매달 나가는 돈
    LOAN = "대출/이자"          # 원금은 자본(대출 기간 동안), 이자는 월 지출(대출 기간 동안)
    BANK = "은행 예금"          # 원금은 자본, 이자는 월 수입
    CASH = "현금/자산"          # 자본
    EXPENSE = "일시 지출"       # 일시 지출 (지출일 지정 가능)
    INCOME = "기타 수입(월)"    # 월 수입 (적용 기간)
    INCOME_ONCE = "일시 수입"   # 일시 수입 (수입일 지정 가능)


# 예전 저장 파일의 분류 이름 → 현재 이름
CATEGORY_ALIASES: dict[str, str] = {
    "기타 지출(일시)": Category.EXPENSE.value,
}

# 분류별 특성
#   amount_label : 금액 입력칸 이름
#   uses_rate    : 연이율을 쓰는가
#   date_mode    : ""(날짜 없음) | "range"(시작일~종료일) | "once"(하루에 끝나는 돈)
#   flow         : "cost"(나가는 돈) | "income"(들어오는 돈) | ""(자본·대출처럼 둘 다 아닌 것)
CATEGORY_INFO: dict[Category, dict] = {
    Category.DEPOSIT: {"amount_label": "보증금", "uses_rate": False, "date_mode": "once", "flow": "cost",
                       "hint": "한 번만 나가는 돈. 지출일을 비우면 기준일에 나갑니다"},
    Category.RENT: {"amount_label": "월세", "uses_rate": False, "date_mode": "range", "flow": "cost",
                    "hint": "적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속)"},
    Category.MAINT: {"amount_label": "월 관리비", "uses_rate": False, "date_mode": "range", "flow": "cost",
                     "hint": "적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속)"},
    Category.FIXED: {"amount_label": "월 고정 지출", "uses_rate": False, "date_mode": "range", "flow": "cost",
                     "hint": "보험료·통신비·식비·교통비처럼 적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속)"},
    Category.LOAN: {"amount_label": "대출 원금", "uses_rate": True, "date_mode": "range", "flow": "",
                    "hint": "대출 기간 동안 원금은 자본에 포함, 이자는 잔액 기준 매달 지출. 정기·중도 상환으로 잔액을 줄일 수 있고 종료일에 잔액 상환"},
    Category.BANK: {"amount_label": "예금액", "uses_rate": True, "date_mode": "", "flow": "",
                    "hint": "원금은 자본에 포함, 이자는 매달 수입"},
    Category.CASH: {"amount_label": "보유 금액", "uses_rate": False, "date_mode": "", "flow": "",
                    "hint": "현재 가진 자본"},
    Category.EXPENSE: {"amount_label": "지출액", "uses_rate": False, "date_mode": "once", "flow": "cost",
                       "hint": "이사비·수수료처럼 한 번만 나가는 돈. 지출일을 비우면 기준일에 나갑니다"},
    Category.INCOME: {"amount_label": "월 수입", "uses_rate": False, "date_mode": "range", "flow": "income",
                      "hint": "급여·부업처럼 적용 기간 동안 매달 들어오는 돈 (종료일 비우면 계속)"},
    Category.INCOME_ONCE: {"amount_label": "수입액", "uses_rate": False, "date_mode": "once", "flow": "income",
                           "hint": "상여금·퇴직금·만기 적금처럼 한 번만 들어오는 돈. 수입일을 비우면 기준일에 들어옵니다"},
}

# 대출 상환 방식
REPAY_METHOD_LIST: list[tuple[str, str]] = [
    ("bullet", "만기 일시 상환"),      # 이자만 내다가 종료일에 원금 전액
    ("equal_principal", "원금 균등"),  # 매달 같은 원금 + 잔액 이자 (상환액이 점점 줄어듦)
    ("equal_payment", "원리금 균등"),  # 매달 같은 금액 (은행 대출의 기본)
    ("rate", "매달 원금의 %"),         # 원금의 n% 씩
]
REPAY_METHODS: dict[str, str] = dict(REPAY_METHOD_LIST)
TERM_METHODS = ("equal_principal", "equal_payment")   # 만기(종료일)가 있어야 계산되는 방식

# 매달 같은 금액이 나가는 분류 (적용 기간 동안)
MONTHLY_COST_CATEGORIES = (Category.RENT, Category.MAINT, Category.FIXED)
# 한 번만 나가는 분류
ONCE_COST_CATEGORIES = (Category.DEPOSIT, Category.EXPENSE)
# 매달 들어오는 분류 (적용 기간 동안)
MONTHLY_INCOME_CATEGORIES = (Category.INCOME,)
# 한 번만 들어오는 분류
ONCE_INCOME_CATEGORIES = (Category.INCOME_ONCE,)

CATEGORY_LIST: list[Category] = list(Category)


# ---------------------------------------------------------------- 날짜 유틸
def parse_date(s: str | None) -> date | None:
    """'YYYY-MM-DD' 또는 'YYYY-MM' → date. 비었거나 형식이 틀리면 None."""
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) == 7:
            return date.fromisoformat(s + "-01")
        return date.fromisoformat(s)
    except ValueError:
        return None


def month_offset(basis: date, d: date) -> int:
    """basis 기준으로 d 가 몇 개월 뒤인지 (월 단위, 일은 무시)."""
    return (d.year - basis.year) * 12 + (d.month - basis.month)


def add_months(basis: date, m: int) -> date:
    """basis 에서 m개월 뒤의 같은 달 1일."""
    y, mo = divmod(basis.month - 1 + m, 12)
    return date(basis.year + y, mo + 1, 1)


@dataclass
class Item:
    name: str
    category: Category
    amount: float = 0.0             # 원
    rate: float = 0.0               # 연이율 % (대출/예금에서만 사용)
    include_principal: bool = True  # 대출 원금을 자본에 포함할지
    start_date: str | None = None   # 'YYYY-MM-DD' (대출 시작일). None 이면 기준일부터
    end_date: str | None = None     # 'YYYY-MM-DD' (대출 종료일). None 이면 무기한
    repayments: list[dict] = field(default_factory=list)  # 중도 상환 [{"date": "YYYY-MM-DD", "amount": 원}]
    monthly_repay_rate: float = 0.0  # 매달 원금의 몇 % 씩 정기 상환 ("rate" 방식에서만)
    repay_method: str = ""           # 상환 방식. "" 이면 자동 (상환율이 있으면 rate, 없으면 bullet)

    def __post_init__(self) -> None:
        if self.repay_method not in REPAY_METHODS:
            self.repay_method = "rate" if self.monthly_repay_rate > 0 else "bullet"

    # ---- 기본 파생 값 ----
    def monthly_interest(self) -> float:
        """연이율 기준 월 이자(원)."""
        if not CATEGORY_INFO[self.category]["uses_rate"]:
            return 0.0
        return self.amount * (self.rate / 100.0) / 12.0

    @property
    def date_mode(self) -> str:
        """"" | "range"(시작일~종료일) | "once"(지출일 하루)"""
        return CATEGORY_INFO[self.category]["date_mode"]

    @property
    def uses_dates(self) -> bool:
        """적용 기간(시작일~종료일)을 쓰는 항목인가."""
        return self.date_mode == "range"

    @property
    def flow(self) -> str:
        """"cost"(나가는 돈) | "income"(들어오는 돈) | ""(그 외)"""
        return CATEGORY_INFO[self.category]["flow"]

    def once_month(self, basis: date) -> int:
        """일시 지출·일시 수입이 실제로 오고 가는 개월. 날짜가 없으면 0(기준일)."""
        if self.date_mode != "once":
            return 0
        d = parse_date(self.start_date)
        return month_offset(basis, d) if d else 0

    def active_range(self, basis: date) -> tuple[int, int | None]:
        """기준일 대비 활성 구간 [start_m, end_m). 날짜를 안 쓰는 항목은 (0, None)."""
        if not self.uses_dates:
            return 0, None
        sd, ed = parse_date(self.start_date), parse_date(self.end_date)
        start_m = month_offset(basis, sd) if sd else 0
        end_m = month_offset(basis, ed) if ed else None
        return start_m, end_m

    def is_active(self, m: int, basis: date) -> bool:
        """m개월째에 이 항목(대출·월세·관리비)이 유효한가."""
        start_m, end_m = self.active_range(basis)
        return m >= start_m and (end_m is None or m < end_m)

    # ---- 중도 상환 ----
    def repayment_at(self, m: int, basis: date) -> float:
        """m개월째에 실행되는 중도 상환액 합."""
        total = 0.0
        for r in self.repayments:
            d = parse_date(r.get("date"))
            if d and month_offset(basis, d) == m:
                total += max(0.0, float(r.get("amount", 0) or 0))
        return total

    def term_months(self, basis: date) -> int | None:
        """대출 기간(개월). 종료일이 없으면 None."""
        if self.category != Category.LOAN:
            return None
        start_m, end_m = self.active_range(basis)
        return None if end_m is None else max(0, end_m - start_m)

    def monthly_rate(self) -> float:
        """월 이율 (연이율 ÷ 12)."""
        return self.rate / 100.0 / 12.0

    def monthly_repay_amount(self) -> float:
        """'매달 원금의 %' 방식의 1회 상환 원금. 다른 방식이면 0."""
        if self.category != Category.LOAN or self.repay_method != "rate":
            return 0.0
        return self.amount * max(0.0, self.monthly_repay_rate) / 100.0

    def level_payment(self, basis: date) -> float:
        """원리금 균등일 때 매달 내는 금액(원금+이자). 다른 방식이거나 만기가 없으면 0."""
        n = self.term_months(basis)
        if self.repay_method != "equal_payment" or not n:
            return 0.0
        i = self.monthly_rate()
        if i <= 0:
            return self.amount / n
        f = (1.0 + i) ** n
        return self.amount * i * f / (f - 1.0)

    def _scheduled_paid_before(self, m: int, basis: date) -> float:
        """m개월 시작 시점까지 정기 상환(방식별 일정)으로 갚은 원금 누계. 중도 상환은 포함하지 않는다."""
        if self.category != Category.LOAN:
            return 0.0
        start_m, end_m = self.active_range(basis)
        k = m - start_m
        if k <= 0:
            return 0.0
        if self.repay_method == "rate":
            per = self.monthly_repay_amount()
            if per <= 0:
                return 0.0
            upto = k if end_m is None else min(k, end_m - start_m)
            return per * max(0, upto)
        n = self.term_months(basis)
        if self.repay_method not in TERM_METHODS or not n:
            return 0.0                                   # 만기 일시 상환: 기간 중 원금 상환 없음
        k = min(k, n)
        if self.repay_method == "equal_principal":
            return self.amount * k / n
        i = self.monthly_rate()
        if i <= 0:
            return self.amount * k / n
        f = (1.0 + i) ** n
        remaining = self.amount * (f - (1.0 + i) ** k) / (f - 1.0)
        return self.amount - remaining

    def remaining_at(self, m: int, basis: date) -> float:
        """m개월째(달 초) 대출 잔액. 그 달까지의 중도 상환과 그 전 달까지의 정기 상환을 반영. 대출이 아니면 amount."""
        if self.category != Category.LOAN:
            return self.amount
        paid = self._scheduled_paid_before(m, basis)
        for r in self.repayments:
            d = parse_date(r.get("date"))
            if d and month_offset(basis, d) <= m:
                paid += max(0.0, float(r.get("amount", 0) or 0))
        return max(0.0, self.amount - paid)

    def regular_repay_at(self, m: int, basis: date) -> float:
        """m개월째에 일정대로 나가는 원금 상환액 (잔액이 그보다 적으면 잔액만큼)."""
        if self.category != Category.LOAN or not self.is_active(m, basis):
            return 0.0
        due = self._scheduled_paid_before(m + 1, basis) - self._scheduled_paid_before(m, basis)
        if due <= 0:
            return 0.0
        return max(0.0, min(due, self.remaining_at(m, basis)))

    def interest_at(self, m: int, basis: date) -> float:
        """m개월째 이자 = 그 달 초 잔액 × 월 이율."""
        if self.category != Category.LOAN or not self.is_active(m, basis):
            return 0.0
        return self.remaining_at(m, basis) * self.monthly_rate()

    def payment_at(self, m: int, basis: date) -> float:
        """m개월째 실제로 나가는 돈 (이자 + 원금 상환 + 중도 상환, 만기 달은 잔액까지)."""
        if self.category != Category.LOAN:
            return 0.0
        total = self.interest_at(m, basis) + self.regular_repay_at(m, basis)
        if self.is_active(m, basis):
            total += self.repayment_at(m, basis)
        _start_m, end_m = self.active_range(basis)
        if end_m is not None and m == end_m:
            total += self.remaining_at(m, basis)
        return total

    def total_interest(self, basis: date) -> float:
        """대출 기간 전체의 이자 합. 만기가 없으면 0."""
        n = self.term_months(basis)
        if not n:
            return 0.0
        start_m, _ = self.active_range(basis)
        return sum(self.interest_at(start_m + k, basis) for k in range(n))

    def months_to_payoff(self, basis: date) -> int | None:
        """원금이 다 갚아지기까지 걸리는 개월 (대출 시작 기준). 만기 일시 상환이면 None."""
        if self.category != Category.LOAN:
            return None
        if self.repay_method == "rate":
            per = self.monthly_repay_amount()
            if per <= 0:
                return None
            start_m, _ = self.active_range(basis)
            return math.ceil(self.remaining_at(start_m, basis) / per)
        if self.repay_method in TERM_METHODS:
            return self.term_months(basis)
        return None

    def total_repaid(self) -> float:
        return sum(max(0.0, float(r.get("amount", 0) or 0)) for r in self.repayments)

    # ---- 시점별 값 (m = 기준일로부터 개월) ----
    def capital_at(self, m: int, basis: date) -> float:
        """m개월 시점에 보유 자금에 더해지는 금액."""
        if self.category in (Category.CASH, Category.BANK):
            return self.amount
        if self.category == Category.LOAN and self.include_principal and self.is_active(m, basis):
            return self.remaining_at(m, basis)   # 상환한 만큼 보유 자금에서 빠진다
        return 0.0

    def once_cost(self) -> float:
        """일시 지출 금액 (날짜와 무관한 총액)."""
        if self.category in ONCE_COST_CATEGORIES:
            return self.amount
        return 0.0

    def once_cost_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 이미 나간 일시 지출. 지출일이 아직 안 왔으면 0."""
        c = self.once_cost()
        if c <= 0:
            return 0.0
        return c if m >= self.once_month(basis) else 0.0

    def once_income(self) -> float:
        """일시 수입 금액 (날짜와 무관한 총액)."""
        if self.category in ONCE_INCOME_CATEGORIES:
            return self.amount
        return 0.0

    def once_income_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 이미 들어온 일시 수입. 수입일이 아직 안 왔으면 0."""
        c = self.once_income()
        if c <= 0:
            return 0.0
        return c if m >= self.once_month(basis) else 0.0

    def monthly_cost_at(self, m: int, basis: date) -> float:
        if self.category in MONTHLY_COST_CATEGORIES:
            return self.amount if self.is_active(m, basis) else 0.0
        if self.category == Category.LOAN:
            cost = self.interest_at(m, basis)        # 그 달 초 잔액 기준
            if not self.include_principal:
                # 원금을 자본에 안 넣은 경우: 상환(중도 + 정기)은 그 달의 지출로 잡는다
                # (자본에 넣은 경우는 capital_at 이 줄어드는 것으로 반영됨)
                start_m, end_m = self.active_range(basis)
                if m >= start_m and (end_m is None or m < end_m):
                    cost += self.repayment_at(m, basis) + self.regular_repay_at(m, basis)
                if end_m is not None and m == end_m:
                    cost += self.remaining_at(m, basis)       # 만기 일시 상환
            return cost
        return 0.0

    def monthly_income_at(self, m: int, basis: date) -> float:
        if self.category in MONTHLY_INCOME_CATEGORIES:
            return self.amount if self.is_active(m, basis) else 0.0
        if self.category == Category.BANK:
            return self.monthly_interest()
        return 0.0

    def monthly_net_at(self, m: int, basis: date) -> float:
        return self.monthly_income_at(m, basis) - self.monthly_cost_at(m, basis)

    # 기준일(0개월) 시점의 값 — 목록 표시용
    def capital(self, basis: date | None = None) -> float:
        return self.capital_at(0, basis or date.today())

    def monthly_cost(self, basis: date | None = None) -> float:
        return self.monthly_cost_at(0, basis or date.today())

    def monthly_income(self, basis: date | None = None) -> float:
        return self.monthly_income_at(0, basis or date.today())

    def monthly_net(self, basis: date | None = None) -> float:
        return self.monthly_net_at(0, basis or date.today())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            name=str(d.get("name", "")),
            category=Category(CATEGORY_ALIASES.get(d.get("category"), d.get("category", Category.CASH.value))),
            amount=float(d.get("amount", 0.0)),
            rate=float(d.get("rate", 0.0)),
            include_principal=bool(d.get("include_principal", True)),
            start_date=d.get("start_date") or None,
            end_date=d.get("end_date") or None,
            repayments=[
                {"date": str(r.get("date", "")), "amount": float(r.get("amount", 0) or 0)}
                for r in (d.get("repayments") or [])
                if isinstance(r, dict)
            ],
            monthly_repay_rate=float(d.get("monthly_repay_rate", 0.0) or 0.0),
            repay_method=str(d.get("repay_method") or ""),
        )


@dataclass
class Summary:
    """기간(months)·목표(target) 기준 요약. 시점별 값은 plan 의 계산 함수를 사용한다."""
    months: int
    target: float
    capital: float          # 0개월 시점 보유 자금
    once_cost: float        # 기간 안에 나가는 일시 지출 합계
    once_income: float      # 기간 안에 들어오는 일시 수입 합계
    monthly_cost: float     # 0개월 시점 월 지출
    monthly_income: float   # 0개월 시점 월 수입
    required: float         # 기간 동안 필요한 총 자금 = 일시 지출 + 월 지출 합
    period_income: float    # 기간 동안의 수입 합 = 일시 수입 + 월 수입 합
    _net_at: callable = field(repr=False, compare=False)

    @property
    def monthly_net(self) -> float:
        return self.monthly_income - self.monthly_cost

    def net_at(self, month: int) -> float:
        """특정 개월 시점의 순 자본."""
        return self._net_at(month)

    @property
    def net(self) -> float:
        """기간 종료 시점의 순 자본."""
        return self.net_at(self.months)

    @property
    def gap(self) -> float:
        """목표 대비 차이. 양수면 초과, 음수면 부족."""
        return self.net - self.target

    @property
    def progress(self) -> float:
        """목표 달성률 0.0 ~ (1.0 이상 가능). 목표가 0 이하이면 1.0."""
        if self.target <= 0:
            return 1.0
        return max(0.0, self.net / self.target)

    MAX_LOOKAHEAD = 600

    def goal_month(self) -> int | None:
        """기준일로부터 몇 개월째에 처음 목표에 닿는지 (0 = 이미 달성). 50년 내 불가능이면 None."""
        if self.target <= 0:
            return 0
        for m in range(0, self.MAX_LOOKAHEAD + 1):
            if self.net_at(m) >= self.target:
                return m
        return None

    def months_to_goal(self) -> int | None:
        """기간 종료 이후 목표에 닿기까지 몇 달 더 걸리는지. 이미 달성이면 0, 50년 내 불가능이면 None."""
        if self.gap >= 0:
            return 0
        for extra in range(1, self.MAX_LOOKAHEAD + 1):
            if self.net_at(self.months + extra) >= self.target:
                return extra
        return None


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    months: int = 12
    target: float = 0.0
    start_date: str = field(default_factory=lambda: date.today().isoformat())  # 기준일 (0개월)
    name: str = ""                                                              # 시나리오 이름

    @property
    def basis(self) -> date:
        return parse_date(self.start_date) or date.today()

    # ---- 리스트 조작 ----
    def add(self, item: Item) -> Item:
        self.items.append(item)
        return item

    def remove(self, index: int) -> Item | None:
        if 0 <= index < len(self.items):
            return self.items.pop(index)
        return None

    def move(self, index: int, delta: int) -> None:
        j = index + delta
        if 0 <= index < len(self.items) and 0 <= j < len(self.items):
            self.items[index], self.items[j] = self.items[j], self.items[index]

    def clear(self) -> None:
        self.items.clear()

    # ---- 시점별 계산 ----
    def capital_at(self, m: int) -> float:
        b = self.basis
        return sum(i.capital_at(m, b) for i in self.items)

    def once_cost(self) -> float:
        """일시 지출 총액 (날짜와 무관)."""
        return sum(i.once_cost() for i in self.items)

    def once_cost_at(self, m: int) -> float:
        """m개월 시점까지 나간 일시 지출 합."""
        b = self.basis
        return sum(i.once_cost_at(m, b) for i in self.items)

    def once_income(self) -> float:
        """일시 수입 총액 (날짜와 무관)."""
        return sum(i.once_income() for i in self.items)

    def once_income_at(self, m: int) -> float:
        """m개월 시점까지 들어온 일시 수입 합."""
        b = self.basis
        return sum(i.once_income_at(m, b) for i in self.items)

    def monthly_cost_at(self, m: int) -> float:
        b = self.basis
        return sum(i.monthly_cost_at(m, b) for i in self.items)

    def monthly_income_at(self, m: int) -> float:
        b = self.basis
        return sum(i.monthly_income_at(m, b) for i in self.items)

    def net_at(self, m: int) -> float:
        """m개월 시점 순 자본 = 그 시점 보유 자금 - 일시 지출 + 일시 수입 + (0..m-1 개월의 월 수입 - 월 지출)."""
        b = self.basis
        flow = sum(i.monthly_net_at(k, b) for i in self.items for k in range(max(0, m)))
        return self.capital_at(m) - self.once_cost_at(m) + self.once_income_at(m) + flow

    SHORTFALL_HORIZON = 36      # 부족 경고는 최소 3년까지 살펴본다

    def shortfall(self, horizon: int | None = None) -> dict:
        """순 자본이 음수로 떨어지는 구간을 찾는다.
        {month: 처음 부족해지는 개월(없으면 None), months: 부족한 달 수,
         min_month / min_net: 가장 낮은 시점과 그때 순 자본, horizon: 살펴본 개월}"""
        h = max(self.months, self.SHORTFALL_HORIZON) if horizon is None else max(0, horizon)
        first: int | None = None
        count = 0
        min_m, min_v = 0, self.net_at(0)
        for m in range(h + 1):
            v = self.net_at(m)
            if v < min_v:
                min_m, min_v = m, v
            if v < 0:
                count += 1
                if first is None:
                    first = m
        return {"month": first, "months": count, "min_month": min_m, "min_net": min_v, "horizon": h}

    def summary(self) -> Summary:
        n = max(0, self.months)
        return Summary(
            months=n,
            target=self.target,
            capital=self.capital_at(0),
            once_cost=self.once_cost_at(n),
            once_income=self.once_income_at(n),
            monthly_cost=self.monthly_cost_at(0),
            monthly_income=self.monthly_income_at(0),
            required=self.once_cost_at(n) + sum(self.monthly_cost_at(k) for k in range(n)),
            period_income=self.once_income_at(n) + sum(self.monthly_income_at(k) for k in range(n)),
            _net_at=self.net_at,
        )

    # ---- 저장 / 불러오기 ----
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "months": self.months,
            "target": self.target,
            "start_date": self.start_date,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            items=[Item.from_dict(x) for x in d.get("items", [])],
            months=int(d.get("months", 12)),
            target=float(d.get("target", 0.0)),
            start_date=str(d.get("start_date") or date.today().isoformat()),
            name=str(d.get("name") or ""),
        )

    def copy(self) -> "Plan":
        return Plan.from_dict(self.to_dict())

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Plan":
        """계획 하나를 읽는다. 시나리오 묶음 파일이면 활성 시나리오를 돌려준다."""
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        if "scenarios" in d:
            return Workspace.from_dict(d).plan
        return cls.from_dict(d)


@dataclass
class Workspace:
    """시나리오 묶음. 각 시나리오는 독립된 Plan(항목·기간·목표·기준일)이고, 하나가 활성 상태다.
    저장 파일에는 모든 시나리오가 함께 들어간다."""

    plans: list[Plan] = field(default_factory=list)
    active: int = 0

    def __post_init__(self) -> None:
        if not self.plans:
            self.plans.append(Plan())
        for p in self.plans:
            if not p.name:
                p.name = self.new_name()
        self.active = min(max(0, self.active), len(self.plans) - 1)

    @property
    def plan(self) -> Plan:
        return self.plans[self.active]

    def names(self) -> list[str]:
        return [p.name for p in self.plans]

    def new_name(self, base: str = "시나리오") -> str:
        used = set(self.names())
        n = 1
        while f"{base} {n}" in used:
            n += 1
        return f"{base} {n}"

    def add(self, name: str = "") -> Plan:
        """빈 시나리오 추가 (기간·목표·기준일은 현재 시나리오 것을 따라감). 추가한 것이 활성화된다."""
        src = self.plan
        p = Plan(months=src.months, target=src.target, start_date=src.start_date, name=name.strip() or self.new_name())
        self.plans.append(p)
        self.active = len(self.plans) - 1
        return p

    def duplicate(self, index: int | None = None) -> Plan:
        """시나리오 복제. 복제본이 바로 뒤에 들어가고 활성화된다."""
        i = self.active if index is None else index
        src = self.plans[i]
        p = src.copy()
        p.name = self.new_name(f"{src.name} 복사")
        self.plans.insert(i + 1, p)
        self.active = i + 1
        return p

    def remove(self, index: int) -> bool:
        """마지막 하나는 지울 수 없다."""
        if len(self.plans) <= 1 or not (0 <= index < len(self.plans)):
            return False
        del self.plans[index]
        if index < self.active:
            self.active -= 1
        self.active = min(self.active, len(self.plans) - 1)
        return True

    def rename(self, index: int, name: str) -> bool:
        name = name.strip()
        if not name or not (0 <= index < len(self.plans)):
            return False
        self.plans[index].name = name
        return True

    def to_dict(self) -> dict:
        return {"version": 2, "active": self.active, "scenarios": [p.to_dict() for p in self.plans]}

    @classmethod
    def from_dict(cls, d: dict) -> "Workspace":
        if "scenarios" in d:
            return cls([Plan.from_dict(x) for x in d.get("scenarios", [])], int(d.get("active", 0)))
        return cls([Plan.from_dict(d)], 0)          # 구버전 파일: 계획 하나

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Workspace":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def sample_plan() -> Plan:
    """처음 실행 시 보여줄 예시 데이터."""
    p = Plan(months=12, target=30_000_000)
    p.add(Item("보유 현금", Category.CASH, 20_000_000))
    p.add(Item("적금 (3.5%)", Category.BANK, 10_000_000, rate=3.5))
    p.add(Item("전세/월세 보증금", Category.DEPOSIT, 10_000_000))
    p.add(Item("월세", Category.RENT, 500_000))
    p.add(Item("관리비", Category.MAINT, 100_000))
    p.add(Item("생활비 (식비·통신)", Category.FIXED, 800_000))
    p.add(Item("신용대출 (5%)", Category.LOAN, 5_000_000, rate=5.0, start_date=p.start_date))
    p.add(Item("급여", Category.INCOME, 2_000_000, start_date=p.start_date))
    p.add(Item("성과급", Category.INCOME_ONCE, 3_000_000, start_date=add_months(p.basis, 6).isoformat()))
    return p


def won(v: float) -> str:
    """원화 표시: 1,234,567원"""
    sign = "-" if v < 0 else ""
    return f"{sign}{abs(v):,.0f}원"
