import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 가계부 화면: 왼쪽에 내역 목록, 오른쪽에 월별·분류별 집계
RowLayout {
    id: view
    spacing: 12

    // 기간이 바뀌어도 같은 달에 계속 적게 기본 날짜를 맞춰 준다
    function openAdd() { entryDialog.openForAdd(view.defaultDate()) }
    function openBudget() { budgetDialog.open() }
    function openFixed() { fixedDialog.open() }

    function defaultDate() {
        if (backend.ledgerMonth > 0)
            return backend.ledgerYear + "-" + String(backend.ledgerMonth).padStart(2, "0") + "-01"
        return backend.today
    }

    EntryDialog { id: entryDialog }
    BudgetDialog { id: budgetDialog }
    FixedDialog { id: fixedDialog }

    // 계획 화면의 항목 삭제와 같게. 되돌릴 수 없으므로 한 번 묻는다.
    ConfirmDialog {
        id: removeEntryDialog
        objectName: "removeEntryDialog"
        property int row: -1
        title: "내역 삭제"
        okText: "삭제"
        onAccepted: backend.removeEntry(row)
    }

    // ✕ 를 눌렀을 때. delegate 안에 두면 테스트에서 부를 수 없어 밖으로 꺼냈다.
    function confirmRemove(row, dateText, name, category, amountText) {
        removeEntryDialog.row = row
        removeEntryDialog.message = dateText + "  "
            + (name !== "" ? "'" + name + "'" : category)
            + "  " + amountText + " 내역을 삭제할까요?"
        removeEntryDialog.open()
    }

    // ⟳ 를 눌렀을 때. 고정으로 올리고 바로 그 목록을 보여 준다.
    function makeFixed(row) {
        if (backend.fixedFromEntry(row) === "")
            fixedDialog.open()
    }

    ConfirmDialog {
        id: clearLedgerDialog
        title: "가계부 비우기"
        message: "기록한 내역을 모두 지웁니다. 되돌릴 수 없습니다."
        onAccepted: backend.clearLedger()
    }

    // ───────────── 왼쪽: 내역
    Card {
        Layout.fillWidth: true
        Layout.fillHeight: true
        title: "가계부 내역  ·  " + backend.ledgerPeriodText
               + (backend.ledgerFiltered
                  ? "  (" + backend.ledgerFilteredSummary.count + " / " + backend.ledgerSummary.count + "건)"
                  : "  (" + backend.ledgerSummary.count + "건)")

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            // 연도 + 월 고르기.
            // 한 줄에 다 넣으면 창이 좁을 때 카드가 오른쪽 집계 밑으로 밀려 들어가
            // 내역의 금액이 가려졌다. 좁으면 단추 묶음을 아랫줄로 내린다.
            GridLayout {
                id: headerGrid
                Layout.fillWidth: true
                columnSpacing: 8
                rowSpacing: 8
                columns: width < periodRow.implicitWidth + actionRow.implicitWidth + columnSpacing ? 1 : 2

            RowLayout {
                id: periodRow
                Layout.fillWidth: true
                spacing: 8

                ComboBox {
                    id: yearBox
                    objectName: "ledgerYearBox"
                    Layout.preferredWidth: 130
                    model: backend.ledgerYears
                    visible: backend.ledgerYears.length > 0
                    onActivated: backend.ledgerYear = String(currentValue)
                    Connections {
                        target: backend
                        function onLedgerChanged() {
                            var i = backend.ledgerYears.indexOf(backend.ledgerYear)
                            if (i >= 0 && i !== yearBox.currentIndex) yearBox.currentIndex = i
                        }
                    }
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                Repeater {
                    model: 13                                   // 0 = 그 해 전체, 1~12 = 월
                    delegate: Rectangle {
                        required property int index
                        readonly property bool on: backend.ledgerMonth === index
                        readonly property var row: index > 0 && backend.ledgerYearMonths.length === 12
                                                   ? backend.ledgerYearMonths[index - 1] : null
                        readonly property bool empty: index > 0 && row && row.count === 0
                        visible: backend.ledgerYears.length > 0
                        width: index === 0 ? 46 : 36
                        height: 30
                        radius: 8
                        color: on ? Theme.accentSoft : (mh.hovered ? Theme.rowHover : "transparent")
                        border.color: on ? Theme.accent : "transparent"
                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                        HoverHandler { id: mh }
                        TapHandler { onTapped: backend.ledgerMonth = index }
                        Text {
                            anchors.centerIn: parent
                            text: index === 0 ? "전체" : index
                            color: parent.on ? Theme.text : (parent.empty ? Theme.textDim : Theme.text)
                            opacity: parent.empty ? 0.45 : 1
                            font.pixelSize: 12
                            font.bold: parent.on
                        }
                    }
                }

                }
            }

            RowLayout {
                id: actionRow
                Layout.alignment: Qt.AlignRight
                spacing: 8
                Button {
                    text: "고정"; flat: true; leftPadding: 10; rightPadding: 10
                    Material.foreground: backend.fixedCount > 0 ? Theme.accent : Theme.textDim
                    onClicked: fixedDialog.open()
                    ToolTip.visible: hovered; ToolTip.delay: 500
                    ToolTip.text: "월세·통신비처럼 달마다 똑같이 오가는 돈을 저절로 적습니다"
                }
                Button {
                    text: "예산"; flat: true; leftPadding: 10; rightPadding: 10
                    Material.foreground: backend.hasBudgets ? Theme.accent : Theme.textDim
                    onClicked: budgetDialog.open()
                    ToolTip.visible: hovered; ToolTip.delay: 500
                    ToolTip.text: "분류마다 한 달에 얼마까지 쓸지 정합니다"
                }
                Button {
                    text: "계획에서 가져오기"; flat: true; leftPadding: 10; rightPadding: 10
                    Material.foreground: Theme.accent
                    enabled: backend.itemCount > 0
                    onClicked: backend.importPlanToLedger()
                    ToolTip.visible: hovered; ToolTip.delay: 500
                    ToolTip.text: "계획 항목을 한꺼번에 기록합니다 (이름이 겹치는 것은 건너뜁니다)"
                }
                Button {
                    text: "지난달 복사"; flat: true; leftPadding: 10; rightPadding: 10
                    visible: backend.canCopyPreviousMonth
                    onClicked: backend.copyPreviousMonth()
                    ToolTip.visible: hovered; ToolTip.delay: 500
                    ToolTip.text: "지난달 내역을 이번 달로 복사합니다 (같은 내역은 건너뜀)"
                }
                Button { text: "＋ 내역 추가"; highlighted: true; onClicked: entryDialog.openForAdd(view.defaultDate()) }
                Button {
                    text: "비우기"; flat: true; leftPadding: 10; rightPadding: 10
                    Material.foreground: Theme.red
                    enabled: backend.ledgerYears.length > 0
                    onClicked: clearLedgerDialog.open()
                }
            }
            }

            // 검색 · 수입/지출 · 분류 거르기
            RowLayout {
                Layout.fillWidth: true
                visible: backend.ledgerYears.length > 0
                spacing: 8

                TextField {
                    id: searchField
                    objectName: "ledgerSearch"
                    Layout.preferredWidth: 220
                    placeholderText: "검색 (내용·분류·메모)"
                    text: backend.ledgerQuery
                    onTextEdited: backend.ledgerQuery = text
                }

                Repeater {
                    model: [{ k: "", t: "전체" }, { k: "income", t: "수입" }, { k: "cost", t: "지출" }]
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool on: backend.ledgerKindFilter === modelData.k
                        width: 50; height: 28; radius: 14
                        color: on ? Theme.accent : "transparent"
                        border.color: on ? Theme.accent : Theme.cardBorder
                        TapHandler { onTapped: backend.ledgerKindFilter = modelData.k }
                        Text {
                            anchors.centerIn: parent
                            text: modelData.t
                            color: parent.on ? "#ffffff" : Theme.textDim
                            font.pixelSize: 11
                        }
                    }
                }

                ComboBox {
                    id: catFilter
                    objectName: "ledgerCategoryFilter"
                    Layout.preferredWidth: 150
                    model: backend.ledgerUsedCategories
                    onActivated: backend.ledgerCategoryFilter = String(currentValue)
                    Connections {
                        target: backend
                        function onLedgerChanged() {
                            var want = backend.ledgerCategoryFilter === "" ? "전체" : backend.ledgerCategoryFilter
                            var i = backend.ledgerUsedCategories.indexOf(want)
                            if (i >= 0 && i !== catFilter.currentIndex) catFilter.currentIndex = i
                        }
                    }
                }

                Button {
                    text: "거르기 해제"; flat: true; leftPadding: 8; rightPadding: 8
                    visible: backend.ledgerFiltered
                    Material.foreground: Theme.yellow
                    onClicked: { searchField.text = ""; backend.clearLedgerFilters() }
                }

                Item { Layout.fillWidth: true }

                Text {
                    visible: backend.ledgerFiltered
                    text: "걸러진 합계  " + (backend.ledgerFilteredSummary.net >= 0 ? "+" : "")
                          + backend.won(backend.ledgerFilteredSummary.net)
                    color: backend.ledgerFilteredSummary.net >= 0 ? Theme.green : Theme.red
                    font.pixelSize: 12
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

            // 기록이 없을 때
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: backend.ledgerItems.rowCount() === 0
                spacing: 8
                Item { Layout.fillHeight: true }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: backend.ledgerFiltered ? "조건에 맞는 내역이 없습니다"
                        : backend.ledgerYears.length === 0 ? "아직 기록이 없습니다"
                        : backend.ledgerPeriodText + " 기록이 없습니다"
                    color: Theme.textDim; font.pixelSize: 14
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: backend.ledgerFiltered ? "검색어나 분류를 바꾸거나 '거르기 해제' 를 누르세요."
                                                 : "＋ 내역 추가 로 쓴 돈과 번 돈을 적어 두면 월별·연도별로 합산됩니다."
                    color: Theme.textDim; font.pixelSize: 12
                }
                Item { Layout.fillHeight: true }
            }

            ListView {
                id: entryList
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: backend.ledgerItems.rowCount() > 0
                clip: true
                spacing: 4
                model: backend.ledgerItems
                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.accentSoft }
                }

                section.property: "daySection"
                section.criteria: ViewSection.FullString
                section.delegate: Item {
                    required property string section
                    readonly property var info: backend.ledgerDayInfo(section)
                    width: ListView.view.width - 10
                    height: 26
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4; anchors.rightMargin: 14
                        spacing: 8
                        Text { text: info.label; color: Theme.textDim; font.pixelSize: 11; font.bold: true }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
                        Text {
                            text: (info.net >= 0 ? "+" : "") + backend.won(info.net)
                            color: info.net >= 0 ? Theme.green : Theme.red
                            font.pixelSize: 11
                        }
                    }
                }

                add: Transition {
                    NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.normal }
                    NumberAnimation { property: "x"; from: 24; to: 0; duration: Theme.normal; easing.type: Easing.OutCubic }
                }
                remove: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast }
                }

                delegate: Rectangle {
                    id: entryRow
                    required property string date
                    required property string dateText
                    required property string category
                    required property string name
                    required property real amount
                    required property string amountText
                    required property string kind
                    required property string note
                    required property int sourceRow
                    required property string rule

                    width: ListView.view.width - 10
                    height: 44
                    radius: 8
                    color: rowHover.hovered ? Theme.rowHover : Theme.row
                    Behavior on color { ColorAnimation { duration: Theme.fast } }

                    Rectangle {
                        width: 4; radius: 2
                        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 }
                        color: entryRow.kind === "income" ? Theme.green : Theme.red
                    }

                    HoverHandler { id: rowHover }
                    TapHandler {
                        onDoubleTapped: entryDialog.openForEdit(entryRow.sourceRow, entryRow.date, entryRow.category,
                                                                entryRow.amount, entryRow.name, entryRow.note)
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 20
                        anchors.rightMargin: 10
                        spacing: 10

                        Rectangle {
                            radius: 10
                            color: Theme.accentSoft
                            implicitWidth: catText.implicitWidth + 16
                            implicitHeight: 22
                            Text { id: catText; anchors.centerIn: parent; text: entryRow.category; color: Theme.text; font.pixelSize: 11 }
                        }
                        // 고정 항목이 저절로 적어 준 줄
                        Rectangle {
                            visible: entryRow.rule !== ""
                            radius: 10
                            color: "transparent"
                            border.color: Theme.accent
                            implicitWidth: fixedTag.implicitWidth + 12
                            implicitHeight: 20
                            Text {
                                id: fixedTag
                                anchors.centerIn: parent
                                text: "고정"; color: Theme.accent; font.pixelSize: 10
                            }
                            HoverHandler { id: tagHover }
                            ToolTip.visible: tagHover.hovered
                            ToolTip.text: "고정 항목이 저절로 적은 내역입니다"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Text {
                                text: entryRow.name !== "" ? entryRow.name : entryRow.category
                                color: Theme.text; font.pixelSize: 13; elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                visible: entryRow.note !== ""
                                text: entryRow.note
                                color: Theme.textDim; font.pixelSize: 10; elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                        Text {
                            text: entryRow.amountText
                            color: entryRow.kind === "income" ? Theme.green : Theme.red
                            font.pixelSize: 14; font.bold: true
                        }
                        ToolButton {
                            text: "⟳"; implicitWidth: 28; implicitHeight: 28
                            visible: entryRow.rule === ""
                            Material.foreground: Theme.accent
                            ToolTip.visible: hovered; ToolTip.delay: 700
                            ToolTip.text: "이 내역을 고정 항목으로 올립니다 (다음 달부터 저절로)"
                            onClicked: view.makeFixed(entryRow.sourceRow)
                        }
                        ToolButton {
                            text: "✕"; implicitWidth: 28; implicitHeight: 28
                            Material.foreground: Theme.red
                            ToolTip.visible: hovered; ToolTip.delay: 700
                            ToolTip.text: "이 내역을 삭제합니다"
                            onClicked: view.confirmRemove(entryRow.sourceRow, entryRow.dateText,
                                                         entryRow.name, entryRow.category,
                                                         entryRow.amountText)
                        }
                    }
                }
            }

            Text {
                text: "행 더블클릭: 수정  ·  ⟳: 고정 항목으로  ·  ✕: 삭제"
                color: Theme.textDim; font.pixelSize: 11
            }
        }
    }

    // ───────────── 오른쪽: 집계
    ColumnLayout {
        Layout.preferredWidth: 380
        Layout.maximumWidth: 380
        Layout.fillHeight: true
        spacing: 12

        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: ledgerSumCol.implicitHeight + Theme.pad * 2 + 30
            title: backend.ledgerPeriodText + " 집계"
            ColumnLayout {
                id: ledgerSumCol
                anchors.fill: parent
                spacing: 6
                StatRow { label: "수입"; value: backend.ledgerSummary.income; prefix: "+"; valueColor: Theme.green }
                StatRow { label: "지출"; value: backend.ledgerSummary.cost; prefix: "-"; valueColor: Theme.red }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                StatRow {
                    label: "남은 돈"; value: backend.ledgerSummary.net; emphasis: true
                    valueColor: backend.ledgerSummary.net >= 0 ? Theme.green : Theme.red
                }

                // 지난달(또는 작년) 대비
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 3
                    visible: backend.ledgerPrev.has
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: 8
                        Text {
                            text: backend.ledgerPrev.label + " 대비 지출"
                            color: Theme.textDim; font.pixelSize: 12
                            Layout.fillWidth: true
                        }
                        Text {
                            text: (backend.ledgerPrev.costDiff >= 0 ? "+" : "-")
                                  + backend.won(Math.abs(backend.ledgerPrev.costDiff))
                                  + (backend.ledgerPrev.cost > 0
                                     ? "  (" + (backend.ledgerPrev.costPct >= 0 ? "+" : "")
                                       + backend.ledgerPrev.costPct.toFixed(0) + "%)" : "")
                            color: backend.ledgerPrev.costDiff > 0 ? Theme.red
                                 : backend.ledgerPrev.costDiff < 0 ? Theme.green : Theme.textDim
                            font.pixelSize: 12
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: backend.ledgerPrev.label + " 대비 수입"
                            color: Theme.textDim; font.pixelSize: 12
                            Layout.fillWidth: true
                        }
                        Text {
                            text: (backend.ledgerPrev.incomeDiff >= 0 ? "+" : "-")
                                  + backend.won(Math.abs(backend.ledgerPrev.incomeDiff))
                                  + (backend.ledgerPrev.income > 0
                                     ? "  (" + (backend.ledgerPrev.incomePct >= 0 ? "+" : "")
                                       + backend.ledgerPrev.incomePct.toFixed(0) + "%)" : "")
                            color: backend.ledgerPrev.incomeDiff >= 0 ? Theme.green : Theme.red
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }

        // ───────────── 분류별 예산
        Card {
            id: budgetCard
            readonly property var totals: backend.ledgerBudgetTotals
            readonly property var rows: backend.ledgerBudgets
            Layout.fillWidth: true
            Layout.preferredHeight: budgetCol.implicitHeight + Theme.pad * 2 + 30
            visible: backend.ledgerYears.length > 0
            title: "분류별 예산" + (backend.budgetMonths > 1 ? "  ·  " + backend.budgetMonths + "개월분" : "")

            ColumnLayout {
                id: budgetCol
                anchors.fill: parent
                spacing: 6

                // 예산을 아직 안 정했을 때
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: !backend.hasBudgets
                    spacing: 6
                    Text {
                        text: "분류마다 한 달 한도를 정하면 얼마나 썼는지 막대로 보입니다."
                        color: Theme.textDim; font.pixelSize: 12
                        wrapMode: Text.Wrap; Layout.fillWidth: true; Layout.preferredWidth: 1
                    }
                    Button { text: "예산 정하기"; highlighted: true; onClicked: budgetDialog.open() }
                }

                // 합계
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: backend.hasBudgets
                    spacing: 4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: "합계"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: backend.won(budgetCard.totals.spent) + " / " + backend.won(budgetCard.totals.limit)
                            color: budgetCard.totals.over ? Theme.red : Theme.text
                            font.pixelSize: 13; font.bold: true
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 8; radius: 4
                        color: Theme.row
                        Rectangle {
                            width: Math.min(1, budgetCard.totals.ratio) * parent.width
                            height: parent.height; radius: 4
                            color: budgetCard.totals.over ? Theme.red
                                 : budgetCard.totals.ratio > 0.85 ? Theme.yellow : Theme.green
                            Behavior on width { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
                        }
                    }
                    Text {
                        text: budgetCard.totals.over
                              ? backend.won(-budgetCard.totals.left) + " 넘었습니다"
                              : backend.won(budgetCard.totals.left) + " 남았습니다"
                        color: budgetCard.totals.over ? Theme.red : Theme.textDim
                        font.pixelSize: 11
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; Layout.topMargin: 4 }
                }

                // 분류별
                Repeater {
                    model: budgetCard.rows
                    delegate: ColumnLayout {
                        required property var modelData
                        readonly property bool noLimit: modelData.limit <= 0
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        spacing: 2

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                text: modelData.category
                                color: Theme.text; font.pixelSize: 12
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                            Text {
                                text: noLimit ? backend.won(modelData.spent) + "  (예산 없음)"
                                              : backend.won(modelData.spent) + " / " + backend.won(modelData.limit)
                                color: modelData.over ? Theme.red : (noLimit ? Theme.textDim : Theme.text)
                                font.pixelSize: 11
                            }
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            height: 6; radius: 3
                            color: Theme.row
                            visible: !parent.noLimit
                            Rectangle {
                                width: Math.min(1, modelData.ratio) * parent.width
                                height: parent.height; radius: 3
                                color: modelData.over ? Theme.red
                                     : modelData.ratio > 0.85 ? Theme.yellow : Theme.green
                                Behavior on width { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
                            }
                        }
                    }
                }

                Text {
                    visible: backend.hasBudgets && budgetCard.rows.length === 0
                    text: backend.ledgerPeriodText + " 에는 지출 기록이 없습니다."
                    color: Theme.textDim; font.pixelSize: 11
                }
            }
        }

        // ───────────── 계획 대비 실적
        Card {
            id: pvaCard
            // 계획(요약)이나 가계부가 바뀌면 다시 계산되도록 둘 다 참조한다
            readonly property var pva: (backend.net, backend.ledgerSummary, backend.planVsActual())
            Layout.fillWidth: true
            Layout.preferredHeight: pva.has ? pvaCol.implicitHeight + Theme.pad * 2 + 30 : 0
            visible: pva.has
            title: "계획 대비  ·  " + (pva.scenario || "")

            ColumnLayout {
                id: pvaCol
                anchors.fill: parent
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: ""; Layout.preferredWidth: 52 }
                    Text { text: "계획"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                    Text { text: "실제"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                    Text { text: "차이"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

                Repeater {
                    model: [
                        { label: "수입", plan: pvaCard.pva.planIn,  act: pvaCard.pva.actIn,  diff: pvaCard.pva.inDiff,  good: 1 },
                        { label: "지출", plan: pvaCard.pva.planOut, act: pvaCard.pva.actOut, diff: pvaCard.pva.outDiff, good: -1 },
                        { label: "남은 돈", plan: pvaCard.pva.planNet, act: pvaCard.pva.actNet, diff: pvaCard.pva.netDiff, good: 1 }
                    ]
                    delegate: RowLayout {
                        required property var modelData
                        readonly property bool last: modelData.label === "남은 돈"
                        Layout.fillWidth: true
                        Layout.topMargin: last ? 4 : 0
                        spacing: 6
                        Text {
                            text: modelData.label
                            color: last ? Theme.text : Theme.textDim
                            font.pixelSize: last ? 13 : 12
                            font.bold: last
                            Layout.preferredWidth: 52
                        }
                        Text {
                            text: backend.won(modelData.plan)
                            color: Theme.textDim; font.pixelSize: 11
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            text: backend.won(modelData.act)
                            color: Theme.text; font.pixelSize: last ? 13 : 12; font.bold: last
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            // 수입·남은 돈은 많을수록, 지출은 적을수록 초록
                            text: (modelData.diff >= 0 ? "+" : "-") + backend.won(Math.abs(modelData.diff))
                            color: modelData.diff * modelData.good >= 0 ? Theme.green : Theme.red
                            font.pixelSize: last ? 13 : 12; font.bold: last
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; Layout.topMargin: 4 }
                Text {
                    text: pvaCard.pva.outPct === 0 ? "계획한 지출과 같습니다"
                        : pvaCard.pva.outDiff < 0
                          ? "계획보다 " + Math.abs(pvaCard.pva.outPct).toFixed(0) + "% 덜 썼습니다"
                          : "계획보다 " + pvaCard.pva.outPct.toFixed(0) + "% 더 썼습니다"
                    color: pvaCard.pva.outDiff <= 0 ? Theme.green : Theme.red
                    font.pixelSize: 12
                    Layout.topMargin: 2
                }
                Text {
                    text: "분류 체계가 서로 달라 총액만 비교합니다."
                         + (pvaCard.pva.months > 1 ? "  기준일 이후 " + pvaCard.pva.months + "개월분입니다." : "")
                    color: Theme.textDim; font.pixelSize: 10
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 392
            title: backend.ledgerYear !== "" ? backend.ledgerYear + "년 월별" : "월별"
            ColumnLayout {
                anchors.fill: parent
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: "월"; color: Theme.textDim; font.pixelSize: 11; Layout.preferredWidth: 28 }
                    Text { text: "수입"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                    Text { text: "지출"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                    Text { text: "남은 돈"; color: Theme.textDim; font.pixelSize: 11; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

                Repeater {
                    model: backend.ledgerYearMonths
                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool on: backend.ledgerMonth === modelData.month
                        Layout.fillWidth: true
                        height: 22
                        radius: 5
                        color: on ? Theme.accentSoft : (mrHover.hovered ? Theme.rowHover : "transparent")
                        opacity: modelData.count === 0 ? 0.4 : 1
                        HoverHandler { id: mrHover }
                        TapHandler { onTapped: backend.ledgerMonth = modelData.month }
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 4; anchors.rightMargin: 4
                            spacing: 6
                            Text { text: modelData.label; color: Theme.text; font.pixelSize: 11; Layout.preferredWidth: 28 }
                            Text {
                                text: modelData.income > 0 ? backend.won(modelData.income) : "-"
                                color: Theme.green; font.pixelSize: 11
                                Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                            }
                            Text {
                                text: modelData.cost > 0 ? backend.won(modelData.cost) : "-"
                                color: Theme.red; font.pixelSize: 11
                                Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                            }
                            Text {
                                text: modelData.count === 0 ? "-" : backend.won(modelData.net)
                                color: modelData.net >= 0 ? Theme.text : Theme.red
                                font.pixelSize: 11; font.bold: true
                                Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                            }
                        }
                    }
                }
            }
        }

        Card {
            id: ledgerPie
            property string kind: "cost"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 260
            title: "분류별"

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Item { Layout.fillWidth: true }
                    Repeater {
                        model: [{ k: "cost", t: "지출" }, { k: "income", t: "수입" }]
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool on: ledgerPie.kind === modelData.k
                            width: 54; height: 24; radius: 12
                            color: on ? Theme.accent : "transparent"
                            border.color: on ? Theme.accent : Theme.cardBorder
                            TapHandler { onTapped: ledgerPie.kind = modelData.k }
                            Text {
                                anchors.centerIn: parent
                                text: modelData.t
                                color: parent.on ? "#ffffff" : Theme.textDim
                                font.pixelSize: 11
                            }
                        }
                    }
                }

                PieChart {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    slices: (backend.ledgerPeriod, backend.ledgerSummary, backend.ledgerByCategory(ledgerPie.kind))
                    total: ledgerPie.kind === "income" ? backend.ledgerSummary.income : backend.ledgerSummary.cost
                    centerTitle: ledgerPie.kind === "income" ? "수입" : "지출"
                }
            }
        }

        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: yearCol.implicitHeight + Theme.pad * 2 + 30
            visible: backend.ledgerYearTotals.length > 1
            title: "연도별"
            ColumnLayout {
                id: yearCol
                anchors.fill: parent
                spacing: 4
                Repeater {
                    model: backend.ledgerYearTotals
                    delegate: RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: modelData.year + "년"; color: Theme.text; font.pixelSize: 12; Layout.preferredWidth: 60 }
                        Text {
                            text: "+" + backend.won(modelData.income)
                            color: Theme.green; font.pixelSize: 11
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            text: "-" + backend.won(modelData.cost)
                            color: Theme.red; font.pixelSize: 11
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                        Text {
                            text: backend.won(modelData.net)
                            color: modelData.net >= 0 ? Theme.text : Theme.red
                            font.pixelSize: 12; font.bold: true
                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                        }
                    }
                }
            }
        }
    }
}
