"""요약과 그래프를 PDF 한 장으로.

엑셀은 숫자를 다시 만지려고 내보내는 것이고, 이쪽은 **보여 주거나 남겨 두려고**
내보내는 것이다. 그래서 A4 한 장에 '지금 어떤 계획인지' 가 다 들어가게 짰다.

글씨는 PDF 안에서 글씨로 남는다(그려 붙인 그림이 아니다). 그래프만 그림으로
받아서 끼운다 — QML 이 그린 것을 그대로 쓰는 게 가장 똑같기 때문이다.
Qt 만 쓰므로 따로 깔 것이 없다.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter

from .model import Plan, add_months, won

# A4 한 장을 300dpi 로 그린다 (인쇄해도 깨지지 않고, 파일도 무겁지 않다)
DPI = 300
MARGIN_MM = 14.0

INK = QColor("#1a1d26")
DIM = QColor("#6b7280")
LINE = QColor("#d6d9e0")
GREEN = QColor("#1c7a4b")
RED = QColor("#b03a3a")


def _mm(v: float) -> int:
    return int(v * DPI / 25.4)


class _Page:
    """맨 위에서부터 아래로 쌓아 그리는 간단한 흐름."""

    def __init__(self, painter: QPainter, width: int, height: int):
        self.p = painter
        self.w = width
        self.h = height
        self.y = 0

    def text(self, s: str, size: int, color: QColor = INK, bold: bool = False,
             gap: int = 2, align: int = Qt.AlignmentFlag.AlignLeft) -> None:
        f = QFont("Malgun Gothic", size)
        f.setBold(bold)
        self.p.setFont(f)
        self.p.setPen(color)
        h = self.p.fontMetrics().height()
        self.p.drawText(QRectF(0, self.y, self.w, h * 1.4), align | Qt.AlignmentFlag.AlignVCenter, s)
        self.y += int(h * 1.4) + _mm(gap)

    def row(self, label: str, value: str, color: QColor = INK, bold: bool = False) -> None:
        f = QFont("Malgun Gothic", 11)
        f.setBold(bold)
        self.p.setFont(f)
        h = self.p.fontMetrics().height()
        box = QRectF(0, self.y, self.w, h * 1.35)
        self.p.setPen(DIM if not bold else INK)
        self.p.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
        self.p.setPen(color)
        self.p.drawText(box, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value)
        self.y += int(h * 1.35)

    def rule(self, gap: int = 2) -> None:
        self.p.setPen(LINE)
        self.p.drawLine(0, self.y + _mm(1), self.w, self.y + _mm(1))
        self.y += _mm(1 + gap)

    def space(self, mm: float) -> None:
        self.y += _mm(mm)

    def image(self, path: str | Path, max_h_mm: float = 95.0) -> bool:
        img = QImage(str(path))
        if img.isNull():
            return False
        max_h = _mm(max_h_mm)
        scale = min(self.w / img.width(), max_h / img.height())
        w, h = int(img.width() * scale), int(img.height() * scale)
        self.p.drawImage(QRectF(0, self.y, w, h), img)
        self.y += h + _mm(3)
        return True


def export_summary(plan: Plan, path: str | Path, chart_image: str | Path | None = None,
                   scenario_rows: list[dict] | None = None) -> Path:
    """계획 요약을 PDF 한 장으로 쓴다. 쓴 경로를 돌려준다."""
    out = Path(path)
    if out.suffix.lower() != ".pdf":
        out = out.with_suffix(".pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    writer = QPdfWriter(str(out))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(MARGIN_MM, MARGIN_MM, MARGIN_MM, MARGIN_MM),
                          QPageLayout.Unit.Millimeter)
    writer.setResolution(DPI)
    writer.setTitle(f"자본금 계산기 — {plan.name}")

    s = plan.summary()
    n = plan.months
    painter = QPainter(writer)
    try:
        page = _Page(painter, painter.viewport().width(), painter.viewport().height())

        page.text("자본금 계산기", 20, INK, bold=True, gap=0)
        page.text(f"{plan.name}  ·  기준일 {plan.start_date}  ·  {n}개월 "
                  f"({add_months(plan.basis, n).isoformat()} 까지)", 10, DIM, gap=2)
        page.rule()

        page.text("요약", 13, INK, bold=True, gap=1)
        page.row("보유 자금 (지금)", won(s.capital), GREEN)
        page.row(f"{n}개월 후 보유 자금", won(plan.capital_at(n)), GREEN)
        page.row("일시 지출", "-" + won(s.once_cost), RED)
        page.row("일시 수입", "+" + won(s.once_income), GREEN)
        page.row("월 지출 (평균)", "-" + won(s.avg_cost), RED)
        page.row("월 수입 (평균)", "+" + won(s.avg_income), GREEN)
        page.row(f"{n}개월 필요 자금", "-" + won(s.required), RED)
        page.row(f"{n}개월 수입", "+" + won(s.period_income), GREEN)
        page.rule(1)
        page.row(f"{n}개월 후 순 자본", won(s.net), GREEN if s.net >= 0 else RED, bold=True)
        page.space(3)

        if plan.target > 0:
            page.text("목표", 13, INK, bold=True, gap=1)
            page.row("목표 자본금", won(plan.target))
            gap = s.net - plan.target
            page.row("목표 대비", ("+" if gap >= 0 else "-") + won(abs(gap)),
                     GREEN if gap >= 0 else RED)
            gm = plan.first_month_reaching(plan.target)
            if gm is None:
                page.row("달성 예측", "지금 계획으로는 닿지 않습니다", RED)
            else:
                d = add_months(plan.basis, gm)
                page.row("달성 예측", f"{d.year}년 {d.month}월 ({gm}개월 뒤)",
                         GREEN if gm <= n else INK)
            for g in plan.goal_list():
                if g["final"]:
                    continue
                m = plan.first_month_reaching(g["amount"])
                when = "못 닿음" if m is None else (
                    "이미 달성" if m <= 0 else f"{add_months(plan.basis, m).year}년 "
                                               f"{add_months(plan.basis, m).month}월 ({m}개월 뒤)")
                page.row(f"  {g['name']}  {won(g['amount'])}", when, DIM)
            page.space(3)

        if chart_image:
            page.text("순 자본 추이", 13, INK, bold=True, gap=1)
            page.image(chart_image)

        if scenario_rows and len(scenario_rows) > 1:
            page.text("시나리오 비교", 13, INK, bold=True, gap=1)
            for r in scenario_rows:
                mark = "●  " if r.get("active") else "    "
                page.row(mark + str(r.get("name", "")), won(float(r.get("net", 0))),
                         INK if r.get("active") else DIM, bold=bool(r.get("active")))
            page.space(3)

        page.text(f"항목 {len(plan.items)}개", 13, INK, bold=True, gap=1)
        basis = plan.basis
        for it in plan.items:
            net = it.monthly_net_at(0, basis)
            if net:
                tail = ("+" if net > 0 else "-") + won(abs(net)) + " / 달"
            elif it.once_cost():
                tail = "일시 -" + won(it.once_cost())
            elif it.once_income():
                tail = "일시 +" + won(it.once_income())
            else:
                tail = "자본"
            name = it.name + ("" if it.active else "  (꺼짐)")
            page.row(f"{name}  ·  {it.category.value}", f"{won(it.amount)}   {tail}",
                     INK if it.active else DIM)

        page.space(4)
        page.text(f"자본금 계산기에서 {date.today().isoformat()} 에 내보냄", 8, DIM, gap=0)
    finally:
        painter.end()
    return out
