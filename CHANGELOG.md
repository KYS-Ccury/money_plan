# Changelog / 바뀐 것

All notable changes are recorded here, newest first. Each release is written
twice: **English** first, **한국어** second.

The version lives in `capital_calc/__init__.py` (`__version__`) and is shown next
to the app title. Bump the **minor** digit when behaviour is added, the **patch**
digit when only bugs are fixed, and add a section here in the same commit —
`tests/test_backend.py::test_version_and_changelog_agree` fails if the two drift
apart.

판 번호는 `capital_calc/__init__.py` 의 `__version__` 이고 앱 제목 옆에 보입니다.
기능이 늘면 가운데 자리, 버그만 고치면 끝자리를 올리고 **같은 커밋에서** 이 문서에
한 칸을 더합니다 — 어긋나면 위 테스트가 깨집니다.

---

## 0.22.0 — 2026-11-25

### Added

- **기간 can be typed now.** The control's own comment said it: "직접 치는 칸은
  없고". Reaching 18개월 meant clicking ＋ fourteen times, because the only
  destinations were the five preset buttons (6개월/1년/2년/3년/5년) and a
  one-month step. That was tolerable while 기간 only set the end date; it is
  not now that the same number also drives 미래 보기 and the 비중 donut.
  The read-only `기간 N개월` label is replaced by a `TextField` (objectName
  `monthsField`) in that same spot — the grid row holds four controls side by
  side, so there was no width for it in the button row, and putting it where
  the number was already read keeps the eye still. ↑/↓ step a month inside the
  field and PageUp/PageDown step a year.
- `3개월` joins the preset buttons. Short plans had no button at all.
- Past 12 months the row reads the span back in years — `18` shows
  `· 1년 6개월` next to it, `36` shows `· 3년`.

### Fixed

- The 기간 input is capped at **600개월 (50년)**. `Backend._set_months()` only
  clamps at 0, and every month added makes the plan re-walk its items, so a
  slipped keystroke of `99999` would have frozen the window. The ＋ button
  disables at the cap, and `IntValidator` refuses the keystroke.
- Emptying the field no longer throws. `parseInt("")` is `NaN`, and the old
  path would have reached `Backend._set_months()` → `int(nan)` → `ValueError`;
  `periodBox.commit()` now catches `NaN` and puts the current value back.

### 더한 것

- **기간을 직접 칠 수 있습니다.** 그 칸 주석에 "직접 치는 칸은 없고" 라고 적혀
  있었습니다. 18개월로 가려면 ＋ 를 **열네 번** 눌러야 했습니다 — 갈 수 있는
  곳이 단추 다섯(6개월·1년·2년·3년·5년)과 한 달씩뿐이었으니까요. 기간이
  종료일만 정할 때는 견딜 만했지만, 이제 같은 숫자가 **미래 보기와 비중 도넛**
  까지 움직입니다. 읽기만 하던 `기간 N개월` 글씨 자리에 입력칸
  (objectName `monthsField`)을 앉혔습니다 — 이 칸은 넷이 한 줄에 서는 그리드
  안이라 단추 줄에 끼울 폭이 없었고, 읽던 숫자 자리에 두면 눈이 덜 움직입니다.
  칸 안에서 ↑↓ 는 한 달, PageUp/PageDown 은 한 해씩 갑니다.
- 단추에 `3개월` 을 더했습니다. 짧은 계획은 누를 단추가 아예 없었습니다.
- 12개월이 넘으면 몇 년 몇 달인지 옆에 읽어 줍니다 — `18` 이면 `· 1년 6개월`,
  `36` 이면 `· 3년`.

### 고친 것

- 기간 입력을 **600개월(50년)** 에서 끊습니다. `Backend._set_months()` 는 0 에서만
  막고, 기간이 길어지면 달마다 항목을 다시 훑으므로 손이 미끄러져 `99999` 가
  들어가면 창이 그 자리에서 멈췄을 것입니다. ＋ 단추는 끝에서 꺼지고,
  `IntValidator` 가 그 글쇠를 아예 안 받습니다.
- 칸을 비워도 터지지 않습니다. `parseInt("")` 는 `NaN` 이고, 그대로 가면
  `Backend._set_months()` 의 `int(nan)` 에서 `ValueError` 가 납니다.
  `periodBox.commit()` 이 `NaN` 을 막고 쓰던 값을 되비칩니다.

---

## 0.21.0 — 2026-11-25

### Changed

- **미래 보기 is now tied to the 기간 at the top; its own month chips are gone.**
  The screen had two places that answered "how many months ahead?". The header
  owns one (`기간 n개월` with ＋/− and the 6개월/1년/2년/3년/5년 buttons), and
  the hero number, the 요약 card and the trend chart all read `backend.months`
  from it. `ItemListPane` owned the other — a `언제와 견줄까요` row of chips
  over `futureSteps: [1, 2, 3, 6, 12, 24]` writing `futureMonths` — so the item
  rows could sit at 1년 뒤 while the big number above them said 4개월 후.
  `futureMonths` is now `readonly property int futureMonths: backend.months`,
  the chip `Flow` and the `futureMonthsPicked(int)` signal are deleted, and so
  are the `futureMonths` properties that `Main.qml` and `ItemWindow.qml` held
  to carry the picked value between pane and window. `pieCard.atMonth` reads
  `backend.months` directly.
- A line next to the 미래 보기 switch says where the month lives now —
  `위 n개월 기간과 견줍니다 · 바꾸려면 위쪽 ＋ / − 를 누르세요` — because the
  control that used to be right there is no longer there.
- `ItemListPane.futureLabel()` used to special-case only 12 and 24, since the
  chips could only produce the six values in `futureSteps`. Any number can
  arrive now, so it reads a multiple of 12 as 년 (`3년 뒤`), 0 or less as 오늘,
  and anything else as 개월.
- The detached 항목 목록 window keeps its own **on/off** for 미래 보기 but no
  longer its own month, so the two windows always compare against the same date.

### 바뀐 것

- **미래 보기가 위쪽 `기간` 에 묶였습니다. 따로 있던 시점 칩 줄은 없앴습니다.**
  한 화면에 "몇 개월 뒤를 볼까" 를 정하는 자리가 둘이었습니다. 위에는
  `기간 n개월` 과 ＋/−, 6개월·1년·2년·3년·5년 단추가 있고 맨 위 큰 숫자·요약
  카드·추이 그래프가 모두 그 `backend.months` 를 봅니다. 그런데 항목 목록 안에는
  `언제와 견줄까요` 칩(`futureSteps: [1, 2, 3, 6, 12, 24]`)이 따로 서서
  `futureMonths` 를 저 혼자 썼습니다 — **큰 숫자는 4개월 후라는데 목록은 1년 뒤를
  보여 주는** 일이 생겼습니다. 이제 `readonly property int futureMonths:
  backend.months` 한 줄이고, 칩 `Flow` 와 `futureMonthsPicked(int)` 신호,
  그 값을 창끼리 주고받으려고 `Main.qml`·`ItemWindow.qml` 에 두었던
  `futureMonths` 까지 다 걷어냈습니다. `pieCard.atMonth` 도 `backend.months` 를
  바로 읽습니다.
- 미래 보기 스위치 옆에 시점이 어디 있는지 적습니다 —
  `위 n개월 기간과 견줍니다 · 바꾸려면 위쪽 ＋ / − 를 누르세요`. 바로 그 자리에
  있던 조절 칸이 없어졌으니 어디로 갔는지는 알려 줘야 합니다.
- `ItemListPane.futureLabel()` 은 칩이 내놓는 여섯 값만 들어오던 때라 12·24 만
  따로 봤습니다. 이제 아무 수나 들어오므로 **12 의 배수는 년**(`3년 뒤`),
  0 이하는 `오늘`, 나머지는 개월로 읽습니다.
- 떼어 낸 항목 목록 창은 미래 보기를 **켜고 끄는 것만** 따로 쥡니다. 달은 같으니
  두 창이 늘 같은 날짜와 견줍니다.

---

## 0.20.0 — 2026-11-25

### Added

- **The 비중 donut now follows the 미래 보기 month.** It was pinned to today:
  `export_excel.composition(plan)` only ever read `capital_at(0, basis)`,
  `monthly_cost_at(0, basis)` and `monthly_income_at(0, basis)`, so picking
  "2년 뒤" in the item list changed the rows and the summary band but left the
  donut showing today's mix — a 적금 that had already matured still held a
  slice of 월 지출. `composition()` takes an `m` (default 0, which is what the
  Excel 비중 sheet keeps using), and `Backend.compositionOf()` /
  `compositionTotal()` take it too. They carry a **single** `@Slot(str, int, …)`
  signature rather than a stacked pair: Python callers that pass one argument
  (the Excel 비중 sheet, the existing tests) still get `m = 0` from the default,
  and QML always passes both, so an overload would only add a way for the
  second argument to be dropped.
  `tests/test_backend.py::test_composition_slot_takes_the_month` pins the
  pass-through — an income that starts 5개월 뒤 is absent at `m = 0` and present
  at `m = 12`, and `monthText()` reads 2027년 1월 / 2028년 1월.
- The month chosen in 미래 보기 is now held by the **window**, not the pane.
  `ItemListPane.futureMonths` used to be set in place by the chip's
  `onClicked`, which is invisible outside the pane; it now emits
  `futureMonthsPicked(int)` and the window writes the value back, the same way
  `futureOpen` / `futureToggled` already worked. `Main.qml` gained
  `property int futureMonths: 3`, and `ItemWindow.qml` keeps its own, so the
  detached window still has a future view of its own.
- The 비중 card's header shows which month it is drawing (`2029년 1월 기준`,
  via the new `Backend.monthText(m)` slot), the donut's centre label carries
  `(n개월 뒤)`, and a line appears when nothing falls into that group at that
  month. 목표 구성 is deliberately left alone — it draws the whole horizon
  including money still to come in, so a single month means nothing there; its
  badge reads 기간 전체.
- `tests/test_scenario.py::test_composition_follows_the_month` pins all of it:
  the 대출 이자 appearing at 입주, the 적금 dropping out of 월 지출 at maturity
  while its balance stays in 보유 자금, 꺼 둔 항목 staying out at every month,
  the slices summing to `Plan.monthly_cost_at(m)` / `monthly_income_at(m)`, and
  a negative `m` falling back to today.

### 더한 것

- **비중 도넛이 미래 보기 시점을 따라갑니다.** 전에는 늘 오늘이었습니다 —
  `export_excel.composition(plan)` 이 `capital_at(0, basis)` 처럼 0개월만
  읽었습니다. 그래서 항목 목록에서 "2년 뒤" 를 골라도 줄과 요약 띠만 바뀌고
  도넛은 그대로였고, **이미 만기가 지난 적금이 여전히 월 지출 한 조각**으로
  남아 있었습니다. `composition()` 이 `m` 을 받습니다(기본 0 — 엑셀 비중 시트는
  그대로 오늘을 씁니다). `Backend.compositionOf()`·`compositionTotal()` 도
  `@Slot(str, int, …)` **하나만** 답니다. 겹쳐 달면 두 번째 인자가 버려질 길만
  하나 더 생기고, 파이썬에서 인자 하나로 부르는 자리(엑셀 비중 시트, 기존
  테스트)는 기본값이 받으며 QML 은 늘 둘을 줍니다.
  `tests/test_backend.py::test_composition_slot_takes_the_month` 가 그 길을
  못 박습니다 — 5개월 뒤 시작하는 수입이 `m = 0` 에는 없고 `m = 12` 에는 있고,
  `monthText()` 가 2027년 1월 / 2028년 1월 을 돌려줍니다.
- 미래 보기로 고른 시점을 이제 **창이 쥡니다.** `ItemListPane.futureMonths` 를
  칩의 `onClicked` 가 그 자리에서 바꾸고 있어서 바깥에서는 알 길이 없었습니다.
  이제 `futureMonthsPicked(int)` 를 쏘고 창이 되돌려 씁니다 — `futureOpen` /
  `futureToggled` 과 같은 결입니다. `Main.qml` 에 `property int futureMonths: 3`
  을 두었고, `ItemWindow.qml` 은 제 것을 따로 쥡니다(떼어 낸 창은 제 시점).
- 비중 카드 머리에 **언제 기준인지**(`2029년 1월 기준`, 새 `Backend.monthText(m)`)
  가 서고, 도넛 가운데에 `(n개월 뒤)` 가 붙고, 그 시점에 그 묶음으로 잡히는
  항목이 하나도 없으면 왜 비었는지 적습니다. **목표 구성은 일부러 그대로** 둡니다
  — 앞으로 들어올 돈까지 포함한 기간 전체 그림이라 한 달을 집어 봐야 뜻이
  없습니다. 그 칩에서는 머리에 `기간 전체` 라고 적습니다.
- `tests/test_scenario.py::test_composition_follows_the_month` 가 못 박습니다 —
  입주 달에 대출 이자가 들어오는 것, 만기 달부터 적금이 월 지출에서 빠지면서도
  모은 돈은 보유 자금에 남는 것, 꺼 둔 항목이 어느 시점에도 안 끼는 것, 조각의
  합이 `Plan.monthly_cost_at(m)`·`monthly_income_at(m)` 과 같은 것, 음수 `m` 은
  오늘로 보는 것.

---

## 0.19.1 — 2026-11-25

### Fixed

- **An Excel round trip lost the repeat cycle and the page of every item.**
  A new end-to-end scenario test (`tests/test_scenario.py`) caught it: the 항목
  sheet never had a 되풀이 or 장 column, so `Item.every` (a 자동차세 that repeats
  every 12 months) came back as a one-off and every item landed on the first
  page. `export_excel.export_plan()` now writes `되풀이` and `장(페이지)` as
  columns 22-23 — appended, so the column numbers the existing export tests
  assert on do not move. `import_plan.HEADER_KEYS` gained a `page` entry
  (matched only on long words — `페이지`/`시트`/`page`/`sheet`, never the single
  letter 장, which hides inside other headers), `_row_dict()` carries `page`,
  and `Backend._apply_plan_import()` passes it to the new `Item`.
- `tests/test_model.py::test_planned_flows` has been failing since 월세 칸 was
  removed from 주거 (`baf66cf`): it still built a 반전세 with `monthly=300_000`
  and expected that rent in `planned_out_at()`, which no longer counts the
  field. The test now builds the item through `split_housing_rent()`, the way a
  loaded file does, and asserts the field is zeroed.

### Added

- **`tests/test_scenario.py` — one plan that exercises the features together.**
  Per-feature tests live in `test_model.py`; this file checks that the features
  do not break each other inside one plan: 전세 보증금 as an asset with a return
  date, a 전세자금 대출 with bullet repayment, three savings (with maturity,
  locked, and with no maturity), a yearly 자동차세, a rising salary and a
  switched-off item. 13 tests covering the month grid, the switched-off item
  being absent from every number, 보증금 not jolting 순 자본 on the way in or
  out, `spendable == net - tied`, the shortfall warning firing while 순 자본
  still looks healthy, the bullet repayment staying out of the monthly average,
  and both round trips (JSON and Excel). It is Qt-free, so it also runs as a
  plain script: `py -3.12 tests/test_scenario.py`.

### 고친 것

- **엑셀로 내보내 다시 읽으면 항목의 되풀이 주기와 장이 사라졌다.** 새로 쓴 종합
  시나리오 테스트(`tests/test_scenario.py`)가 잡아냈다. `항목` 시트에 `되풀이`·`장`
  칸이 애초에 없어서, 열두 달마다 되풀이되는 자동차세가 한 번만 나가는 지출로
  돌아오고 모든 항목이 첫 장으로 몰렸다. `export_excel.export_plan()` 이 이제
  `되풀이`·`장(페이지)` 를 22~23열에 적는다 — **뒤에 붙였다.** 앞에 끼우면 열
  번호를 보는 기존 내보내기 테스트가 깨진다. `import_plan.HEADER_KEYS` 에 `page`
  짝을 더했고(`페이지`·`시트`·`page`·`sheet` 처럼 **긴 낱말로만** 본다 — '장' 한
  글자는 다른 머리글 안에 숨어 있어 잘못 잡힌다), `_row_dict()` 가 `page` 를 싣고,
  `Backend._apply_plan_import()` 이 그것을 새 `Item` 에 넘긴다.
- `tests/test_model.py::test_planned_flows` 는 주거에서 월세 칸을 없앤
  `baf66cf` 때부터 깨져 있었다. 반전세를 `monthly=300_000` 으로 세우고 그 월세가
  `planned_out_at()` 에 들기를 기대했는데, 이제 그 칸은 계산에 쓰이지 않는다.
  파일을 불러올 때와 같게 `split_housing_rent()` 를 거쳐 세우고, 칸이 0 으로
  비워지는 것까지 확인하도록 고쳤다.

### 더한 것

- **`tests/test_scenario.py` — 기능들을 한 계획에 모아 돌리는 시나리오.** 낱개
  기능은 `test_model.py` 가 본다. 이 파일은 **기능들이 서로를 망치지 않는지**를
  본다: 반환일 있는 전세 보증금을 자산으로 켜 두고, 만기 일시 상환 전세자금 대출을
  끼고, 적금 셋(만기 있는 것·묶어 둔 것·만기 없는 것)을 돌리고, 해마다 되풀이되는
  자동차세와 오르는 월급, 꺼 둔 항목을 섞는다. 테스트 13개로 눈금, 꺼 둔 항목이
  어느 숫자에도 없는지, 보증금이 들고 나는 달에 순 자본이 튀지 않는지,
  `쓸 수 있는 돈 = 순 자본 − 묶인 돈`, 순 자본은 멀쩡한데도 부족 경고가 뜨는지,
  만기 일시 상환이 월 평균에 안 녹는지, 그리고 왕복 둘(JSON·엑셀)을 본다.
  Qt 를 안 쓰므로 그냥 스크립트로도 돈다: `py -3.12 tests/test_scenario.py`.

---

## 0.19.0 — 2026-11-25

### Added

- **A saving with no maturity date is now flagged.** 적금 payments stop
  correctly once the end date arrives — `Item.monthly_cost_at()` pays only while
  `is_active(m)`, i.e. `m < end_m`, so the maturity month itself costs nothing
  and the balance simply sits there. But leaving 종료일 **empty** makes
  `active_range()` return `(start, None)`, so the payment never stops: it is
  charged as 월 지출 for the whole plan and 순 자본 comes out lower than it
  really is. "Blank means forever" is right for a loan or rent, and almost
  always a mistake for a saving, and nothing said so.
  New `Item.open_ended_saving()` (Qt-free, date-independent — it reads the empty
  field, not the calendar). `ItemListModel` gained `WarnRole` (`warn`,
  UserRole + 34), a general slot for "this setting will skew your numbers";
  the item row draws a yellow **⚠** next to the name with the reason on hover,
  and the small print under the name gains `⚠ 만기(종료일) 없음 — 계속 납입합니다`.
  `ItemDialog` turns the 적용 기간 hint yellow while a 적금 has no end date and
  says what it will cost. `categoryInfo()` gained `isSaving` so the dialog does
  not have to compare category names.

### 더한 것

- **만기(종료일)를 안 넣은 적금에 경고를 붙였다.** 적금 납입이 만기에 멈추는 것
  자체는 맞게 돌아간다 — `Item.monthly_cost_at()` 은 `is_active(m)`, 곧
  `m < end_m` 인 동안만 납입액을 내놓으므로 **만기 달부터 월 지출이 0** 이고 쌓인
  잔액은 그대로 남는다. 문제는 종료일을 **비웠을 때**다. `active_range()` 가
  `(시작, None)` 을 돌려주어 멈출 곳을 모르니 납입이 **계획 기간 내내** 월 지출로
  깔리고, 그만큼 순 자본이 실제보다 낮게 나온다. '비우면 계속' 은 대출·월세에서는
  맞는 뜻이지만 적금에서는 거의 늘 실수인데, 아무 말도 해 주지 않았다.
  `Item.open_ended_saving()` 을 더했다 (Qt 없이 도는 값이고, 달력이 아니라 빈 칸을
  보므로 basis 가 필요 없다). `ItemListModel` 에 `WarnRole`(`warn`,
  UserRole + 34) — '이대로 두면 숫자가 틀어지는 설정' 을 모아 두는 자리 — 을 더해,
  목록 줄이 이름 옆에 노란 **⚠** 를 세우고 올려 두면 까닭을 띄운다. 이름 아래 작은
  글씨에도 `⚠ 만기(종료일) 없음 — 계속 납입합니다` 가 붙는다. `ItemDialog` 은 적금에
  종료일이 비어 있는 동안 `적용 기간` 안내를 노랗게 바꾸고 무슨 일이 벌어지는지
  적는다. 분류 이름을 글자로 비교하지 않도록 `categoryInfo()` 에 `isSaving` 을 더했다.

---

## 0.18.0 — 2026-11-25

### Added

- **미래 보기 now carries its own summary band, inside the item list.**
  Picking a month did change the rows, but there was no way to tell from the
  pop-out window: the only figures that moved were in the main window's 요약
  card, and that card follows the plan's whole horizon, not the chip. Worse,
  the pop-out window has no 요약 card at all, so the month chips looked inert.
  `ItemListPane` now reads `backend.monthSnapshot(0)` as well (`nowSnap`) and
  draws a band under the chips with **보유 자금 · 묶인 돈 · 쓸 수 있는 돈 ·
  순 자본** for that month, each with the difference from today underneath
  (`SnapFigure`, a root-scope inline component). 쓸 수 있는 돈 turns red when
  negative; 묶인 돈 is marked `neutral` so its change is not coloured as good
  or bad. The band lives in the pane, so it shows in both windows.

### Fixed

- Nothing about the month chips was broken — `futureMonths` is per-pane and the
  pop-out window has always applied it — but with no figure of its own in that
  window the UI gave no feedback, which amounts to the same thing.

### 더한 것

- **미래 보기가 제 요약 띠를 목록 안에 들고 있게 되었다.** 시점을 누르면 줄 값은
  분명히 바뀌었는데, 떼어 낸 창에서는 그걸 알 길이 없었다 — 함께 움직이는 숫자가
  본 창 `요약` 카드뿐이었고, 그 카드는 계획 전체 기간을 보는 것이어서 칩을 따라가지
  않는다. 게다가 떼어 낸 창에는 그 카드조차 없으니 칩이 안 먹는 것처럼 보였다.
  이제 `ItemListPane` 이 `backend.monthSnapshot(0)` 도 읽어 두고(`nowSnap`), 칩
  아래에 그 달의 **보유 자금 · 묶인 돈 · 쓸 수 있는 돈 · 순 자본** 을 띠로 세운다.
  각 숫자 아래에 오늘 대비 차이가 붙는다(`SnapFigure` — 뿌리에 둔 inline
  component). 쓸 수 있는 돈이 마이너스면 빨갛고, 묶인 돈은 `neutral` 로 두어
  늘어난 것을 좋다/나쁘다로 물들이지 않는다. 띠가 목록 안에 있으므로 본 창과
  떼어 낸 창 양쪽에 똑같이 선다.

### 고친 것

- 칩 자체는 고장난 적이 없다 — `futureMonths` 는 목록 판마다 따로 있고, 떼어 낸
  창도 늘 그 값을 썼다. 다만 그 창에 함께 움직이는 숫자가 없어 아무 대답이 없었고,
  쓰는 사람에게는 그게 안 먹는 것과 다르지 않았다.

---

## 0.17.0 — 2026-11-24

### Changed

- **미래 보기 is now two extra columns on the same row, not a second list.**
  The point was always to see *how much each item changes*, and two lists side
  by side could not do that: their rows never lined up (each has its own
  category headers, collapsing and scrolling), so the eye had to hunt across
  the gap, and the width split left both halves cramped. Switching 미래 보기 on
  now adds `그때 금액` and `달라지는 만큼` to every row of the one list, with a
  chip row above it to pick the month (1·2·3·6·12·24개월 뒤) and that month's
  보유 자금 / 쓸 수 있는 돈 beside the chips. Rows that have not happened yet
  (a deposit not paid) are dimmed in place. The 연이율 column folds away while
  it is on, since it is also in the small print under each name.
- `ItemListPane` reads `backend.itemsAt(m)` once per month change and each row
  looks itself up by its **source row**, so a row shows the same item on both
  sides even when 분류별로 묶기 reorders the list.
- `qml/FutureList.qml` is deleted — the separate panel it drew no longer
  exists, and the window no longer splits in two to hold it.

### 바뀐 것

- **미래 보기가 '목록 한 벌 더' 에서 '같은 줄의 칸 두 개' 가 되었다.** 애초에
  보고 싶었던 것은 **항목마다 얼마나 달라지는가** 인데, 목록을 둘로 세우면 그걸
  볼 수가 없었다 — 두 목록은 분류 머리글·접힘·스크롤이 각자 놀아서 줄이 서로
  맞지 않으니 눈이 건너편을 더듬어야 했고, 폭까지 반으로 갈라 양쪽 다 좁았다.
  이제 미래 보기를 켜면 **한 목록의 줄마다** `그때 금액` 과 `달라지는 만큼` 이
  붙는다. 위에는 시점 칩(1·2·3·6·12·24개월 뒤)과 그 달의 보유 자금·쓸 수 있는
  돈이 함께 선다. 아직 일어나지 않은 줄(안 낸 보증금)은 그 자리에서 흐려진다.
  켜 둔 동안 `연이율` 칸은 접는다 — 이름 아래 작은 글씨에도 있는 값이다.
- `ItemListPane` 은 시점이 바뀔 때 `backend.itemsAt(m)` 을 한 번 읽고, 줄마다
  **원본 줄 번호**로 제 값을 찾는다. 그래서 분류별로 묶어 순서가 달라져도 한
  줄의 양쪽이 같은 항목이다.
- `qml/FutureList.qml` 은 지웠다 — 그리던 칸이 없어졌고, 창을 둘로 가를 일도
  없어졌다.

---

## 0.16.2 — 2026-11-24

### Changed

- **The three metric cards under the hero are gone.** 보유 자금, 월 지출 and
  월 수입 sat there *and* in the 요약 card on the right, so the same figures
  were read twice and the list lost 100px of height for nothing. The hero card
  keeps the one number the summary does not lead with — N개월 후 순 자본 and
  the goal bar. `HeroSummary.qml` lost its `Metric` inline component with them
  (186 → 111 lines).

### 바뀐 것

- **히어로 아래 숫자 카드 셋을 뺐다.** 보유 자금·월 지출·월 수입이 거기에도,
  오른쪽 `요약` 카드에도 있어서 같은 숫자를 두 번 읽게 했다. 그 값을 두느라
  목록이 100px 쯤 낮아지기까지 했다. 히어로 카드에는 요약이 맨 앞에 두지 않는
  값 하나 — `N개월 후 순 자본` 과 목표 막대 — 만 남겼다. 함께 쓰이지 않게 된
  `Metric` 인라인 부품도 지웠다 (`HeroSummary.qml` 186 → 111줄).

---

## 0.16.1 — 2026-11-24

### Fixed

- **"그때 목록" renamed to "미래 목록".** The panel shows the same items at a
  month in the future, and "그때" (then) named no particular time, so it said
  nothing. The switch now reads `미래 보기` and the panel title
  `미래 목록 · 3개월 뒤`.
- **Turning 미래 보기 on pushed its own switch off the row, so it could not be
  turned off again.** The options row was a `RowLayout`, which does not wrap;
  opening the second list halves the pane's width and the switch at the right
  end simply went past the edge — the same failure the toolbar had. It is a
  `Flow` now, and each label+switch pair is wrapped in a `Row` so a wrap never
  separates them.
- **Dragging the grip did nothing.** `DragHandler.activeTranslation` and its
  `centroid` reset the moment the drag ends, and the check read them in
  `onActiveChanged` — *after* the release — so the distance was always 0 and
  never passed the threshold. The grip now records the furthest distance and
  the hand's screen position **while** the drag is live (`onCentroidChanged`),
  and uses those on release. The threshold dropped 60 → 40px, the grip grew to
  26x28 with a hover/drag highlight so it is visible and easy to catch, and a
  drop position of 0 (which means nothing was recorded) now leaves the window
  at its remembered place instead of parking it in the screen corner.

### 고친 것

- **'그때 목록' 이라는 이름을 '미래 목록' 으로.** 그 칸은 같은 항목을 몇 개월 뒤
  값으로 보여 주는 것인데, '그때' 는 어느 때인지 가리키는 말이 없어 뜻이 안
  섰다. 켜는 스위치는 `미래 보기`, 칸 제목은 `미래 목록 · 3개월 뒤` 다.
- **미래 보기를 켜면 그 스위치가 줄 밖으로 밀려 나가 다시 끌 수 없던 것.**
  보기 옵션 줄이 `RowLayout` 이라 줄바꿈을 모른다. 미래 목록을 켜면 목록 칸이
  반으로 좁아지는데, 그러면 오른쪽 끝에 있던 그 스위치가 밀려 나가 보이지
  않았다 (상단 단추 줄에서 겪은 것과 같은 일이다). 이제 `Flow` 라서 좁아지면
  아래로 접히고, '이름 + 스위치' 짝은 `Row` 로 묶어 두어 접혀도 따로 떨어지지
  않는다.
- **손잡이를 끌어도 아무 일이 없던 것.** `DragHandler` 의 `activeTranslation`
  과 `centroid` 는 **손을 떼는 순간 0 으로 돌아간다.** 그런데 거리를 재는 코드가
  `onActiveChanged`, 곧 손을 뗀 **뒤에** 그 값을 읽고 있었다 — 그래서 늘 '0px
  움직였다' 가 되어 문턱을 넘지 못했다. 이제 **끄는 동안**
  (`onCentroidChanged`) 가장 멀리 간 거리와 그때의 화면 좌표를 적어 두고, 뗄 때
  그것을 쓴다. 문턱은 60 → 40px 로 낮추고, 손잡이는 26x28 로 키워 손이 닿거나
  끄는 동안 바탕색이 들어오게 했다 (보이지 않으면 쥘 수도 없다). 좌표가 0 이면
  (아무것도 못 적은 경우) 창을 화면 구석에 처박지 않고 지난번 자리에 띄운다.

---

## 0.16.0 — 2026-11-24

### Added

- **Drag the list out of the window.** A `⠿` grip sits at the left of the
  list's options row; grab it, pull about 60px, and the list leaves for its own
  window — which opens centred on where the hand let go, clamped to the screen
  so it can never land off-view. A `DragHandler` with `target: null` is doing
  the measuring: it drags nothing, it only reports `activeTranslation` and the
  centroid, which `Item.mapToGlobal()` turns into a screen position for the new
  window. Below the 60px threshold nothing happens, so a mis-click does not
  tear the window apart. The button and **Ctrl+Shift+1** still work, and the
  grip hides in the detached window (it is already out).
- **The first page can be renamed too.** It used to be fixed at `기본` because
  its items identify it by storing an **empty** page, and renaming looked like
  it would mean rewriting every one of them. `Plan.page_title` holds the first
  page's display name on its own instead, so renaming swaps a label and touches
  no item at all — `Plan.first_page()` resolves the name everywhere the
  constant used to be hardcoded. It still cannot be **deleted**: deleting any
  other page moves its items to the first one, so one page must always exist.

### 더한 것

- **목록을 끌어서 떼어 낸다.** 목록의 보기 옵션 줄 왼쪽에 `⠿` 손잡이가 있다.
  쥐고 60px 쯤 끌면 목록이 제 창으로 나가고, 그 창은 **손을 놓은 자리**에 뜬다
  (화면 밖으로는 못 나가게 가둬 둔다). 재는 일은 `target: null` 인
  `DragHandler` 가 한다 — 아무것도 끌지 않고 `activeTranslation` 과 centroid 만
  알려 주며, 그것을 `Item.mapToGlobal()` 이 화면 좌표로 바꿔 새 창 자리로
  쓴다. 60px 이 안 되면 아무 일도 없으니, 잘못 눌렀다고 창이 뜯겨 나가지
  않는다. 단추와 **Ctrl+Shift+1** 도 그대로 쓸 수 있고, 떼어 낸 창에서는
  손잡이를 숨긴다 (이미 나와 있으므로).
- **첫 장도 이름을 바꿀 수 있다.** 지금까지 `기본` 에 못 박혀 있던 까닭은, 첫
  장의 항목이 page 를 **빈 값**으로 들고 그 장을 가리키기 때문이다 — 이름을
  바꾸려면 항목을 전부 고쳐 적어야 하는 것처럼 보였다. 그래서 첫 장의 이름만
  `Plan.page_title` 이 따로 들고 있게 했다. 이제 이름을 바꿔도 **항목은 하나도
  건드리지 않는다** — 이름표만 갈아 끼우는 셈이고, 상수를 박아 두었던 자리는
  `Plan.first_page()` 가 대신한다. 다만 **지울 수는** 없다. 다른 장을 지우면 그
  항목이 첫 장으로 오므로, 장 하나는 늘 있어야 한다.

---

## 0.15.1 — 2026-11-24

### Fixed

- **Both lists in the main window left neither of them usable.** 오늘 목록,
  미래 목록 and the 430px summary column were sharing one row, so each list got
  roughly a third of the width — narrower than the row's own 590px minimum,
  which is what the `roomy` breakpoint then folded away. The pop-out window now
  carries **both** lists side by side (its own `futureOpen`, its own switch),
  and while the list is popped out the main window hides its 미래 목록 instead
  of leaving it beside the placeholder card — alone it has nothing to compare
  against. Turning the second list on in that window widens it to 1280px once,
  only when it is narrower than that and only at the moment it is switched on,
  so a window the user deliberately shrank is not resized behind their back.

### 고친 것

- **본 창에서 두 목록을 함께 띄우면 양쪽 다 못 쓰게 좁아지던 것.** 오늘 목록과
  미래 목록, 그리고 430px 짜리 요약 칸이 한 줄을 나눠 가져서 목록 하나가 폭의
  3분의 1쯤밖에 못 받았다 — 줄 하나가 필요로 하는 590px 보다 좁아서, `roomy`
  눈금이 연이율 칸과 ▲▼ 를 접어 버리던 그 폭이다. 이제 따로 띄운 창이 **두
  목록을 나란히** 들고 있다(그 창만의 `futureOpen` 과 스위치). 목록을 띄워 둔
  동안 본 창은 미래 목록을 숨긴다 — 안내 카드 옆에 혼자 서 있어 봐야 견줄 짝이
  없기 때문이다. 그 창에서 두 번째 목록을 켜면 창이 1280px 로 한 번 넓어지는데,
  **그보다 좁을 때만, 켜는 그 순간에만** 그렇게 한다 (사람이 일부러 줄여 놓은
  창을 제멋대로 키우지 않는다).

---

## 0.15.0 — 2026-11-24

### Added

- **The item list pops out into its own window.** In the main window the list
  shares the height with the hero, the summary and the chart, so a plan with
  twenty-odd items showed a handful of rows at a time. `항목 목록 따로 띄우기`
  in the sidebar (or **Ctrl+Shift+1**, or the toolbar button on a narrow
  window) moves it to a 1100x760 window of its own; the main window keeps a
  card in its place with `그 창으로 가기` / `본 창으로 되돌리기`, so the layout
  never shows an empty hole.
- To make that possible the whole list — options row, header, `ListView`,
  section headers, page tabs, hint line — moved out of `Main.qml` into
  **`qml/ItemListPane.qml`** (423 lines; `Main.qml` lost 184). The pane now
  owns the dialogs it opens (`ItemDialog`, the delete confirmation) instead of
  reaching for ids in `Main.qml`, which is what lets a second copy live in
  another window and behave identically. `win.itemPane()` returns whichever
  copy is on screen, so `＋ 항목 추가`, Ctrl+N and the test helpers all keep
  working without knowing where the list is — the same shape the ledger
  pop-out already had.
- The window remembers its size, position and whether it was open
  (`Backend.itemWindowState()` / `saveItemWindowState()`, in the window-state
  ini beside the data file), and reopens on the next launch.

### 더한 것

- **항목 목록을 제 창으로 떼어 낼 수 있다.** 본 창 안에서는 목록이 히어로·요약·
  그래프와 세로를 나눠 쓰느라, 항목이 스무 개쯤 되면 한 번에 몇 줄밖에 안 보였다.
  사이드바의 `항목 목록 따로 띄우기`(또는 **Ctrl+Shift+1**, 좁은 창에서는 상단
  단추)로 1100x760 짜리 제 창에 띄운다. 본 창의 그 자리에는 `그 창으로 가기` ·
  `본 창으로 되돌리기` 가 있는 카드가 남아서, 화면에 빈 구멍이 생기지 않는다.
- 그러려고 목록 전체(보기 옵션 줄·머리글·`ListView`·분류 머리글·장 탭·안내 줄)를
  `Main.qml` 에서 **`qml/ItemListPane.qml`**(423줄)로 옮겼다 — `Main.qml` 은
  184줄 줄었다. 이 부품은 제가 여는 팝업(`ItemDialog`, 삭제 확인)을 **직접
  들고 있는다.** `Main.qml` 의 id 를 넘겨다보지 않으므로 다른 창에 한 벌 더
  세워도 똑같이 움직인다. `win.itemPane()` 이 '지금 화면에 있는 그 목록' 을
  돌려주어서 `＋ 항목 추가`·Ctrl+N·테스트 도우미는 목록이 어디 있는지 몰라도
  된다 — 가계부 따로 띄우기와 같은 모양이다.
- 그 창의 크기·자리·띄워 둔 상태는 기억한다
  (`Backend.itemWindowState()` / `saveItemWindowState()`, 데이터 파일 옆 창 상태
  ini). 다음에 켜면 그대로 다시 뜬다.

---

## 0.14.0 — 2026-11-24

### Added

- **The item list is now split into pages, and you make the pages yourself —
  like Excel sheets.** Tabs sit under the list (`qml/PageTabs.qml`): `전체`,
  then one per page, then `＋ 장`. Click to open a page, double-click to
  rename, `✕` to delete, and a new item lands on whichever page is open.
- **A page is a *view* grouping, never a separate plan.** `Item.page` says
  where an item is shown and nothing else: 요약, 그래프, 순 자본 and every
  other number always count **all** pages, which is what keeps pages from
  duplicating scenarios (those compare whole plans). Deleting a page therefore
  moves its items to the first page instead of deleting them —
  `Backend.removePage()` says how many it moved. The filtering lives entirely
  in `GroupedItems.filterAcceptsRow()`, one layer above the model.
- `Plan.pages` stores the page names in order so an **empty** page survives a
  save and reload (items alone cannot prove a page exists), and
  `Plan.page_list()` adds any page an item claims but the list has lost, so an
  older file or a half-finished delete can never hide an item.
  `Plan.items_on(page)` treats the empty string and `기본` as the same first
  page, so nothing has to be migrated.
- New in the backend: `PageRole` (UserRole+33), the `pages` / `pageCounts` /
  `activePage` properties, and the `addPage` / `renamePage` / `removePage` /
  `setItemPage` slots (all undoable). The item dialog gained a `장` picker, and
  `updateItem` deliberately keeps the old page — moving is `setItemPage`'s job,
  so editing an amount never slides an item to another page.

### 더한 것

- **항목 목록을 장(페이지)으로 나눈다. 장은 직접 만든다 — 엑셀 시트처럼.**
  목록 아래에 탭이 선다(`qml/PageTabs.qml`) — `전체`, 장들, `＋ 장`. 클릭하면
  그 장만 보고, 더블클릭은 이름 바꾸기, `✕` 는 삭제다. 새 항목은 **지금 펴 둔
  장**에 들어간다.
- **장은 '보기' 묶음이지 따로 된 계획이 아니다.** `Item.page` 는 그 항목을
  어디에 보여 줄지만 정한다 — 요약·그래프·순 자본을 비롯한 모든 숫자는 늘
  **모든 장**을 함께 센다. 그래야 장이 시나리오(계획 전체를 통째로 견주는
  것)와 역할이 겹치지 않는다. 그래서 장을 지우면 그 항목들은 **지워지지 않고
  첫 장으로 옮겨 간다** — `Backend.removePage()` 가 몇 개를 옮겼는지 알려 준다.
  걸러내는 일은 모델 한 겹 위 `GroupedItems.filterAcceptsRow()` 에서만 한다.
- `Plan.pages` 가 장 이름을 순서대로 들고 있어서 **빈 장**도 저장되고 다시
  열린다(항목만으로는 장이 있다는 것을 알 수 없다). `Plan.page_list()` 는
  목록에 없는데 항목이 쓰고 있는 장을 뒤에 붙여 주므로, 예전 파일이나 지우다 만
  상태에서도 항목이 숨지 않는다. `Plan.items_on(page)` 은 빈 값과 `기본` 을
  같은 첫 장으로 보아, 옮겨 적을 것이 없다.
- 백엔드에 더한 것: `PageRole`(UserRole+33), `pages`·`pageCounts`·`activePage`
  프로퍼티, 그리고 `addPage`·`renamePage`·`removePage`·`setItemPage` 슬롯(모두
  되돌리기 됨). 항목 팝업에 `장` 고르는 칸이 생겼고, `updateItem` 은 일부러
  예전 장을 그대로 둔다 — 옮기는 일은 `setItemPage` 가 하므로, 금액만 고쳤는데
  항목이 다른 장으로 미끄러지는 일이 없다.

---

## 0.13.0 — 2026-11-24

### Added

- **The Figma design is in: light "모아" palette, a left sidebar and a hero
  summary.** The tokens come from the design's own `src/styles.css`, not from
  guesswork — ink `#19251f`, muted `#778079`, green `#145f43`, lime `#cbea6d`,
  orange `#d98456`, paper `#fffefa`, line `#deded6`, page `#f5f3ed`, sidebar
  `#fbfaf6`, active nav `#e9eee5`.
- `Theme.qml` now derives surfaces in **both directions**: on a light base the
  card goes lighter than the page (paper over ivory, as the design does) and
  rows sit slightly below it; on a dark base everything still rises out of the
  background. That is why the same file can hold the old dark look and the new
  light one. New tokens: `sidebar`, `orange`, `lime`, `heroBg`/`heroText`/
  `heroDim`/`heroLabel`, `radiusBig` (20). `radius` moved 12 → 16 and the
  scenario colours became the design's earthy set.
- **`SideBar.qml`** (new) holds what used to crowd the top bar: the app name,
  the 계획/가계부/한눈에 switch, and the scenario list — each scenario a round
  colour badge, its initial, click to switch, double-click to rename, `＋` to
  add. Scenarios now grow **downwards** instead of wrapping the toolbar onto a
  third line. Below 900px the sidebar folds away and the old top-bar switch and
  scenario row reappear (`win.sideBarShown`), so a narrow window never loses a
  way to change screens.
- **`HeroSummary.qml`** (new) puts the numbers that matter at the top of the
  plan screen: a dark-green card with N개월 후 순 자본, the goal progress bar in
  lime, 지금 보유 / 목표 underneath, then three metric cards — 보유 자금
  (with 쓸 수 있는 돈 when a deposit is tied up), 월 지출 (with 월 순수입) and
  월 수입 (with the goal date).
- **Eight colour modes, not just a background picker.** A mode in `Theme.modes`
  carries five colours — `bg`, `accent`, `point`, `inc` (money in), `exp`
  (money out) — and everything else is derived, so adding a mode is one line:
  미색 초록 (the design's own), 흰 종이 쪽빛, 연둣빛 올리브, 모래 팥죽, 밤 남색
  (the old look), 먹색 라임, 숲 녹색, 자줏빛 보라. `accentSoft`, `greenSoft`
  and `redSoft` now come from a `soft(c)` helper that dissolves the colour into
  the background instead of being fixed hexes, and the hero card picks dark or
  light text from its own luminance, so a light accent still reads. Scenario
  line colours start from the mode's palette. `Theme.customBg` keeps the
  "background only" override separate from the mode, and both are saved
  (`Backend.saveAppearance(bg, mode)`), so the next launch restores exactly
  what was chosen. The dialog opens from **설정 · 바탕색** at the foot of the
  sidebar; the `모양` toolbar button survives only for the narrow-window case
  where the sidebar is folded away — buried at the end of a wrapping toolbar,
  nobody could find it.

### Fixed

- **Half the controls vanished on the light background.** `Material.theme` was
  pinned to `Material.Dark` in `Main.qml` and `LedgerWindow.qml`, so every
  Controls item (Button, Switch, ComboBox, TextField, ToolButton) drew its text
  **white** — invisible on ivory. That is why the 기간 buttons (6개월·1년·2년…),
  the ± steppers, the 목표 자본금 field and several toolbar buttons looked
  missing. The theme now follows the background: `Theme.light ? Material.Light
  : Material.Dark`, with `Material.foreground: Theme.text`.
- **Surfaces with a hardcoded dark hex stayed dark.** The category section
  header (`#1a1f33`), the goal progress track and prediction box, the chart's
  horizon chips, the loan date box, the pie's ring and the trend chart's
  backdrop and grid all carried literal colours from the dark-only days; they
  now take `Theme.row` / `greenSoft` / `redSoft` / `cardBorder`.
- **The item list was squeezed to two rows.** `HeroSummary` sat in the same
  `ColumnLayout` with no height cap, so the layout handed it a share of the
  leftover vertical space. It is now `Layout.fillHeight: false` with
  `preferredHeight: implicitHeight`, it is itself shorter (hero 176→128 min,
  number 40→32px, metric cards 128→102), and the list row carries
  `Layout.minimumHeight: 260`.

### 더한 것

- **피그마 시안을 입혔다 — 밝은 '모아' 색, 왼쪽 사이드바, 맨 위 큰 숫자 카드.**
  색은 눈대중이 아니라 시안의 `src/styles.css` 에 적힌 값 그대로다 — 글자
  `#19251f`, 흐린 글자 `#778079`, 초록 `#145f43`, 라임 `#cbea6d`, 주황
  `#d98456`, 종이 `#fffefa`, 선 `#deded6`, 바탕 `#f5f3ed`, 사이드바 `#fbfaf6`,
  고른 메뉴 `#e9eee5`.
- `Theme.qml` 이 면 색을 **양쪽으로** 만든다. 밝은 바탕에서는 카드가 바탕보다
  더 희어지고(미색 위의 종이 — 시안이 그렇다) 줄은 살짝 가라앉으며, 어두운
  바탕에서는 예전처럼 카드·줄이 바탕에서 떠오른다. 그래서 파일 하나가 예전의
  어두운 모습과 새 밝은 모습을 함께 담는다. 새 색이름: `sidebar`, `orange`,
  `lime`, `heroBg`·`heroText`·`heroDim`·`heroLabel`, `radiusBig`(20).
  `radius` 는 12 → 16, 시나리오 색도 시안의 흙빛 묶음으로 바꿨다.
- **`SideBar.qml`**(새 파일)이 상단 바에 몰려 있던 것을 가져갔다 — 앱 이름,
  계획·가계부·한눈에 전환, 그리고 시나리오 목록(색 동그라미와 첫 글자, 클릭은
  전환, 더블클릭은 이름 바꾸기, `＋` 는 추가). 시나리오가 늘면 이제 단추 줄이
  세 줄로 번지는 대신 **아래로** 늘어난다. 창이 900px 보다 좁으면 사이드바가
  접히고 예전 상단 전환 단추와 시나리오 줄이 다시 선다(`win.sideBarShown`) —
  좁다고 화면을 못 바꾸게 되면 안 되기 때문이다.
- **`HeroSummary.qml`**(새 파일)이 계획 화면 맨 위에 중요한 숫자를 세운다.
  짙은 초록 카드에 `N개월 후 순 자본`, 라임색 목표 진행 막대, 그 아래 지금
  보유·목표. 이어서 숫자 카드 셋 — 보유 자금(보증금이 묶여 있으면 쓸 수 있는
  돈까지), 월 지출(월 순수입까지), 월 수입(목표 달성 시점까지).
- **바탕색 고르기가 아니라 색 모드 여덟 가지.** `Theme.modes` 의 한 모드는 색
  다섯 개만 들고 있다 — 바탕 `bg`, 강조 `accent`, 포인트 `point`, 들어오는 돈
  `inc`, 나가는 돈 `exp`. 나머지는 전부 거기서 유도하므로 모드를 더하려면 한
  줄만 적으면 된다: 미색 초록(시안 그대로), 흰 종이 쪽빛, 연둣빛 올리브,
  모래 팥죽, 밤 남색(예전 모습), 먹색 라임, 숲 녹색, 자줏빛 보라.
  `accentSoft`·`greenSoft`·`redSoft` 는 박아 둔 색이 아니라 `soft(c)` 가 그 색을
  바탕에 풀어 만들고, 히어로 카드는 제 밝기를 보고 글자를 검정/흰색으로 고른다
  (강조색이 밝아도 글씨가 읽힌다). 시나리오 선 색도 모드의 색에서 시작한다.
  `Theme.customBg` 는 '바탕만 직접 고른 색' 을 모드와 따로 들고 있고 둘 다
  저장되므로(`Backend.saveAppearance(bg, mode)`), 다음에 켜도 고른 그대로다.
  여는 자리는 사이드바 맨 아래 **설정 · 바탕색** 이다. 상단 `모양` 단추는
  사이드바가 접히는 좁은 창에서만 남겨 두었다 — 줄바꿈되는 단추 줄 끝에 묻혀
  있으면 아무도 못 찾는다.

### 고친 것

- **밝은 바탕에서 단추의 절반이 사라져 보이던 것.** `Main.qml` 과
  `LedgerWindow.qml` 에 `Material.theme: Material.Dark` 가 못 박혀 있어서,
  Controls(단추·스위치·콤보·입력칸·툴버튼)가 글자를 **흰색**으로 그렸다.
  미색 바탕에서는 흰 글자라 안 보인다. `기간` 단추(6개월·1년·2년…)와 ±,
  목표 자본금 입력칸, 상단 단추 몇 개가 없어진 것처럼 보이던 까닭이 이것이다.
  이제 테마가 바탕색을 따른다 — `Theme.light ? Material.Light : Material.Dark`,
  `Material.foreground: Theme.text`.
- **색을 박아 둔 면들이 혼자 캄캄하게 남던 것.** 분류 머리글(`#1a1f33`), 목표
  진행 바와 예측 칸, 그래프의 기간 고르기 칸, 대출 날짜 칸, 원그래프 고리,
  추이 그래프의 바탕과 눈금이 어두운 시절의 색을 그대로 들고 있었다. 모두
  `Theme.row` · `greenSoft` · `redSoft` · `cardBorder` 로 바꿨다.
- **항목 목록이 두 줄만 보이던 것.** `HeroSummary` 가 같은 `ColumnLayout` 안에
  높이 제한 없이 들어가 있어서, 레이아웃이 남는 세로 자리를 히어로에게도 나눠
  주었다. 이제 `Layout.fillHeight: false` + `preferredHeight: implicitHeight`
  로 **필요한 만큼만** 쓰고, 히어로 자체도 낮췄다(최소 176→128, 숫자 40→32px,
  숫자 카드 128→102). 목록 줄에는 `Layout.minimumHeight: 260` 을 두었다.

---

## 0.12.0 — 2026-11-24

### Added

- **A second item list beside the first, showing the same items N months out.**
  `qml/FutureList.qml` is a `Card` with a chip row (1·2·3·6·12·24개월 뒤) whose
  rows come from two new read-only backend slots — `Backend.itemsAt(m)` returns
  `{name, sub, category, group, amountText, tail, tone, off}` per item and
  `Backend.monthSnapshot(m)` returns that month's 보유 자금 / 묶인 돈 /
  쓸 수 있는 돈 / 순 자본. **Neither computes anything**: they read
  `saving_balance_at`, `remaining_at`, `once_month`, `monthly_*_at`,
  `count_upto`, `capital_at`, `tied_capital_at`, `spendable_at` and shape the
  result into rows, so the calculation layer is untouched. The panel is a
  `Loader` with `active: win.futureShown`, like the Overview, so nothing is
  built or queried while it is off. A `Switch` above the list toggles it;
  `futureFits` (`width >= 1280`) folds it away on a narrow window without
  turning the switch off. It answers the question the single list could not:
  "두 달 뒤에 이 보증금을 낼 수 있나" — rows that have not happened yet are
  dimmed with `아직`, and the footer turns red with the shortfall when 쓸 수
  있는 돈 goes negative.
- **Background colour is now a setting (모양 button → `ThemeDialog`).**
  `Theme.qml` stopped being a wall of `readonly` constants: `bgBase` is the one
  writable property and `surface(t)` lifts 카드·줄·테두리 off it, lightening a
  dark base and darkening a light one. `light` (luminance > 0.5) flips the text
  and the accent/green/red/yellow set to darker variants, so a light background
  is legible rather than a wash. Seven presets plus a `ColorDialog` for a custom
  colour; each swatch previews a surface and a label on that base. The choice
  saves through `Backend.saveAppearance()` into the window-state ini next to the
  data file — **not** into the plan file, since it is this PC's taste and not
  part of the plan, and it never marks the plan dirty. `Main.qml` applies it in
  `Component.onCompleted` **before** the early return for a missing window
  state, or a first run would start on the default colour.

### 더한 것

- **항목 목록 옆에 같은 목록을 'N개월 뒤' 값으로 한 칸 더.**
  `qml/FutureList.qml` 은 시점 칩(1·2·3·6·12·24개월 뒤)이 달린 `Card` 이고,
  줄은 백엔드의 읽기 전용 슬롯 둘에서 온다 — `Backend.itemsAt(m)` 이 항목마다
  `{name, sub, category, group, amountText, tail, tone, off}` 을,
  `Backend.monthSnapshot(m)` 이 그 달의 보유 자금·묶인 돈·쓸 수 있는 돈·순
  자본을 돌려준다. **둘 다 새로 셈하지 않는다** — `saving_balance_at`,
  `remaining_at`, `once_month`, `monthly_*_at`, `count_upto`, `capital_at`,
  `tied_capital_at`, `spendable_at` 이 이미 내놓는 값을 줄 모양으로 옮길
  뿐이라 계산 쪽은 그대로다. 칸은 '한눈에' 와 같이 `Loader` 로 두어
  (`active: win.futureShown`) 꺼 두면 아예 만들지도, 부르지도 않는다. 목록 위
  `Switch` 로 켜고, 창이 좁으면 (`futureFits`, 1280px) 스위치는 켜진 채 칸만
  접힌다. 목록 하나로는 못 하던 "두 달 뒤에 이 보증금을 낼 수 있나" 가 여기서
  답이 나온다 — 아직 일어나지 않은 줄은 `아직` 으로 흐려지고, 쓸 수 있는 돈이
  마이너스면 바닥이 빨갛게 서며 얼마가 모자란지 적힌다.
- **바탕색을 고를 수 있다 (`모양` 단추 → `ThemeDialog`).** `Theme.qml` 이
  `readonly` 상수 더미이기를 그만두었다 — 쓸 수 있는 속성은 `bgBase` 하나뿐이고
  `surface(t)` 가 카드·줄·테두리를 그 색에서 한 겹씩 띄운다 (어두우면 흰 쪽으로,
  밝으면 검은 쪽으로). `light`(밝기 0.5 초과)가 글자색과 강조·초록·빨강·노랑을
  어두운 변종으로 뒤집어, 밝은 바탕에서도 글씨가 읽힌다. 미리 고른 일곱 가지와
  `ColorDialog` 로 직접 고르기가 있고, 색판마다 그 바탕 위의 면과 글자가 어떻게
  보일지 미리 그려 준다. 고른 값은 `Backend.saveAppearance()` 가 데이터 파일 옆
  창 상태 ini 에 적는다 — **계획 파일에는 안 적는다.** 그 PC 의 취향이지 그
  계획의 내용이 아니고, 계획을 '저장 안 됨' 으로 만들어서도 안 되기 때문이다.
  `Main.qml` 은 이 값을 `Component.onCompleted` 에서 **창 상태가 없을 때 일찍
  빠져나가는 줄보다 먼저** 넣는다 (그러지 않으면 처음 켜는 PC 는 기본색으로 뜬다).

---

## 0.11.0 — 2026-11-24

### Added

- **A deposit (`보증금/매매가`) can now be counted as an asset.** `Item` gained
  `as_asset: bool = False` and `deposit_value_at(m, basis)`, and
  `Item.capital_at()` routes `DEPOSIT` through it. While the money is lodged the
  deposit sits in 보유 자금 **and** is still subtracted as a `once_cost`, so the
  two cancel and 순 자본 does not move — cash merely changes shape. On the
  return month `deposit_value_at()` drops to 0 while `once_income_at()` pays it
  back, so 순 자본 does not jump there either. A deposit paid **before** the
  basis date benefits most: `count_upto()` never charges it (the money left
  before the plan began), so until now it appeared out of nowhere on the return
  date; with the flag on it stands in 순 자본 from month 0.
  The default is `False` on purpose — loading an existing plan must not change
  a single number. `__post_init__` clears the flag off every other category.
- **The summary now splits 보유 자금 into spendable cash and money tied up in a
  deposit.** Turning the flag on makes 보유 자금 larger, and reading all of it as
  cash is how a plan goes wrong. `Plan.tied_capital_at(m)` sums
  `deposit_value_at()` over the live items, `Backend.tiedCapital` exposes it at
  month 0, and both the 요약 card and the Overview's 지금 보유 자금 tile print
  `쓸 수 있는 돈 … · 보증금에 묶인 돈 …` whenever it is above zero. The Overview's
  plain-value snapshot gained `tied: 0` to match (see 0.10.1's `undefined` bug).
- **The 현금 부족 경고 now measures spendable money, not net worth.** With the
  asset flag on, 순 자본 no longer dips when a deposit is paid — so a plan that
  puts 150M into a lease while holding 100M looked perfectly healthy and no
  warning fired. `Plan.spendable_series(n)` / `spendable_at(m)` subtract
  `tied_capital_at(m)` from the net, and `Plan.shortfall()` reads that series;
  `Backend.shortfall`'s `net`/`minNet` are the spendable figure, and the card
  now reads 쓸 수 있는 돈 and suggests moving the move-in date when something is
  tied up. For a plan that does not use the flag the two series are identical,
  so the warning behaves exactly as before.
- Plumbing for the flag: `AsAssetRole` (UserRole+32), `categoryInfo.canBeAsset`,
  the `assetCheck` box in `ItemDialog` (its label follows `housingType`, so
  `매매` reads 집값), a trailing `as_asset` argument on
  `addItem`/`updateItem`/`_make_item` with the matching `@Slot` overload, the
  `자산으로 포함` column in the Excel `항목` sheet, `as_asset` in
  `import_plan.HEADER_KEYS`, and `순 자본에 자산으로 포함` in the row subtext.

### Fixed

- **`Unable to assign [undefined] to double` ×4 on startup**
  (`OverviewView.qml:496,500,505,509`). The Overview is kept alive while hidden
  and seeded with plain-value snapshots rather than bindings, so its bindings
  evaluate once before `refresh()` ever runs. The seed for `now` carried
  `vsPlan: { has: false }` and nothing else, so the four `StatRow` rows for
  계획/실제 지출·수입 bound `vsCol.vs.planOut` … to `undefined` against a `double`
  property. `visible: vsCol.vs.has` does not help — QML evaluates a binding
  whether or not the item is visible. The seed now mirrors every key of
  `Backend._plan_vs_actual()`'s `empty` dict (and `ym`), with a comment tying
  the two together.

### 더한 것

- **보증금·매매가를 '맡겨 둔 자산' 으로 보아 순 자본에 넣을 수 있다.** 보증금은
  쓴 돈이 아니라 맡겨 둔 돈이다. `Item` 에 `as_asset` 과
  `deposit_value_at(m, basis)` 를 더하고 `capital_at()` 이 보증금을 그리로
  보낸다. 묶여 있는 동안에는 보유 자금에 **더해지면서** 일시 지출로도 그대로
  빠지므로 둘이 맞물려 **순 자본이 움직이지 않는다** — 현금이 보증금으로 모양만
  바뀐 것이다. 돌려받는 달에는 `deposit_value_at()` 이 0 이 되고 그 돈이
  `once_income_at()`(보증금 반환)으로 들어와, 거기서도 순 자본이 튀지 않는다.
  **이미 살고 있는 집**이 가장 크게 달라진다 — 기준일 전에 나간 돈은
  `count_upto()` 가 세지 않아서(계획이 시작되기 전에 나간 돈이다) 예전에는
  반환일에 없던 돈이 갑자기 생겨났다. 켜 두면 0개월째부터 제자리에 선다.
  **기본값은 꺼짐**이다 — 예전 계획을 불러오기만 했는데 숫자가 달라지면 안 된다.
  보증금이 아닌 분류에서는 `__post_init__` 이 이 설정을 털어 낸다.
- **요약이 보유 자금을 '쓸 수 있는 돈' 과 '보증금에 묶인 돈' 으로 갈라 보여 준다.**
  자산으로 켜면 보유 자금이 커지는데, 그게 다 현금인 줄 알면 계획을 잘못 세운다.
  `Plan.tied_capital_at(m)` 이 살아 있는 항목의 `deposit_value_at()` 을 더하고,
  `Backend.tiedCapital` 이 0개월 시점 값을 내준다. 요약 카드와 '한눈에' 의
  `지금 보유 자금` 타일이 묶인 돈이 있을 때만
  `쓸 수 있는 돈 … · 보증금에 묶인 돈 …` 을 적는다. '한눈에' 의 처음 값에도
  `tied: 0` 을 넣었다 (0.10.1 의 `undefined` 와 같은 까닭이다).
- **현금 부족 경고가 '가진 돈' 이 아니라 '쓸 수 있는 돈' 을 본다.** 자산으로 켜면
  보증금을 내도 순 자본이 안 깎이므로, 1억을 가지고 1.5억짜리 전세에 들어가는
  계획도 멀쩡해 보이고 경고가 안 떴다. `Plan.spendable_series(n)` /
  `spendable_at(m)` 이 순 자본에서 `tied_capital_at(m)` 을 빼고,
  `Plan.shortfall()` 이 그 값을 본다. `Backend.shortfall` 의 `net`·`minNet` 도
  쓸 수 있는 돈이며, 경고 카드가 '쓸 수 있는 돈' 으로 말하고 묶인 돈이 있으면
  **입주 시점을 미루라**고 일러 준다. 이 설정을 안 쓰는 계획에서는 두 값이 같아
  경고가 예전과 똑같이 움직인다.
- 그 설정이 지나가는 길: `AsAssetRole`(UserRole+32), `categoryInfo.canBeAsset`,
  `ItemDialog` 의 `assetCheck`(주거 형태가 `매매` 면 '집값' 으로 글이 바뀐다),
  `addItem`/`updateItem`/`_make_item` 맨 뒤의 `as_asset` 인자와 그에 맞춘
  `@Slot` 줄, 엑셀 '항목' 시트의 `자산으로 포함` 칸,
  `import_plan.HEADER_KEYS` 의 `as_asset`, 그리고 목록 줄 아래의
  `순 자본에 자산으로 포함`.

### 고친 것

- **켤 때 `Unable to assign [undefined] to double` 이 네 줄 뜨던 것**
  (`OverviewView.qml:496,500,505,509`). '한눈에' 는 숨어도 지워지지 않고, 처음
  값을 바인딩이 아니라 그냥 값으로 심어 둔다 (그래야 안 보는 동안 백엔드를
  다시 부르지 않는다). 그런데 `now` 의 처음 값에 `vsPlan: { has: false }` 만
  들어 있어서, `refresh()` 가 돌기 전에 계획/실제 지출·수입 `StatRow` 네 개가
  `vsCol.vs.planOut` … 을 `undefined` 인 채로 `double` 속성에 넣었다.
  `visible: vsCol.vs.has` 로는 막을 수 없다 — QML 은 안 보이는 것의 바인딩도
  계산한다. 이제 처음 값이 `Backend._plan_vs_actual()` 의 `empty` 와 같은 칸을
  모두 갖추며(`ym` 도), 둘이 짝이라는 주석을 달아 두었다.

---

## 0.10.0 — 2026-11-19

### Added

- **The Excel `항목` sheet is now a round trip, not just a report.** Export →
  edit in Excel → `가져오기` used to drop every per-item setting that the
  importer could not name. `export_excel.py` writes five more columns —
  `받는 날`, `복리`, `세후 이자`, `가계부 분류`, `켜짐` — and writes
  `만기까지 묶임` as `예`/`아니오` for `SAVING` instead of leaving it blank when
  false, since a blank cell is indistinguishable from "no such column".
  `import_plan.HEADER_KEYS` gained the matching keys plus `원금 자본 포함`,
  `상환 방식` and `중도 상환`. Ordering matters and is commented in place:
  `include_principal` must precede `amount` (whose aliases contain `원금`) and
  `locked` must precede `end` (whose aliases contain `만기`), or
  `find_header()` assigns those columns to the wrong field.
- New parsers in `import_plan.py`: `parse_yesno()` returns `None` for a blank or
  unreadable cell so a missing column falls back to the `Item` default rather
  than to `False`; `parse_day()` clamps to 1–31; `parse_repay_method()` maps the
  exported label back to a `REPAY_METHOD_LIST` key and pulls the `%` out of
  `매달 원금의 % (1.5%)`; `parse_repayments()` finds `date + amount` pairs by
  regex because the amounts themselves contain commas.
- `_row_dict()` carries the settings through the preview and strips the ones
  that are meaningless for the category (`locked` off `SAVING`, `pay_day` off
  non-monthly shapes), and `Backend.applyPlanImport()` passes all ten to
  `Item(...)`. `planImportRows` shows `매달 25일`, `만기까지 묶음`,
  `원금 자본 미포함` and `꺼짐` in the preview tail.

### Fixed

- **A disabled item came back as a new item named `"급여 (꺼짐)"`.** The export
  marked inactive items by appending `(꺼짐)` to the name and the importer only
  stripped that suffix — `active` itself was never read, so re-importing
  produced an enabled item under a mangled name. The suffix is still recognised
  for older files, but `active` now comes from the `켜짐` column.
- **`ItemDialog` did not say what happens on the 29th–31st.** The behaviour was
  already right (`ledger.same_day_in()` clamps with
  `calendar.monthrange()`, so 31 lands on 28/29 February), but the hint under
  the `받는 날` combo only said "이 날짜로 들어갑니다". It now switches text at
  `payDay >= 29`.

### 더한 것

- **엑셀 `항목` 시트가 '보고서' 에서 '왕복' 이 되었다.** 내보내기 → 엑셀에서
  고치기 → `가져오기` 를 하면 가져오기가 이름을 모르는 설정이 모두 기본값으로
  돌아갔다. `export_excel.py` 가 `받는 날`·`복리`·`세후 이자`·`가계부 분류`·
  `켜짐` 다섯 칸을 더 적고, `만기까지 묶임` 은 적금이면 꺼져 있어도
  `아니오` 라고 적는다 (빈 칸은 '그런 칸이 없다' 와 구별되지 않는다).
  `import_plan.HEADER_KEYS` 에 그 머리글들과 `원금 자본 포함`·`상환 방식`·
  `중도 상환` 을 더했다. **순서가 중요하다** — `원금 자본 포함` 은 `금액`
  (별명에 `원금` 이 있다) 보다, `만기까지 묶임` 은 `종료일`(별명에 `만기`) 보다
  앞에 와야 `find_header()` 가 엉뚱한 칸으로 짝짓지 않는다. 주석으로 적어 두었다.
- `import_plan.py` 에 읽는 함수들: `parse_yesno()` 는 빈 칸이면 `False` 가 아니라
  `None` 을 돌려주어, 칸이 없는 표(사람이 손으로 적은 것)가 `Item` 의 기본값을
  쓰게 한다. `parse_day()` 는 1~31 로 자르고, `parse_repay_method()` 는 내보낸
  이름을 `REPAY_METHOD_LIST` 키로 되돌리며 `매달 원금의 % (1.5%)` 에서 상환율을
  꺼낸다. `parse_repayments()` 는 금액 안에도 쉼표가 있어서 쉼표로 자르지 않고
  날짜+금액 짝을 정규식으로 찾는다.
- `_row_dict()` 가 그 설정들을 미리보기까지 들고 가면서 분류에 뜻이 없는 것은
  털어 내고(적금 아닌 것의 `locked`, 매달 오가지 않는 것의 `pay_day`),
  `Backend.applyPlanImport()` 가 열 가지를 모두 `Item(...)` 에 넘긴다.
  미리보기 꼬리말에 `매달 25일`·`만기까지 묶음`·`원금 자본 미포함`·`꺼짐` 이 뜬다.

### 고친 것

- **꺼 둔 항목이 `"급여 (꺼짐)"` 이라는 새 항목으로 되돌아오던 것.** 내보낼 때
  꺼진 항목을 이름 뒤 `(꺼짐)` 으로만 나타냈고, 가져올 때는 그 꼬리를 떼기만
  했다 — `active` 자체는 읽은 적이 없어서 켜진 항목이 이상한 이름으로 하나 더
  생겼다. 꼬리는 예전 파일을 위해 그대로 알아보되, 이제 `켜짐` 칸에서 읽는다.
- **29·30·31일을 고르면 어떻게 되는지 알려 주지 않던 것.** 동작은 이미
  맞았다 — `ledger.same_day_in()` 이 `calendar.monthrange()` 로 잘라서 31일은
  2월 28·29일에 들어간다. 다만 `받는 날` 밑 안내가 "이 날짜로 들어갑니다" 뿐이라
  알 길이 없었다. `payDay >= 29` 이면 안내가 바뀐다.

---

## 0.9.0 — 2026-11-19

### Added

- **One-a-year expenses (car insurance, vehicle tax).** `ItemDialog` gained
  `makeYearly()`: it moves the item to `일시 지출` / `일시 수입`
  (`setCategoryNamed()` resolves the name to a `cat_index`, never a combo row
  position) and sets `every = 12`, keeping the amount and date already typed.
  The prompt is shown for monthly-shaped categories only
  (`categoryInfo.usesPayDay`, minus `SAVING`) because `canRepeat` is false
  there and the repeat control is hidden — that was the dead end users hit.

### Fixed

- **Item rows pushed the `✕` (delete) button outside the row.** The delegate's
  columns add up to a 590px minimum (18 + 90 + 48 + 104 + 34 + 80 + 168 +
  margins). `RowLayout` cannot shrink a `Button` below its content, so a
  narrower row overflowed and the row's `clip: true` cut the trailing button.
  `Main.qml` now exposes `readonly property bool roomy: width > 600` on the
  delegate, hides the rate column and `▲▼` below it, lowers the text minimums
  (name 90→70, amount 104→92, monthly 80→70) and **pins** the button group
  (`Layout.minimumWidth === Layout.preferredWidth`, 160 / 96) so it can never be
  squeezed. The header row mirrors the breakpoint at `list.width > 614` (row
  width is `list.width - 14`).
- **Double-clicking a row to edit it silently cleared `pay_day`.** 0.8.0 added a
  21st argument to `ItemDialog.openForEdit()` and updated `win.openEditDialog()`
  but not the delegate's `TapHandler.onDoubleTapped` path, so `payDay` arrived
  as `undefined` and `payDay || 0` stored 0. The delegate now declares
  `required property int payDay` and passes it.
- **Importing the same plan twice piled rows up.** `_mark_plan_import()` flagged
  a row as known only when `(name, category, round(amount))` matched an existing
  item, so any item whose category or amount was corrected after the first
  import no longer matched and was added again. Added `_plan_names()` (trimmed,
  case-folded) and a second flag `sameName`; `applyPlanImport()` skips
  `dupe or sameName` while "skip existing" is on, and `PlanImportDialog` labels
  the two cases `이미 있음` / `이름이 같음` so the difference is visible rather
  than silent.
- **A lump-sum loan repayment was averaged into "월 지출 (평균)".** For a loan
  with `include_principal = False`, `monthly_cost_at()` adds the maturity
  repayment in the month it falls and `Summary.avg_cost` is
  `sum(monthly_cost_at) / months`, so repaying ₩94M once read as ₩2.9M every
  month (₩1.13M → ₩4.08M). Added `Item.once_repay_at()` / `Plan.once_repay_at()`
  (one-off repayments of a loan whose principal is not counted as capital) and
  `Plan.summary()` now subtracts them from the per-month costs and adds them to
  `once_cost`. `net_at()` is untouched and `required` is unchanged — a test
  asserts the split still sums to `once_cost_at(n) + Σ monthly_cost_at(m)`.

### 더한 것

- **1년에 한 번 내는 돈 (자동차 보험·자동차세).** `ItemDialog` 에 `makeYearly()`
  를 더했습니다. 분류를 `일시 지출`·`일시 수입` 으로 옮기고(`setCategoryNamed()`
  가 이름으로 분류 번호를 찾습니다 — 콤보의 줄 번호가 아닙니다) 되풀이를 12개월로
  맞추며, 적던 금액·날짜는 그대로 둡니다. 안내는 매달 오가는 분류에서만 뜹니다
  (`categoryInfo.usesPayDay`, 적금 제외) — 거기서는 `canRepeat` 가 거짓이라
  되풀이 칸이 아예 안 보였고, 길이 거기서 끊겼습니다.

### 고친 것

- **항목 줄의 `✕`(삭제)가 줄 밖으로 밀려 잘리던 것.** 칸들의 최소 폭 합이
  590px(18+90+48+104+34+80+168+여백)인데, `RowLayout` 은 `Button` 을 글자보다
  좁게 만들지 못해 줄이 그보다 좁으면 넘쳐 나가고 줄의 `clip: true` 가 끝을
  잘랐습니다. 이제 델리게이트에 `readonly property bool roomy: width > 600` 을
  두고 그 아래에서는 연이율 칸과 `▲▼` 를 접습니다. 글자 칸 최소 폭도 낮추고
  (이름 90→70, 금액 104→92, 월 환산 80→70), 단추 칸은 `Layout.minimumWidth` 를
  `preferredWidth` 와 같게(160/96) 못 박아 절대 줄지 않게 했습니다. 머리줄은
  `list.width > 614` 로 같은 눈금을 씁니다(줄 폭 = 목록 폭 − 14).
- **줄을 더블클릭해 고치면 `pay_day` 가 조용히 지워지던 것.** 0.8.0 에서
  `ItemDialog.openForEdit()` 에 인자가 하나 늘었는데 `win.openEditDialog()` 만
  고치고 델리게이트의 `TapHandler.onDoubleTapped` 쪽을 빠뜨려, `payDay` 가
  `undefined` 로 와서 `payDay || 0` 이 0 을 저장했습니다. 델리게이트에
  `required property int payDay` 를 선언하고 넘기도록 했습니다.
- **같은 계획을 두 번 가져오면 쌓이던 것.** `_mark_plan_import()` 가
  `(이름, 분류, 반올림한 금액)` 이 모두 맞을 때만 '이미 있음' 으로 보아서, 처음
  가져온 뒤 분류나 금액을 고쳐 두면 다음 번에 어긋나 또 들어왔습니다.
  `_plan_names()`(앞뒤 공백·대소문자 무시)와 `sameName` 표시를 더하고, '이미 있는
  항목 건너뛰기' 가 켜져 있으면 `applyPlanImport()` 가 `dupe or sameName` 을
  건너뜁니다. 미리보기에서 `이미 있음` / `이름이 같음` 으로 갈라 보여 주어 조용히
  넘어가지 않습니다.
- **만기에 한 번 갚는 대출 원금이 '월 지출 (평균)' 에 녹던 것.**
  `include_principal = False` 인 대출은 `monthly_cost_at()` 이 만기 달에 상환액을
  얹고 `Summary.avg_cost` 는 `sum(monthly_cost_at) / 개월` 이라, 9,400만원을 한 번
  갚는 것이 달마다 294만원처럼 읽혔습니다(113만 → 408만). `Item.once_repay_at()`
  / `Plan.once_repay_at()` 을 더하고 `Plan.summary()` 에서 월별 지출에서 빼
  `once_cost` 로 옮겼습니다. `net_at()` 은 건드리지 않았고 `required` 도 그대로입니다
  — 갈라 놓은 합이 `once_cost_at(n) + Σ monthly_cost_at(m)` 과 같은지 테스트합니다.

---

## 0.8.0 — 2026-11-19

### Added

- **Two-level category taxonomy.** `model.CATEGORY_TREE` (자본 / 수입 / 주거 /
  생활 / 금융) and `ledger.LEDGER_TREE` (수입 / 주거 / 생활 / 금융 / 기타) are now
  the single source: `CATEGORY_LIST`, `CATEGORY_ORDER`, `ORDER_OF`, `GROUP_OF`,
  `LEDGER_INCOME_CATEGORIES` and `LEDGER_COST_CATEGORIES` are all derived, and
  `CATEGORY_INFO[...]["group"]` is filled by a loop instead of by hand. A
  category missing from the tree raises at import time. `cat_index` is
  **deliberately left in enum order** — it is the address QML uses in ~100 call
  sites — with `_display_pos()` (list sorting) and `categoryChoices()` (grouped
  picker) as the only two bridges to the tree order.
- **A `shape` column** on every category (`monthly_cost`, `once_income`,
  `loan`…). `MONTHLY_COST_CATEGORIES` and the four other membership tuples are
  derived from it, so adding a category can no longer silently skip the
  calculation.
- **Housing split in the ledger.** The single `주거/관리비` category became
  월세 / 관리비 / 공과금 / 보증금. The old name is kept (entries still carry it)
  but hidden from pickers unless something uses it. `PLAN_TO_LEDGER` maps plan
  월세 → ledger 월세, 관리비 → 관리비, 보증금/매매가 → 보증금.
- **`custom_groups`** — a new save key holding the first level of user-made
  ledger categories. Old files simply lack it and fall back to `기타`, so no
  migration was needed.
- **`pay_day`** (1–31) on monthly categories. It does not change the plan math
  (which is month-bucketed); it sets the date used when writing to the ledger.
- **Plan import** (`capital_calc/import_plan.py`, `qml/PlanImportDialog.qml`) —
  Excel / CSV / pasted text, with header matching and a preview.
- **Detachable ledger window** (`qml/LedgerWindow.qml`, Ctrl+Shift+2).

### Fixed

- **"한눈에" froze the window on every visit.** The `Loader` was
  `active: mode === "overview"`, so the page was destroyed on leaving and
  rebuilt — a dozen cards plus three charts and twelve backend calls — in a
  single frame. It is now kept alive (`active: win.overviewReady`, warmed up
  1.5s after start), built `asynchronous`ly, and `OverviewView.refresh()`
  returns early while `!visible`, setting `stale` so it refreshes once when
  shown again. The snapshot properties no longer start as live bindings, which
  is what made "just hide it" slow in the first place.
- **The toolbar ran off the window.** A `RowLayout` cannot shrink buttons, so
  the right-hand ones were pushed outside and nothing clipped them. The toolbar
  and the scenario row are `Flow`s now. The header card also got a
  `Layout.minimumHeight` (it was squeezed vertically, cutting its last row), and
  기준일 / 종료일 / 기간 / 목표 moved into a `GridLayout` whose `columns` follows
  the window width (4 → 2 → 1).
- **`SliderInput` clipped its suffix.** The number field moved up to the label
  row and the slider now owns its own row, which also removed the duplicated
  value text.
- **Two ways to enter rent.** The housing item's monthly-rent field is gone;
  rent is always its own `월세` item. Old files are split on load by
  `split_housing_rent()` and imports by `split_rent_rows()`. The numbers are
  identical because `housing_active()` and `is_active()` describe the same
  window — asserted by comparing `net_series()` against a hand-built plan.

### 더한 것

- **분류를 1차 / 2차 두 단으로.** `model.CATEGORY_TREE`(자본·수입·주거·생활·금융)와
  `ledger.LEDGER_TREE`(수입·주거·생활·금융·기타)가 유일한 표가 되고,
  `CATEGORY_LIST`·`CATEGORY_ORDER`·`ORDER_OF`·`GROUP_OF`·
  `LEDGER_INCOME_CATEGORIES`·`LEDGER_COST_CATEGORIES` 를 모두 거기서 끌어냅니다.
  `CATEGORY_INFO[...]["group"]` 도 손으로 적지 않고 반복문이 채우며, 트리에 빠진
  분류가 있으면 불러올 때 터집니다. `cat_index` 는 **일부러 enum 순서 그대로**
  두었습니다 — QML 이 분류를 가리키는 주소라 쓰는 자리가 백여 군데입니다. 트리
  순서와 잇는 다리는 `_display_pos()`(목록 정렬)와 `categoryChoices()`(두 단 목록)
  둘뿐입니다.
- **`shape` 칸.** 분류마다 돈이 오가는 성격(`monthly_cost`, `once_income`, `loan` …)
  을 적고, `MONTHLY_COST_CATEGORIES` 등 묶음 다섯을 거기서 끌어냅니다. 분류를
  더하면서 묶음을 잊어 계산에서 조용히 빠지는 일이 없어집니다.
- **가계부 주거 쪼개기.** `주거/관리비` 하나이던 것을 월세·관리비·공과금·보증금으로
  갈랐습니다. 예전 이름은 내역이 들고 있으므로 남기되, 쓰는 데가 없으면 목록에서
  숨깁니다. `PLAN_TO_LEDGER` 도 월세→월세, 관리비→관리비, 보증금/매매가→보증금.
- **`custom_groups`** — 직접 만든 가계부 분류의 1차를 담는 새 저장 칸. 예전 파일에는
  키가 없어 `기타` 로 읽히므로 변환이 필요 없습니다.
- **`pay_day`**(1~31) — 매달 오가는 분류의 '받는 날 / 나가는 날'. 계산은 달 단위라
  숫자를 바꾸지 않고, 가계부에 적을 때 쓰는 날짜를 정합니다.
- **계획 가져오기**(`capital_calc/import_plan.py`, `qml/PlanImportDialog.qml`) —
  엑셀·CSV·붙여넣은 글을 머리글로 알아보고 미리보기를 거쳐 넣습니다.
- **가계부를 따로 띄우는 창**(`qml/LedgerWindow.qml`, Ctrl+Shift+2).

### 고친 것

- **'한눈에' 로 들어갈 때마다 창이 멈추던 것.** `Loader` 가
  `active: mode === "overview"` 라 화면을 떠나면 지우고, 들어갈 때 카드 열몇 개와
  그래프 셋, 백엔드 호출 열두 번을 **한 프레임에** 다시 만들었습니다. 이제 지우지
  않고(`active: win.overviewReady`, 시작 1.5초 뒤 미리 만듦) `asynchronous` 로
  만들며, `OverviewView.refresh()` 는 `!visible` 이면 `stale` 만 켜고 돌아섭니다.
  스냅샷 속성의 첫 값도 바인딩이 아니게 바꿨습니다 — 숨겨만 뒀을 때 느려지던
  까닭이 그 바인딩이었습니다.
- **상단 바가 창 밖으로 나가던 것.** `RowLayout` 은 단추를 글자보다 좁게 만들지
  못해 오른쪽 것들이 밖으로 밀려났고 아무도 잘라 주지 않았습니다. 단추 줄과
  시나리오 줄을 `Flow` 로 바꿨습니다. 상단 카드에는 `Layout.minimumHeight` 를
  주었고(세로로 눌려 맨 아랫줄이 잘렸습니다), 기준일·종료일·기간·목표는 창 너비를
  따라 `columns` 가 4 → 2 → 1 로 바뀌는 `GridLayout` 으로 옮겼습니다.
- **`SliderInput` 의 단위가 잘리던 것.** 숫자 칸을 라벨 줄로 올리고 슬라이더가 제
  줄을 통째로 쓰게 했습니다. 같은 숫자를 두 군데서 보여 주던 것도 없앴습니다.
- **월세를 넣는 길이 둘이던 것.** 주거 항목의 월세 칸을 없애고 `월세` 분류 하나만
  남겼습니다. 예전 파일은 불러올 때 `split_housing_rent()` 가, 가져오기는
  `split_rent_rows()` 가 갈라냅니다. `housing_active()` 와 `is_active()` 가 같은
  구간을 말하므로 숫자는 그대로이고, 손으로 두 항목을 넣은 계획과 `net_series()` 가
  같은지 테스트합니다.
