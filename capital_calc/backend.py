"""QML 프론트엔드에 노출되는 Python 백엔드.

역할 분담:
- model.py  : 순수 계산 로직 (Qt 를 전혀 모름)
- backend.py: model.py 를 QObject / QAbstractListModel 로 감싸서 QML 에 신호·슬롯·프로퍼티로 제공
- qml/      : 화면, 레이아웃, 애니메이션 (Python 을 모름, backend 프로퍼티만 바인딩)
"""
from __future__ import annotations

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
from .ledger import (LEDGER_COST_CATEGORIES, LEDGER_INCOME_CATEGORIES, Entry, Ledger,
                     kind_of, prev_period, sample_ledger, shift_month)
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
        if role == self.SourceRowRole:
            return index.row()
        if role == self.RepayMethodRole:
            return it.repay_method
        if role == self.HousingTypeRole:
            return it.housing_type
        if role == self.MonthlyRole:
            return it.monthly
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
                k = it.saving_months(self._plan.months, self._plan.basis)
                parts.append(f"{self._plan.months}개월 후 {won(it.saving_balance_at(self._plan.months, self._plan.basis))} ({k}회 납입)")
            if it.category == Category.LOAN:
                basis = self._plan.basis
                label = REPAY_METHODS.get(it.repay_method, "")
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
                om = it.once_month(basis)
                prefix = f"{om}개월 뒤 " if om > 0 else ""
                kind, text = "once", prefix + "일시 -" + won(it.once_cost())
            elif it.once_income() > 0:
                om = it.once_month(basis)
                prefix = f"{om}개월 뒤 " if om > 0 else ""
                kind, text = "income", prefix + "일시 +" + won(it.once_income())
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
        if 0 <= start < n:
            self.dataChanged.emit(self.index(start), self.index(n - 1), [self.SourceRowRole])

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
    }

    def __init__(self, ledger: Ledger, parent: QObject | None = None):
        super().__init__(parent)
        self._ledger = ledger
        self._period = ""
        self._query = ""
        self._kind = ""
        self._category = ""
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
            return e.date
        return None

    # ---- 갱신 ----
    def _rebuild(self) -> None:
        rows = [(e.date, i) for i, e in enumerate(self._ledger.entries)
                if self._ledger.matches(e, self._period, self._query, self._kind, self._category)]
        rows.sort(key=lambda t: t[0], reverse=True)
        self._rows = [i for _, i in rows]

    def refresh(self) -> None:
        self.beginResetModel()
        self._rebuild()
        self.endResetModel()

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

    def set_filters(self, query: str, kind: str, category: str) -> None:
        if (query, kind, category) != (self._query, self._kind, self._category):
            self.beginResetModel()
            self._query, self._kind, self._category = query, kind, category
            self._rebuild()
            self.endResetModel()


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
        self._ledger_year = ""
        self._ledger_month = 0          # 0 = 그 해 전체
        self._ledger_query = ""
        self._ledger_kind = ""          # "" | income | cost
        self._ledger_category = ""      # "" = 전체
        self._grouped = GroupedItems(self._items, self)
        self._group_by_category = True
        self._status = ""
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
        self.summaryChanged.emit()
        self.itemsChanged.emit()

    def _set_status(self, text: str) -> None:
        self._status = text
        self.statusChanged.emit()

    # ------------------------------------------------------------ 프로퍼티
    @Property(QObject, constant=True)
    def items(self) -> ItemListModel:
        return self._items

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
        items = [i for i in self._plan.items if i.category == cat]
        monthly = 0.0
        for it in items:
            net = it.monthly_net_at(0, basis)
            if it.category == Category.LOAN and it.include_principal:
                net -= it.regular_repay_at(0, basis)
            monthly += net
        return {
            "count": len(items),
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
    def addScenario(self, name: str = "") -> None:
        """빈 시나리오를 추가하고 활성화. 기간·목표·기준일은 현재 것을 이어받는다."""
        p = self._ws.add(name)
        self._replace_plan(p)
        self._set_status(f"시나리오 추가: {p.name}")

    @Slot()
    def duplicateScenario(self) -> None:
        """현재 시나리오를 복제하고 복제본을 활성화."""
        p = self._ws.duplicate()
        self._replace_plan(p)
        self._set_status(f"시나리오 복제: {p.name}")

    @Slot(int)
    def removeScenario(self, index: int) -> None:
        name = self._ws.plans[index].name if 0 <= index < len(self._ws.plans) else ""
        if not self._ws.remove(index):
            self.failed.emit("시나리오는 최소 1개 있어야 합니다.")
            return
        self._replace_plan(self._ws.plan)
        self._set_status(f"시나리오 삭제: {name}")

    @Slot(int, str)
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
        out = []
        for i, p in enumerate(self._ws.plans):
            gm = p.summary().goal_month() if p.target > 0 else None
            out.append({
                "index": i,
                "name": p.name,
                "active": i == self._ws.active,
                "values": [p.net_at(m) for m in range(max(1, horizon) + 1)],
                "goalMonth": -1 if gm is None else gm,
            })
        return out

    @Slot(result="QVariantList")
    def compareRows(self) -> list[dict]:
        """비교표: 현재 시나리오의 기간(N개월) 기준으로 모든 시나리오를 나란히.
        [{index, name, active, net, diff, monthlyNet, target, goalText}]"""
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
            self.monthsChanged.emit()
            self.summaryChanged.emit()

    months = Property(int, _get_months, _set_months, notify=monthsChanged)

    def _get_target(self) -> float:
        return self._plan.target

    def _set_target(self, v: float) -> None:
        v = max(0.0, float(v))
        if v != self._plan.target:
            self._plan.target = v
            self.targetChanged.emit()
            self.summaryChanged.emit()

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
            self.summaryChanged.emit()

    basisDate = Property(str, _get_basis_date, _set_basis_date, notify=basisDateChanged)

    @Slot(str, result=bool)
    def isValidDate(self, v: str) -> bool:
        return v.strip() == "" or parse_date(v) is not None

    # 요약 값들 (전부 summaryChanged 로 갱신)
    def _s(self):
        return self._plan.summary()

    @Property(float, notify=summaryChanged)
    def capital(self) -> float:
        return self._s().capital

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
        s = self._s()
        return [s.net_at(m) for m in range(max(1, months) + 1)]

    @Slot(int, result=float)
    def netAt(self, month: int) -> float:
        return self._s().net_at(month)

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
        s = self._plan.shortfall()
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
                   housing_type: str = "", monthly: float = 0.0) -> Item:
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
        )

    @Slot(str, int, float, float, bool, str, str, str, float, str, str, float)
    @Slot(str, int, float, float, bool, str, str, str, float, str)
    @Slot(str, int, float, float, bool, str, str, str, float)
    @Slot(str, int, float, float, bool, str, str, str)
    @Slot(str, int, float, float, bool)
    def addItem(self, name: str, cat_index: int, amount: float, rate: float, include_principal: bool,
                start_date: str = "", end_date: str = "", repayments_json: str = "[]",
                monthly_repay_rate: float = 0.0, repay_method: str = "",
                housing_type: str = "", monthly: float = 0.0) -> None:
        item = self._make_item(name, cat_index, amount, rate, include_principal, start_date, end_date,
                               repayments_json, monthly_repay_rate, repay_method, housing_type, monthly)
        self._items.add(item)
        self._set_status(f"추가: {item.name}")

    @Slot(int, str, int, float, float, bool, str, str, str, float, str, str, float)
    @Slot(int, str, int, float, float, bool, str, str, str, float, str)
    @Slot(int, str, int, float, float, bool, str, str, str, float)
    @Slot(int, str, int, float, float, bool, str, str, str)
    @Slot(int, str, int, float, float, bool)
    def updateItem(self, row: int, name: str, cat_index: int, amount: float, rate: float, include_principal: bool,
                   start_date: str = "", end_date: str = "", repayments_json: str = "[]",
                   monthly_repay_rate: float = 0.0, repay_method: str = "",
                   housing_type: str = "", monthly: float = 0.0) -> None:
        item = self._make_item(name, cat_index, amount, rate, include_principal, start_date, end_date,
                               repayments_json, monthly_repay_rate, repay_method, housing_type, monthly)
        self._items.update(row, item)
        self._set_status(f"수정: {item.name}")

    @Slot(int)
    def removeItem(self, row: int) -> None:
        removed = self._items.remove(row)
        if removed:
            self._set_status(f"삭제: {removed.name}")

    @Slot(int, int)
    def moveItem(self, row: int, delta: int) -> None:
        self._items.move(row, delta)

    @Slot()
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
    def _reset_ledger(self) -> None:
        """가계부가 통째로 바뀐 뒤 (불러오기·예시) 기간을 최신으로 맞춘다."""
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
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_model.set_filters(self._ledger_query, self._ledger_kind, self._ledger_category)
        self.ledgerChanged.emit()
        self.budgetsChanged.emit()

    def _apply_filters(self) -> None:
        self._ledger_model.set_filters(self._ledger_query, self._ledger_kind, self._ledger_category)
        self.ledgerChanged.emit()

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

    @Property("QVariantList", notify=ledgerChanged)
    def ledgerUsedCategories(self) -> list[str]:
        """현재 기간에 실제로 쓴 분류 (필터 콤보박스용, 맨 앞에 '전체')."""
        return ["전체"] + self._ws.ledger.categories_used(self.ledgerPeriod)

    @Property(bool, notify=ledgerChanged)
    def ledgerFiltered(self) -> bool:
        return bool(self._ledger_query or self._ledger_kind or self._ledger_category)

    @Slot()
    def clearLedgerFilters(self) -> None:
        if self.ledgerFiltered:
            self._ledger_query = self._ledger_kind = self._ledger_category = ""
            self._apply_filters()

    @Property("QVariantMap", notify=ledgerChanged)
    def ledgerFilteredSummary(self) -> dict:
        """걸러진 내역만의 {income, cost, net, count} (필터가 없으면 기간 전체와 같다)."""
        income = cost = 0.0
        count = 0
        for e in self._ws.ledger.entries:
            if not self._ws.ledger.matches(e, self.ledgerPeriod, self._ledger_query,
                                           self._ledger_kind, self._ledger_category):
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
    @Slot(str, str, float, str, str, int)
    def addEntryRepeat(self, date_str: str, category: str, amount: float,
                       name: str, note: str, months: int) -> None:
        """같은 내역을 months 달 동안 (이번 달 포함) 넣는다."""
        months = max(1, min(60, int(months)))
        e = Entry(date_str, category, amount, name.strip(), note=note.strip())
        self._ws.ledger.add(e)
        made = self._ws.ledger.repeat(e, months)
        if not self._ledger_year:
            self._ledger_year, self._ledger_month = e.year, e.day.month
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부 추가: {e.category} {won(e.amount)}"
                         + (f" · {len(made) + 1}개월 반복" if made else ""))

    @Slot()
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
                for c in LEDGER_COST_CATEGORIES]

    @Slot(str, float)
    def setBudget(self, category: str, amount: float) -> None:
        """예산만 바꾼다. 내역·집계는 그대로이므로 budgetsChanged 만 보낸다 (슬라이더를 끌 때 가볍게)."""
        self._ws.ledger.set_budget(category, amount)
        self.budgetsChanged.emit()

    @Slot()
    def clearBudgets(self) -> None:
        self._ws.ledger.budgets.clear()
        self.budgetsChanged.emit()
        self._set_status("예산을 모두 지웠습니다.")

    @Slot()
    def fillBudgetsFromPeriod(self) -> None:
        """지금 보고 있는 기간에 실제로 쓴 금액(월평균)을 예산으로 채운다."""
        n = self._ws.ledger.budget_from_period(self.ledgerPeriod)
        self.budgetsChanged.emit()
        self._set_status(f"{self.ledgerPeriodText} 실적으로 예산 {n}개를 채웠습니다."
                         if n else "채울 지출 기록이 없습니다.")

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
        period = self.ledgerPeriod
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

        s = self._ws.ledger.summary(period)
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

    @Property(bool, notify=ledgerChanged)
    def canCopyPreviousMonth(self) -> bool:
        if self._ledger_month <= 0:
            return False
        return self._ws.ledger.summary(shift_month(self.ledgerPeriod, -1))["count"] > 0

    @Property(QObject, constant=True)
    def ledgerItems(self) -> QObject:
        """가계부 내역 모델 (현재 기간)."""
        return self._ledger_model

    @Property("QVariantList", constant=True)
    def ledgerCategories(self) -> list[dict]:
        """가계부 분류 [{value, kind}] — 수입 먼저, 지출 다음."""
        return ([{"value": c, "kind": "income"} for c in LEDGER_INCOME_CATEGORIES]
                + [{"value": c, "kind": "cost"} for c in LEDGER_COST_CATEGORIES])

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

    @Slot(str, result=str)
    def ledgerKindOf(self, category: str) -> str:
        return kind_of(category)

    @Slot(str, str, float, str, str)
    @Slot(str, str, float, str)
    @Slot(str, str, float)
    def addEntry(self, date_str: str, category: str, amount: float, name: str = "", note: str = "") -> None:
        e = Entry(date_str, category, amount, name.strip(), note=note.strip())
        self._ws.ledger.add(e)
        if not self._ledger_year:                 # 첫 기록이면 그 달로 맞춘다
            self._ledger_year, self._ledger_month = e.year, e.day.month
        self._ledger_model.set_period(self.ledgerPeriod)
        self._ledger_touched()
        self._set_status(f"가계부 추가: {e.category} {won(e.amount)}")  # noqa: E501

    @Slot(int, str, str, float, str, str)
    @Slot(int, str, str, float, str)
    @Slot(int, str, str, float)
    def updateEntry(self, row: int, date_str: str, category: str, amount: float,
                    name: str = "", note: str = "") -> None:
        if self._ws.ledger.update(row, Entry(date_str, category, amount, name.strip(), note=note.strip())):
            self._ledger_touched()
            self._set_status("가계부 수정")

    @Slot(int)
    def removeEntry(self, row: int) -> None:
        e = self._ws.ledger.remove(row)
        if e:
            self._ledger_touched()
            self._set_status(f"가계부 삭제: {e.category} {won(e.amount)}")

    @Slot()
    def clearLedger(self) -> None:
        self._ws.ledger.clear()
        self._reset_ledger()
        self._set_status("가계부를 비웠습니다.")

    def _replace_plan(self, plan: Plan) -> None:
        self._plan = plan
        self._items.set_plan(plan)
        self._grouped.expand_all()
        self.monthsChanged.emit()
        self.targetChanged.emit()
        self.basisDateChanged.emit()
        self.summaryChanged.emit()
        self.itemsChanged.emit()
        self.scenariosChanged.emit()
