"""PDF 로 내보내기 — 파일이 제대로 만들어지는지."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage  # noqa: E402

from capital_calc.export_pdf import export_summary  # noqa: E402
from capital_calc.model import Category, Item, Plan, sample_plan  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _app():
    # QPdfWriter·QPainter 는 Qt 가 깨어 있어야 쓸 수 있다
    return QGuiApplication.instance() or QGuiApplication([])


def _head(p: Path) -> bytes:
    return p.read_bytes()[:8]


def test_makes_a_real_pdf(tmp_path):
    out = export_summary(sample_plan(), tmp_path / "요약.pdf")
    assert out.exists() and _head(out).startswith(b"%PDF")
    assert out.stat().st_size > 3000


def test_suffix_is_forced(tmp_path):
    out = export_summary(sample_plan(), tmp_path / "이름만")
    assert out.name == "이름만.pdf" and out.exists()


def test_chart_image_goes_in(tmp_path):
    plain = export_summary(sample_plan(), tmp_path / "a.pdf")

    img = QImage(600, 300, QImage.Format.Format_RGB32)
    img.fill(QColor("#101320"))
    png = tmp_path / "chart.png"
    assert img.save(str(png))

    withchart = export_summary(sample_plan(), tmp_path / "b.pdf", png)
    assert withchart.stat().st_size > plain.stat().st_size      # 그림이 들어갔다


def test_a_broken_image_is_skipped_not_fatal(tmp_path):
    bad = tmp_path / "nope.png"
    bad.write_text("이건 그림이 아니다", encoding="utf-8")
    out = export_summary(sample_plan(), tmp_path / "c.pdf", bad)
    assert out.exists() and _head(out).startswith(b"%PDF")


def test_goals_and_scenarios_and_off_items(tmp_path):
    p = sample_plan()
    p.goals = [{"name": "1차 전세금", "amount": 20_000_000}]
    p.items[0].active = False
    p.add(Item("자동차세", Category.EXPENSE, 500_000, start_date=p.start_date, every=12))
    rows = [{"name": "가", "net": 1_000_000, "active": True},
            {"name": "나", "net": 2_000_000, "active": False}]
    out = export_summary(p, tmp_path / "d.pdf", None, rows)
    assert out.exists() and out.stat().st_size > 3000


def test_empty_plan_still_works(tmp_path):
    out = export_summary(Plan(months=12), tmp_path / "e.pdf")
    assert out.exists() and _head(out).startswith(b"%PDF")
