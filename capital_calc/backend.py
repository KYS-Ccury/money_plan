"""QML 프론트엔드에 노출되는 Python 백엔드.

역할 분담:
- model.py  : 순수 계산 로직 (Qt 를 전혀 모름)
- backend.py: model.py 를 QObject / QAbstractListModel 로 감싸서 QML 에 신호·슬롯·프로퍼티로 제공
- qml/      : 화면, 레이아웃, 애니메이션 (Python 을 모름, backend 프로퍼티만 바인딩)
"""
from __future__ import annotations

import functools
import json
from datetime import date
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QUrl,
    Signal,
    Slot,
)

from .export_excel import composition, export_plan
from .import_ledger import parse_file, parse_text
from .ledger import sort_key
from .ledger import (LEDGER_COST_CATEGORIES, LEDGER_INCOME_CATEGORIES, Entry, Fixed,
                     Ledger, kind_of, month_key, prev_period, same_day_in, sample_ledger,
                     shift_month)
from .model import (CATEGORY_INFO, CATEGORY_LIST, HOUSING_INFO, HOUSING_TYPE_LIST, HOUSING_TYPES,
                     REPAY_METHOD_LIST, REPAY_METHODS, TERM_METHODS, month_offset,
                     Category, Item, Plan, Workspace, add_months, parse_date, sample_plan, won)

DATA_FILE = Path(__file__).resolve().parent.parent / "capital_data.json"


class ItemListModel(QAbstractListModel):
    """Plan.items 를 QML ListView 에 보여주는 리스트 모델."""

    NameRole = Qt.ItemDataRole.UserRole + 1
    CategoryRole = Qt.ItemDataRole.UserRole + 2
    CategoryIndexRole = Qt.ItemDataRole.UserRole + 3
    AmountRole = Qt.ItemDataRole.UserRole + 4
    AmountTextRole = Qt.ItemDataRole.UserRole + 5
    RateRole = Qt.ItemDataRole.UserRole + 6
    RateTextRole = Qt.ItemDataRole.UserRole + 7
    MonthlyTextRole = Qt.ItemDataRole.UserRole + 8
    MonthlyKindRole = Qt.ItemDataRole.UserRole + 9   # "income" | "cost" | "once" | "capital"
    IncludePrincipalRole = Qt.ItemDataRole.UserRole + 10
    UsesRateRole = Qt.ItemDataRole.UserRole + 11
    StartDateRole = Qt.ItemDataRole.UserRole + 12
    EndDateRole = Qt.ItemDataRole.UserRole + 13
    RepaymentsRole = Qt.ItemDataRole.UserRole + 14
    SubTextRole = Qt.ItemDataRole.UserRole + 15   # 적용 기간·상환 요약 (이름 아래 작은 글씨)
    MonthlyRepayRateRole = Qt.ItemDataRole.UserRole + 16
    SourceRowRole = Qt.ItemDataRole.UserRole + 17   # 원본 모델에서의 행 번호 (묶어 보기용)
    RepayMethodRole = Qt.ItemDataRole.UserRole + 18
    HousingTypeRole = Qt.ItemDataRole.UserRole + 19
    MonthlyRole = Qt.ItemDataRole.UserRole + 20     # 주거의 월세
    GrowthRole = Qt.ItemDataRole.UserRole + 21      # 연 상승률 %
    SupportRole = Qt.ItemDataRole.UserRole + 22     # 적금 월 지원금
    LockedRole = Qt.ItemDataRole.UserRole + 23      # 만기 전까지 묶인 돈인가
    GroupPosRole = Qt.ItemDataRole.UserRole + 24    # 같은 분류 안에서 몇 번째인가 (묶어 보기 ▲▼ 용)
    GroupCountRole = Qt.ItemDataRole.UserRole + 25  # 같은 분류 항목이 몇 개인가
    ActiveRole = Qt.ItemDataRole.UserRole + 26      # 켜져 있는가 (꺼 두면 계산에서 빠진다)
    EveryRole = Qt.ItemDataRole.UserRole + 27       # 몇 개월마다 되풀이되는지 (0 = 한 번만)

    _ROLES = {
        NameRole: b"name",
        CategoryRole: b"category",
        CategoryIndexRole: b"categoryIndex",
        AmountRole: b"amount",
        AmountTextRole: b"amountText",
        RateRole: b"rate",
        RateTextRole: b"rateText",
        MonthlyTextRole: b"monthlyText",
        MonthlyKindRole: b"monthlyKind",
        IncludePrincipalRole: b"includePrincipal",
        UsesRateRole: b"usesRate",
        StartDateRole: b"startDate",
        EndDateRole: b"endDate",
        RepaymentsRole: b"repayments",
        SubTextRole: b"subText",
        MonthlyRepayRateRole: b"monthlyRepayRate",
        SourceRowRole: b"sourceRow",
        RepayMethodRole: b"repayMethod",
        HousingTypeRole: b"housingType",
        MonthlyRole: b"monthly",
        GrowthRole: b"growth",
        SupportRole: b"support",
        LockedRole: b"locked",
        GroupPosRole: b"groupPos",
        GroupCountRole: b"groupCount",
        ActiveRole: b"active",
        EveryRole: b"every",
    }

    def __init__(self, plan: Plan, parent: QObject | None = None):
        super().__init__(parent)
        self._plan = plan

    # ---- Qt 모델 필수 메서드 ----
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._plan.items)

    def roleNames(self) -> dict:  # noqa: N802
        return dict(self._ROLES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._plan.items)):
            return None
        it = self._plan.items[index.row()]
        if role == self.NameRole:
            return it.name
        if role == self.CategoryRole:
            return it.category.value
        if role == self.CategoryIndexRole:
            return CATEGORY_LIST.index(it.category)
        if role == self.AmountRole:
            return it.amount
        if role == self.AmountTextRole:
            return won(it.amount)
        if role == self.RateRole:
            return it.rate
        if role == self.RateTextRole:
            return f"{it.rate:.2f}%" if CATEGORY_INFO[it.category]["uses_rate"] else "-"
        if role == self.UsesRateRole:
            return CATEGORY_INFO[it.category]["uses_rate"]
        if role == self.IncludePrincipalRole:
            return it.include_principal
        if role == self.StartDateRole:
            return it.start_date or ""
        if role == self.EndDateRole:
            return it.end_date or ""
        if role == self.RepaymentsRole:
            return [dict(r) for r in it.repayments]
        if role == self.MonthlyRepayRateRole:
            return it.monthly_repay_rate
        if role == self.ActiveRole:
            return it.active
        if role == self.EveryRole:
            return it.every
        if role in (self.GroupPosRole, self.GroupCountRole):
            same = [k for k, x in enumerate(self._plan.items) if x.category == it.category]
            if role == self.GroupCountRole:
                return len(same)
            return same.index(index.row())
        if role == self.SourceRowRole:
            return index.row()
        if role == self.RepayMethodRole:
            return it.repay_method
        if role == self.HousingTypeRole:
            return it.housing_type
        if role == self.MonthlyRole:
            return it.monthly
        if role == self.GrowthRole:
            return it.growth
        if role == self.SupportRole:
            return it.support
        if role == self.LockedRole:
            return it.locked
        if role == self.SubTextRole:
            if it.date_mode == "once":
                d = parse_date(it.start_date) or (self._plan.basis if it.is_housing else None)
                if not d:
                    return ""
                om = it.once_month(self._plan.basis)
                word = "수입" if it.flow == "income" else "지출"
                when = f"지난 {word}" if om < 0 else (f"기준일에 {word}" if om == 0 else f"{om}개월 뒤 {word}")
                head = f"{it.housing_label} · {d.isoformat()[:7]} 입주" if it.is_housing else f"{d.isoformat()[:7]}  ·  {when}"
                parts = [head]
                if it.repeats:
                    n = self._plan.months
                    times = it.count_upto(n, self._plan.basis)
                    cycle = {3: "분기마다", 6: "반년마다", 12: "해마다"}.get(it.every, f"{it.every}개월마다")
                    tail = f"{cycle} · {n}개월 안에 {times}번"
                    if it.end_date:
                        tail += f" · {it.end_date[:7]} 까지"
                    parts.append(tail)
                if it.housing_rent() > 0:
                    parts.append(f"월세 {won(it.housing_rent())}")
                rm = it.return_month(self._plan.basis)
                if rm is not None:
                    parts.append(f"{it.end_date[:7]} 반환" + (f" ({rm}개월 뒤)" if rm > 0 else ""))
                return "  ·  ".join(parts)
            if not it.uses_dates:
                return ""
            start = (it.start_date or self._plan.start_date)[:7]
            end = it.end_date[:7] if it.end_date else "계속"
            parts = [f"{start} ~ {end}"]
            if it.category == Category.SAVING:
                basis = self._plan.basis
                n = self._plan.months
                k = it.saving_months(n, basis)
                if it.support > 0:
                    parts.append(f"내 돈 {won(it.amount)} + 지원 {won(it.support)} = 매달 {won(it.saving_deposit())}")
                parts.append(f"{n}개월 후 {won(it.saving_balance_at(n, basis))} ({k}회 납입)")
                if it.support > 0 and k > 0:
                    parts.append(f"받은 지원금 {won(it.support_total_at(n, basis))}")
                if it.is_locked(basis):
                    mat = it.maturity_month(basis)
                    parts.append(f"만기까지 묶임 · {mat}개월 뒤 {won(it.saving_balance_at(mat, basis))} 수령")
                elif it.locked:
                    parts.append("묶임 설정했지만 만기(종료일)가 없습니다")
            if it.category == Category.LOAN:
                basis = self._plan.basis
                label = REPAY_METHODS.get(it.repay_method, "")
                start_m, _end_m = it.active_range(basis)
                interest = it.interest_at(max(0, start_m), basis)
                if interest > 0:
                    parts.append(f"월 이자 {won(interest)}")
                if it.repay_method == "rate" and it.monthly_repay_amount() > 0:
                    n = it.months_to_payoff(basis)
                    parts.append(f"월 {it.monthly_repay_rate:g}% 상환 {won(it.monthly_repay_amount())}" + (f" · {n}개월 완납" if n else ""))
                elif it.repay_method in TERM_METHODS:
                    n = it.term_months(basis)
                    if n:
                        start_m, _ = it.active_range(basis)
                        parts.append(f"{label} {n}개월 · 첫 달 {won(it.payment_at(start_m, basis))}")
                    else:
                        parts.append(f"{label} · 종료일(만기) 필요")
                else:
                    parts.append(label)
            if it.repayments:
                parts.append(f"중도상환 {len(it.repayments)}건 {won(it.total_repaid())}")
            if it.growth:
                parts.append(f"해마다 {it.growth:g}% 인상")
            return "  ·  ".join(parts)
        if role in (self.MonthlyTextRole, self.MonthlyKindRole):
            basis = self._plan.basis
            if it.uses_dates and not it.is_active(0, basis):
                start_m, _end_m = it.active_range(basis)
                text = f"{start_m}개월 뒤 시작" if start_m > 0 else "종료됨"
                return text if role == self.MonthlyTextRole else "capital"
            net = it.monthly_net(basis)
            if it.category == Category.LOAN and it.include_principal and it.regular_repay_at(0, basis) > 0:
                # 원금 포함 대출: 이자는 지출, 정기 상환은 자본에서 빠짐 → 둘 다 매달 나가는 돈으로 표시
                net -= it.regular_repay_at(0, basis)
            if net > 0:
                kind, text = "income", "+" + won(net)
            elif net < 0:
                kind, text = "cost", won(net)
            elif it.once_cost() > 0:
                kind, text = "once", self._once_text(it, basis, "-" + won(it.once_cost()))
            elif it.once_income() > 0:
                kind, text = "income", self._once_text(it, basis, "+" + won(it.once_income()))
            else:
                kind, text = "capital", "자본"
            return text if role == self.MonthlyTextRole else kind
        return None

    def _renumbered_from(self, start: int) -> None:
        """start 이후 행의 번호가 밀렸다고 알린다.

        SourceRowRole 은 '행 번호' 그 자체라서 삭제·이동만으로 값이 달라진다.
        알리지 않으면 QML 델리게이트가 예전 번호를 들고 있다가 엉뚱한 항목을 지운다.
        """
        n = len(self._plan.items)
        if n:
            # 묶음 안 위치·개수는 start 앞쪽 항목도 달라질 수 있으므로 전부 알린다
            self.dataChanged.emit(self.index(0), self.index(n - 1),
                                  [self.SourceRowRole, self.GroupPosRole, self.GroupCountRole])

    def _once_text(self, it: Item, basis, money: str) -> str:
        """일시 지출·수입의 '월 환산' 칸 글. 되풀이면 몇 달마다인지 보여 준다."""
        if it.repeats:
            cycle = {3: "분기마다", 6: "반년마다", 12: "해마다"}.get(it.every, f"{it.every}개월마다")
            return f"{cycle} {money}"
        om = it.once_month(basis)
        prefix = f"{om}개월 뒤 " if om > 0 else ""
        return prefix + "일시 " + money

    def refresh_all(self) -> None:
        """기준일이 바뀌면 표시 문자열이 전부 달라지므로 전체 갱신."""
        if self._plan.items:
            self.dataChanged.emit(self.index(0), self.index(len(self._plan.items) - 1))

    # ---- 변경 (begin/end 호출로 QML 에 add/remove 애니메이션이 걸린다) ----
    def set_plan(self, plan: Plan) -> None:
        self.beginResetModel()
        self._plan = plan
        self.endResetModel()

    def add(self, item: Item) -> None:
        n = len(self._plan.items)
        self.beginInsertRows(QModelIndex(), n, n)
        self._plan.add(item)
        self.endInsertRows()

    def update(self, row: int, item: Item) -> None:
        if 0 <= row < len(self._plan.items):
            self._plan.items[row] = item
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

    def remove(self, row: int) -> Item | None:
        if not (0 <= row < len(self._plan.items)):
            return None
        self.beginRemoveRows(QModelIndex(), row, row)
        removed = self._plan.remove(row)
        self.endRemoveRows()
        self._renumbered_from(row)
        return removed

    def move(self, row: int, delta: int) -> bool:
        dst = row + delta
        n = len(self._plan.items)
        if not (0 <= row < n and 0 <= dst < n):
            return False
        # beginMoveRows 의 destinationChild 규칙: 아래로 옮길 땐 dst+1
        qt_dst = dst + 1 if delta > 0 else dst
        if not self.beginMoveRows(QModelIndex(), row, row, QModelIndex(), qt_dst):
            return False
        self._plan.move(row, delta)
        self.endMoveRows()
        self._renumbered_from(min(row, dst))
        return True

    def set_active(self, row: int, on: bool) -> bool:
        """항목을 켜거나 끈다. 목록에서 사라지지 않고 계산에서만 빠진다."""
        if not (0 <= row < len(self._plan.items)):
            return False
        it = self._plan.items[row]
        if it.active == on:
            return False
        it.active = on
        idx = self.index(row)
        self.dataChanged.emit(idx, idx)      # 역할을 가리지 않는다 (요약 글씨도 함께 흐려진다)
        return True

    def swap(self, a: int, b: int) -> bool:
        """떨어져 있는 두 줄의 자리를 맞바꾼다 (묶어 보기에서 같은 분류끼리 옮길 때).

        move() 는 이웃끼리만 바꾸므로, 사이에 다른 분류가 끼어 있으면 쓸 수 없다.
        beginMoveRows 를 두 번 써서 다른 줄은 그대로 두고 둘만 바꾼다.
        """
        n = len(self._plan.items)
        if a == b or not (0 <= a < n and 0 <= b < n):
            return False
        lo, hi = (a, b) if a < b else (b, a)
        items = self._plan.items
        if not self.beginMoveRows(QModelIndex(), hi, hi, QModelIndex(), lo):
            return False
        items.insert(lo, items.pop(hi))
        self.endMoveRows()
        # 방금 밀려난 '원래 lo' 가 지금 lo+1 에 있다. 그걸 hi 자리로 보낸다.
        if self.beginMoveRows(QModelIndex(), lo + 1, lo + 1, QModelIndex(), hi + 1):
            items.insert(hi, items.pop(lo + 1))
            self.endMoveRows()
        self._renumbered_from(lo)
        return True

    def clear(self) -> None:
        if not self._plan.items:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._plan.items) - 1)
        self._plan.clear()
        self.endRemoveRows()


class GroupedItems(QSortFilterProxyModel):
    """분류별로 묶어 보여주는 프록시. 분류 순서(CATEGORY_LIST)로 정렬한다.
    같은 분류 안에서는 원본 순서를 유지한다 (안정 정렬).

    접기는 '걸러내기'가 아니라 '화면에서 숨기기'다. 줄을 걸러내면 그 분류의
    섹션 헤더까지 사라져 다시 펼 수가 없고, 헤더를 누르는 순간 그 헤더 자신이
    파괴되면서 앱이 죽는다. 그래서 줄은 그대로 두고 QML 이 높이를 0 으로 만든다."""

    def __init__(self, source: ItemListModel, parent: QObject | None = None):
        super().__init__(parent)
        self._collapsed: set[int] = set()
        self._grouped = True          # 끄면 원본 순서 그대로 (ListView 의 모델은 바꾸지 않는다)
        self.setSourceModel(source)
        self.setSortRole(ItemListModel.CategoryIndexRole)
        self.setDynamicSortFilter(True)
        self.sort(0, Qt.SortOrder.AscendingOrder)

    def roleNames(self) -> dict:  # noqa: N802
        return self.sourceModel().roleNames()

    def set_grouped(self, on: bool) -> None:
        """분류별 묶기 켜기/끄기. 끄면 걸러내지도 정렬하지도 않는다."""
        on = bool(on)
        if on != self._grouped:
            self._grouped = on
            self.invalidate()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        if not self._grouped:
            return left.row() < right.row()        # 묶기를 끄면 원본 순서
        a = self.sourceModel().data(left, ItemListModel.CategoryIndexRole)
        b = self.sourceModel().data(right, ItemListModel.CategoryIndexRole)
        if a != b:
            return a < b
        return left.row() < right.row()        # 같은 분류: 원본 순서

    def is_collapsed(self, cat_index: int) -> bool:
        return cat_index in self._collapsed

    def toggle(self, cat_index: int) -> None:
        """접힘 상태만 바꾼다. 줄을 걸러내지 않으므로 모델 구조는 그대로다."""
        if cat_index in self._collapsed:
            self._collapsed.discard(cat_index)
        else:
            self._collapsed.add(cat_index)

    def expand_all(self) -> None:
        self._collapsed.clear()




class LedgerModel(QAbstractListModel):
    """가계부 내역을 기간으로 걸러서 보여주는 리스트 모델 (최신 날짜가 위)."""

    DateRole = Qt.ItemDataRole.UserRole + 1
    DateTextRole = Qt.ItemDataRole.UserRole + 2
    CategoryRole = Qt.ItemDataRole.UserRole + 3
    NameRole = Qt.ItemDataRole.UserRole + 4
    AmountRole = Qt.ItemDataRole.UserRole + 5
    AmountTextRole = Qt.ItemDataRole.UserRole + 6
    KindRole = Qt.ItemDataRole.UserRole + 7
    NoteRole = Qt.ItemDataRole.UserRole + 8
    SourceRowRole = Qt.ItemDataRole.UserRole + 9   # Ledger.entries 에서의 번호
    DaySectionRole = Qt.ItemDataRole.UserRole + 10  # 날짜 구분 헤더용
    RuleRole = Qt.ItemDataRole.UserRole + 11        # 고정 규칙이 적어 준 줄이면 그 번호
    SelectedRole = Qt.ItemDataRole.UserRole + 12    # 여러 건 고르기에서 골라졌는가
    PayRole = Qt.ItemDataRole.UserRole + 13         # 결제수단

    _ROLES = {
        DateRole: b"date",
        DateTextRole: b"dateText",
        CategoryRole: b"category",
        NameRole: b"name",
        AmountRole: b"amount",
        AmountTextRole: b"amountText",
        KindRole: b"kind",
        NoteRole: b"note",
        SourceRowRole: b"sourceRow",
        DaySectionRole: b"daySection",
        RuleRole: b"rule",
        SelectedRole: b"selected",
        PayRole: b"pay",
    }

    def __init__(self, ledger: Ledger, parent: QObject | None = None):
        super().__init__(parent)
        self._ledger = ledger
        # 고른 줄 (Ledger.entries 의 번호). Backend 가 가진 집합을 그대로 가리킨다
        self._selection: set[int] = set()
        self._period = ""
        self._query = ""
        self._kind = ""
        self._category = ""
        self._pay = ""
        self._min = 0.0
        self._max = 0.0
        self._sort = "date"          # "date" | "amount"
        self._desc = True
        self._rows: list[int] = []
        self._rebuild()

    def roleNames(self):
        return dict(self._ROLES)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        src = self._rows[index.row()]
        e = self._ledger.entries[src]
        if role == self.DateRole:
            return e.date
        if role == self.DateTextRole:
            d = e.day
            return f"{d.month}월 {d.day}일"
        if role == self.CategoryRole:
            return e.category
        if role == self.NameRole:
            return e.name
        if role == self.AmountRole:
            return e.amount
        if role == self.AmountTextRole:
            return ("+" if e.is_income else "-") + won(e.amount)
        if role == self.KindRole:
            return e.kind
        if role == self.NoteRole:
            return e.note
        if role == self.SourceRowRole:
            return src
        if role == self.DaySectionRole:
            return e.date if self._sort == "date" else ""
        if role == self.RuleRole:
            return e.rule
        if role == self.PayRole:
            return e.pay
        if role == self.SelectedRole:
            return src in self._selection
        return None

    # ---- 갱신 ----
    def _rebuild(self) -> None:
        key = sort_key(self._sort)
        rows = [(key(e), i) for i, e in enumerate(self._ledger.entries)
                if self._ledger.matches(e, self._period, self._query, self._kind,
                                        self._category, self._pay, self._min, self._max)]
        rows.sort(key=lambda t: t[0], reverse=self._desc)
        self._rows = [i for _, i in rows]

    def refresh(self) -> None:
        self.beginResetModel()
        self._rebuild()
        self.endResetModel()

    def set_selection(self, selection: set) -> None:
        """Backend 의 집합을 그대로 들고 있는다 (복사하면 둘이 어긋난다)."""
        self._selection = selection
        self.refresh_selection()

    def refresh_selection(self) -> None:
        """고른 줄 표시만 다시 그린다 (목록을 통째로 새로 만들지 않는다)."""
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1),
                                  [self.SelectedRole])

    def visible_sources(self) -> list[int]:
        """지금 보이는 줄들의 Ledger.entries 번호."""
        return list(self._rows)

    def set_ledger(self, ledger: Ledger) -> None:
        self.beginResetModel()
        self._ledger = ledger
        self._rebuild()
        self.endResetModel()

    def set_period(self, period: str) -> None:
        if period != self._period:
            self.beginResetModel()
            self._period = period
            self._rebuild()
            self.endResetModel()

    def set_filters(self, query: str, kind: str, category: str, pay: str = "",
                    min_amount: float = 0.0, max_amount: float = 0.0) -> None:
        want = (query, kind, category, pay, min_amount, max_amount)
        if want != (self._query, self._kind, self._category, self._pay, self._min, self._max):
            self.beginResetModel()
            (self._query, self._kind, self._category, self._pay,
             self._min, self._max) = want
            self._rebuild()
            self.endResetModel()

    def set_sort(self, sort: str, desc: bool) -> None:
        if (sort, desc) != (self._sort, self._desc):
            self.beginResetModel()
            self._sort, self._desc = sort, desc
            self._rebuild()
            self.endResetModel()


def undoable(label: str):
    """이 슬롯이 무언가를 바꿨으면, 바꾸기 전 상태를 되돌리기 더미에 올린다.

    하기 전/후를 견줘서 **정말 바뀐 경우에만** 쌓는다. 이름이 겹쳐 거절된
    '계획에서 가져오기' 처럼 아무 일도 안 일어난 동작으로 더미가 더러워지면,
    Ctrl+Z 를 눌러도 아무 일도 안 일어나는 것처럼 보이기 때문이다.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            before = self._ws.to_dict()
            path = self._data_path
            out = fn(self, *args, **kwargs)
            if self._ws.to_dict() != before:
                self._push_undo(label, before, path)
            return out
        return wrapper
    return deco


class Backend(QObject):
    """QML 에서 `backend` 이름으로 접근하는 객체."""

    summaryChanged = Signal()
    monthsChanged = Signal()
    targetChanged = Signal()
    basisDateChanged = Signal()
    statusChanged = Signal()
    itemsChanged = Signal()
    dataPathChanged = Signal()
    groupsChanged = Signal()        # 묶어 보기 켜짐/꺼짐, 접힘 상태 변화
    scenariosChanged = Signal()     # 시나리오 추가/삭제/이름/활성 변경
    ledgerChanged = Signal()        # 가계부 내역·기간 변경
    budgetsChanged = Signal()       # 예산만 변경 (가계부 집계는 그대로)
    fixedChanged = Signal()         # 고정 지출·수입 규칙 변경
    undoChanged = Signal()          # 되돌리기 더미 변경
    selectionChanged = Signal()     # 가계부에서 고른 줄 변경
    importChanged = Signal()        # 가져오기 미리보기 변경
    saved = Signal(str)        # 저장 완료 (경로)
    exported = Signal(str)     # 엑셀 내보내기 완료 (경로)
    loaded = Signal(str)       # 불러오기 완료 (경로)
    failed = Signal(str)       # 실패 메시지

    def __init__(self, plan: Plan | Workspace | None = None, parent: QObject | None = None):
        super().__init__(parent)
        if isinstance(plan, Workspace):
            self._ws = plan
        elif plan is not None:
            self._ws = Workspace([plan])
        else:
            self._ws = self._load_or_sample()
        self._plan = self._ws.plan
        self._items = ItemListModel(self._plan, self)
        self._ledger_model = LedgerModel(self._ws.ledger, self)
        self._selected: set[int] = set()        # 가계부에서 고른 줄 (entries 번호)
        self._import: list[dict] = []           # 가져오기 미리보기 (아직 넣지 않은 내역)
        self._import_info: dict = {}
        self._ledger_model.set_selection(self._selected)
        self._ledger_year = ""
        self._ledger_month = 0          # 0 = 그 해 전체
        self._ledger_query = ""
        self._ledger_kind = ""          # "" | income | cost
        self._ledger_category = ""      # "" = 전체
        self._ledger_pay = ""           # "" = 전체 (결제수단 거르기)
        self._ledger_min = 0.0          # 금액 범위 (0 = 제한 없음)
        self._ledger_max = 0.0
        self._ledger_sort = "date"      # "date" | "amount"
        self._ledger_desc = True        # 큰 것·최신이 위
        self._grouped = GroupedItems(self._items, self)
        self._group_by_category = True
        self._status = ""
        # 한 번 계산한 요약·부족 구간·들어올 돈을 담아 둔다.
        # QML 은 바인딩마다 이 값을 읽으므로 (기간 1개월 바꾸면 summary 만 187번)
        # 계획이 바뀔 때까지는 같은 결과를 돌려준다.
        self._cache: dict = {}
        self._end_text = ""            # 사용자가 직접 친 종료일 (개월 수와 맞는 동안 그대로 보여 준다)
        # 되돌리기: (무엇을 했는지, 그 전 상태, 그때의 파일 경로)
        self._undo: list[tuple[str, dict, Path]] = []
        self._redo: list[tuple[str, dict, Path]] = []
        self.summaryChanged.connect(self._clear_cache)
        self._data_path = Path(DATA_FILE)
        # 모델이 바뀌면 요약도 다시 계산되도록 연결
        for sig in (
            self._items.rowsInserted,
            self._items.rowsRemoved,
            self._items.rowsMoved,
            self._items.dataChanged,
            self._items.modelReset,
        ):
            sig.connect(self._emit_summary)

    @staticmethod
    def _load_or_sample() -> Workspace:
        if DATA_FILE.exists():
            try:
                return Workspace.load(DATA_FILE)
            except Exception:
                pass
        return Workspace([sample_plan()])

    def _emit_summary(self, *_args) -> None:
        self._summary_changed()
        self.itemsChanged.emit()

    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    # ------------------------------------------------------------ 프로퍼티
    @Property(QObject, constant=True)
    def items(self) -> ItemListModel:
        return self._items

    @Property(int, notify=itemsChanged)
    def offCount(self) -> int:
        """꺼 둔 항목 수 (계산에서 빠져 있다)."""
        return self._plan.off_count

    @Property(int, notify=itemsChanged)
    def itemCount(self) -> int:
        return len(self._plan.items)

    # ---- 분류별 묶어 보기 ----
    @Property(QObject, constant=True)
    def groupedItems(self) -> GroupedItems:
        return self._grouped

    def _get_group_by(self) -> bool:
        return self._group_by_category

    def _set_group_by(self, v: bool) -> None:
        v = bool(v)
        if v != self._group_by_category:
            self._group_by_category = v
            if not v:
                self._grouped.expand_all()
            self._grouped.set_grouped(v)
            self.groupsChanged.emit()

    groupByCategory = Property(bool, _get_group_by, _set_group_by, notify=groupsChanged)

    @Slot(int, result=int)
    def sourceRowAt(self, visible_row: int) -> int:
        """목록에서 보이는 N번째 줄이 원본에서 몇 번째인지. 없으면 -1.

        삭제·순서 변경처럼 되돌릴 수 없는 동작은 저장해 둔 번호 대신 이걸로 그 자리에서 확인한다.
        """
        idx = self._grouped.index(visible_row, 0)
        if not idx.isValid():
            return -1
        return self._grouped.mapToSource(idx).row()

    @Slot(int)
    def toggleGroup(self, cat_index: int) -> None:
        self._grouped.toggle(cat_index)
        self.groupsChanged.emit()

    @Slot(int, result=bool)
    def isGroupCollapsed(self, cat_index: int) -> bool:
        return self._grouped.is_collapsed(cat_index)

    @Slot(str, result="QVariantMap")
    def groupSummary(self, category_name: str) -> dict:
        """분류 이름 → {count, total(금액 합), monthly(월 환산 합), catIndex}."""
        try:
            cat = Category(category_name)
        except ValueError:
            return {"count": 0, "total": 0.0, "monthly": 0.0, "catIndex": -1}
        basis = self._plan.basis
        all_items = [i for i in self._plan.items if i.category == cat]
        items = [i for i in all_items if i.active]       # 합계는 켜진 것만
        monthly = 0.0
        for it in items:
            net = it.monthly_net_at(0, basis)
            if it.category == Category.LOAN and it.include_principal:
                net -= it.regular_repay_at(0, basis)
            monthly += net
        return {
            "count": len(all_items),
            "off": len(all_items) - len(items),
            "total": sum(i.amount for i in items),
            "monthly": monthly,
            "catIndex": CATEGORY_LIST.index(cat),
        }

    # ---- 시나리오 ----
    @Property("QVariantList", notify=scenariosChanged)
    def scenarioNames(self) -> list[str]:
        return self._ws.names()

    @Property(int, notify=scenariosChanged)
    def scenarioCount(self) -> int:
        return len(self._ws.plans)

    def _get_active_scenario(self) -> int:
        return self._ws.active

    def _set_active_scenario(self, i: int) -> None:
        i = int(i)
        if 0 <= i < len(self._ws.plans) and i != self._ws.active:
            self._ws.active = i
            self._replace_plan(self._ws.plan)
            self._set_status(f"시나리오 전환: {self._ws.plan.name}")

    activeScenario = Property(int, _get_active_scenario, _set_active_scenario, notify=scenariosChanged)

    @Slot()
    @Slot(str)
    @undoable("시나리오 추가")
    def addScenario(self, name: str = "") -> None:
        """빈 시나리오를 추가하고 활성화. 기간·목표·기준일은 현재 것을 이어받는다."""
        p = self._ws.add(name)
        self._replace_plan(p)
        self._set_status(f"시나리오 추가: {p.name}")

    @Slot()
    @undoable("시나리오 복제")
    def duplicateScenario(self) -> None:
        """현재 시나리오를 복제하고 복제본을 활성화."""
        p = self._ws.duplicate()
        self._replace_plan(p)
        self._set_status(f"시나리오 복제: {p.name}")

    @Slot(int)
    @undoable("시나리오 삭제")
    def removeScenario(self, index: int) -> None:
        name = self._ws.plans[index].name if 0 <= index < len(self._ws.plans) else ""
        if not self._ws.remove(index):
            self.failed.emit("시나리오는 최소 1개 있어야 합니다.")
            return
        self._replace_plan(self._ws.plan)
        self._set_status(f"시나리오 삭제: {name}")

    @Slot(int, str)
    @undoable("시나리오 이름 바꾸기")
    def renameScenario(self, index: int, name: str) -> None:
        if self._ws.rename(index, name):
            self.scenariosChanged.emit()
            self._set_status(f"시나리오 이름 변경: {name.strip()}")

    def _goal_text(self, plan: Plan) -> str:
        s = plan.summary()
        m = s.goal_month()
        if plan.target <= 0:
            return "목표 없음"
        if m is None:
            return "도달 불가"
        if m == 0:
            return "이미 달성"
        d = add_months(plan.basis, m)
        return f"{d.year}년 {d.month}월 ({m}개월)"

    @Slot(int, result="QVariantList")
    def compareTrends(self, horizon: int) -> list[dict]:
        """모든 시나리오의 0..horizon 개월 순 자본. [{index, name, active, values, goalMonth}]"""
        key = f"cmp{max(1, horizon)}"
        if key in self._cache:
            return self._cache[key]
        out = []
        for i, p in enumerate(self._ws.plans):
            gm = p.summary().goal_month() if p.target > 0 else None
            out.append({
                "index": i,
                "name": p.name,
                "active": i == self._ws.active,
                "values": p.net_series(max(1, horizon)),
                "goalMonth": -1 if gm is None else gm,
            })
        self._cache[key] = out
        return out

    @Slot(result="QVariantList")
    def compareRows(self) -> list[dict]:
        """비교표: 현재 시나리오의 기간(N개월) 기준으로 모든 시나리오를 나란히.
        [{index, name, active, net, diff, monthlyNet, target, goalText}]"""
        if "rows" in self._cache:
            return self._cache["rows"]
        n = max(0, self._plan.months)
        base = self._plan.net_at(n)
        rows = []
        for i, p in enumerate(self._ws.plans):
            net = p.net_at(n)
            rows.append({
                "index": i,
                "name": p.name,
                "active": i == self._ws.active,
                "net": net,
                "diff": net - base,
                "monthlyNet": p.monthly_income_at(0) - p.monthly_cost_at(0),
                "target": p.target,
                "goalText": self._goal_text(p),
            })
        self._cache["rows"] = rows
        return rows

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=dataPathChanged)
    def dataPath(self) -> str:
        """현재 저장/불러오기에 쓰는 파일의 전체 경로."""
        return str(self._data_path)

    @Property(str, notify=dataPathChanged)
    def dataDirUrl(self) -> str:
        """파일 대화상자 시작 폴더 (file:// URL)."""
        return QUrl.fromLocalFile(str(self._data_path.parent)).toString()

    @staticmethod
    def _to_path(url_or_path: str) -> Path:
        u = QUrl(url_or_path)
        if u.isLocalFile():
            return Path(u.toLocalFile())
        return Path(url_or_path)

    @Property("QVariantList", constant=True)
    def categories(self) -> list[str]:
        return [c.value for c in CATEGORY_LIST]

    def _get_months(self) -> int:
        return self._plan.months

    def _set_months(self, v: int) -> None:
        v = max(0, int(v))
        if v != self._plan.months:
            self._plan.months = v
            self._end_text = ""            # 슬라이더로 바꿨으니 기억해 둔 종료일은 버린다
            self._items.refresh_all()      # 목록의 'N개월 후 …' 표시가 기간을 따라간다
            self.monthsChanged.emit()
            self._summary_changed()

    months = Property(int, _get_months, _set_months, notify=monthsChanged)

    def _get_end_date(self) -> str:
        """기간의 끝 날짜. 직접 친 날짜가 있으면 그대로, 아니면 기준일에서 months 개월 뒤."""
        if self._end_text:
            d = parse_date(self._end_text)
            if d and month_offset(self._plan.basis, d) == self._plan.months:
                return self._end_text          # 친 날짜가 지금 기간과 맞으면 그대로
        return add_months(self._plan.basis, self._plan.months).isoformat()

    def _set_end_date(self, v: str) -> None:
        """끝 날짜로 기간을 정한다 (개월 수를 거꾸로 계산). 친 날짜는 그대로 기억한다."""
        d = parse_date(v)
        if d is None:
            return
        months = max(0, month_offset(self._plan.basis, d))
        if months == self._plan.months:
            self._end_text = d.isoformat()
            self._summary_changed()         # 개월 수는 그대로여도 보여 줄 날짜가 바뀐다
        else:
            self.months = months               # 여기서 _end_text 를 비우므로
            self._end_text = d.isoformat()     # 친 날짜는 그 뒤에 기억한다

    # 기준일이 바뀌어도 끝 날짜가 달라지므로 summaryChanged 로 알린다 (둘 다에서 올라온다)
    endDate = Property(str, _get_end_date, _set_end_date, notify=summaryChanged)

    @Property(str, notify=summaryChanged)
    def endDateText(self) -> str:
        """'2029년 1월' — 기간 옆에 곁들여 보여 준다."""
        return self._month_text(self._plan.months)

    def _get_target(self) -> float:
        return self._plan.target

    def _set_target(self, v: float) -> None:
        v = max(0.0, float(v))
        if v != self._plan.target:
            self._plan.target = v
            self.targetChanged.emit()
            self._summary_changed()

    target = Property(float, _get_target, _set_target, notify=targetChanged)

    def _get_basis_date(self) -> str:
        return self._plan.start_date

    def _set_basis_date(self, v: str) -> None:
        d = parse_date(v)
        if d is None:
            self.basisDateChanged.emit()      # 잘못된 입력: 화면을 원래 값으로 되돌리기 위해 신호만
            return
        iso = d.isoformat()
        if iso != self._plan.start_date:
            self._plan.start_date = iso
            self.basisDateChanged.emit()
            self._items.refresh_all()
            self._summary_changed()

    basisDate = Property(str, _get_basis_date, _set_basis_date, notify=basisDateChanged)

    @Slot(str, result=bool)
    def isValidDate(self, v: str) -> bool:
        return v.strip() == "" or parse_date(v) is not None

    def _clear_cache(self) -> None:
        """계획이 바뀌었으니 담아 둔 계산 결과를 버린다 (summaryChanged 가 올 때마다)."""
        self._cache.clear()

    def _summary_changed(self) -> None:
        """요약이 달라졌다고 알린다. **알리기 전에** 담아 둔 계산을 버린다.

        QML 바인딩은 알림을 받는 그 자리에서 값을 다시 읽는데, QML 쪽 연결이
        파이썬 슬롯(_clear_cache)보다 먼저 불릴 수 있다. 그러면 캐시가 아직
        남아 있어 바뀌기 전 숫자를 그대로 읽어 간다 — 항목을 껐는데 요약은
        그대로인 것처럼 보였던 게 이것이다.
        """
        self._cache.clear()
        self.summaryChanged.emit()

    def _cached(self, key: str, make):
        v = self._cache.get(key)
        if v is None:
            v = self._cache[key] = make()
        return v

    # 요약 값들 (전부 summaryChanged 로 갱신)
    def _s(self):
        return self._cached("summary", self._plan.summary)

    def _sf(self):
        return self._cached("shortfall", self._plan.shortfall)

    def _pending(self):
        return self._cached("pending", self._plan.pending_inflows)

    def _series(self, upto: int) -> list[float]:
        """0..upto 개월 순 자본. 한 번 구해 두고 모자랄 때만 더 멀리까지 다시 구한다."""
        s = self._cache.get("series")
        if s is None or len(s) <= upto:
            s = self._cache["series"] = self._plan.net_series(max(upto, self._plan.months, 36))
        return s

    @Property(float, notify=summaryChanged)
    def capital(self) -> float:
        return self._s().capital

    @Property(float, notify=summaryChanged)
    def capitalAtEnd(self) -> float:
        """기간이 끝나는 시점의 보유 자금. 적금이 쌓이고 예금 이자가 붙어 지금과 다르다."""
        return self._plan.capital_at(self._plan.months)

    @Property(float, notify=summaryChanged)
    def capitalGrowth(self) -> float:
        """보유 자금이 기간 동안 얼마나 늘었는지 (적금 적립·이자·대출 원금 유입)."""
        return self.capitalAtEnd - self._s().capital

    @Property(float, notify=summaryChanged)
    def onceCost(self) -> float:
        return self._s().once_cost

    @Property(float, notify=summaryChanged)
    def onceIncome(self) -> float:
        return self._s().once_income

    @Property(float, notify=summaryChanged)
    def monthlyCost(self) -> float:
        return self._s().monthly_cost

    @Property(float, notify=summaryChanged)
    def monthlyIncome(self) -> float:
        return self._s().monthly_income

    @Property(float, notify=summaryChanged)
    def monthlyNet(self) -> float:
        return self._s().monthly_net

    # ---- 기간을 반영한 월 수지 (기간 중에 시작하는 이자·월세까지 센다) ----
    @Property(float, notify=summaryChanged)
    def avgMonthlyCost(self) -> float:
        return self._s().avg_cost

    @Property(float, notify=summaryChanged)
    def avgMonthlyIncome(self) -> float:
        return self._s().avg_income

    @Property(float, notify=summaryChanged)
    def avgMonthlyNet(self) -> float:
        return self._s().avg_net

    @Property(float, notify=summaryChanged)
    def lastMonthlyCost(self) -> float:
        return self._s().last_cost

    @Property(float, notify=summaryChanged)
    def lastMonthlyIncome(self) -> float:
        return self._s().last_income

    @Property(float, notify=summaryChanged)
    def lastMonthlyNet(self) -> float:
        return self._s().last_net

    @Property(bool, notify=summaryChanged)
    def monthlyVaries(self) -> bool:
        """기간 중에 월 수지가 달라지는가 (달라지면 '지금 → 마지막 달' 을 같이 보여 준다)."""
        return self._s().monthly_varies

    @Property(float, notify=summaryChanged)
    def required(self) -> float:
        return self._s().required

    @Property(float, notify=summaryChanged)
    def periodIncome(self) -> float:
        return self._s().period_income

    @Property(float, notify=summaryChanged)
    def net(self) -> float:
        return self._s().net

    @Property(float, notify=summaryChanged)
    def gap(self) -> float:
        return self._s().gap

    @Property(float, notify=summaryChanged)
    def progress(self) -> float:
        return self._s().progress

    PENDING_LABELS = {"deposit": "돌려받을 보증금", "saving": "만기에 받을 적금", "loan": "받을 대출"}

    @Property("QVariantMap", notify=summaryChanged)
    def pendingInflow(self) -> dict:
        """기간이 끝난 뒤에 들어올 돈 (목표 바에 색을 달리해 이어 붙인다).

        {has, total, count, withNet, shortfall, progress, progressWith,
         groups: [{kind, label, total, count, month, dateText, name, progressTo}]}
        groups 의 progressTo 는 순 자본에 이 종류까지 더했을 때의 달성률이다 (바 구간 끝).
        """
        s = self._s()
        net, target = s.net, self._plan.target

        def frac(v: float) -> float:
            return max(0.0, v / target) if target > 0 else 1.0

        rows = self._pending()
        total = sum(r["amount"] for r in rows)
        if not rows or total <= 0:
            return {"has": False, "total": 0.0, "count": 0, "withNet": net,
                    "shortfall": max(0.0, target - net), "progress": s.progress,
                    "progressWith": s.progress, "groups": []}

        groups = []
        running = net
        for kind in ("deposit", "saving", "loan"):       # 바에 칠하는 순서
            part = [r for r in rows if r["kind"] == kind]
            if not part:
                continue
            part.sort(key=lambda d: d["month"])
            amount = sum(r["amount"] for r in part)
            running += amount
            first = part[0]
            groups.append({
                "kind": kind,
                "label": self.PENDING_LABELS[kind],
                "total": amount,
                "count": len(part),
                "month": first["month"],
                "dateText": self._month_text(first["month"]),
                "name": first["name"] if len(part) == 1 else f"{first['name']} 외 {len(part) - 1}건",
                "progressTo": frac(running),
            })

        with_net = net + total
        return {
            "has": True,
            "total": total,
            "count": len(rows),
            "withNet": with_net,
            "shortfall": max(0.0, target - with_net),
            "progress": s.progress,
            "progressWith": frac(with_net),
            "groups": groups,
        }

    @Property(int, notify=summaryChanged)
    def monthsToGoal(self) -> int:
        """목표까지 추가로 필요한 개월. 이미 달성 0, 도달 불가 -1."""
        m = self._s().months_to_goal()
        return -1 if m is None else m

    # ---- 달성 예측 ----
    @Property(int, notify=summaryChanged)
    def goalMonth(self) -> int:
        """기준일로부터 목표에 처음 닿는 개월 (0 = 이미 달성). 50년 내 불가능이면 -1."""
        m = self._s().goal_month()
        return -1 if m is None else m

    @Property(str, notify=summaryChanged)
    def goalDateText(self) -> str:
        """달성 예상 시점 'YYYY년 M월'. 불가능이면 빈 문자열."""
        m = self._s().goal_month()
        if m is None:
            return ""
        d = add_months(self._plan.basis, m)
        return f"{d.year}년 {d.month}월"

    @Property(float, notify=summaryChanged)
    def peakNet(self) -> float:
        """50년 내 순 자본 최댓값 (도달 불가일 때 '최대 얼마까지' 안내용)."""
        s = self._s()
        return max(s.net_at(m) for m in range(0, s.MAX_LOOKAHEAD + 1))

    @Property("QVariantList", notify=summaryChanged)
    def trend(self) -> list[float]:
        s = self._s()
        return [s.net_at(m) for m in range(s.months + 1)]

    MILESTONE_MONTHS = (6, 12, 24, 36)

    @Property("QVariantList", notify=summaryChanged)
    def milestones(self) -> list[dict]:
        """6/12/24/36개월 시점 지표. 그래프 마커와 표에 사용."""
        s = self._s()
        out = []
        for m in self.MILESTONE_MONTHS:
            net = s.net_at(m)
            out.append({
                "month": m,
                "net": net,
                "gap": net - s.target,
                "progress": (net / s.target) if s.target > 0 else 1.0,
                "reached": s.target <= 0 or net >= s.target,
            })
        return out

    @Slot(int, result="QVariantList")
    def trendFor(self, months: int) -> list[float]:
        """임의 기간의 월별 순 자본 (그래프 보기 기간 전환용)."""
        n = max(1, months)
        return self._series(n)[:n + 1]

    @Slot(int, result=float)
    def netAt(self, month: int) -> float:
        m = max(0, int(month))
        return self._series(m)[m]

    # ------------------------------------------------------------ 슬롯
    @Slot(float, result=str)
    def won(self, v: float) -> str:
        return won(v)

    @Slot(int, result="QVariantMap")
    def categoryInfo(self, cat_index: int) -> dict:
        cat = CATEGORY_LIST[max(0, min(cat_index, len(CATEGORY_LIST) - 1))]
        info = CATEGORY_INFO[cat]
        return {
            "amountLabel": info["amount_label"],
            "usesRate": info["uses_rate"],
            "hint": info["hint"],
            "isLoan": cat == Category.LOAN,
            "dateMode": info["date_mode"],
            "usesDates": info["date_mode"] == "range",
            "group": info["group"],
            "returnable": bool(info.get("returnable")),
            "isHousing": bool(info.get("housing")),
            "usesGrowth": bool(info.get("uses_growth")),
            "usesSupport": bool(info.get("uses_support")),
            "canLock": cat == Category.SAVING,
            "flow": info["flow"],
            "onceWord": "수입" if info["flow"] == "income" else "지출",
        }

    @Property("QVariantList", constant=True)
    def housingTypes(self) -> list[dict]:
        """주거 형태 [{value, label}] (팝업 콤보박스용)."""
        return [{"value": k, "label": v} for k, v in HOUSING_TYPE_LIST]

    @Slot(str, result="QVariantMap")
    def housingInfo(self, housing_type: str) -> dict:
        """주거 형태별 입력 안내. {label, amountLabel, usesRent, returnable, hint}"""
        t = housing_type if housing_type in HOUSING_TYPES else "jeonse"
        info = HOUSING_INFO[t]
        return {
            "label": HOUSING_TYPES[t],
            "amountLabel": info["amount_label"],
            "usesRent": info["uses_rent"],
            "returnable": info["returnable"],
            "hint": info["hint"],
        }

    @Property("QVariantList", constant=True)
    def repayMethods(self) -> list[dict]:
        """대출 상환 방식 [{value, label}] (팝업 콤보박스용)."""
        return [{"value": k, "label": v} for k, v in REPAY_METHOD_LIST]

    @Slot(float, float, str, str, str, float, result="QVariantMap")
    def loanPreview(self, amount: float, rate: float, method: str,
                    start_date: str, end_date: str, monthly_repay_rate: float) -> dict:
        """팝업에서 보여줄 상환 미리보기. {method, months, needsEnd, first, last, totalInterest, text}"""
        basis = self._plan.basis
        sd, ed = parse_date(start_date), parse_date(end_date)
        it = Item("", Category.LOAN, max(0.0, amount), max(0.0, rate),
                  start_date=sd.isoformat() if sd else None,
                  end_date=ed.isoformat() if ed else None,
                  monthly_repay_rate=max(0.0, monthly_repay_rate),
                  repay_method=method if method in REPAY_METHODS else "")
        start_m, _end_m = it.active_range(basis)
        n = it.term_months(basis)
        needs_end = it.repay_method in TERM_METHODS and not n
        out = {"method": it.repay_method, "months": n or 0, "needsEnd": needs_end,
               "first": 0.0, "last": 0.0, "totalInterest": 0.0, "text": ""}
        if amount <= 0:
            out["text"] = "대출 원금을 입력하세요."
            return out
        if needs_end:
            out["text"] = "원금 균등·원리금 균등은 종료일(만기)을 넣어야 월 상환액이 계산됩니다."
            return out
        out["first"] = it.payment_at(start_m, basis)
        out["totalInterest"] = it.total_interest(basis)
        if it.repay_method == "bullet":
            out["text"] = (f"매달 이자 {won(it.interest_at(start_m, basis))}"
                           + (f"  ·  {n}개월 뒤 만기에 원금 {won(amount)} 일시 상환"
                              f"  ·  총 이자 {won(out['totalInterest'])}" if n
                              else "  ·  종료일이 없으면 이자만 계속 냅니다"))
        elif it.repay_method == "rate":
            per = it.monthly_repay_amount()
            if per <= 0:
                out["text"] = "상환율이 0% 이면 원금은 그대로이고 이자만 나갑니다."
            else:
                k = it.months_to_payoff(basis)
                out["text"] = (f"매달 원금 {won(per)} 상환  ·  첫 달 {won(out['first'])} (원금+이자)"
                               + (f"  ·  약 {k}개월 뒤 완납" if k else ""))
        else:
            out["last"] = it.payment_at(start_m + n - 1, basis)
            label = REPAY_METHODS[it.repay_method]
            if it.repay_method == "equal_payment":
                out["text"] = (f"{label}  ·  {n}개월 동안 매달 {won(out['first'])}"
                               f"  ·  총 이자 {won(out['totalInterest'])}"
                               f"  ·  총 상환 {won(amount + out['totalInterest'])}")
            else:
                out["text"] = (f"{label}  ·  {n}개월  ·  첫 달 {won(out['first'])} → 마지막 달 {won(out['last'])}"
                               f"  ·  총 이자 {won(out['totalInterest'])}")
        return out

    # ---- 현금 부족 경고 ----
    def _month_text(self, m: int) -> str:
        d = add_months(self._plan.basis, m)
        return f"{d.year}년 {d.month}월"

    @Property("QVariantMap", notify=summaryChanged)
    def shortfall(self) -> dict:
        """순 자본이 음수가 되는 구간. has 가 False 면 경고 없음."""
        s = self._sf()
        m = s["month"]
        return {
            "has": m is not None,
            "month": -1 if m is None else m,
            "dateText": "" if m is None else self._month_text(m),
            "net": 0.0 if m is None else self._plan.net_at(m),
            "months": s["months"],
            "minMonth": s["min_month"],
            "minNet": s["min_net"],
            "minDateText": self._month_text(s["min_month"]),
            "horizon": s["horizon"],
        }

    @Slot(float, float, result=float)
    def monthlyInterest(self, amount: float, rate: float) -> float:
        return amount * rate / 100.0 / 12.0

    @Slot(float, float, result=int)
    def payoffMonths(self, amount: float, monthly_repay_rate: float) -> int:
        """원금의 월 상환율로 완납까지 걸리는 개월 (0 이면 정기 상환 없음)."""
        import math
        if amount <= 0 or monthly_repay_rate <= 0:
            return 0
        return math.ceil(100.0 / monthly_repay_rate)

    @staticmethod
    def _parse_repayments(repayments_json: str) -> list[dict]:
        """QML 에서 넘어온 JSON 문자열 → [{"date","amount"}]. 날짜가 잘못되거나 금액 0 이하는 버린다."""
        try:
            raw = json.loads(repayments_json or "[]")
        except ValueError:
            return []
        out = []
        for r in raw if isinstance(raw, list) else []:
            if not isinstance(r, dict):
                continue
            d = parse_date(str(r.get("date", "")))
            try:
                amt = float(r.get("amount", 0) or 0)
            except (TypeError, ValueError):
                amt = 0.0
            if d is not None and amt > 0:
                out.append({"date": d.isoformat(), "amount": amt})
        out.sort(key=lambda r: r["date"])
        return out

    def _make_item(self, name: str, cat_index: int, amount: float, rate: float, include_principal: bool,
                   start_date: str = "", end_date: str = "", repayments_json: str = "[]",
                   monthly_repay_rate: float = 0.0, repay_method: str = "",
                   housing_type: str = "", monthly: float = 0.0, growth: float = 0.0,
                   support: float = 0.0, locked: bool = False, every: int = 0) -> Item:
        cat = CATEGORY_LIST[max(0, min(cat_index, len(CATEGORY_LIST) - 1))]
        mode = CATEGORY_INFO[cat]["date_mode"]
        sd = parse_date(start_date) if mode in ("range", "once") else None   # once 면 지출일·수입일
        returnable = bool(CATEGORY_INFO[cat].get("returnable"))
        ed = parse_date(end_date) if mode == "range" or returnable else None   # 보증금이면 반환일
        return Item(
            name.strip() or cat.value, cat, max(0.0, amount), max(0.0, rate), include_principal,
            start_date=sd.isoformat() if sd else None,
            end_date=ed.isoformat() if ed else None,
            repayments=self._parse_repayments(repayments_json) if cat == Category.LOAN else [],
            monthly_repay_rate=max(0.0, float(monthly_repay_rate)) if cat == Category.LOAN else 0.0,
            repay_method=(repay_method if cat == Category.LOAN and repay_method in REPAY_METHODS else ""),
            housing_type=(housing_type if cat == Category.DEPOSIT else ""),
            monthly=(max(0.0, float(monthly)) if cat == Category.DEPOSIT else 0.0),
            growth=max(0.0, float(growth)),
            support=max(0.0, float(support)),
            locked=bool(locked),
            # 되풀이는 일시 지출·수입에서만 (다른 분류는 이미 매달 오간다)
            every=max(0, int(every)) if cat in (Category.EXPENSE, Category.INCOME_ONCE) else 0,
        )

    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float, float, float, bool, int)
    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float, float, float, bool)
    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float, float, float)
    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float, float)
    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float)
    @Slot(str, int, float, float, bool, str, str, str, float, str)
    @Slot(str, int, float, float, bool, str, str, str, float)
    @Slot(str, int, float, float, bool, str, str, str)
    @Slot(str, int, float, float, bool)
    @undoable("항목 추가")
    def addItem(self, name: str, cat_index: int, amount: float, rate: float, include_principal: bool,
                start_date: str = "", end_date: str = "", repayments_json: str = "[]",
                monthly_repay_rate: float = 0.0, repay_method: str = "",
                housing_type: str = "", monthly: float = 0.0, growth: float = 0.0,
                support: float = 0.0, locked: bool = False, every: int = 0) -> None:
        item = self._make_item(name, cat_index, amount, rate, include_principal, start_date, end_date,
                               repayments_json, monthly_repay_rate, repay_method, housing_type, monthly,
                               growth, support, locked, every)
        self._items.add(item)
        self._set_status(f"추가: {item.name}")

    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float, float, float, bool, int)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float, float, float, bool)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float, float, float)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float, float)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str)
    @Slot(int, str, int, float, float, bool, str, str, str, float)
    @Slot(int, str, int, float, float, bool, str, str, str)
    @Slot(int, str, int, float, float, bool)
    @undoable("항목 수정")
    def updateItem(self, row: int, name: str, cat_index: int, amount: float, rate: float, include_principal: bool,
                   start_date: str = "", end_date: str = "", repayments_json: str = "[]",
                   monthly_repay_rate: float = 0.0, repay_method: str = "",
                   housing_type: str = "", monthly: float = 0.0, growth: float = 0.0,
                   support: float = 0.0, locked: bool = False, every: int = 0) -> None:
        item = self._make_item(name, cat_index, amount, rate, include_principal, start_date, end_date,
                               repayments_json, monthly_repay_rate, repay_method, housing_type, monthly,
                               growth, support, locked, every)
        old = self._plan.items[row] if 0 <= row < len(self._plan.items) else None
        item.active = old.active if old else True      # 꺼 둔 항목은 고쳐도 꺼진 채로
        self._items.update(row, item)
        self._set_status(f"수정: {item.name}")

    @Slot(int)
    @undoable("항목 삭제")
    def removeItem(self, row: int) -> None:
        removed = self._items.remove(row)
        if removed:
            self._set_status(f"삭제: {removed.name}")

    @Slot(int, result=bool)
    @undoable("항목 끄기/켜기")
    def toggleItemActive(self, row: int) -> bool:
        """항목을 잠시 끄거나 다시 켠다 (지우지 않고 빼 보는 용도)."""
        if not (0 <= row < len(self._plan.items)):
            return False
        it = self._plan.items[row]
        self._items.set_active(row, not it.active)
        self._set_status(("다시 켰습니다: " if it.active else "껐습니다: ") + it.name)
        return True

    @Slot(int, int)
    @undoable("항목 순서 바꾸기")
    def moveItem(self, row: int, delta: int) -> None:
        self._items.move(row, delta)

    @Slot(int, int, result=bool)
    @undoable("항목 순서 바꾸기")
    def moveInGroup(self, row: int, delta: int) -> bool:
        """묶어 보기에서 ▲▼. 같은 분류 안의 위/아래 항목과 자리를 바꾼다.

        묶어 보면 보이는 차례와 원본 차례가 달라서, 이웃끼리 바꾸면 엉뚱한 데로 간다.
        같은 분류 항목만 찾아 그것과 맞바꾼다.
        """
        items = self._plan.items
        if not (0 <= row < len(items)):
            return False
        same = [k for k, x in enumerate(items) if x.category == items[row].category]
        at = same.index(row)
        to = at + (1 if delta > 0 else -1)
        if not (0 <= to < len(same)):
            return False
        return self._items.swap(row, same[to])

    @Slot()
    @undoable("항목 전체 삭제")
    def clearItems(self) -> None:
        self._items.clear()
        self._set_status("모든 항목을 삭제했습니다.")

    @Slot()
    def save(self) -> None:
        """현재 경로에 저장."""
        self.saveTo(str(self._data_path))

    @Slot(str)
    def saveTo(self, url_or_path: str) -> None:
        """지정한 경로(file:// URL 또는 로컬 경로)에 저장하고 그 경로를 기본 경로로 삼는다."""
        path = self._to_path(url_or_path)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._ws.save(path)
        except Exception as e:
            self._set_status(f"저장 실패: {e}")
            self.failed.emit(f"저장 실패: {e}")
            return
        self._set_data_path(path)
        self._set_status(f"저장됨: {path}")
        self.saved.emit(str(path))

    @Slot()
    def load(self) -> None:
        """현재 경로에서 불러오기."""
        self.loadFrom(str(self._data_path))

    @Slot(str)
    @undoable("파일 불러오기")
    def loadFrom(self, url_or_path: str) -> None:
        path = self._to_path(url_or_path)
        try:
            ws = Workspace.load(path)
        except Exception as e:
            self._set_status(f"불러오기 실패: {e}")
            self.failed.emit(f"불러오기 실패: {path.name} — {e}")
            return
        self._ws = ws
        self._replace_plan(ws.plan)
        self._reset_ledger()
        self._set_data_path(path)
        self._set_status(f"불러옴: {path}")
        self.loaded.emit(str(path))

    @Slot(str)
    def exportExcel(self, url_or_path: str) -> None:
        """엑셀(.xlsx)로 내보내기."""
        path = self._to_path(url_or_path)
        try:
            out = export_plan(self._plan, path, scenarios=self._ws.plans, ledger=self._ws.ledger)
        except Exception as e:
            self._set_status(f"엑셀 내보내기 실패: {e}")
            self.failed.emit(f"엑셀 내보내기 실패: {e}")
            return
        self._set_status(f"엑셀로 내보냄: {out}")
        self.exported.emit(str(out))

    @Property(str, notify=dataPathChanged)
    def excelDefaultUrl(self) -> str:
        """엑셀 저장 대화상자의 기본 파일 (file:// URL)."""
        return QUrl.fromLocalFile(str(self._data_path.with_suffix(".xlsx"))).toString()

    # ---- 되돌리기 ----
    UNDO_LIMIT = 30                # 이만큼만 기억한다 (메모리에만 있다)

    def _push_undo(self, label: str, data: dict, path: Path) -> None:
        self._undo.append((label, data, path))
        if len(self._undo) > self.UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()         # 되돌린 뒤 새로 뭔가 했으면 '다시 실행' 은 버린다
        self.undoChanged.emit()

    def _restore(self, data: dict, path: Path) -> None:
        """찍어 둔 상태로 통째로 돌아간다. 보고 있던 달은 가능하면 그대로 둔다."""
        year, month = self._ledger_year, self._ledger_month
        self._ws = Workspace.from_dict(data)
        self._selected.clear()
        self.selectionChanged.emit()
        self._replace_plan(self._ws.plan)
        self._ledger_model.set_ledger(self._ws.ledger)
        months = self._ws.ledger.months()
        if year and year in self._ws.ledger.years():
            self._ledger_year, self._ledger_month = year, month
        elif months:
            self._ledger_year, self._ledger_month = months[0][:4], int(months[0][5:7])
        else:
            self._ledger_year, self._ledger_month = "", 0
        # 여기서 고정 항목을 다시 적지는 않는다. 어느 달을 적었는지도 함께 되돌아가므로
        # 되돌린 직후에 밀린 달이 다시 생겨나면 되돌린 보람이 없다.
        self._apply_period()
        self.budgetsChanged.emit()
        self.fixedChanged.emit()
        self._set_data_path(path)

    @Property(bool, notify=undoChanged)
    def canUndo(self) -> bool:
        return bool(self._undo)

    @Property(bool, notify=undoChanged)
    def canRedo(self) -> bool:
        return bool(self._redo)

    @Property(str, notify=undoChanged)
    def undoLabel(self) -> str:
        """되돌리면 무엇이 취소되는지 (단추 설명용)."""
        return self._undo[-1][0] if self._undo else ""

    @Property(str, notify=undoChanged)
    def redoLabel(self) -> str:
        return self._redo[-1][0] if self._redo else ""

    @Slot(result=bool)
    def undo(self) -> bool:
        if not self._undo:
            self._set_status("되돌릴 것이 없습니다.")
            return False
        label, data, path = self._undo.pop()
        self._redo.append((label, self._ws.to_dict(), self._data_path))
        self._restore(data, path)
        self.undoChanged.emit()
        self._set_status(f"되돌렸습니다: {label}")
        return True

    @Slot(result=bool)
    def redo(self) -> bool:
        if not self._redo:
            self._set_status("다시 실행할 것이 없습니다.")
            return False
        label, data, path = self._redo.pop()
        self._undo.append((label, self._ws.to_dict(), self._data_path))
        self._restore(data, path)
        self.undoChanged.emit()
        self._set_status(f"다시 실행: {label}")
        return True

    # ---- 비중 ----
    @Slot(str, result="QVariantList")
    def compositionOf(self, group: str) -> list[dict]:
        """'보유 자금' | '월 지출' | '월 수입' 의 항목별 비중 [{label, value, share}] (큰 순)."""
        entries = composition(self._plan).get(group, [])
        total = sum(v for _, v in entries)
        entries = sorted(entries, key=lambda x: -x[1])
        return [{"label": n, "value": v, "share": (v / total) if total else 0.0} for n, v in entries]

    @Slot(str, result=float)
    def compositionTotal(self, group: str) -> float:
        return sum(v for _, v in composition(self._plan).get(group, []))

    def _set_data_path(self, path: Path) -> None:
        if path != self._data_path:
            self._data_path = path
            self.dataPathChanged.emit()

    @Slot()
    @undoable("예시 데이터 불러오기")
    def loadSample(self) -> None:
        """현재 시나리오를 예시 데이터로 바꾼다 (다른 시나리오는 그대로). 가계부도 예시로 채운다."""
        p = sample_plan()
        p.name = self._ws.plan.name
        self._ws.plans[self._ws.active] = p
        self._replace_plan(p)
        self._ws.ledger = sample_ledger(p.basis)
        self._reset_ledger()
        self._set_status("예시 데이터를 불러왔습니다.")

    # ------------------------------------------------------------ 가계부
    def _apply_fixed(self) -> int:
        """이번 달까지 아직 안 적힌 고정 지출·수입을 적는다. 적은 건수를 돌려준다."""
        return len(self._ws.ledger.apply_fixed(month_key(date.today())))

    def _reset_ledger(self) -> None:
        """가계부가 통째로 바뀐 뒤 (불러오기·예시) 기간을 최신으로 맞춘다."""
        self._clear_selection()
        self._apply_fixed()              # 안 쓴 동안 밀린 고정 지출·수입을 먼저 적는다
        self._ledger_model.set_ledger(self._ws.ledger)
        months = self._ws.ledger.months()
        if months:                                   # 가장 최근 달을 보여준다
            self._ledger_year, self._ledger_month = months[0][:4], int(months[0][5:7])
        else:
            self._ledger_year, self._ledger_month = "", 0
        self._apply_period()

    def _apply_period(self) -> None:
        if self._ledger_category and self._ledger_category not in self._ws.ledger.categories_used(self.ledgerPeriod):
            self._ledger_category = ""
        if self._ledger_pay and self._ledger_pay not in self._ws.ledger.pays_used(self.ledgerPeriod):
            self._ledger_pay = ""
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_model.set_filters(self._ledger_query, self._ledger_kind,
                                       self._ledger_category, self._ledger_pay,
                                       self._ledger_min, self._ledger_max)
        self.ledgerChanged.emit()
        self.budgetsChanged.emit()
        self.fixedChanged.emit()

    def _apply_filters(self) -> None:
        self._ledger_model.set_filters(self._ledger_query, self._ledger_kind,
                                       self._ledger_category, self._ledger_pay,
                                       self._ledger_min, self._ledger_max)
        self.ledgerChanged.emit()

    def _clear_selection(self) -> None:
        """줄을 지우거나 가계부를 갈아 끼우면 번호가 밀리므로 고른 것을 푼다."""
        if self._selected:
            self._selected.clear()
            self._ledger_model.refresh_selection()
            self.selectionChanged.emit()

    def _ledger_touched(self) -> None:
        self._ledger_model.refresh()
        self.ledgerChanged.emit()
        self.budgetsChanged.emit()

    # ---- 검색 / 필터 ----
    @Property(str, notify=ledgerChanged)
    def ledgerQuery(self) -> str:
        return self._ledger_query

    @ledgerQuery.setter
    def ledgerQuery(self, q: str) -> None:
        q = str(q)
        if q != self._ledger_query:
            self._ledger_query = q
            self._apply_filters()

    @Property(str, notify=ledgerChanged)
    def ledgerKindFilter(self) -> str:
        """"" = 전체 | income | cost"""
        return self._ledger_kind

    @ledgerKindFilter.setter
    def ledgerKindFilter(self, k: str) -> None:
        k = k if k in ("income", "cost") else ""
        if k != self._ledger_kind:
            self._ledger_kind = k
            self._apply_filters()

    @Property(str, notify=ledgerChanged)
    def ledgerCategoryFilter(self) -> str:
        return self._ledger_category

    @ledgerCategoryFilter.setter
    def ledgerCategoryFilter(self, c: str) -> None:
        c = "" if c in ("", "전체") else str(c)
        if c != self._ledger_category:
            self._ledger_category = c
            self._apply_filters()

    @Property(str, notify=ledgerChanged)
    def ledgerPayFilter(self) -> str:
        """"" = 전체"""
        return self._ledger_pay

    @ledgerPayFilter.setter
    def ledgerPayFilter(self, v: str) -> None:
        v = "" if v in ("전체", "모두") else v
        if v != self._ledger_pay:
            self._ledger_pay = v
            self._apply_filters()

    @Property(float, notify=ledgerChanged)
    def ledgerMinAmount(self) -> float:
        """이 금액 이상만 보기 (0 = 제한 없음). 부호는 보지 않는다."""
        return self._ledger_min

    @ledgerMinAmount.setter
    def ledgerMinAmount(self, v: float) -> None:
        v = max(0.0, float(v or 0))
        if v != self._ledger_min:
            self._ledger_min = v
            self._apply_filters()

    @Property(float, notify=ledgerChanged)
    def ledgerMaxAmount(self) -> float:
        """이 금액 이하만 보기 (0 = 제한 없음)."""
        return self._ledger_max

    @ledgerMaxAmount.setter
    def ledgerMaxAmount(self, v: float) -> None:
        v = max(0.0, float(v or 0))
        if v != self._ledger_max:
            self._ledger_max = v
            self._apply_filters()

    @Property(str, notify=ledgerChanged)
    def ledgerSort(self) -> str:
        """"date"(날짜순) | "amount"(금액순)"""
        return self._ledger_sort

    @Property(bool, notify=ledgerChanged)
    def ledgerSortDesc(self) -> bool:
        """큰 것·최신이 위인가."""
        return self._ledger_desc

    @Slot(str)
    def sortLedgerBy(self, how: str) -> None:
        """정렬 기준을 바꾼다. 같은 기준을 다시 누르면 오름/내림을 뒤집는다."""
        how = "amount" if how == "amount" else "date"
        if how == self._ledger_sort:
            self._ledger_desc = not self._ledger_desc
        else:
            self._ledger_sort, self._ledger_desc = how, True
        self._ledger_model.set_sort(self._ledger_sort, self._ledger_desc)
        self.ledgerChanged.emit()

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerUsedPays(self) -> list[str]:
        """그 기간에 실제로 쓴 결제수단 (거르기 목록용)."""
        return ["전체"] + self._ws.ledger.pays_used(self.ledgerPeriod)

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerPays(self) -> list[str]:
        """고를 수 있는 결제수단 (팝업용). 직접 적은 이름도 목록에 남는다."""
        return self._ws.ledger.pays()

    @Slot(str, result="QVariantList")
    def ledgerByPay(self, kind: str) -> list[dict]:
        """결제수단별 합계 [{label, value, share}] — 지금 보고 있는 기간."""
        rows = self._ws.ledger.by_pay(self.ledgerPeriod, kind if kind in ("income", "cost") else "cost")
        total = sum(v for _, v in rows)
        return [{"label": n, "value": v, "share": (v / total) if total else 0.0} for n, v in rows]

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerUsedCategories(self) -> list[str]:
        """현재 기간에 실제로 쓴 분류 (필터 콤보박스용, 맨 앞에 '전체')."""
        return ["전체"] + self._ws.ledger.categories_used(self.ledgerPeriod)

    @Property(bool, notify=ledgerChanged)
    def ledgerFiltered(self) -> bool:
        return bool(self._ledger_query or self._ledger_kind or self._ledger_category
                    or self._ledger_pay or self._ledger_min or self._ledger_max)

    @Slot()
    def clearLedgerFilters(self) -> None:
        if self.ledgerFiltered:
            self._ledger_query = self._ledger_kind = self._ledger_category = ""
            self._ledger_pay = ""
            self._ledger_min = self._ledger_max = 0.0
            self._apply_filters()

    @Property("QVariantMap", notify=ledgerChanged)
    def ledgerFilteredSummary(self) -> dict:
        """걸러진 내역만의 {income, cost, net, count} (필터가 없으면 기간 전체와 같다)."""
        income = cost = 0.0
        count = 0
        for e in self._ws.ledger.entries:
            if not self._ws.ledger.matches(e, self.ledgerPeriod, self._ledger_query,
                                           self._ledger_kind, self._ledger_category,
                                           self._ledger_pay, self._ledger_min,
                                           self._ledger_max):
                continue
            count += 1
            if e.is_income:
                income += e.amount
            else:
                cost += e.amount
        return {"income": income, "cost": cost, "net": income - cost, "count": count}

    # ---- 지난 기간 대비 ----
    @Property("QVariantMap", notify=ledgerChanged)
    def ledgerPrev(self) -> dict:
        """직전 기간(지난달 또는 작년)과의 비교.
        {has, label, income, cost, net, costDiff, incomeDiff, costPct, incomePct}"""
        prev = prev_period(self.ledgerPeriod)
        s = self._ws.ledger.summary(self.ledgerPeriod)
        # 비교할 게 없어도 칸은 모두 채워서 돌려준다 (QML 바인딩이 undefined 를 보지 않게)
        empty = {"has": False, "label": "", "income": 0.0, "cost": 0.0, "net": 0.0,
                 "incomeDiff": 0.0, "costDiff": 0.0, "incomePct": 0.0, "costPct": 0.0}
        if not prev:
            return empty
        p = self._ws.ledger.summary(prev)
        if p["count"] == 0:
            return empty
        label = "작년" if len(prev) == 4 else "지난달"

        def pct(now: float, before: float) -> float:
            return ((now - before) / before * 100.0) if before > 0 else 0.0

        return {
            "has": True, "label": label,
            "income": p["income"], "cost": p["cost"], "net": p["net"],
            "incomeDiff": s["income"] - p["income"], "costDiff": s["cost"] - p["cost"],
            "incomePct": pct(s["income"], p["income"]), "costPct": pct(s["cost"], p["cost"]),
        }

    # ---- 날짜 구분 헤더 ----
    @Slot(str, result="QVariantMap")
    def ledgerDayInfo(self, day: str) -> dict:
        """날짜 구분줄에 쓸 {label, net}"""
        d = parse_date(day)
        if not d:
            return {"label": day, "net": 0.0}
        names = ["월", "화", "수", "목", "금", "토", "일"]
        return {"label": f"{d.month}월 {d.day}일 ({names[d.weekday()]})",
                "net": self._ws.ledger.day_total(day)}

    # ---- 반복 / 복사 ----
    @Slot(str, str, float, str, str, int, str)
    @Slot(str, str, float, str, str, int)
    @undoable("가계부 내역 반복 추가")
    def addEntryRepeat(self, date_str: str, category: str, amount: float,
                       name: str, note: str, months: int, pay: str = "") -> None:
        """같은 내역을 months 달 동안 (이번 달 포함) 넣는다."""
        months = max(1, min(60, int(months)))
        e = Entry(date_str, category, amount, name.strip(),
                  kind=self._ws.ledger.kind_of(category), note=note.strip(), pay=pay.strip())
        self._ws.ledger.add(e)
        made = self._ws.ledger.repeat(e, months)
        if not self._ledger_year:
            self._ledger_year, self._ledger_month = e.year, e.day.month
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부 추가: {e.category} {won(e.amount)}"
                         + (f" · {len(made) + 1}개월 반복" if made else ""))

    @Slot()
    @undoable("지난달 복사")
    def copyPreviousMonth(self) -> None:
        """지난달 내역을 이번 달로 복사한다 (월을 고른 상태에서만)."""
        if self._ledger_month <= 0:
            self._set_status("월을 고른 뒤에 쓸 수 있습니다.")
            return
        dst = self.ledgerPeriod
        src = shift_month(dst, -1)
        made = self._ws.ledger.copy_month(src, dst)
        if not made:
            self._set_status(f"{src} 에 복사할 내역이 없습니다.")
            return
        self._ledger_touched()
        self._set_status(f"지난달({src}) 내역 {len(made)}건을 복사했습니다.")

    # ---- 계획 항목을 가계부로 ----
    #   계획의 분류 → 가계부 분류. 없는 분류(현금·예금)는 기록할 거리가 아니다
    PLAN_TO_LEDGER = {
        Category.RENT: "주거/관리비",
        Category.MAINT: "주거/관리비",
        Category.DEPOSIT: "주거/관리비",
        Category.FIXED: "기타 지출",
        Category.EXPENSE: "기타 지출",
        Category.INCOME: "급여",
        Category.INCOME_ONCE: "기타 수입",
        Category.LOAN: "대출 상환",
        Category.SAVING: "저축/투자",
    }

    def _ledger_date(self) -> str:
        """가계부에 넣을 날짜. 달을 골라 놨으면 그 달의 오늘 날짜, 아니면 오늘."""
        today = date.today()
        if self._ledger_year and self._ledger_month > 0:
            return same_day_in(f"{self._ledger_year}-{self._ledger_month:02d}", today.day)
        return today.isoformat()

    def _ledger_amount(self, it: Item) -> float:
        """그 항목이 한 달에 실제로 오고 가는 돈."""
        b = self._plan.basis
        if it.category == Category.LOAN:
            return it.payment_at(0, b)
        for v in (it.monthly_cost_at(0, b), it.monthly_income_at(0, b), it.once_cost(), it.once_income()):
            if v > 0:
                return v
        return 0.0

    @Slot(int, result=bool)
    @undoable("계획에서 가져오기")
    def toLedger(self, source_row: int) -> bool:
        """계획 항목 하나를 가계부에 기록한다. 같은 이름이 이미 있으면 넣지 않는다."""
        if not (0 <= source_row < len(self._plan.items)):
            return False
        it = self._plan.items[source_row]
        cat = self.PLAN_TO_LEDGER.get(it.category)
        if not cat:
            self.failed.emit(f"'{it.category.value}' 분류는 가계부에 기록할 수 없습니다.")
            return False
        amount = self._ledger_amount(it)
        if amount <= 0:
            self.failed.emit(f"'{it.name}' 은(는) 이번 달에 오고 가는 돈이 없습니다.")
            return False

        day = self._ledger_date()
        period = day[:7]
        if self._ws.ledger.has_name(period, it.name):
            self.failed.emit(f"'{it.name}' 은(는) 이미 {period[:4]}년 {int(period[5:7])}월 가계부에 있습니다.")
            return False

        self._ws.ledger.add(Entry(day, cat, amount, it.name, note="계획에서 가져옴"))
        if not self._ledger_year:
            self._ledger_year, self._ledger_month = period[:4], int(period[5:7])
            self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부에 기록: {it.name} {won(amount)}")
        return True

    @Slot(result=int)
    @undoable("계획에서 가져오기")
    def importPlanToLedger(self) -> int:
        """계획 항목을 한꺼번에 가계부에 기록한다. 이름이 겹치는 것은 건너뛴다."""
        day = self._ledger_date()
        period = day[:7]
        added = skipped = 0
        for it in list(self._plan.items):
            cat = self.PLAN_TO_LEDGER.get(it.category)
            if not cat or self._ledger_amount(it) <= 0:
                continue
            if self._ws.ledger.has_name(period, it.name):
                skipped += 1
                continue
            self._ws.ledger.add(Entry(day, cat, self._ledger_amount(it), it.name, note="계획에서 가져옴"))
            added += 1

        if not added and not skipped:
            self.failed.emit("가계부에 기록할 항목이 없습니다.")
            return 0
        if not added:
            self.failed.emit(f"{skipped}건 모두 이미 가계부에 있습니다.")
            return 0
        if not self._ledger_year:
            self._ledger_year, self._ledger_month = period[:4], int(period[5:7])
            self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"계획에서 {added}건을 가계부에 기록했습니다."
                         + (f" ({skipped}건은 이미 있어 건너뜀)" if skipped else ""))
        return added

    # ---- 여러 건 한꺼번에 ----
    @Property(int, notify=selectionChanged)
    def selectedCount(self) -> int:
        return len(self._selected)

    @Property("QVariantMap", notify=selectionChanged)
    def selectionSummary(self) -> dict:
        """고른 줄의 {count, income, cost, net}."""
        income = cost = 0.0
        for i in sorted(self._selected):
            if not (0 <= i < len(self._ws.ledger.entries)):
                continue
            e = self._ws.ledger.entries[i]
            if e.is_income:
                income += e.amount
            else:
                cost += e.amount
        return {"count": len(self._selected), "income": income, "cost": cost,
                "net": income - cost}

    @Slot(int)
    def toggleEntrySelected(self, row: int) -> None:
        """한 줄을 골랐다 풀었다 한다 (row 는 Ledger.entries 번호)."""
        if not (0 <= row < len(self._ws.ledger.entries)):
            return
        self._selected.discard(row) if row in self._selected else self._selected.add(row)
        self._ledger_model.refresh_selection()
        self.selectionChanged.emit()

    @Slot()
    def selectVisibleEntries(self) -> None:
        """지금 걸러져 보이는 줄을 모두 고른다. 이미 다 골랐으면 모두 푼다."""
        rows = set(self._ledger_model.visible_sources())
        if rows and rows <= self._selected:
            self._selected -= rows
        else:
            self._selected |= rows
        self._ledger_model.refresh_selection()
        self.selectionChanged.emit()

    @Slot()
    def clearSelection(self) -> None:
        self._clear_selection()

    @Slot(result=int)
    @undoable("가계부 내역 여러 건 삭제")
    def removeSelectedEntries(self) -> int:
        """고른 줄을 한꺼번에 지운다. 지운 건수를 돌려준다."""
        rows = sorted(self._selected, reverse=True)      # 뒤에서부터 지워야 번호가 안 밀린다
        gone = 0
        for i in rows:
            if self._ws.ledger.remove(i):
                gone += 1
        if not gone:
            return 0
        self._clear_selection()
        self._ledger_touched()
        self._set_status(f"가계부 내역 {gone}건을 지웠습니다.")
        return gone

    @Slot(str, result=int)
    @undoable("가계부 분류 여러 건 바꾸기")
    def setSelectedCategory(self, category: str) -> int:
        """고른 줄의 분류를 한꺼번에 바꾼다. 수입/지출도 새 분류를 따라간다."""
        if not category:
            return 0
        kind = self._ws.ledger.kind_of(category)
        changed = 0
        for i in sorted(self._selected):
            if not (0 <= i < len(self._ws.ledger.entries)):
                continue
            e = self._ws.ledger.entries[i]
            if e.category == category:
                continue
            e.category, e.kind = category, kind
            changed += 1
        if not changed:
            return 0
        self._ledger_touched()
        self._set_status(f"{changed}건의 분류를 '{category}' 로 바꿨습니다.")
        return changed

    @Slot(str, result=int)
    @undoable("결제수단 여러 건 바꾸기")
    def setSelectedPay(self, pay: str) -> int:
        """고른 줄의 결제수단을 한꺼번에 바꾼다 ('지정 안 함' 이면 비운다)."""
        want = "" if pay in ("지정 안 함", "전체") else (pay or "").strip()
        changed = 0
        for i in sorted(self._selected):
            if not (0 <= i < len(self._ws.ledger.entries)):
                continue
            e = self._ws.ledger.entries[i]
            if e.pay == want:
                continue
            e.pay = want
            changed += 1
        if not changed:
            return 0
        self._ledger_touched()
        self._set_status(f"{changed}건의 결제수단을 '{want or '지정 안 함'}' 으로 바꿨습니다.")
        return changed

    # ---- 가져오기 (CSV · 엑셀 · 메모장 · 붙여넣기) ----
    IMPORT_PREVIEW = 200                 # 미리보기에 보여 줄 최대 줄 수

    def _dupe_keys(self) -> set:
        return {(e.date, round(e.amount), e.name.strip(), e.kind) for e in self._ws.ledger.entries}

    def _mark_import(self, rows: list[dict], problems: list[str], how: str, source: str) -> dict:
        """읽어 온 줄에 '이미 있는 내역인가' 를 표시하고 미리보기를 만든다."""
        seen = self._dupe_keys()
        self._import = []
        for r in rows:
            key = (r["date"], round(r["amount"]), (r.get("name") or "").strip(), r["kind"])
            r = dict(r)
            r["dupe"] = key in seen
            seen.add(key)                 # 파일 안에서 같은 줄이 두 번 나오는 것도 중복으로 본다
            self._import.append(r)
        dupes = sum(1 for r in self._import if r["dupe"])
        income = sum(r["amount"] for r in self._import if r["kind"] == "income")
        cost = sum(r["amount"] for r in self._import if r["kind"] != "income")
        self._import_info = {
            "ok": bool(self._import),
            "source": source, "how": how,
            "count": len(self._import), "dupes": dupes, "fresh": len(self._import) - dupes,
            "income": income, "cost": cost,
            "problems": problems[:30], "problemCount": len(problems),
            "from": min((r["date"] for r in self._import), default=""),
            "to": max((r["date"] for r in self._import), default=""),
        }
        self.importChanged.emit()
        return self._import_info

    @Slot(str, result="QVariantMap")
    def previewImportFile(self, url_or_path: str) -> dict:
        """파일을 읽어 미리보기를 만든다 (아직 가계부에 넣지 않는다)."""
        path = self._to_path(url_or_path)
        try:
            rows, problems, how = parse_file(path)
        except Exception as e:                      # 파일이 깨졌거나 열 수 없을 때
            self._import, self._import_info = [], {
                "ok": False, "source": path.name, "how": "",
                "count": 0, "dupes": 0, "fresh": 0, "income": 0.0, "cost": 0.0,
                "problems": [f"읽지 못했습니다: {e}"], "problemCount": 1, "from": "", "to": "",
            }
            self.importChanged.emit()
            self.failed.emit(f"가져오기 실패: {path.name} — {e}")
            return self._import_info
        return self._mark_import(rows, problems, how, path.name)

    @Slot(str, result="QVariantMap")
    def previewImportText(self, text: str) -> dict:
        """붙여넣은 글로 미리보기를 만든다."""
        rows, problems, how = parse_text(text or "")
        return self._mark_import(rows, problems, how, "붙여넣은 글")

    @Property("QVariantMap", notify=importChanged)
    def importInfo(self) -> dict:
        return dict(self._import_info)

    @Property("QVariantList", notify=importChanged)
    def importRows(self) -> list[dict]:
        """미리보기 줄 [{date, amount, amountText, kind, name, category, pay, note, dupe}]"""
        out = []
        for r in self._import[:self.IMPORT_PREVIEW]:
            out.append({**r, "amountText": ("+" if r["kind"] == "income" else "-") + won(r["amount"])})
        return out

    @Slot()
    def cancelImport(self) -> None:
        if self._import or self._import_info:
            self._import, self._import_info = [], {}
            self.importChanged.emit()

    def _import_category(self, name: str, kind: str) -> tuple[str, str]:
        """파일에 적힌 분류를 쓸 수 있는 분류로. (분류, 메모에 덧붙일 말)"""
        lg = self._ws.ledger
        name = (name or "").strip()
        fallback = "기타 수입" if kind == "income" else "기타 지출"
        if not name:
            return fallback, ""
        if name in lg.categories():
            return name, ""
        if lg.add_category(name, kind) == "":       # 없는 분류는 만들어 준다
            return name, ""
        return fallback, f"원래 분류: {name}"

    @Slot(bool, str, result=int)
    @Slot(bool, result=int)
    @Slot(result=int)
    @undoable("가계부 가져오기")
    def applyImport(self, skip_dupes: bool = True, default_pay: str = "") -> int:
        """미리보기의 줄을 가계부에 넣는다. 넣은 건수를 돌려준다."""
        if not self._import:
            return 0
        added = 0
        for r in self._import:
            if skip_dupes and r.get("dupe"):
                continue
            cat, extra = self._import_category(r.get("category", ""), r["kind"])
            note = (r.get("note") or "").strip()
            if extra:
                note = f"{note} ({extra})".strip() if note else extra
            self._ws.ledger.add(Entry(r["date"], cat, r["amount"], (r.get("name") or "").strip(),
                                      kind=r["kind"], note=note,
                                      pay=(r.get("pay") or default_pay).strip()))
            added += 1
        if not added:
            self._set_status("넣을 내역이 없습니다 (모두 이미 있는 내역).")
            return 0
        self._import, self._import_info = [], {}
        self.importChanged.emit()
        if not self._ledger_year:
            m = self._ws.ledger.months()[0]
            self._ledger_year, self._ledger_month = m[:4], int(m[5:7])
            self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부로 {added}건을 가져왔습니다.")
        return added

    # ---- 분류별 예산 ----
    @Property(bool, notify=budgetsChanged)
    def hasBudgets(self) -> bool:
        return self._ws.ledger.has_budgets()

    @Property(int, notify=budgetsChanged)
    def budgetMonths(self) -> int:
        """지금 보고 있는 기간이 몇 달치인가 (월=1, 연=12)."""
        return self._ws.ledger.period_months(self.ledgerPeriod)

    @Property("QVariantList", notify=budgetsChanged)
    def ledgerBudgets(self) -> list[dict]:
        """분류별 예산 현황 [{category, limit, spent, left, ratio, over}]"""
        return self._ws.ledger.budget_rows(self.ledgerPeriod)

    @Property("QVariantMap", notify=budgetsChanged)
    def ledgerBudgetTotals(self) -> dict:
        return self._ws.ledger.budget_totals(self.ledgerPeriod)

    @Property("QVariantList", notify=budgetsChanged)
    def budgetEditRows(self) -> list[dict]:
        """예산 설정 팝업용 — 지출 분류 전체와 지금 정해진 한 달 예산."""
        return [{"category": c, "limit": self._ws.ledger.budget_of(c)}
                for c in self._ws.ledger.cost_categories()]

    @Slot(str, float)
    def setBudget(self, category: str, amount: float) -> None:
        """예산만 바꾼다. 내역·집계는 그대로이므로 budgetsChanged 만 보낸다 (슬라이더를 끌 때 가볍게)."""
        self._ws.ledger.set_budget(category, amount)
        self.budgetsChanged.emit()

    @Slot()
    @undoable("예산 지우기")
    def clearBudgets(self) -> None:
        self._ws.ledger.budgets.clear()
        self.budgetsChanged.emit()
        self._set_status("예산을 모두 지웠습니다.")

    @Slot()
    @undoable("실적으로 예산 채우기")
    def fillBudgetsFromPeriod(self) -> None:
        """지금 보고 있는 기간에 실제로 쓴 금액(월평균)을 예산으로 채운다."""
        n = self._ws.ledger.budget_from_period(self.ledgerPeriod)
        self.budgetsChanged.emit()
        self._set_status(f"{self.ledgerPeriodText} 실적으로 예산 {n}개를 채웠습니다."
                         if n else "채울 지출 기록이 없습니다.")

    # ---- 고정 지출·수입 ----
    @Property("QVariantList", notify=fixedChanged)
    def fixedRows(self) -> list[dict]:
        """고정 지출·수입 규칙 목록 (수입 먼저, 그 다음 금액이 큰 것부터)."""
        lg = self._ws.ledger
        rows = []
        for f in lg.fixed:
            rows.append({
                "rid": f.rid, "name": f.name, "label": f.label,
                "category": f.category, "amount": f.amount,
                "amountText": ("+" if f.is_income else "-") + won(f.amount),
                "day": f.day, "kind": f.kind, "note": f.note, "pay": f.pay,
                "start": f.start, "end": f.end, "active": f.active,
                "made": len(lg.fixed_entries(f.rid)),
                "periodText": (f.start or "") + " ~ " + (f.end or "계속"),
            })
        rows.sort(key=lambda r: (r["kind"] != "income", -r["amount"]))
        return rows

    @Property("QVariantMap", notify=fixedChanged)
    def fixedTotals(self) -> dict:
        """쉬지 않는 규칙의 한 달 합계 {income, cost, net, count}."""
        return self._ws.ledger.fixed_totals()

    @Property(int, notify=fixedChanged)
    def fixedCount(self) -> int:
        return len(self._ws.ledger.fixed)

    def _fixed_touched(self, status: str = "") -> None:
        n = self._apply_fixed()
        if not self._ledger_year and self._ws.ledger.entries:
            m = self._ws.ledger.months()[0]
            self._ledger_year, self._ledger_month = m[:4], int(m[5:7])
            self._ledger_model.set_period(self.ledgerPeriod)
        self.fixedChanged.emit()
        self._ledger_touched()
        if status:
            self._set_status(status + (f" · 내역 {n}건 적음" if n else ""))

    @Slot(str, str, float, int, str, str, str, str, result=str)
    @Slot(str, str, float, int, str, str, str, result=str)
    @Slot(str, str, float, int, str, str, result=str)
    @Slot(str, str, float, int, str, result=str)
    @Slot(str, str, float, int, result=str)
    @undoable("고정 항목 추가")
    def addFixed(self, name: str, category: str, amount: float, day: int,
                 note: str = "", start: str = "", end: str = "", pay: str = "") -> str:
        """고정 지출·수입을 하나 만든다. 만들었으면 빈 문자열, 아니면 까닭을 돌려준다."""
        why = self._check_fixed(category, amount, start, end)
        if why:
            self.failed.emit(why)
            return why
        f = self._ws.ledger.add_fixed(Fixed(name=name, category=category, amount=amount,
                                            day=day, note=note.strip(), pay=pay.strip(),
                                            start=start[:7], end=end[:7]))
        self._fixed_touched(f"고정 {'수입' if f.is_income else '지출'} 추가: {f.label} {won(f.amount)}")
        return ""

    @Slot(str, str, str, float, int, str, str, str, str, result=str)
    @Slot(str, str, str, float, int, str, str, str, result=str)
    @Slot(str, str, str, float, int, str, str, result=str)
    @Slot(str, str, str, float, int, str, result=str)
    @Slot(str, str, str, float, int, result=str)
    @undoable("고정 항목 수정")
    def updateFixed(self, rid: str, name: str, category: str, amount: float, day: int,
                    note: str = "", start: str = "", end: str = "", pay: str = "") -> str:
        """규칙 내용을 바꾼다 (이미 적어 둔 내역은 그대로 둔다)."""
        why = self._check_fixed(category, amount, start, end)
        if why:
            self.failed.emit(why)
            return why
        ok = self._ws.ledger.update_fixed(rid, Fixed(name=name, category=category,
                                                     amount=amount, day=day,
                                                     note=note.strip(), pay=pay.strip(),
                                                     start=start[:7], end=end[:7]))
        if not ok:
            return "없는 규칙입니다."
        self._fixed_touched("고정 항목 수정")
        return ""

    def _check_fixed(self, category: str, amount: float, start: str, end: str) -> str:
        if not category:
            return "분류를 골라 주세요."
        if not amount or float(amount) <= 0:
            return "금액을 넣어 주세요."
        s, e = (start or "")[:7], (end or "")[:7]
        for v in (s, e):
            if v and (len(v) != 7 or not v[:4].isdigit() or not v[5:7].isdigit()):
                return "달은 2026-03 처럼 적어 주세요."
        if s and e and s > e:
            return "끝나는 달이 시작하는 달보다 앞설 수 없습니다."
        return ""

    @Slot(str, result=bool)
    @undoable("고정 항목 쉬기/돌리기")
    def toggleFixed(self, rid: str) -> bool:
        """쉬게 하거나 다시 돌린다. 다시 돌리면 밀린 달도 그때 적는다."""
        f = self._ws.ledger.fixed_of(rid)
        if f is None:
            return False
        self._ws.ledger.set_fixed_active(rid, not f.active)
        self._fixed_touched(f"{f.label} 고정 항목을 " + ("다시 돌립니다." if f.active else "쉬게 했습니다."))
        return True

    @Slot(str, bool, result=int)
    @Slot(str, result=int)
    @undoable("고정 항목 삭제")
    def removeFixed(self, rid: str, purge: bool = False) -> int:
        """규칙을 지운다. purge 면 그 규칙이 적어 둔 내역까지 지운다. 지운 내역 수."""
        f = self._ws.ledger.fixed_of(rid)
        if f is None:
            return -1
        label = f.label
        gone = self._ws.ledger.remove_fixed(rid, purge)
        if gone:
            self._clear_selection()
        self.fixedChanged.emit()
        self._ledger_touched()
        self._set_status(f"고정 항목 삭제: {label}" + (f" · 내역 {gone}건도 지움" if gone else ""))
        return gone

    @Slot(str, result=int)
    def fixedEntryCount(self, rid: str) -> int:
        return len(self._ws.ledger.fixed_entries(rid))

    @Slot(int, result=str)
    @undoable("고정 항목 등록")
    def fixedFromEntry(self, row: int) -> str:
        """적어 둔 내역 하나를 고정 항목으로 올린다 (그 달은 이미 적혀 있으니 다음 달부터)."""
        if not (0 <= row < len(self._ws.ledger.entries)):
            return "없는 내역입니다."
        e = self._ws.ledger.entries[row]
        if e.rule:
            why = "이미 고정 항목이 적어 준 내역입니다."
            self.failed.emit(why)
            return why
        f = self._ws.ledger.add_fixed(Fixed(name=e.name, category=e.category, amount=e.amount,
                                            day=e.day.day, kind=e.kind, note=e.note,
                                            pay=e.pay, start=shift_month(e.ym, 1)))
        self._fixed_touched(f"고정 항목 등록: {f.label} {won(f.amount)} (매달 {f.day}일)")
        return ""

    @Slot(result=int)
    @undoable("고정 항목 적용")
    def applyFixedNow(self) -> int:
        """밀린 고정 항목을 지금 적는다 (보통은 앱을 열 때 저절로 적힌다)."""
        n = self._apply_fixed()
        if n:
            self._fixed_touched("")
            self._set_status(f"고정 항목으로 내역 {n}건을 적었습니다.")
        else:
            self._set_status("밀린 고정 항목이 없습니다.")
        return n

    # ---- 계획 대비 실적 ----
    def _period_months(self, period: str) -> list[str]:
        """'2026-03' → ['2026-03'], '2026' → 1~12월."""
        if len(period) == 7:
            return [period]
        if len(period) == 4:
            return [f"{period}-{m:02d}" for m in range(1, 13)]
        return []

    @Slot(result="QVariantMap")
    def planVsActual(self) -> dict:
        """지금 보고 있는 기간의 계획과 가계부 실적 비교.
        {has, scenario, months, planIn, planOut, planNet, actIn, actOut, actNet,
         inDiff, outDiff, netDiff, outPct}"""
        return self._plan_vs_actual(self.ledgerPeriod)

    @Slot(str, result="QVariantMap")
    def planVsActualFor(self, period: str) -> dict:
        """기간을 직접 주고 비교한다 ('2026-11' 또는 '2026')."""
        return self._plan_vs_actual(period)

    def _plan_vs_actual(self, period: str) -> dict:
        empty = {
            "has": False, "scenario": self._plan.name, "months": 0,
            "planIn": 0.0, "planOut": 0.0, "planNet": 0.0,
            "actIn": 0.0, "actOut": 0.0, "actNet": 0.0,
            "inDiff": 0.0, "outDiff": 0.0, "netDiff": 0.0, "outPct": 0.0,
        }
        if not period:
            return empty
        basis = self._plan.basis
        plan_in = plan_out = 0.0
        counted = 0
        for ym in self._period_months(period):
            m = month_offset(basis, date(int(ym[:4]), int(ym[5:7]), 1))
            if m < 0:
                continue                      # 기준일 이전은 계획이 없다
            counted += 1
            plan_in += self._plan.planned_in_at(m)
            plan_out += self._plan.planned_out_at(m)
        if counted == 0 or (plan_in <= 0 and plan_out <= 0):
            return empty

        s = self._ws.ledger.summary(period)   # noqa: E501
        plan_net = plan_in - plan_out
        return {
            "has": True,
            "scenario": self._plan.name,
            "months": counted,
            "planIn": plan_in, "planOut": plan_out, "planNet": plan_net,
            "actIn": s["income"], "actOut": s["cost"], "actNet": s["net"],
            "inDiff": s["income"] - plan_in,
            "outDiff": s["cost"] - plan_out,
            "netDiff": s["net"] - plan_net,
            "outPct": ((s["cost"] - plan_out) / plan_out * 100.0) if plan_out > 0 else 0.0,
        }

    # ---- 한눈에 보기 (대시보드) ----
    OVERVIEW_MONTHS = 12

    def _recent_yms(self) -> list[str]:
        """대시보드가 보는 기간 — 이번 달까지 최근 12개월."""
        last = month_key(date.today())
        return [shift_month(last, -i) for i in range(self.OVERVIEW_MONTHS - 1, -1, -1)]

    @Property("QVariantMap", notify=summaryChanged)
    def overviewPlan(self) -> dict:
        """계획 쪽 한눈 요약. 숫자는 모두 지금 고른 시나리오 기준이다."""
        p = self._plan
        s = self._s()
        sf = self.shortfall
        return {
            "scenario": p.name, "months": p.months,
            "basis": p.start_date, "end": self.endDate,
            "capital": s.capital, "capitalAtEnd": self.capitalAtEnd,
            "required": s.required, "periodIncome": s.period_income,
            "net": s.net, "target": p.target, "gap": self.gap,
            "progress": self.progress, "peak": self.peakNet,
            "goalMonth": self.goalMonth, "goalDateText": self.goalDateText,
            "monthlyNet": self.monthlyNet, "avgMonthlyNet": self.avgMonthlyNet,
            "itemCount": self.itemCount,
            "shortfallMonth": sf.get("month", -1) if sf.get("has") else -1,
            "shortfallText": sf.get("dateText", ""),
        }

    @Property("QVariantList", notify=ledgerChanged)
    def overviewMonths(self) -> list[dict]:
        """최근 12개월의 가계부 수입·지출·수지 (오래된 달이 앞)."""
        rows = self._ws.ledger.recent_months(self.OVERVIEW_MONTHS)
        this = month_key(date.today())
        for r in rows:
            r["isThis"] = r["ym"] == this
        return rows

    @Property("QVariantMap", notify=ledgerChanged)
    def overviewLedger(self) -> dict:
        """최근 12개월 가계부 합계와 월평균. 기록이 있는 달만으로 평균을 낸다."""
        yms = self._recent_yms()
        s = self._ws.ledger.range_summary(yms)
        rows = [r for r in self._ws.ledger.recent_months(self.OVERVIEW_MONTHS) if r["count"] > 0]
        n = len(rows) or 1
        best = max(rows, key=lambda r: r["net"], default=None)
        worst = min(rows, key=lambda r: r["net"], default=None)
        return {
            "has": s["count"] > 0,
            "from": yms[0], "to": yms[-1], "months": len(rows),
            "income": s["income"], "cost": s["cost"], "net": s["net"], "count": s["count"],
            "avgIncome": s["income"] / n, "avgCost": s["cost"] / n, "avgNet": s["net"] / n,
            "bestLabel": best["label"] if best else "", "bestNet": best["net"] if best else 0.0,
            "worstLabel": worst["label"] if worst else "", "worstNet": worst["net"] if worst else 0.0,
        }

    @Slot(str, result="QVariantList")
    def overviewByCategory(self, kind: str) -> list[dict]:
        """최근 12개월 분류별 합계 [{label, value, share}] — 도넛용."""
        rows = self._ws.ledger.range_by_category(self._recent_yms(), kind)
        total = sum(v for _, v in rows)
        return [{"label": n, "value": v, "share": (v / total) if total else 0.0}
                for n, v in rows]

    @Property("QVariantList", notify=budgetsChanged)
    def overviewBudgets(self) -> list[dict]:
        """이번 달 예산 현황 (예산을 정한 분류만, 많이 쓴 순)."""
        rows = self._ws.ledger.budget_rows(month_key(date.today()))
        return [r for r in rows if r["limit"] > 0]

    @Property("QVariantMap", notify=ledgerChanged)
    def overviewThisMonth(self) -> dict:
        """이번 달 가계부 {ym, label, income, cost, net, count} 와 계획 대비."""
        ym = month_key(date.today())
        s = self._ws.ledger.summary(ym)
        return {"ym": ym, "label": f"{int(ym[:4])}년 {int(ym[5:7])}월", **s,
                "vsPlan": self._plan_vs_actual(ym)}

    @Property(bool, notify=ledgerChanged)
    def canCopyPreviousMonth(self) -> bool:
        if self._ledger_month <= 0:
            return False
        return self._ws.ledger.summary(shift_month(self.ledgerPeriod, -1))["count"] > 0

    @Property(QObject, constant=True)
    def ledgerItems(self) -> QObject:
        """가계부 내역 모델 (현재 기간)."""
        return self._ledger_model

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerCategories(self) -> list[dict]:
        """가계부 분류 [{value, kind, custom}] — 수입 먼저, 지출 다음."""
        lg = self._ws.ledger
        return ([{"value": c, "kind": "income", "custom": c in lg.custom}
                 for c in lg.income_categories()]
                + [{"value": c, "kind": "cost", "custom": c in lg.custom}
                   for c in lg.cost_categories()])

    @Slot(str, str, result=str)
    @undoable("분류 추가")
    def addLedgerCategory(self, name: str, kind: str) -> str:
        """분류를 직접 만든다. 만들었으면 빈 문자열, 못 만들었으면 까닭을 돌려준다."""
        why = self._ws.ledger.add_category(name, kind)
        if why:
            self.failed.emit(why)
        else:
            self._ledger_touched()
            self._set_status(f"분류 추가: {name.strip()}")
        return why

    @Slot(str, result=str)
    @undoable("분류 삭제")
    def removeLedgerCategory(self, name: str) -> str:
        """직접 만든 분류를 지운다 (그 분류로 적어 둔 내역이 있으면 거절)."""
        why = self._ws.ledger.remove_category(name)
        if why:
            self.failed.emit(why)
        else:
            self._ledger_touched()
            self._set_status(f"분류 삭제: {name}")
        return why

    @Property(str, constant=True)
    def today(self) -> str:
        """오늘 날짜 'YYYY-MM-DD' (가계부 입력 기본값)."""
        return date.today().isoformat()

    @Property(str, notify=ledgerChanged)
    def ledgerPeriod(self) -> str:
        """'YYYY' 또는 'YYYY-MM'. 기록이 없으면 빈 문자열."""
        if not self._ledger_year:
            return ""
        return self._ledger_year if self._ledger_month <= 0 else f"{self._ledger_year}-{self._ledger_month:02d}"

    @Property(str, notify=ledgerChanged)
    def ledgerPeriodText(self) -> str:
        if not self._ledger_year:
            return "기록 없음"
        return f"{self._ledger_year}년" + ("" if self._ledger_month <= 0 else f" {self._ledger_month}월")

    @Property(str, notify=ledgerChanged)
    def ledgerYear(self) -> str:
        return self._ledger_year

    @ledgerYear.setter
    def ledgerYear(self, y: str) -> None:
        y = str(y).strip()
        if y != self._ledger_year:
            self._ledger_year = y
            self._apply_period()

    @Property(int, notify=ledgerChanged)
    def ledgerMonth(self) -> int:
        """0 이면 그 해 전체."""
        return self._ledger_month

    @ledgerMonth.setter
    def ledgerMonth(self, m: int) -> None:
        m = max(0, min(12, int(m)))
        if m != self._ledger_month:
            self._ledger_month = m
            self._apply_period()

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerYears(self) -> list[str]:
        return self._ws.ledger.years()

    @Property("QVariantMap", notify=ledgerChanged)
    def ledgerSummary(self) -> dict:
        """현재 기간의 {income, cost, net, count}"""
        return self._ws.ledger.summary(self.ledgerPeriod)

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerYearMonths(self) -> list[dict]:
        """선택한 해의 1~12월 {month, ym, income, cost, net, count, label}"""
        if not self._ledger_year:
            return []
        rows = self._ws.ledger.year_months(self._ledger_year)
        for r in rows:
            r["label"] = f"{r['month']}월"
        return rows

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerYearTotals(self) -> list[dict]:
        """해마다 {year, income, cost, net, count}"""
        return self._ws.ledger.totals_by_year()

    @Slot(str, result="QVariantList")
    def ledgerByCategory(self, kind: str) -> list[dict]:
        """현재 기간의 분류별 합계 [{label, value, share}] (큰 순)."""
        rows = self._ws.ledger.by_category(self.ledgerPeriod, kind if kind in ("income", "cost") else "cost")
        total = sum(v for _, v in rows)
        return [{"label": n, "value": v, "share": (v / total) if total else 0.0} for n, v in rows]

    @Slot(float, float, int, result="QVariantMap")
    def growthPreview(self, amount: float, growth: float, years: int) -> dict:
        """해마다 growth% 씩 오르면 years 년 뒤에 얼마가 되는지. {amount, text}"""
        years = max(1, min(40, int(years)))
        later = max(0.0, amount) * ((1.0 + max(0.0, growth) / 100.0) ** years)
        if growth <= 0 or amount <= 0:
            return {"amount": amount, "text": "오르지 않습니다"}
        return {"amount": later, "text": f"{years}년 뒤 {won(later)} (지금보다 +{won(later - amount)})"}

    @Slot(str, result=str)
    def ledgerKindOf(self, category: str) -> str:
        return self._ws.ledger.kind_of(category)

    @Slot(str, str, float, str, str, str)
    @Slot(str, str, float, str, str)
    @Slot(str, str, float, str)
    @Slot(str, str, float)
    @undoable("가계부 내역 추가")
    def addEntry(self, date_str: str, category: str, amount: float, name: str = "",
                 note: str = "", pay: str = "") -> None:
        e = Entry(date_str, category, amount, name.strip(),
                  kind=self._ws.ledger.kind_of(category), note=note.strip(), pay=pay.strip())
        self._ws.ledger.add(e)
        if not self._ledger_year:                 # 첫 기록이면 그 달로 맞춘다
            self._ledger_year, self._ledger_month = e.year, e.day.month
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부 추가: {e.category} {won(e.amount)}")  # noqa: E501

    @Slot(int, str, str, float, str, str, str)
    @Slot(int, str, str, float, str, str)
    @Slot(int, str, str, float, str)
    @Slot(int, str, str, float)
    @undoable("가계부 내역 수정")
    def updateEntry(self, row: int, date_str: str, category: str, amount: float,
                    name: str = "", note: str = "", pay: str = "") -> None:
        old = self._ws.ledger.entries[row] if 0 <= row < len(self._ws.ledger.entries) else None
        if self._ws.ledger.update(row, Entry(date_str, category, amount, name.strip(),
                                            kind=self._ws.ledger.kind_of(category),
                                            note=note.strip(),
                                            rule=old.rule if old else "",
                                            pay=pay.strip())):
            self._ledger_touched()
            self._set_status("가계부 수정")

    @Slot(int)
    @undoable("가계부 내역 삭제")
    def removeEntry(self, row: int) -> None:
        e = self._ws.ledger.remove(row)
        if e:
            self._clear_selection()
            self._ledger_touched()
            self._set_status(f"가계부 삭제: {e.category} {won(e.amount)}")

    @Slot()
    @undoable("가계부 비우기")
    def clearLedger(self) -> None:
        self._clear_selection()
        self._ws.ledger.clear()
        self._reset_ledger()
        self._set_status("가계부를 비웠습니다.")

    def _replace_plan(self, plan: Plan) -> None:
        self._plan = plan
        self._cache.clear()
        self._items.set_plan(plan)
        self._grouped.expand_all()
        self.monthsChanged.emit()
        self.targetChanged.emit()
        self.basisDateChanged.emit()
        self._summary_changed()
        self.itemsChanged.emit()
        self.scenariosChanged.emit()
