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
