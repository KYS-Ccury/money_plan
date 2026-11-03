"""OpenGL(GLFW) 창 위에 Dear ImGui 로 그리는 자본금 계산기 UI.

- GLFW 가 OS 창과 OpenGL 컨텍스트를 만들고
- Dear ImGui 가 위젯을 OpenGL 로 렌더링한다.
- 항목 추가/수정/삭제는 ImGui 모달 팝업창으로 처리한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import glfw
import numpy as np
from OpenGL import GL
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from .model import (
    CATEGORY_INFO,
    CATEGORY_LIST,
    Category,
    Item,
    Plan,
    sample_plan,
    won,
)

WINDOW_TITLE = "자본금 계산기"
WINDOW_SIZE = (1100, 720)
DATA_FILE = Path(__file__).resolve().parent.parent / "capital_data.json"

KOREAN_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\malgun.ttf",
    r"C:\Windows\Fonts\NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]

# 색상
C_GREEN = imgui.ImVec4(0.35, 0.80, 0.45, 1.0)
C_RED = imgui.ImVec4(0.92, 0.40, 0.40, 1.0)
C_GRAY = imgui.ImVec4(0.65, 0.65, 0.65, 1.0)
C_YELLOW = imgui.ImVec4(0.95, 0.80, 0.35, 1.0)


class ItemForm:
    """추가/수정 팝업에서 쓰는 임시 입력값."""

    def __init__(self, item: Item | None = None):
        if item is None:
            self.name = ""
            self.cat_index = CATEGORY_LIST.index(Category.CASH)
            self.amount = 0.0
            self.rate = 0.0
            self.include_principal = True
        else:
            self.name = item.name
            self.cat_index = CATEGORY_LIST.index(item.category)
            self.amount = item.amount
            self.rate = item.rate
            self.include_principal = item.include_principal

    @property
    def category(self) -> Category:
        return CATEGORY_LIST[self.cat_index]

    def to_item(self) -> Item:
        name = self.name.strip() or self.category.value
        return Item(name, self.category, self.amount, self.rate, self.include_principal)


class CapitalApp:
    def __init__(self, plan: Plan | None = None):
        self.plan = plan or self._load_or_sample()
        self.form = ItemForm()
        self.edit_index: int | None = None
        self.delete_index: int | None = None
        self.status = ""
        self._open_add = False
        self._open_edit = False
        self._open_delete = False
        self._open_clear = False

    # ------------------------------------------------------------------ 데이터
    @staticmethod
    def _load_or_sample() -> Plan:
        if DATA_FILE.exists():
            try:
                return Plan.load(DATA_FILE)
            except Exception:
                pass
        return sample_plan()

    def save(self) -> None:
        try:
            self.plan.save(DATA_FILE)
            self.status = f"저장됨: {DATA_FILE.name}"
        except Exception as e:  # pragma: no cover
            self.status = f"저장 실패: {e}"

    def load(self) -> None:
        try:
            self.plan = Plan.load(DATA_FILE)
            self.status = f"불러옴: {DATA_FILE.name}"
        except Exception as e:
            self.status = f"불러오기 실패: {e}"

    # ------------------------------------------------------------------ UI 루트
    def draw(self) -> None:
        vp = imgui.get_main_viewport()
        imgui.set_next_window_pos(vp.work_pos)
        imgui.set_next_window_size(vp.work_size)
        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_bring_to_front_on_focus
        )
        imgui.begin("##root", None, flags)

        self._draw_header()
        imgui.separator()

        avail = imgui.get_content_region_avail()
        left_w = avail.x * 0.58
        imgui.begin_child("##left", imgui.ImVec2(left_w, avail.y - 24), imgui.ChildFlags_.borders)
        self._draw_item_table()
        imgui.end_child()

        imgui.same_line()
        imgui.begin_child("##right", imgui.ImVec2(0, avail.y - 24), imgui.ChildFlags_.borders)
        self._draw_summary()
        imgui.end_child()

        imgui.text_colored(C_GRAY, self.status)

        self._draw_popups()
        imgui.end()

    # ------------------------------------------------------------------ 상단
    def _draw_header(self) -> None:
        imgui.text("자본금 계산기")
        imgui.same_line(0, 30)

        imgui.set_next_item_width(120)
        changed, months = imgui.input_int("기간(개월)", self.plan.months, 1, 12)
        if changed:
            self.plan.months = max(0, months)

        imgui.same_line(0, 20)
        imgui.set_next_item_width(200)
        changed, target = imgui.input_double("목표 자본금(원)", self.plan.target, 1_000_000, 10_000_000, "%.0f")
        if changed:
            self.plan.target = max(0.0, target)

        imgui.same_line(0, 30)
        if imgui.button("+ 항목 추가"):
            self.form = ItemForm()
            self._open_add = True
        imgui.same_line()
        if imgui.button("저장"):
            self.save()
        imgui.same_line()
        if imgui.button("불러오기"):
            self.load()
        imgui.same_line()
        if imgui.button("예시 데이터"):
            self.plan = sample_plan()
            self.status = "예시 데이터를 불러왔습니다."
        imgui.same_line()
        if imgui.button("전체 삭제"):
            self._open_clear = True

    # ------------------------------------------------------------------ 항목 표
    def _draw_item_table(self) -> None:
        imgui.text(f"항목 목록 ({len(self.plan.items)}개)")
        imgui.text_colored(C_GRAY, "행을 더블클릭하면 수정, ▲▼ 로 순서 변경, X 로 삭제")

        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.scroll_y
        )
        if not imgui.begin_table("items", 7, flags):
            return
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_setup_column("이름", imgui.TableColumnFlags_.width_stretch, 1.6)
        imgui.table_setup_column("분류", imgui.TableColumnFlags_.width_stretch, 1.2)
        imgui.table_setup_column("금액", imgui.TableColumnFlags_.width_stretch, 1.5)
        imgui.table_setup_column("연이율", imgui.TableColumnFlags_.width_fixed, 60)
        imgui.table_setup_column("월 환산", imgui.TableColumnFlags_.width_stretch, 1.9)
        imgui.table_setup_column("순서", imgui.TableColumnFlags_.width_fixed, 56)
        imgui.table_setup_column("삭제", imgui.TableColumnFlags_.width_fixed, 36)
        imgui.table_headers_row()

        for i, it in enumerate(self.plan.items):
            imgui.push_id(i)
            imgui.table_next_row()

            imgui.table_set_column_index(0)
            # 행 전체 선택 가능하게 → 더블클릭 시 수정
            if imgui.selectable(
                it.name, False,
                imgui.SelectableFlags_.span_all_columns | imgui.SelectableFlags_.allow_double_click,
            )[0] and imgui.is_mouse_double_clicked(0):
                self.form = ItemForm(it)
                self.edit_index = i
                self._open_edit = True

            imgui.table_set_column_index(1)
            imgui.text(it.category.value)

            imgui.table_set_column_index(2)
            imgui.text(won(it.amount))

            imgui.table_set_column_index(3)
            if CATEGORY_INFO[it.category]["uses_rate"]:
                imgui.text(f"{it.rate:.2f}%")
            else:
                imgui.text_colored(C_GRAY, "-")

            imgui.table_set_column_index(4)
            net = it.monthly_net()
            if net > 0:
                imgui.text_colored(C_GREEN, "+" + won(net))
            elif net < 0:
                imgui.text_colored(C_RED, won(net))
            else:
                once = it.once_cost()
                if once:
                    imgui.text_colored(C_YELLOW, f"일시 -{won(once)}")
                else:
                    imgui.text_colored(C_GRAY, "자본")

            imgui.table_set_column_index(5)
            if imgui.small_button("▲"):
                self.plan.move(i, -1)
            imgui.same_line()
            if imgui.small_button("▼"):
                self.plan.move(i, +1)

            imgui.table_set_column_index(6)
            if imgui.small_button("X"):
                self.delete_index = i
                self._open_delete = True

            imgui.pop_id()
        imgui.end_table()

    # ------------------------------------------------------------------ 요약
    def _draw_summary(self) -> None:
        s = self.plan.summary()
        imgui.text("요약")
        imgui.separator()

        def row(label: str, value: float, color=None, prefix: str = ""):
            imgui.text(label)
            imgui.same_line(170)
            txt = prefix + won(value)
            if color is not None:
                imgui.text_colored(color, txt)
            else:
                imgui.text(txt)

        row("보유 자금", s.capital, C_GREEN)
        row("일시 지출", s.once_cost, C_RED, "-")
        row("월 지출", s.monthly_cost, C_RED, "-")
        row("월 수입", s.monthly_income, C_GREEN, "+")
        row("월 순수입", s.monthly_net, C_GREEN if s.monthly_net >= 0 else C_RED)
        imgui.spacing()
        row(f"{s.months}개월 필요 자금", s.required, C_RED, "-")
        row(f"{s.months}개월 수입", s.period_income, C_GREEN, "+")
        imgui.separator()
        row(f"{s.months}개월 후 순 자본", s.net, C_GREEN if s.net >= 0 else C_RED)

        imgui.spacing()
        imgui.separator()
        imgui.text("목표")
        row("목표 자본금", s.target)
        frac = min(1.0, s.progress)
        if s.target > 0:
            overlay = f"{s.progress * 100:.1f}%"
        else:
            overlay = "목표를 입력하세요"
        color = C_GREEN if s.gap >= 0 else (C_YELLOW if s.progress >= 0.7 else C_RED)
        imgui.push_style_color(imgui.Col_.plot_histogram, color)
        imgui.progress_bar(frac, imgui.ImVec2(-1, 22), overlay)
        imgui.pop_style_color()

        if s.target > 0:
            if s.gap >= 0:
                row("목표 초과", s.gap, C_GREEN, "+")
            else:
                row("목표 부족", -s.gap, C_RED, "-")
                m = s.months_to_goal()
                if m is None:
                    imgui.text_colored(C_GRAY, "월 순수입이 0 이하라 현재 구성으로는 목표에 도달할 수 없습니다.")
                else:
                    imgui.text_colored(C_YELLOW, f"현재 월 순수입 기준 약 {m}개월 더 필요")

        # 월별 순 자본 추이 그래프
        imgui.spacing()
        imgui.separator()
        imgui.text("월별 순 자본 추이")
        n = max(2, s.months + 1)
        values = np.array([s.net_at(m) for m in range(n)], dtype=np.float32)
        lo = float(min(values.min(), 0.0, s.target))
        hi = float(max(values.max(), s.target, 1.0))
        imgui.plot_lines("##trend", values, 0, f"0 → {s.months}개월", lo, hi, imgui.ImVec2(-1, 110))
        if s.target > 0:
            imgui.text_colored(C_GRAY, f"그래프 범위 {won(lo)} ~ {won(hi)} (목표선 {won(s.target)})")

    # ------------------------------------------------------------------ 팝업창
    def _item_form_body(self) -> None:
        """추가/수정 팝업에 공통으로 들어가는 입력 폼."""
        imgui.set_next_item_width(300)
        _, self.form.name = imgui.input_text("이름", self.form.name)

        imgui.set_next_item_width(300)
        _, self.form.cat_index = imgui.combo("분류", self.form.cat_index, [c.value for c in CATEGORY_LIST])
        info = CATEGORY_INFO[self.form.category]
        imgui.text_colored(C_GRAY, info["hint"])

        imgui.set_next_item_width(300)
        changed, amount = imgui.input_double(info["amount_label"] + "(원)", self.form.amount, 10_000, 100_000, "%.0f")
        if changed:
            self.form.amount = max(0.0, amount)

        if info["uses_rate"]:
            imgui.set_next_item_width(300)
            changed, rate = imgui.input_double("연이율(%)", self.form.rate, 0.1, 1.0, "%.2f")
            if changed:
                self.form.rate = max(0.0, rate)
            preview = self.form.amount * self.form.rate / 100 / 12
            imgui.text_colored(C_GRAY, f"월 이자: {won(preview)}")
            if self.form.category == Category.LOAN:
                _, self.form.include_principal = imgui.checkbox("대출 원금을 보유 자금에 포함", self.form.include_principal)

    def _draw_popups(self) -> None:
        # 팝업은 open_popup 을 호출한 같은 ID 스택에서 begin_popup_modal 해야 하므로
        # 플래그를 보고 여기서 한 번에 연다.
        if self._open_add:
            imgui.open_popup("항목 추가")
            self._open_add = False
        if self._open_edit:
            imgui.open_popup("항목 수정")
            self._open_edit = False
        if self._open_delete:
            imgui.open_popup("삭제 확인")
            self._open_delete = False
        if self._open_clear:
            imgui.open_popup("전체 삭제 확인")
            self._open_clear = False

        center = imgui.get_main_viewport().get_center()
        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        if imgui.begin_popup_modal("항목 추가", None, imgui.WindowFlags_.always_auto_resize)[0]:
            self._item_form_body()
            imgui.separator()
            if imgui.button("추가", imgui.ImVec2(120, 0)):
                self.plan.add(self.form.to_item())
                self.status = f"추가: {self.form.to_item().name}"
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("취소", imgui.ImVec2(120, 0)):
                imgui.close_current_popup()
            imgui.end_popup()

        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        if imgui.begin_popup_modal("항목 수정", None, imgui.WindowFlags_.always_auto_resize)[0]:
            self._item_form_body()
            imgui.separator()
            if imgui.button("저장", imgui.ImVec2(120, 0)):
                if self.edit_index is not None and 0 <= self.edit_index < len(self.plan.items):
                    self.plan.items[self.edit_index] = self.form.to_item()
                    self.status = f"수정: {self.form.to_item().name}"
                self.edit_index = None
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("취소", imgui.ImVec2(120, 0)):
                self.edit_index = None
                imgui.close_current_popup()
            imgui.end_popup()

        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        if imgui.begin_popup_modal("삭제 확인", None, imgui.WindowFlags_.always_auto_resize)[0]:
            name = ""
            if self.delete_index is not None and 0 <= self.delete_index < len(self.plan.items):
                name = self.plan.items[self.delete_index].name
            imgui.text(f"'{name}' 항목을 삭제할까요?")
            imgui.separator()
            if imgui.button("삭제", imgui.ImVec2(120, 0)):
                if self.delete_index is not None:
                    removed = self.plan.remove(self.delete_index)
                    if removed:
                        self.status = f"삭제: {removed.name}"
                self.delete_index = None
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("취소", imgui.ImVec2(120, 0)):
                self.delete_index = None
                imgui.close_current_popup()
            imgui.end_popup()

        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        if imgui.begin_popup_modal("전체 삭제 확인", None, imgui.WindowFlags_.always_auto_resize)[0]:
            imgui.text("모든 항목을 삭제할까요? (목표/기간은 유지)")
            imgui.separator()
            if imgui.button("전체 삭제", imgui.ImVec2(120, 0)):
                self.plan.clear()
                self.status = "모든 항목을 삭제했습니다."
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("취소", imgui.ImVec2(120, 0)):
                imgui.close_current_popup()
            imgui.end_popup()


# ---------------------------------------------------------------------- 런처
def _load_korean_font(io) -> None:
    for path in KOREAN_FONT_CANDIDATES:
        if os.path.exists(path):
            cfg = imgui.ImFontConfig()
            cfg.size_pixels = 18.0
            io.fonts.add_font_from_file_ttf(path, 18.0, cfg)
            return
    # 한글 폰트가 없으면 기본 폰트(한글 깨짐) 로 진행
    io.fonts.add_font_default()


def _save_screenshot(window, path: str) -> None:
    """현재 프레임버퍼를 PNG 로 저장 (검증용)."""
    w, h = glfw.get_framebuffer_size(window)
    data = GL.glReadPixels(0, 0, w, h, GL.GL_RGB, GL.GL_UNSIGNED_BYTE)
    from PIL import Image
    img = Image.frombytes("RGB", (w, h), data).transpose(Image.FLIP_TOP_BOTTOM)
    img.save(path)


def run(max_frames: int | None = None, screenshot: str | None = None, on_app=None) -> int:
    """창을 띄우고 메인 루프를 돈다.

    max_frames: 테스트용. 지정하면 그 프레임 수 후 자동 종료.
    screenshot:  테스트용. 종료 직전 프레임을 PNG 로 저장.
    on_app:      테스트용. 앱 객체 생성 직후 호출되는 콜백 (팝업 강제 열기 등).
    """
    if not glfw.init():
        print("GLFW 초기화 실패", file=sys.stderr)
        return 1

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL.GL_TRUE)

    window = glfw.create_window(WINDOW_SIZE[0], WINDOW_SIZE[1], WINDOW_TITLE, None, None)
    if not window:
        glfw.terminate()
        print("GLFW 창 생성 실패", file=sys.stderr)
        return 1
    glfw.make_context_current(window)
    glfw.swap_interval(1)

    imgui.create_context()
    io = imgui.get_io()
    io.config_flags |= imgui.ConfigFlags_.nav_enable_keyboard
    _load_korean_font(io)
    imgui.style_colors_dark()
    style = imgui.get_style()
    style.window_rounding = 6.0
    style.frame_rounding = 4.0

    renderer = GlfwRenderer(window)
    app = CapitalApp()
    if on_app is not None:
        on_app(app)

    frame = 0
    try:
        while not glfw.window_should_close(window):
            glfw.poll_events()
            renderer.process_inputs()

            imgui.new_frame()
            app.draw()
            imgui.render()

            w, h = glfw.get_framebuffer_size(window)
            GL.glViewport(0, 0, w, h)
            GL.glClearColor(0.10, 0.10, 0.12, 1.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            renderer.render(imgui.get_draw_data())

            if screenshot and max_frames and frame == max_frames - 1:
                _save_screenshot(window, screenshot)

            glfw.swap_buffers(window)
            frame += 1
            if max_frames is not None and frame >= max_frames:
                break
    finally:
        renderer.shutdown()
        imgui.destroy_context()
        glfw.terminate()
    return 0
