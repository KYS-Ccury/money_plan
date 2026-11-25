"""자본금 계산기 데이터 모델.

항목(Item)을 리스트로 관리하고, 기준일·기간(개월)·목표 자본금을 기준으로
보유 자금 / 필요 자금 / 순 자본 / 목표 달성률을 계산한다.
UI(QML)와 분리되어 있어 단독으로 테스트할 수 있다.

시간 축: 기준일(Plan.start_date)을 0개월로 놓고, m개월 시점의 순 자본을 계산한다.
대출처럼 날짜 범위가 있는 항목은 그 범위에 해당하는 달에만 효과가 난다.
"""
from __future__ import annotations

import calendar
import json
import math
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    """2차 분류. 저장 파일에는 이 **값(한글 이름)** 이 들어간다.

    여기 나열한 순서는 **번호(cat_index) 순서**다 — QML·백엔드가 분류를 가리키는
    주소이고, 한 번 정하면 바꾸지 않는다 (바꾸면 번호를 쓰는 자리를 다 고쳐야 한다).
    **사람이 보는 순서는 CATEGORY_TREE 가 정한다.**
    """

    # ── 자본 (가지고 있는 것) ──
    CASH = "현금/자산"          # 자본
    BANK = "은행 예금"          # 원금은 자본, 이자는 월 수입
    SAVING = "적금/저축(월)"    # 매달 넣는 돈. 나간 만큼 자본으로 쌓인다
    LOAN = "대출/이자"          # 원금은 자본(대출 기간 동안), 이자는 월 지출(대출 기간 동안)
    # ── 수입 (들어오는 것) ──
    INCOME = "월 수입"          # 월 수입 (적용 기간)
    INCOME_ONCE = "일시 수입"   # 일시 수입 (수입일 지정 가능)
    # ── 지출 (나가는 것) ──
    RENT = "월세"               # 월 지출 (적용 기간)
    MAINT = "관리비"            # 월 지출 (적용 기간)
    FIXED = "고정 지출"         # 월 지출 (적용 기간) — 보험료·통신비·식비처럼 매달 나가는 돈
    DEPOSIT = "보증금/매매가"            # 전세·반전세·월세·매매. 보증금/매매가는 일시 지출, 월세는 월 지출
    EXPENSE = "일시 지출"       # 일시 지출 (지출일 지정 가능)


# 예전 저장 파일의 분류 이름 → 현재 이름 (불러올 때 자동 변환)
CATEGORY_ALIASES: dict[str, str] = {
    "기타 지출(일시)": Category.EXPENSE.value,
    "기타 수입(월)": Category.INCOME.value,
    "고정 지출(월)": Category.FIXED.value,
    "보증금": Category.DEPOSIT.value,
    "주거": Category.DEPOSIT.value,
}

# 주거 형태
HOUSING_TYPE_LIST: list[tuple[str, str]] = [
    ("jeonse", "전세"),        # 보증금만, 만기에 반환
    ("banjeonse", "반전세"),   # 보증금 + 월세, 만기에 반환
    ("wolse", "월세"),         # 보증금(소액) + 월세, 만기에 반환
    ("buy", "매매"),           # 매매가. 돌려받는 돈이 아니라 집으로 남는다
]
HOUSING_TYPES: dict[str, str] = dict(HOUSING_TYPE_LIST)
HOUSING_WITH_RENT = ("banjeonse", "wolse")   # 월세를 함께 내는 형태
# (월세 금액 자체는 '월세' 분류로 따로 선다 — 주거 항목에는 월세 칸이 없다)
HOUSING_BUY = "buy"

# 주거 형태별 입력 안내
HOUSING_INFO: dict[str, dict] = {
    "jeonse": {"amount_label": "보증금", "returnable": True,
               "hint": "보증금만 내고 월세가 없습니다. 만기에 보증금을 돌려받습니다"},
    "banjeonse": {"amount_label": "보증금", "returnable": True,
                  "hint": "보증금과 월세를 함께 냅니다. 여기에는 보증금만 넣고, "
                          "월세는 '월세' 분류로 따로 넣으세요. 만기에 보증금을 돌려받습니다"},
    "wolse": {"amount_label": "보증금", "returnable": True,
              "hint": "보증금은 적고 월세가 큽니다. 여기에는 보증금만 넣고, "
                      "월세는 '월세' 분류로 따로 넣으세요. 만기에 보증금을 돌려받습니다"},
    "buy": {"amount_label": "매매가", "returnable": False,
            "hint": "집값이 그대로 나가고 돌려받지 않습니다. 취득세·중개수수료는 일시 지출로 따로 넣으세요"},
}

# 1차 분류 (묶음). 2차 분류(Category)를 '무엇에 쓰는 돈인가' 로 묶는다.
# 어느 2차가 어느 1차에 속하는지는 아래 CATEGORY_TREE 한 군데서만 정한다.
GROUP_CAPITAL, GROUP_INCOME = "자본", "수입"
GROUP_HOUSING, GROUP_LIVING, GROUP_FINANCE = "주거", "생활", "금융"

# ── 돈이 오가는 성격 (shape) ──
# 예전에는 이 사실이 분류표에 없고 MONTHLY_COST_CATEGORIES 같은 튜플에만 있었다.
# 그래서 분류를 더하면 표는 고치고도 튜플을 잊어 계산에서 빠질 수 있었다.
SHAPE_NONE = "none"                    # 가지고만 있다 (현금)
SHAPE_HOLD = "hold"                    # 가지고 있고 이자가 붙는다 (예금)
SHAPE_SAVE = "save"                    # 매달 나가고 그만큼 자본으로 쌓인다 (적금)
SHAPE_LOAN = "loan"                    # 빌린 돈 — 상환·이자로 제 계산을 따른다
SHAPE_MONTHLY_COST = "monthly_cost"    # 적용 기간 동안 매달 나간다
SHAPE_MONTHLY_INCOME = "monthly_income"  # 적용 기간 동안 매달 들어온다
SHAPE_ONCE_COST = "once_cost"          # 한 번 나간다 (되풀이 가능)
SHAPE_ONCE_INCOME = "once_income"      # 한 번 들어온다 (되풀이 가능)

# 매달 같은 날 오가는 성격 (받는 날·내는 날을 정할 수 있다)
MONTHLY_SHAPES = (SHAPE_MONTHLY_COST, SHAPE_MONTHLY_INCOME, SHAPE_SAVE)

# 분류별 특성
#   amount_label : 금액 입력칸 이름
#   uses_rate    : 연이율을 쓰는가
#   date_mode    : ""(날짜 없음) | "range"(시작일~종료일) | "once"(하루에 끝나는 돈)
#   flow         : "cost"(나가는 돈) | "income"(들어오는 돈) | ""(자본·대출처럼 둘 다 아닌 것)
#   group        : 1차 분류. **여기 적지 않는다** — CATEGORY_TREE 가 채운다
#   shape        : 돈이 어떻게 오가는가. 계산이 갈라지는 바로 그 기준이고,
#                  MONTHLY_COST_CATEGORIES 같은 묶음 표를 여기서 끌어낸다
#   uses_growth  : 해마다 오르는 돈인가 (급여 인상, 물가·월세 인상)
#   returnable   : 돌려받을 수 있는 돈인가 (보증금). 반환일을 넣으면 그 달에 되돌아온다
CATEGORY_INFO: dict[Category, dict] = {
    Category.CASH: {"shape": SHAPE_NONE, "amount_label": "보유 금액", "uses_rate": False,
                    "date_mode": "", "flow": "",
                    "hint": "지금 가진 돈. 통장 잔고·현금처럼 이자가 붙지 않는 자본"},
    Category.BANK: {"shape": SHAPE_HOLD, "amount_label": "예금액", "uses_rate": True,
                    "date_mode": "", "flow": "",
                    "hint": "원금은 자본에 포함, 이자는 매달 수입"},
    Category.SAVING: {"shape": SHAPE_SAVE, "amount_label": "월 납입액", "uses_rate": True,
                      "date_mode": "range", "flow": "cost", "uses_support": True,
                      "hint": "매달 넣는 적금·저축. 납입 기간 동안 매달 나가고 그만큼 자본으로 쌓입니다. "
                              "청년도약계좌처럼 보태 주는 돈이 있으면 월 지원금에 넣으세요"},
    Category.LOAN: {"shape": SHAPE_LOAN, "amount_label": "대출 원금", "uses_rate": True,
                    "date_mode": "range", "flow": "",
                    "hint": "대출 기간 동안 원금은 자본에 포함, 이자는 잔액 기준 매달 지출. 정기·중도 상환으로 잔액을 줄일 수 있고 종료일에 잔액 상환"},
    Category.INCOME: {"shape": SHAPE_MONTHLY_INCOME, "amount_label": "월 수입", "uses_rate": False,
                      "uses_growth": True, "date_mode": "range", "flow": "income",
                      "hint": "급여·부업처럼 적용 기간 동안 매달 들어오는 돈 (종료일 비우면 계속)"},
    Category.INCOME_ONCE: {"shape": SHAPE_ONCE_INCOME, "amount_label": "수입액", "uses_rate": False,
                           "date_mode": "once", "flow": "income",
                           "hint": "상여금·퇴직금·만기 적금처럼 한 번만 들어오는 돈. 수입일을 비우면 기준일에 들어옵니다"},
    Category.RENT: {"shape": SHAPE_MONTHLY_COST, "amount_label": "월세", "uses_rate": False,
                    "uses_growth": True, "date_mode": "range", "flow": "cost",
                    "hint": "적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속)"},
    Category.MAINT: {"shape": SHAPE_MONTHLY_COST, "amount_label": "월 관리비", "uses_rate": False,
                     "uses_growth": True, "date_mode": "range", "flow": "cost",
                     "hint": "적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속)"},
    Category.FIXED: {"shape": SHAPE_MONTHLY_COST, "amount_label": "월 고정 지출", "uses_rate": False,
                     "uses_growth": True, "date_mode": "range", "flow": "cost",
                     "hint": "보험료·통신비·식비·교통비처럼 적용 기간 동안 매달 나가는 돈 (종료일 비우면 계속). "
                            "1년에 한 번 내는 자동차 보험·자동차세는 '일시 지출' 로 넣고 되풀이를 '해마다' 로 하세요"},
    Category.DEPOSIT: {"shape": SHAPE_ONCE_COST, "amount_label": "보증금", "uses_rate": False,
                       "date_mode": "once", "flow": "cost", "returnable": True, "housing": True,
                       "hint": "전세·반전세·월세·매매 중에서 고릅니다. 입주일에 보증금(매매가)이 나가고, 만기에 돌려받습니다"},
    Category.EXPENSE: {"shape": SHAPE_ONCE_COST, "amount_label": "지출액", "uses_rate": False,
                       "date_mode": "once", "flow": "cost",
                       "hint": "이사비·수수료처럼 한 번만 나가는 돈. 지출일을 비우면 기준일에 나갑니다"},
}

# 장(페이지) — 항목을 엑셀 시트처럼 나눠 담는 묶음. 첫 장의 이름은 고정이다.
PAGE_DEFAULT = "기본"

# 대출 상환 방식
REPAY_METHOD_LIST: list[tuple[str, str]] = [
    ("bullet", "만기 일시 상환"),      # 이자만 내다가 종료일에 원금 전액
    ("equal_principal", "원금 균등"),  # 매달 같은 원금 + 잔액 이자 (상환액이 점점 줄어듦)
    ("equal_payment", "원리금 균등"),  # 매달 같은 금액 (은행 대출의 기본)
    ("rate", "매달 원금의 %"),         # 원금의 n% 씩
]
REPAY_METHODS: dict[str, str] = dict(REPAY_METHOD_LIST)
TERM_METHODS = ("equal_principal", "equal_payment")   # 만기(종료일)가 있어야 계산되는 방식

# ────────────────────────────────── 1차 분류 → 2차 분류
# 이 표가 **1차·2차와 사람이 보는 순서**를 한 군데서 정한다.
# 분류를 더하거나 옮길 때 고칠 곳은 여기와 CATEGORY_INFO 둘뿐이다.
CATEGORY_TREE: dict[str, list[Category]] = {
    GROUP_CAPITAL: [Category.CASH, Category.BANK],
    GROUP_INCOME: [Category.INCOME, Category.INCOME_ONCE],
    GROUP_HOUSING: [Category.DEPOSIT, Category.RENT, Category.MAINT],
    GROUP_LIVING: [Category.FIXED, Category.EXPENSE],
    GROUP_FINANCE: [Category.SAVING, Category.LOAN],
}
GROUP_LIST: list[str] = list(CATEGORY_TREE)
GROUP_OF: dict[Category, str] = {c: g for g, cs in CATEGORY_TREE.items() for c in cs}

# 분류표의 'group' 은 손으로 적지 않는다 — 두 군데면 반드시 어긋난다
for _cat, _group in GROUP_OF.items():
    CATEGORY_INFO[_cat]["group"] = _group

# 번호(cat_index)의 순서. **CATEGORY_TREE 와 일부러 다르다.**
# 저장 파일에는 분류가 이름으로 들어가므로 번호는 실행 중에만 쓰는 주소다.
CATEGORY_LIST: list[Category] = list(Category)
# 화면에 늘어놓을 순서 (1차 순서대로 평평하게)
CATEGORY_ORDER: list[Category] = [c for cs in CATEGORY_TREE.values() for c in cs]
ORDER_OF: dict[Category, int] = {c: i for i, c in enumerate(CATEGORY_ORDER)}

if set(CATEGORY_ORDER) != set(CATEGORY_LIST):      # 분류를 더하고 트리에 안 넣은 때
    missing = [c.value for c in CATEGORY_LIST if c not in ORDER_OF]
    raise RuntimeError(f"CATEGORY_TREE 에 빠진 분류: {missing}")


def group_of(category: Category) -> str:
    """2차 분류 → 1차 분류."""
    return GROUP_OF[category]


def _shaped(*shapes: str) -> tuple[Category, ...]:
    """성격(shape)이 맞는 분류들. 계산이 보는 묶음을 분류표에서 끌어낸다."""
    return tuple(c for c in CATEGORY_LIST if CATEGORY_INFO[c]["shape"] in shapes)


# 자본으로 잡히는가 / 들어오는 돈인가 / 나가는 돈인가.
# 1차가 다섯이 되어 '자본·수입·지출' 로 가를 수 없는 자리에서 쓴다
# (가져오기 미리보기 합계, 비중).
SIDE_CAPITAL, SIDE_INCOME, SIDE_COST = "capital", "income", "cost"
_SIDE_BY_SHAPE: dict[str, str] = {
    SHAPE_NONE: SIDE_CAPITAL, SHAPE_HOLD: SIDE_CAPITAL,
    SHAPE_SAVE: SIDE_CAPITAL, SHAPE_LOAN: SIDE_CAPITAL,
    SHAPE_MONTHLY_INCOME: SIDE_INCOME, SHAPE_ONCE_INCOME: SIDE_INCOME,
    SHAPE_MONTHLY_COST: SIDE_COST, SHAPE_ONCE_COST: SIDE_COST,
}


def side_of(category: Category) -> str:
    """분류 → capital | income | cost."""
    return _SIDE_BY_SHAPE[CATEGORY_INFO[category]["shape"]]


# 매달 같은 금액이 나가는 분류 (적용 기간 동안)
MONTHLY_COST_CATEGORIES = _shaped(SHAPE_MONTHLY_COST)
# 한 번만 나가는 분류
INTEREST_TAX = 15.4          # 이자소득세 (소득세 14% + 지방소득세 1.4%)
INTEREST_CATEGORIES = _shaped(SHAPE_HOLD, SHAPE_SAVE)    # 이자가 붙는 분류

ONCE_COST_CATEGORIES = _shaped(SHAPE_ONCE_COST)
# 매달 들어오는 분류 (적용 기간 동안)
MONTHLY_INCOME_CATEGORIES = _shaped(SHAPE_MONTHLY_INCOME)
# 한 번만 들어오는 분류
ONCE_INCOME_CATEGORIES = _shaped(SHAPE_ONCE_INCOME)

def categories_in(group: str) -> list[Category]:
    """1차 분류에 속한 2차 분류들 (화면 순서)."""
    return list(CATEGORY_TREE.get(group, ()))


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
    """d 가 몇 번째 달 칸에 들어가는지. 일(日)까지 센다.

    시간 축은 기준일에 못을 박은 한 달 간격의 눈금이다 (기준일이 10월 28일이면
    0개월 = 10/28, 1개월 = 11/28, …). 날짜는 **그 날이 지난 첫 눈금**으로 올려 붙인다.
    그래야 12월 1일에 나갈 돈이 11월 28일 칸에서 미리 나가 버리는 일이 없다.
    기준일보다 앞선 날짜는 음수가 된다.
    """
    months = (d.year - basis.year) * 12 + (d.month - basis.month)
    if d.day > basis.day:
        months += 1
    return months


def add_months(basis: date, m: int) -> date:
    """basis 에서 m개월 뒤. 날짜(일)는 그대로 두되 그 달에 없으면 말일로 맞춘다."""
    y, mo = divmod(basis.month - 1 + m, 12)
    year, month = basis.year + y, mo + 1
    return date(year, month, min(basis.day, calendar.monthrange(year, month)[1]))


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
    housing_type: str = ""           # 주거 형태 (전세/반전세/월세/매매). 주거 항목에서만 사용
    # 예전 파일의 '주거에 딸린 월세'. 이제 계산에 쓰지 않는다 — 불러올 때
    # split_housing_rent() 가 '월세' 항목으로 갈라내고 이 칸을 0 으로 만든다.
    monthly: float = 0.0
    growth: float = 0.0              # 연 상승률 % (급여 인상, 물가·월세 인상). 해마다 한 번 오른다
    support: float = 0.0             # 월 지원금 (청년도약계좌처럼 남이 보태 주는 돈). 내 돈은 안 나가고 잔액만 는다
    locked: bool = False             # 만기 전까지 못 쓰는 돈으로 볼지 (적금). 만기가 있어야 적용된다
    active: bool = True              # 끄면 계산에서 빠진다 (지우지 않고 잠시 빼 볼 때)
    every: int = 0                   # 일시 지출·수입이 몇 개월마다 되풀이되는지 (0 = 한 번만)
    ledger_category: str = ""        # 가계부에서는 어느 분류로 볼지 (비우면 분류표대로 자동)
    after_tax: bool = False          # 이자에서 이자소득세 15.4% 를 뗄지 (비과세 상품이면 끈다)
    compound: bool = False           # 이자를 복리로 굴릴지 (끄면 단리)
    # 매달 며칠에 오가는 돈인지 (1~31, 0 = 정하지 않음).
    # 자본금 계산은 **달 단위**라 이 값이 숫자를 바꾸지는 않는다. 가계부에 적을 때
    # 그 날짜를 쓰고, 화면에 '매달 25일' 로 보여 준다.
    pay_day: int = 0
    # 어느 장(페이지)에 둔 항목인가. 빈 값이면 첫 장이다.
    # **계산과는 상관이 없다** — 장은 항목이 많아졌을 때 눈으로 나눠 보는
    # 묶음일 뿐이고, 요약·그래프·순 자본은 늘 모든 장을 함께 센다
    # (통째로 견주는 것은 시나리오가 한다).
    page: str = ""
    # 보증금·매매가를 '맡겨 둔 자산' 으로 보아 보유 자금에 그대로 둘지.
    # **기본값은 False 다** — 켜면 순 자본이 보증금만큼 올라가므로, 예전에 저장해
    # 둔 계획의 숫자가 불러오기만 해도 달라지면 안 된다.
    as_asset: bool = False

    def __post_init__(self) -> None:
        if self.repay_method not in REPAY_METHODS:
            self.repay_method = "rate" if self.monthly_repay_rate > 0 else "bullet"
        if self.category == Category.DEPOSIT:
            if self.housing_type not in HOUSING_TYPES:
                self.housing_type = "wolse" if self.monthly > 0 else "jeonse"
        else:
            self.housing_type, self.monthly = "", 0.0
        if not CATEGORY_INFO[self.category].get("uses_growth"):
            self.growth = 0.0
        if not CATEGORY_INFO[self.category].get("uses_support"):
            self.support = 0.0
        if self.category != Category.SAVING:
            self.locked = False
        # 날짜는 매달 오가는 돈에서만 뜻이 있다
        if CATEGORY_INFO[self.category]["shape"] not in MONTHLY_SHAPES:
            self.pay_day = 0
        else:
            self.pay_day = min(31, max(0, int(self.pay_day or 0)))
        if self.category != Category.DEPOSIT:
            self.as_asset = False

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
    def group(self) -> str:
        """자본 | 수입 | 지출"""
        return CATEGORY_INFO[self.category]["group"]

    # ---- 적금/저축 ----
    def saving_months(self, m: int, basis: date) -> int:
        """m개월 시점까지 넣은 횟수 (납입 기간을 넘지 않는다)."""
        if self.category != Category.SAVING:
            return 0
        start_m, end_m = self.active_range(basis)
        k = m - start_m
        if end_m is not None:
            k = min(k, end_m - start_m)
        return max(0, k)

    @property
    def uses_support(self) -> bool:
        """지원금을 받을 수 있는 항목인가 (적금·저축)."""
        return bool(CATEGORY_INFO[self.category].get("uses_support"))

    def saving_deposit(self) -> float:
        """매달 통장에 쌓이는 금액 = 내 납입액 + 지원금."""
        if self.category != Category.SAVING:
            return 0.0
        return self.amount + max(0.0, self.support)

    def saving_balance_at(self, m: int, basis: date) -> float:
        """m개월 시점의 적금 잔액 = (납입액 + 지원금) 누계 + 이자.

        이자는 납입분마다 묶여 있던 개월 수에 붙는다 (은행 적금과 같은 방식).
        복리를 켜면 월복리로, 세후를 켜면 이자에서 15.4% 를 뗀다.
        만기 뒤에는 납입도 이자도 멈춘다.
        """
        k = self.saving_months(m, basis)
        if k <= 0:
            return 0.0
        per = self.saving_deposit()
        principal = per * k
        mr = self.monthly_rate()
        if mr <= 0:
            return principal
        start_m, end_m = self.active_range(basis)
        mm = m if end_m is None else min(m, end_m)
        if self.compound:
            # 납입분마다 (1+i)^묶인개월 로 불어난다
            interest = 0.0
            for j in range(k):
                held = mm - (start_m + j)
                if held > 0:
                    interest += per * ((1.0 + mr) ** held - 1.0)
        else:
            months_held = k * (mm - start_m) - k * (k - 1) / 2   # 묶여 있던 개월 수의 합
            interest = per * mr * max(0.0, months_held)
        return principal + self.net_interest(interest)

    def support_total_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 받은 지원금 누계."""
        return max(0.0, self.support) * self.saving_months(m, basis)

    def maturity_month(self, basis: date) -> int | None:
        """적금 만기(개월). 종료일이 없으면 None."""
        if self.category != Category.SAVING:
            return None
        _start_m, end_m = self.active_range(basis)
        return end_m

    def open_ended_saving(self) -> bool:
        """만기(종료일)를 안 넣은 적금인가.

        대출·월세는 종료일을 비우면 '계획 끝까지 계속' 이 맞는 뜻이지만, 적금은
        만기가 있는 것이 보통이다. 비워 두면 `is_active()` 가 끝을 모르므로 납입이
        **계획 기간 내내** 월 지출로 깔리고, 그만큼 순 자본이 실제보다 낮게 나온다.
        날짜가 아니라 '빈 칸' 을 보는 값이므로 basis 가 필요 없다.
        """
        return self.category == Category.SAVING and not (self.end_date or "").strip()

    def is_locked(self, basis: date) -> bool:
        """만기 전까지 손댈 수 없는 돈인가. 만기가 있어야 묶임이 성립한다."""
        return bool(self.locked) and self.maturity_month(basis) is not None

    # ---- 해마다 오르는 금액 ----
    @property
    def uses_growth(self) -> bool:
        return bool(CATEGORY_INFO[self.category].get("uses_growth"))

    def growth_factor(self, m: int, basis: date) -> float:
        """m개월 시점의 배수. 시작한 지 1년이 지날 때마다 한 번씩 오른다."""
        if not self.growth or not self.uses_growth:
            return 1.0
        start_m, _ = self.active_range(basis)
        years = max(0, m - start_m) // 12
        return (1.0 + self.growth / 100.0) ** years

    def amount_at(self, m: int, basis: date) -> float:
        """m개월 시점의 월 금액 (상승률 반영)."""
        return self.amount * self.growth_factor(m, basis)

    @property
    def is_housing(self) -> bool:
        return self.category == Category.DEPOSIT

    @property
    def is_purchase(self) -> bool:
        """집을 사는 것인가 (매매)."""
        return self.is_housing and self.housing_type == HOUSING_BUY

    @property
    def housing_label(self) -> str:
        return HOUSING_TYPES.get(self.housing_type, "")

    def housing_rent(self) -> float:
        """예전 파일에 딸려 온 월세. 전세·매매면 0.

        계산은 이 값을 보지 않는다 (월세는 제 항목으로 선다). 불러올 때
        갈라내는 split_housing_rent() 만 이 값을 읽는다.
        """
        if self.is_housing and self.housing_type in HOUSING_WITH_RENT:
            return max(0.0, self.monthly)
        return 0.0

    def housing_active(self, m: int, basis: date) -> bool:
        """입주 후 만기 전인가 (월세가 나가는 구간)."""
        if m < self.once_month(basis):
            return False
        r = self.return_month(basis)
        return r is None or m < r

    @property
    def returnable(self) -> bool:
        """돌려받을 수 있는 돈인가 (매매는 아니다)."""
        return bool(CATEGORY_INFO[self.category].get("returnable")) and not self.is_purchase

    def return_month(self, basis: date) -> int | None:
        """보증금을 돌려받는 개월. 반환일이 없으면 None(계속 묶여 있음)."""
        if not self.returnable:
            return None
        d = parse_date(self.end_date)
        return month_offset(basis, d) if d else None

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

    @property
    def repeats(self) -> bool:
        """몇 달마다 되풀이되는 일시 지출·수입인가.

        자동차세·보험 연납처럼 한 달 주기가 아닌 돈을 위한 것이다. 보증금처럼
        돌려받는 항목은 되풀이라는 말이 어울리지 않으므로 뺀다.
        """
        return self.every > 0 and self.date_mode == "once" and not self.returnable

    def repeat_end_month(self, basis: date) -> int | None:
        """되풀이가 끝나는 개월 (종료일이 없으면 None = 계속)."""
        d = parse_date(self.end_date) if self.repeats else None
        return month_offset(basis, d) if d else None

    def first_month(self, basis: date) -> int | None:
        """이 계획 안에서 처음 돈이 오가는 개월. 기준일 전이면 되풀이의 첫 회차를 찾는다."""
        om = self.once_month(basis)
        if om >= 0:
            return om
        if not self.repeats:
            return None                       # 기준일 전에 이미 치른 돈은 세지 않는다
        k = (-om + self.every - 1) // self.every
        return om + k * self.every

    def occurs_at(self, m: int, basis: date) -> bool:
        """m개월에 이 돈이 오가는가."""
        first = self.first_month(basis)
        if first is None or m < first:
            return False
        if not self.repeats:
            return m == first
        end = self.repeat_end_month(basis)
        if end is not None and m > end:
            return False
        return (m - first) % self.every == 0

    def count_upto(self, m: int, basis: date) -> int:
        """m개월까지 이 돈이 몇 번 오갔는지 (되풀이가 아니면 0 또는 1)."""
        first = self.first_month(basis)
        if first is None or m < first:
            return 0
        if not self.repeats:
            return 1
        end = self.repeat_end_month(basis)
        last = m if end is None else min(m, end)
        if last < first:
            return 0
        return (last - first) // self.every + 1

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

    @property
    def taxes_interest(self) -> bool:
        """이 항목의 이자에서 세금을 떼는가 (이자가 붙는 분류에서만 뜻이 있다)."""
        return self.after_tax and self.category in INTEREST_CATEGORIES

    def net_interest(self, interest: float) -> float:
        """세금을 뗀 이자. 끄면 그대로."""
        if interest <= 0 or not self.taxes_interest:
            return interest
        return interest * (1.0 - INTEREST_TAX / 100.0)

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
    def bank_balance_at(self, m: int) -> float:
        """예금 잔액. 복리면 이자가 안에서 불어나고, 단리면 원금 그대로다
        (단리 이자는 매달 '월 수입' 으로 빠져나가기 때문)."""
        if self.category != Category.BANK or not self.compound:
            return self.amount
        mr = self.monthly_rate()
        if mr <= 0 or m <= 0:
            return self.amount
        return self.amount + self.net_interest(self.amount * ((1.0 + mr) ** m - 1.0))

    def deposit_value_at(self, m: int, basis: date) -> float:
        """맡겨 둔 보증금·매매가 중 m개월 시점에 **아직 묶여 있는** 금액.

        as_asset 을 켠 보증금만 해당한다. 이 값은 보유 자금에 더해지는데,
        같은 금액이 once_cost 로 빠져나가므로 **묶여 있는 동안 순 자본은
        그대로다** (현금이 보증금으로 모양만 바뀐 것이다). 돌려받는 달부터는
        0 이 되고, 그 돈은 once_income(보증금 반환)으로 다시 들어온다 — 그래서
        반환 시점에도 순 자본이 튀지 않는다.
        """
        if self.category != Category.DEPOSIT or not self.as_asset:
            return 0.0
        if m < self.once_month(basis):        # 아직 맡기기 전 (기준일 전이면 음수라 늘 참)
            return 0.0
        r = self.return_month(basis)
        if r is not None and m >= r:
            return 0.0                        # 돌려받았다
        return self.amount

    def capital_at(self, m: int, basis: date) -> float:
        """m개월 시점에 보유 자금에 더해지는 금액."""
        if self.category == Category.DEPOSIT:
            return self.deposit_value_at(m, basis)
        if self.category == Category.CASH:
            return self.amount
        if self.category == Category.BANK:
            return self.bank_balance_at(m)
        if self.category == Category.SAVING:
            # 묶어 둔 적금은 보유 자금에 넣지 않는다.
            # 만기 수령액은 once_income_at 으로 들어가므로 요약의 '일시 수입' 에 드러난다.
            if self.is_locked(basis):
                return 0.0
            return self.saving_balance_at(m, basis)   # 넣은 만큼 쌓인다
        if self.category == Category.LOAN and self.include_principal and self.is_active(m, basis):
            return self.remaining_at(m, basis)   # 상환한 만큼 보유 자금에서 빠진다
        return 0.0

    def once_cost(self) -> float:
        """일시 지출 금액 (날짜와 무관한 총액)."""
        if self.category in ONCE_COST_CATEGORIES:
            return self.amount
        return 0.0

    def once_cost_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 이 계획 안에서 나간 일시 지출.

        기준일 전에 이미 나간 돈은 보유 자금에 애초에 없으므로 세지 않는다.
        (그러지 않으면 이미 치른 보증금이 순 자본에서 또 한 번 깎인다.)
        """
        c = self.once_cost()
        if c <= 0:
            return 0.0
        return c * self.count_upto(m, basis)

    def once_returned_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 돌려받은 보증금. 언제 냈든 돌려받는 건 그대로 들어온다."""
        c = self.once_cost()
        r = self.return_month(basis)
        if c <= 0 or r is None or r < 0:
            return 0.0
        return c if m >= r else 0.0

    def once_income(self) -> float:
        """일시 수입 금액 (날짜와 무관한 총액)."""
        if self.category in ONCE_INCOME_CATEGORIES:
            return self.amount
        return 0.0

    def once_income_at(self, m: int, basis: date) -> float:
        """m개월 시점까지 들어온 일시 수입. 보증금 반환과 묶인 적금의 만기 수령을 포함한다."""
        c = self.once_income()
        if c > 0:
            return c * self.count_upto(m, basis)
        got = self.once_returned_at(m, basis)
        if self.is_locked(basis):                       # 묶인 적금은 만기에 한꺼번에 들어온다
            mat = self.maturity_month(basis)
            if m >= mat:
                got += self.saving_balance_at(mat, basis)
        return got

    def once_repay_at(self, m: int, basis: date) -> float:
        """대출에서 **한 번에** 빠져나가는 상환액 (중도 상환 + 만기 일시 상환).

        원금을 자본에 넣지 않은 대출만 해당한다 (넣은 경우는 자본이 줄어드는
        것으로 이미 반영된다). 이 돈은 monthly_cost_at 안에도 들어 있다 —
        순 자본 계산이 거기를 보기 때문이다. 다만 **요약에서는 월 지출 평균에서
        빼고 일시 지출로 옮겨 보여 준다.** 그러지 않으면 만기에 한 번 갚는
        9천만원이 월 평균에 녹아들어 달마다 그만큼 나가는 것처럼 읽힌다.
        """
        if self.category != Category.LOAN or self.include_principal:
            return 0.0
        start_m, end_m = self.active_range(basis)
        out = 0.0
        if m >= start_m and (end_m is None or m < end_m):
            out += self.repayment_at(m, basis)
        if end_m is not None and m == end_m:
            out += self.remaining_at(m, basis)
        return out

    def monthly_cost_at(self, m: int, basis: date) -> float:
        if self.category == Category.SAVING:
            return self.amount if self.is_active(m, basis) else 0.0
        if self.category in MONTHLY_COST_CATEGORIES:
            return self.amount_at(m, basis) if self.is_active(m, basis) else 0.0
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
            return self.amount_at(m, basis) if self.is_active(m, basis) else 0.0
        if self.category == Category.BANK:
            # 복리는 이자를 빼지 않고 안에서 굴리므로 월 수입으로 잡지 않는다
            return 0.0 if self.compound else self.net_interest(self.monthly_interest())
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

    def planned_out_at(self, m: int, basis: date) -> float:
        """이 항목이 m개월에 내보내는 돈 (가계부와 견주려고 쓴다).

        월 지출 + 그 달에 걸린 일시 지출 + 대출 원금 상환. 원금을 자본에 넣은
        대출은 월 지출에 상환액이 안 잡히므로 여기서 따로 더한다.
        """
        out = self.monthly_cost_at(m, basis)
        if self.date_mode == "once" and self.once_cost() > 0 and self.occurs_at(m, basis):
            out += self.once_cost()
        if self.category == Category.LOAN and self.include_principal:
            out += self.regular_repay_at(m, basis)
            if self.is_active(m, basis):
                out += self.repayment_at(m, basis)
            _start_m, end_m = self.active_range(basis)
            if end_m is not None and m == end_m:
                out += self.remaining_at(m, basis)
        return out

    def planned_in_at(self, m: int, basis: date) -> float:
        """이 항목이 m개월에 들여오는 돈. 월 수입 + 그 달의 일시 수입 + 보증금 반환 + 적금 만기."""
        inc = self.monthly_income_at(m, basis)
        if self.once_income() > 0 and self.occurs_at(m, basis):
            inc += self.once_income()
        if self.return_month(basis) == m:
            inc += self.once_cost()
        if self.is_locked(basis) and self.maturity_month(basis) == m:
            inc += self.saving_balance_at(m, basis)
        return inc

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
            housing_type=str(d.get("housing_type") or ""),
            monthly=float(d.get("monthly", 0.0) or 0.0),
            growth=float(d.get("growth", 0.0) or 0.0),
            support=float(d.get("support", 0.0) or 0.0),
            locked=bool(d.get("locked", False)),
            active=bool(d.get("active", True)),
            every=int(d.get("every", 0) or 0),
            pay_day=int(d.get("pay_day", 0) or 0),
            ledger_category=str(d.get("ledger_category") or ""),
            after_tax=bool(d.get("after_tax", False)),
            compound=bool(d.get("compound", False)),
            as_asset=bool(d.get("as_asset", False)),
            page=str(d.get("page") or ""),
        )


@dataclass
class Summary:
    """기간(months)·목표(target) 기준 요약. 시점별 값은 plan 의 계산 함수를 사용한다."""
    months: int
    target: float
    capital: float          # 0개월 시점 보유 자금
    once_cost: float        # 기간 안에 나가는 일시 지출 합계 (대출 일시 상환 포함)
    once_income: float      # 기간 안에 들어오는 일시 수입 합계
    monthly_cost: float     # 0개월 시점 월 지출
    monthly_income: float   # 0개월 시점 월 수입
    required: float         # 기간 동안 필요한 총 자금 = 일시 지출 + 월 지출 합
    period_income: float    # 기간 동안의 수입 합 = 일시 수입 + 월 수입 합
    avg_cost: float = 0.0       # 기간 평균 월 지출 (기간 중에 시작하는 이자·월세까지 반영)
    avg_income: float = 0.0     # 기간 평균 월 수입
    last_cost: float = 0.0      # 기간 마지막 달의 월 지출
    last_income: float = 0.0    # 기간 마지막 달의 월 수입
    _net_at: callable = field(default=None, repr=False, compare=False)
    _find: callable = field(default=None, repr=False, compare=False)
    _net: float | None = field(default=None, repr=False, compare=False)

    @property
    def monthly_net(self) -> float:
        """0개월 시점의 월 순수입."""
        return self.monthly_income - self.monthly_cost

    @property
    def avg_net(self) -> float:
        """기간 평균 월 순수입."""
        return self.avg_income - self.avg_cost

    @property
    def last_net(self) -> float:
        """기간 마지막 달의 월 순수입."""
        return self.last_income - self.last_cost

    @property
    def monthly_varies(self) -> bool:
        """기간 중에 월 지출·수입이 달라지는가 (이자가 중간에 시작하는 등)."""
        return (abs(self.last_cost - self.monthly_cost) > 0.5
                or abs(self.last_income - self.monthly_income) > 0.5)

    def net_at(self, month: int) -> float:
        """특정 개월 시점의 순 자본."""
        return self._net_at(month)

    @property
    def net(self) -> float:
        """기간 종료 시점의 순 자본. 여러 곳에서 읽으므로 한 번만 구한다."""
        if self._net is None:
            self._net = self.net_at(self.months)
        return self._net

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
        """기준일로부터 몇 개월째에 처음 목표에 닿는지 (0 = 이미 달성). 50년 내 불가능이면 None.

        대개 가까운 달에 닿으므로 한 달씩 보는 편이 빠르다 (여러 달을 한 번에 구하면
        닿은 뒤의 달까지 쓸데없이 계산한다).
        """
        if self.target <= 0:
            return 0
        if self._find is not None:
            return self._find(self.target, 0, self.MAX_LOOKAHEAD)
        for m in range(0, self.MAX_LOOKAHEAD + 1):
            if self.net_at(m) >= self.target:
                return m
        return None

    def months_to_goal(self) -> int | None:
        """기간 종료 이후 목표에 닿기까지 몇 달 더 걸리는지. 이미 달성이면 0, 50년 내 불가능이면 None."""
        if self.gap >= 0:
            return 0
        if self._find is not None:
            m = self._find(self.target, self.months + 1, self.MAX_LOOKAHEAD)
            return None if m is None else m - self.months
        for extra in range(1, self.MAX_LOOKAHEAD + 1):
            if self.net_at(self.months + extra) >= self.target:
                return extra
        return None


def split_housing_rent(items: list[Item]) -> list[Item]:
    """예전 파일의 '주거 항목에 딸린 월세' 를 따로 선 월세 항목으로 갈라낸다.

    월세를 넣는 길이 둘이면 (주거 항목의 월세 칸, '월세' 분류) 어디에 넣는 게
    맞는지 알 수 없다. 그래서 칸을 없애고 길을 하나로 줄였다.

    **숫자는 그대로다.** 주거의 월세가 나가던 구간(입주~만기)과 월세 항목의
    적용 구간이 똑같은 식이기 때문이다 (housing_active 와 is_active).
    매매는 예전에도 월세가 안 나갔으므로 갈라지지 않는다.
    """
    out: list[Item] = []
    for it in items:
        out.append(it)
        if not it.is_housing:
            continue
        rent = it.housing_rent()
        it.monthly = 0.0                 # 갈라냈으니 죽은 값을 남기지 않는다
        if rent > 0:
            out.append(Item(f"{it.name} 월세".strip(), Category.RENT, rent,
                            start_date=it.start_date, end_date=it.end_date,
                            active=it.active))
    return out


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    months: int = 12
    target: float = 0.0
    inflation: float = 0.0          # 연 물가 상승률 % (0 이면 '지금 돈' 환산을 안 쓴다)
    # 중간 목표 [{name, amount}]. 최종 목표(target) 로 가는 길에 거쳐 가는 지점들이다
    goals: list[dict] = field(default_factory=list)
    start_date: str = field(default_factory=lambda: date.today().isoformat())  # 기준일 (0개월)
    name: str = ""                                                              # 시나리오 이름
    # 장(페이지) 이름들. 첫 장은 여기 적지 않는다 (page_title 이 들고 있다).
    # 항목이 하나도 없는 장도 남아 있어야 해서 따로 들고 있는다.
    pages: list[str] = field(default_factory=list)
    # 첫 장의 이름. 비어 있으면 PAGE_DEFAULT("기본")로 보여 준다.
    #
    # **첫 장의 항목은 page 를 빈 값으로 들고 있다.** 그래서 이름을 바꿔도
    # 항목은 하나도 건드리지 않는다 — 이름표만 갈아 끼우는 셈이다.
    page_title: str = ""

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

    @property
    def live(self) -> list[Item]:
        """계산에 넣을 항목 — 꺼 둔 것은 뺀다.

        목록·저장에는 그대로 남아 있고 계산에서만 빠진다. '이 대출을 안 받으면
        어떻게 되지' 를 지웠다 다시 넣지 않고 보려고 둔 장치다.
        """
        return [i for i in self.items if i.active]

    @property
    def off_count(self) -> int:
        return sum(1 for i in self.items if not i.active)

    # ---- 시점별 계산 ----
    def capital_at(self, m: int) -> float:
        b = self.basis
        return sum(i.capital_at(m, b) for i in self.live)

    def once_cost(self) -> float:
        """일시 지출 총액 (날짜와 무관)."""
        return sum(i.once_cost() for i in self.live)

    def once_cost_at(self, m: int) -> float:
        """m개월 시점까지 나간 일시 지출 합."""
        b = self.basis
        return sum(i.once_cost_at(m, b) for i in self.live)

    def once_income(self) -> float:
        """일시 수입 총액 (날짜와 무관)."""
        return sum(i.once_income() for i in self.live)

    def once_income_at(self, m: int) -> float:
        """m개월 시점까지 들어온 일시 수입 합."""
        b = self.basis
        return sum(i.once_income_at(m, b) for i in self.live)

    def monthly_cost_at(self, m: int) -> float:
        b = self.basis
        return sum(i.monthly_cost_at(m, b) for i in self.live)

    def tied_capital_at(self, m: int) -> float:
        """보유 자금 가운데 **지금 쓸 수 없는** 돈 (자산으로 보는 보증금·매매가).

        보유 자금에는 들어 있지만 집에 묶여 있어 당장 쓸 수는 없다. 요약에서
        '쓸 수 있는 돈' 과 갈라 보여 주려고 센다 — 보증금을 자산으로 켜면 보유
        자금이 커지는데, 그게 다 현금인 줄 알면 계획을 잘못 세우게 된다.
        """
        b = self.basis
        return sum(i.deposit_value_at(m, b) for i in self.live)

    def once_repay_at(self, m: int) -> float:
        """m개월째에 한 번에 빠져나가는 대출 상환액 (요약에서 갈라 보여 주려고)."""
        b = self.basis
        return sum(i.once_repay_at(m, b) for i in self.live)

    def monthly_income_at(self, m: int) -> float:
        b = self.basis
        return sum(i.monthly_income_at(m, b) for i in self.live)

    def net_at(self, m: int) -> float:
        """m개월 시점 순 자본 = 그 시점 보유 자금 - 일시 지출 + 일시 수입 + (0..m-1 개월의 월 수입 - 월 지출)."""
        b = self.basis
        flow = sum(i.monthly_net_at(k, b) for i in self.live for k in range(max(0, m)))
        return self.capital_at(m) - self.once_cost_at(m) + self.once_income_at(m) + flow

    # ---- 그 달에 실제로 오고 가는 돈 (가계부와 비교하려고 쓴다) ----
    def goal_list(self) -> list[dict]:
        """중간 목표 + 최종 목표를 **금액 순**으로. [{name, amount, final}]

        거쳐 가는 차례대로 읽히도록 금액이 작은 것부터 놓는다. 중간 목표를
        최종보다 크게 적어 두었다면 그 사다리의 맨 위에 서게 된다.
        """
        out = []
        for g in self.goals:
            amount = max(0.0, float(g.get("amount", 0) or 0))
            if amount <= 0:
                continue
            out.append({"name": str(g.get("name") or "중간 목표"),
                        "amount": amount, "final": False})
        if self.target > 0:
            out.append({"name": "최종 목표", "amount": float(self.target), "final": True})
        out.sort(key=lambda g: g["amount"])
        return out

    def real_value(self, amount: float, m: int | None = None) -> float:
        """m개월 뒤의 돈을 **지금 돈** 으로 환산한다 (물가 상승률만큼 깎는다).

        물가 상승률이 0 이면 그대로 돌려준다.
        """
        if self.inflation <= 0:
            return amount
        n = self.months if m is None else m
        return amount / ((1.0 + self.inflation / 100.0) ** (max(0, n) / 12.0))

    def planned_out_at(self, m: int) -> float:
        """m개월에 나갈 것으로 계획된 돈 (항목별 계산을 모은 것)."""
        b = self.basis
        return sum(i.planned_out_at(m, b) for i in self.live)

    def planned_in_at(self, m: int) -> float:
        """m개월에 들어올 것으로 계획된 돈 (항목별 계산을 모은 것)."""
        b = self.basis
        return sum(i.planned_in_at(m, b) for i in self.live)

    def pending_inflows(self) -> list[dict]:
        """기간이 끝난 뒤에 들어올 돈. 지금 순 자본에는 안 잡히지만 목표에 보탬이 된다.

        - deposit: 돌려받을 보증금 (반환일이 기간 뒤)
        - loan: 받을 대출 (원금을 자본에 넣는 대출이 기간 뒤에 실행)

        기간 안에 들어오는 것은 이미 순 자본에 있으므로 뺀다.
        [{name, amount, month, kind}] — month 는 기준일로부터의 개월, 이른 순.
        """
        b = self.basis
        out = []
        for i in self.live:
            r = i.return_month(b)
            if r is not None and r > self.months and i.once_cost() > 0:
                out.append({"name": i.name, "amount": i.once_cost(), "month": r, "kind": "deposit"})
            if i.is_locked(b):
                mat = i.maturity_month(b)
                if mat > self.months:
                    amount = i.saving_balance_at(mat, b)
                    if amount > 0:
                        out.append({"name": i.name, "amount": amount, "month": mat, "kind": "saving"})
            if i.category == Category.LOAN and i.include_principal:
                start_m, end_m = i.active_range(b)
                if start_m > self.months and (end_m is None or start_m < end_m):
                    amount = i.remaining_at(start_m, b)
                    if amount > 0:
                        out.append({"name": i.name, "amount": amount, "month": start_m, "kind": "loan"})
        out.sort(key=lambda d: (d["month"], d["name"]))
        return out

    def pending_total(self, kind: str = "") -> float:
        """종류를 주면 그 종류만, 비우면 전부."""
        return sum(d["amount"] for d in self.pending_inflows() if not kind or d["kind"] == kind)

    def net_series(self, n: int) -> list[float]:
        """0..n 개월의 순 자본을 한 번에 구한다.

        net_at(m) 은 0..m-1 개월의 월 수지를 매번 다시 더하므로, 그래프처럼
        여러 달을 연달아 물으면 비용이 제곱으로 는다. 여기서는 달을 한 번만
        훑으면서 월 수지를 쌓아 간다.
        """
        b = self.basis
        out: list[float] = []
        flow = 0.0
        for m in range(max(0, n) + 1):
            out.append(self.capital_at(m) - self.once_cost_at(m) + self.once_income_at(m) + flow)
            flow += sum(i.monthly_net_at(m, b) for i in self.live)
        return out

    def spendable_series(self, n: int) -> list[float]:
        """0..n 개월의 **쓸 수 있는 돈** = 순 자본 - 그 달에 보증금에 묶여 있는 돈.

        순 자본은 '얼마나 가졌는가' 이고 이쪽은 '지금 손에 쥐고 쓸 수 있는가' 다.
        보증금을 자산으로 켜 두면 순 자본은 안 깎이므로, 돈이 모자란지는 순
        자본으로 알 수 없다 — 1억을 가지고 1.5억짜리 전세에 들어가도 순 자본은
        1억 그대로다. 부족 경고는 그래서 이 값을 본다.
        """
        return [v - self.tied_capital_at(m) for m, v in enumerate(self.net_series(n))]

    def spendable_at(self, m: int) -> float:
        """m개월 시점에 쓸 수 있는 돈 (묶인 보증금을 뺀 순 자본)."""
        return self.net_at(m) - self.tied_capital_at(m)

    def first_month_reaching(self, amount: float, after: int = 0, limit: int = 600) -> int | None:
        """순 자본이 amount 이상이 되는 첫 달 (after 개월 이후). 못 닿으면 None.

        net_at 을 한 달씩 부르면 그때마다 0개월부터 다시 더하므로 비용이 제곱으로 는다.
        여기서는 달을 한 번만 훑으면서 월 수지를 쌓고, 닿는 순간 멈춘다.
        """
        b = self.basis
        flow = 0.0
        for m in range(max(0, limit) + 1):
            v = self.capital_at(m) - self.once_cost_at(m) + self.once_income_at(m) + flow
            if m >= after and v >= amount:
                return m
            flow += sum(i.monthly_net_at(m, b) for i in self.live)
        return None

    SHORTFALL_HORIZON = 36      # 부족 경고는 최소 3년까지 살펴본다

    def shortfall(self, horizon: int | None = None) -> dict:
        """**쓸 수 있는 돈**이 음수로 떨어지는 구간을 찾는다 (= 현금이 비는 때).

        순 자본이 아니라 spendable_series 를 본다. 보증금을 자산으로 켜 두면
        순 자본은 안 깎이기 때문에, 순 자본만 보면 '낼 돈이 없는데도' 경고가
        안 뜬다. 보증금을 자산으로 보지 않는 계획에서는 둘이 같은 값이라
        예전과 똑같이 움직인다.

        {month: 처음 부족해지는 개월(없으면 None), months: 부족한 달 수,
         min_month / min_net: 가장 낮은 시점과 그때 쓸 수 있는 돈,
         horizon: 살펴본 개월}
        """
        h = max(self.months, self.SHORTFALL_HORIZON) if horizon is None else max(0, horizon)
        series = self.spendable_series(h)
        first: int | None = None
        count = 0
        min_m, min_v = 0, series[0]
        for m, v in enumerate(series):
            if v < min_v:
                min_m, min_v = m, v
            if v < 0:
                count += 1
                if first is None:
                    first = m
        return {"month": first, "months": count, "min_month": min_m, "min_net": min_v, "horizon": h}

    def summary(self) -> Summary:
        n = max(0, self.months)
        k = n if n > 0 else 1                       # 기간이 0이면 이번 달 하나만 본다
        # 대출을 '한 번에' 갚는 돈은 월 지출에서 빼고 일시 지출로 옮긴다.
        # 숫자의 합(required)과 순 자본은 그대로고, 보여 주는 자리만 바뀐다 —
        # 만기에 한 번 갚는 원금이 월 평균에 녹으면 달마다 나가는 것처럼 읽힌다.
        repays = [self.once_repay_at(m) for m in range(k)]
        costs = [self.monthly_cost_at(m) - repays[m] for m in range(k)]
        incomes = [self.monthly_income_at(m) for m in range(k)]
        once_cost = self.once_cost_at(n) + sum(repays[:n])
        return Summary(
            months=n,
            target=self.target,
            capital=self.capital_at(0),
            once_cost=once_cost,
            once_income=self.once_income_at(n),
            monthly_cost=costs[0],
            monthly_income=incomes[0],
            required=once_cost + sum(costs[:n]),
            period_income=self.once_income_at(n) + sum(incomes[:n]),
            avg_cost=sum(costs) / k,
            avg_income=sum(incomes) / k,
            last_cost=costs[-1],
            last_income=incomes[-1],
            _net_at=self.net_at,
            _find=self.first_month_reaching,
        )

    # ---- 저장 / 불러오기 ----
    def first_page(self) -> str:
        """첫 장의 이름. 이름을 안 바꿨으면 "기본" 이다."""
        return (self.page_title or "").strip() or PAGE_DEFAULT

    def page_list(self) -> list[str]:
        """이 계획의 장 이름들 (왼쪽부터).

        첫 장은 늘 PAGE_DEFAULT 다. 빈 장도 남아 있어야 하므로 이름은 pages 에
        따로 적어 두고, 혹시 목록에 없는 장을 쓰는 항목이 있으면 뒤에 붙인다
        (예전 파일을 열거나 장을 지운 직후).
        """
        out = [self.first_page()]
        for p in self.pages:
            if p and p not in out:
                out.append(p)
        for i in self.items:
            if i.page and i.page not in out:
                out.append(i.page)
        return out

    def items_on(self, page: str) -> list["Item"]:
        """그 장의 항목들. 첫 장은 page 가 비어 있는 항목까지 데려온다."""
        if page == self.first_page():
            return [i for i in self.items if not i.page or i.page == page]
        return [i for i in self.items if i.page == page]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "months": self.months,
            "target": self.target,
            "inflation": self.inflation,
            "pages": list(self.pages),
            "page_title": self.page_title,
            "goals": [{"name": str(g.get("name") or ""),
                       "amount": float(g.get("amount", 0) or 0)} for g in self.goals],
            "start_date": self.start_date,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            # 예전 파일의 '주거에 딸린 월세' 는 여기서 월세 항목으로 갈라진다
            items=split_housing_rent([Item.from_dict(x) for x in d.get("items", [])]),
            months=int(d.get("months", 12)),
            target=float(d.get("target", 0.0)),
            inflation=float(d.get("inflation", 0.0) or 0.0),
            goals=[{"name": str(g.get("name") or ""), "amount": float(g.get("amount", 0) or 0)}
                   for g in (d.get("goals") or []) if isinstance(g, dict)],
            start_date=str(d.get("start_date") or date.today().isoformat()),
            name=str(d.get("name") or ""),
            pages=[str(p) for p in (d.get("pages") or []) if str(p).strip()],
            page_title=str(d.get("page_title") or ""),
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
    ledger: object = None          # Ledger (가계부). 시나리오와 무관하게 하나만 둔다

    def __post_init__(self) -> None:
        from .ledger import Ledger
        if self.ledger is None:
            self.ledger = Ledger()
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
        return {
            "version": 3,
            "active": self.active,
            "scenarios": [p.to_dict() for p in self.plans],
            "ledger": self.ledger.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Workspace":
        from .ledger import Ledger
        lg = Ledger.from_dict(d.get("ledger"))
        if "scenarios" in d:
            return cls([Plan.from_dict(x) for x in d.get("scenarios", [])], int(d.get("active", 0)), lg)
        return cls([Plan.from_dict(d)], 0, lg)      # 구버전 파일: 계획 하나

    def save(self, path: str | Path) -> Path | None:
        """저장. 쓰다가 죽어도 원본이 잘리지 않게 **옆에 다 써 놓고 바꿔친다**.

        1. 같은 폴더의 .tmp 에 전부 쓰고 디스크까지 내려보낸 뒤 (flush + fsync)
        2. 직전 파일을 .bak 으로 복사해 두고
        3. os.replace 로 한 번에 바꾼다 (같은 볼륨 안에서는 원자적이다).

        돌려주는 값은 남겨 둔 .bak 경로 (처음 저장이면 None).
        """
        p = Path(path)
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

        bak = None
        if p.exists():
            bak = p.with_name(p.name + ".bak")
            try:
                shutil.copy2(p, bak)      # 옮기지 않고 복사한다 (바꿔치기 전까지 원본을 그대로 둔다)
            except OSError:
                bak = None
        os.replace(tmp, p)
        return bak

    @classmethod
    def load(cls, path: str | Path) -> "Workspace":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def sample_plan() -> Plan:
    """처음 실행 시 보여줄 예시 데이터."""
    p = Plan(months=12, target=30_000_000)
    p.add(Item("보유 현금", Category.CASH, 20_000_000))
    p.add(Item("예금 (3.5%)", Category.BANK, 10_000_000, rate=3.5))
    p.add(Item("청년도약계좌", Category.SAVING, 200_000, rate=3.0, support=300_000, locked=True,
               start_date=p.start_date, end_date=add_months(p.basis, 60).isoformat()))
    p.add(Item("전셋집", Category.DEPOSIT, 10_000_000, housing_type="banjeonse",
               end_date=add_months(p.basis, 24).isoformat()))
    p.add(Item("전셋집 월세", Category.RENT, 500_000,
               end_date=add_months(p.basis, 24).isoformat()))
    p.add(Item("관리비", Category.MAINT, 100_000))
    p.add(Item("생활비 (식비·통신)", Category.FIXED, 800_000))
    p.add(Item("신용대출 (5%)", Category.LOAN, 5_000_000, rate=5.0, start_date=p.start_date))
    p.add(Item("급여", Category.INCOME, 2_000_000, start_date=p.start_date, growth=3.0))
    p.add(Item("성과급", Category.INCOME_ONCE, 3_000_000, start_date=add_months(p.basis, 6).isoformat()))
    return p


def won(v: float) -> str:
    """원화 표시: 1,234,567원"""
    sign = "-" if v < 0 else ""
    return f"{sign}{abs(v):,.0f}원"
