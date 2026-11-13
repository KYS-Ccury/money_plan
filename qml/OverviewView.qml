import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 한눈에 보기: 계획(자본금)과 가계부를 한 화면에 모아 보여 준다.
// 숫자는 모두 다른 화면이 쓰는 백엔드 값 그대로다 — 여기서 따로 계산하지 않는다.
Flickable {
    id: view
    objectName: "overviewView"

    contentWidth: width
    contentHeight: col.implicitHeight + Theme.pad * 2
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

    // ── 이 화면은 '보여 주기만' 한다 ──
    // 백엔드에 바로 바인딩해 두면 슬라이더를 한 픽셀 끌 때마다 카드 열몇 개가
    // 통째로 다시 계산·배치된다. 그래서 값을 스냅샷으로 떠서 쓰고, 그 스냅샷은
    // 마지막 변화에서 잠깐 지난 뒤 한 번만 새로 뜬다.
    property var plan: backend.overviewPlan
    property var led: backend.overviewLedger
    property var now: backend.overviewThisMonth
    property var trendValues: []
    property var trendSeries: []
    property var goalAmounts: []
    property var bars: []
    property var budgets: []
    property var scenarios: []

    // 창이 좁으면 두 칸짜리 줄을 한 칸으로 접는다
    readonly property bool wide: width > 1000
    readonly property int horizon: Math.max(12, plan.months)

    function refresh() {
        view.plan = backend.overviewPlan
        view.led = backend.overviewLedger
        view.now = backend.overviewThisMonth
        view.bars = backend.overviewMonths
        view.budgets = backend.overviewBudgets
        view.scenarios = backend.compareRows()
        view.goalAmounts = backend.goalAmounts
        var h = Math.max(12, view.plan.months)
        view.trendValues = backend.trendFor(h)
        var ss = backend.compareTrends(h)
        for (var i = 0; i < ss.length; i++)
            ss[i].color = Theme.scenarioColor(ss[i].index)
        view.trendSeries = ss
        pieCard.reload()
        trendCard.reload()
    }

    Timer {
        id: refreshTimer
        interval: 250            // 손을 떼고 나서 한 번만 (끄는 동안은 기다린다)
        onTriggered: view.refresh()
    }

    Connections {
        target: backend
        function onSummaryChanged() { refreshTimer.restart() }
        function onLedgerChanged() { refreshTimer.restart() }
        function onBudgetsChanged() { refreshTimer.restart() }
    }

    Component.onCompleted: view.refresh()

    // 한 칸 (제목 · 큰 숫자 · 설명)
    component Tile: Rectangle {
        id: tile
        property string label: ""
        property string value: ""
        property string sub: ""
        property color valueColor: Theme.text
        Layout.fillWidth: true
        implicitHeight: 86
        radius: Theme.radius
        color: Theme.card
        border.color: Theme.cardBorder
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 2
            Text { text: tile.label; color: Theme.textDim; font.pixelSize: 12 }
            Text {
                text: tile.value; color: tile.valueColor
                font.pixelSize: 20; font.bold: true
                elide: Text.ElideRight; Layout.fillWidth: true
            }
            Text {
                text: tile.sub; color: Theme.textDim; font.pixelSize: 11
                elide: Text.ElideRight; Layout.fillWidth: true
                visible: text !== ""
            }
        }
    }

    ColumnLayout {
        id: col
        width: view.width - Theme.pad * 2
        x: Theme.pad
        y: Theme.pad
        spacing: 12

        // ───────────── 첫 줄: 가장 중요한 네 숫자
        GridLayout {
            Layout.fillWidth: true
            columns: view.wide ? 4 : 2
            columnSpacing: 12
            rowSpacing: 12

            Tile {
                label: "지금 보유 자금"
                value: backend.won(view.plan.capital)
                sub: view.plan.scenario + "  ·  항목 " + view.plan.itemCount + "개"
                valueColor: Theme.green
            }
            Tile {
                label: view.plan.months + "개월 후 순 자본"
                value: backend.won(view.plan.net)
                sub: view.plan.basis + " ~ " + view.plan.end
                valueColor: view.plan.net >= 0 ? Theme.green : Theme.red
            }
            Tile {
                label: view.plan.target > 0 ? "목표까지" : "목표"
                value: view.plan.target <= 0 ? "정하지 않음"
                       : (view.plan.gap >= 0 ? "달성 (+" + backend.won(view.plan.gap) + ")"
                                             : backend.won(-view.plan.gap) + " 부족")
                sub: view.plan.target <= 0 ? "계획 화면에서 목표 금액을 정할 수 있습니다"
                     : (view.plan.goalMonth >= 0
                        ? view.plan.goalMonth + "개월 뒤 (" + view.plan.goalDateText + ") 도달"
                        : "지금 계획으로는 기간 안에 닿지 않습니다")
                valueColor: view.plan.target <= 0 ? Theme.textDim
                            : (view.plan.gap >= 0 ? Theme.green : Theme.yellow)
            }
            Tile {
                label: view.now.label + " 가계부"
                value: view.now.count === 0 ? "기록 없음"
                       : (view.now.net >= 0 ? "+" : "") + backend.won(view.now.net)
                sub: view.now.count === 0 ? "가계부 화면에서 적을 수 있습니다"
                     : "수입 " + backend.won(view.now.income) + "  ·  지출 " + backend.won(view.now.cost)
                valueColor: view.now.count === 0 ? Theme.textDim
                            : (view.now.net >= 0 ? Theme.green : Theme.red)
            }
        }

        // 경고 줄 (돈이 비는 달 · 예산 초과)
        Rectangle {
            Layout.fillWidth: true
            visible: view.plan.shortfallMonth >= 0
            implicitHeight: 38
            radius: 8
            color: Theme.redSoft
            border.color: Theme.red
            Text {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left; anchors.leftMargin: 12
                text: "돈이 비는 때가 있습니다 — " + view.plan.shortfallText
                      + " (" + view.plan.shortfallMonth + "개월 뒤) 부터 순 자본이 마이너스입니다."
                color: Theme.red; font.pixelSize: 12
            }
        }

        // ───────────── 순 자본 추이
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: 300
            title: "순 자본 추이  ·  " + view.horizon + "개월"

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                TrendChart {
                    objectName: "overviewTrend"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    values: view.trendValues
                    lineColor: Theme.scenarioColor(backend.activeScenario)
                    series: view.trendSeries
                    target: view.plan.target
                    goalMonth: view.plan.goalMonth
                    shortfallMonth: view.plan.shortfallMonth
                    goals: view.goalAmounts
                    markers: [6, 12, 24, 36].filter(function(m) { return m <= view.horizon })
                }
            }
        }

        // ───────────── 가계부: 최근 12개월 막대 + 지출 구성
        GridLayout {
            Layout.fillWidth: true
            columns: view.wide ? 2 : 1
            columnSpacing: 12
            rowSpacing: 12

            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 280
                Layout.columnSpan: view.wide ? 1 : 1
                title: "최근 12개월 수입·지출"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Text {
                            text: view.led.has ? "기록 " + view.led.months + "달  ·  월평균 수지" : "기록 없음"
                            color: Theme.textDim; font.pixelSize: 12
                        }
                        Text {
                            visible: view.led.has
                            text: (view.led.avgNet >= 0 ? "+" : "") + backend.won(view.led.avgNet)
                            color: view.led.avgNet >= 0 ? Theme.green : Theme.red
                            font.pixelSize: 13; font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: view.led.has
                            text: "가장 좋았던 달 " + view.led.bestLabel + "  ·  힘들었던 달 " + view.led.worstLabel
                            color: Theme.textDim; font.pixelSize: 11
                        }
                    }

                    BarChart {
                        objectName: "overviewBars"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        rows: view.bars
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Rectangle { width: 10; height: 10; radius: 2; color: Theme.green }
                        Text { text: "수입"; color: Theme.textDim; font.pixelSize: 11 }
                        Rectangle { width: 10; height: 10; radius: 2; color: Theme.red }
                        Text { text: "지출"; color: Theme.textDim; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: view.led.has
                            text: "12개월 합계  수입 " + backend.won(view.led.income)
                                  + "  ·  지출 " + backend.won(view.led.cost)
                            color: Theme.textDim; font.pixelSize: 11
                        }
                    }
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 280
                title: "최근 12개월 " + (pieCard.kind === "cost" ? "지출" : "수입") + " 구성"

                ColumnLayout {
                    id: pieCard
                    property string kind: "cost"
                    property var slices: []
                    function reload() { pieCard.slices = backend.overviewByCategory(pieCard.kind) }
                    onKindChanged: pieCard.reload()
                    anchors.fill: parent
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Repeater {
                            model: [{ k: "cost", t: "지출" }, { k: "income", t: "수입" }]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on: pieCard.kind === modelData.k
                                width: 50; height: 26; radius: 13
                                color: on ? Theme.accent : "transparent"
                                border.color: on ? Theme.accent : Theme.cardBorder
                                TapHandler { onTapped: pieCard.kind = modelData.k }
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.t
                                    color: parent.on ? "#ffffff" : Theme.textDim
                                    font.pixelSize: 11
                                }
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }

                    PieChart {
                        objectName: "overviewPie"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        slices: pieCard.slices
                        total: pieCard.kind === "cost" ? view.led.cost : view.led.income
                        centerTitle: "12개월"
                    }
                }
            }
        }

        // ───────────── 분류별 추이
        Card {
            id: trendCard
            property string kind: "cost"
            property string category: ""
            property var cats: []
            property var info: ({ "has": false, "rows": [] })

            function reload() {
                trendCard.cats = backend.trendCategories(trendCard.kind)
                var ok = false
                for (var i = 0; i < trendCard.cats.length; i++)
                    if (trendCard.cats[i].category === trendCard.category) ok = true
                if (!ok)            // 아직 안 골랐거나 없어진 분류면 가장 많이 쓴 것으로
                    trendCard.category = trendCard.cats.length > 0 ? trendCard.cats[0].category : ""
                trendCard.info = backend.categoryTrend(trendCard.category, trendCard.kind)
            }
            onKindChanged: trendCard.reload()
            onCategoryChanged: trendCard.info = backend.categoryTrend(trendCard.category,
                                                                      trendCard.kind)

            Layout.fillWidth: true
            Layout.preferredHeight: 300
            visible: view.led.has
            title: "분류별 추이  ·  최근 12개월"

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Repeater {
                        model: [{ k: "cost", t: "지출" }, { k: "income", t: "수입" }]
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool on: trendCard.kind === modelData.k
                            width: 50; height: 26; radius: 13
                            color: on ? Theme.accent : "transparent"
                            border.color: on ? Theme.accent : Theme.cardBorder
                            TapHandler { onTapped: trendCard.kind = modelData.k }
                            Text {
                                anchors.centerIn: parent
                                text: modelData.t
                                color: parent.on ? "#ffffff" : Theme.textDim
                                font.pixelSize: 11
                            }
                        }
                    }

                    Item { width: 4 }

                    // 많이 쓴 분류부터 (여덟 개까지)
                    Flow {
                        Layout.fillWidth: true
                        spacing: 6
                        Repeater {
                            model: trendCard.cats.slice(0, 8)
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on: trendCard.category === modelData.category
                                objectName: "trendCat_" + modelData.category
                                width: catLabel.implicitWidth + 18
                                height: 26; radius: 13
                                color: on ? Theme.accentSoft : "transparent"
                                border.color: on ? Theme.accent : Theme.cardBorder
                                TapHandler { onTapped: trendCard.category = modelData.category }
                                Text {
                                    id: catLabel
                                    anchors.centerIn: parent
                                    text: modelData.category
                                    color: parent.on ? Theme.text : Theme.textDim
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }
                }

                // 늘고 있는지 줄고 있는지
                RowLayout {
                    Layout.fillWidth: true
                    visible: trendCard.info.has
                    spacing: 10
                    Text {
                        text: trendCard.category
                        color: Theme.text; font.pixelSize: 14; font.bold: true
                    }
                    Text {
                        text: trendCard.info.before > 0
                              ? (trendCard.info.up ? "늘고 있습니다  " : "줄고 있습니다  ")
                                + (trendCard.info.changePct >= 0 ? "+" : "")
                                + trendCard.info.changePct.toFixed(0) + "%"
                              : "견줄 지난 석 달이 없습니다"
                        color: trendCard.info.before <= 0 ? Theme.textDim
                             : (trendCard.kind === "income"
                                ? (trendCard.info.up ? Theme.green : Theme.red)
                                : (trendCard.info.up ? Theme.red : Theme.green))
                        font.pixelSize: 13
                    }
                    Text {
                        visible: trendCard.info.before > 0
                        text: "최근 석 달 " + backend.won(trendCard.info.recent)
                              + " / 그 앞 석 달 " + backend.won(trendCard.info.before)
                        color: Theme.textDim; font.pixelSize: 11
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "달 평균 " + backend.won(trendCard.info.avg)
                              + "  ·  12개월 합계 " + backend.won(trendCard.info.total)
                        color: Theme.textDim; font.pixelSize: 11
                    }
                }

                BarChart {
                    objectName: "trendBars"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    rows: trendCard.info.rows || []
                }

                Text {
                    visible: !trendCard.info.has
                    Layout.fillWidth: true
                    text: "고른 분류로 적어 둔 내역이 최근 12개월에 없습니다."
                    color: Theme.textDim; font.pixelSize: 12
                }
            }
        }

        // ───────────── 계획 대비 실적 · 이번 달 예산 · 고정
        GridLayout {
            Layout.fillWidth: true
            columns: view.wide ? 2 : 1
            columnSpacing: 12
            rowSpacing: 12

            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 250
                title: "이번 달 계획 대비 실적"

                ColumnLayout {
                    id: vsCol
                    anchors.fill: parent
                    spacing: 6
                    readonly property var vs: view.now.vsPlan

                    Text {
                        visible: !vsCol.vs.has
                        Layout.fillWidth: true
                        text: "이번 달에 걸친 계획이 없거나 가계부 기록이 없어 비교할 수 없습니다."
                        color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
                    }

                    Text {
                        visible: vsCol.vs.has
                        text: vsCol.vs.scenario + " 시나리오의 이번 달 계획과 견줍니다"
                        color: Theme.textDim; font.pixelSize: 11
                    }
                    StatRow {
                        visible: vsCol.vs.has
                        label: "계획 지출"; value: vsCol.vs.planOut; prefix: "-"; valueColor: Theme.textDim
                    }
                    StatRow {
                        visible: vsCol.vs.has
                        label: "실제 지출"; value: vsCol.vs.actOut; prefix: "-"
                        valueColor: vsCol.vs.outDiff <= 0 ? Theme.green : Theme.red
                    }
                    StatRow {
                        visible: vsCol.vs.has
                        label: "계획 수입"; value: vsCol.vs.planIn; prefix: "+"; valueColor: Theme.textDim
                    }
                    StatRow {
                        visible: vsCol.vs.has
                        label: "실제 수입"; value: vsCol.vs.actIn; prefix: "+"
                        valueColor: vsCol.vs.inDiff >= 0 ? Theme.green : Theme.red
                    }
                    Rectangle {
                        visible: vsCol.vs.has
                        Layout.fillWidth: true; height: 1; color: Theme.cardBorder
                        Layout.topMargin: 2; Layout.bottomMargin: 2
                    }
                    Text {
                        visible: vsCol.vs.has
                        Layout.fillWidth: true
                        text: vsCol.vs.outDiff <= 0
                              ? "계획보다 " + backend.won(-vsCol.vs.outDiff) + " 덜 썼습니다"
                              : "계획보다 " + backend.won(vsCol.vs.outDiff) + " 더 썼습니다"
                        color: vsCol.vs.outDiff <= 0 ? Theme.green : Theme.red
                        font.pixelSize: 13; font.bold: true
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            Card {
                Layout.fillWidth: true
                Layout.preferredHeight: 250
                title: "이번 달 예산  ·  고정 지출·수입"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 6

                    Text {
                        visible: view.budgets.length === 0
                        Layout.fillWidth: true
                        text: "정해 둔 예산이 없습니다. 가계부 화면의 '예산' 에서 분류마다 한 달 한도를 정할 수 있습니다."
                        color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
                    }

                    Repeater {
                        // 많이 쓴 순으로 네 개까지만. 전부는 가계부 화면에서 본다.
                        model: view.budgets.slice(0, 4)
                        delegate: ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 30
                            spacing: 2
                            RowLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: modelData.category; color: Theme.text; font.pixelSize: 12
                                    Layout.fillWidth: true; elide: Text.ElideRight
                                }
                                Text {
                                    text: backend.won(modelData.spent) + " / " + backend.won(modelData.limit)
                                    color: modelData.over ? Theme.red
                                           : (modelData.ratio >= 0.85 ? Theme.yellow : Theme.textDim)
                                    font.pixelSize: 11
                                }
                            }
                            Rectangle {
                                Layout.fillWidth: true
                                height: 6; radius: 3; color: Theme.row
                                Rectangle {
                                    width: parent.width * Math.min(1, modelData.ratio)
                                    height: parent.height; radius: 3
                                    color: modelData.over ? Theme.red
                                           : (modelData.ratio >= 0.85 ? Theme.yellow : Theme.green)
                                    Behavior on width { NumberAnimation { duration: Theme.normal } }
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: backend.fixedTotals.count > 0
                                  ? "고정 " + backend.fixedTotals.count + "건 · 달마다"
                                  : "고정 항목 없음"
                            color: Theme.textDim; font.pixelSize: 12
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: backend.fixedTotals.count > 0
                            text: (backend.fixedTotals.net >= 0 ? "+" : "") + backend.won(backend.fixedTotals.net)
                            color: backend.fixedTotals.net >= 0 ? Theme.green : Theme.red
                            font.pixelSize: 14; font.bold: true
                        }
                    }
                }
            }
        }

        // ───────────── 시나리오 비교
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: scenCol.implicitHeight + Theme.pad * 2 + 30
            visible: backend.scenarioCount > 1
            title: "시나리오 비교  ·  " + view.plan.months + "개월 후"

            ColumnLayout {
                id: scenCol
                anchors.fill: parent
                spacing: 4

                Repeater {
                    model: view.scenarios
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 34
                        radius: 8
                        color: modelData.active ? Theme.accentSoft : Theme.row
                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10; anchors.rightMargin: 10
                            spacing: 8
                            Rectangle {
                                width: 8; height: 8; radius: 4
                                color: Theme.scenarioColor(modelData.index)
                            }
                            Text {
                                text: modelData.name; color: Theme.text; font.pixelSize: 12
                                font.bold: modelData.active
                                Layout.preferredWidth: 140; elide: Text.ElideRight
                            }
                            Text {
                                text: modelData.goalText; color: Theme.textDim; font.pixelSize: 11
                                Layout.fillWidth: true; elide: Text.ElideRight
                            }
                            Text {
                                text: (modelData.diff === 0 ? "기준" :
                                       (modelData.diff > 0 ? "+" : "-") + backend.won(Math.abs(modelData.diff)))
                                color: modelData.diff === 0 ? Theme.textDim
                                       : (modelData.diff > 0 ? Theme.green : Theme.red)
                                font.pixelSize: 11
                            }
                            Text {
                                text: backend.won(modelData.net)
                                color: modelData.net >= 0 ? Theme.text : Theme.red
                                font.pixelSize: 13; font.bold: true
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: "계획 쪽 숫자는 지금 고른 시나리오(" + view.plan.scenario + ") 기준이고, "
                  + "가계부 쪽은 이번 달까지 최근 12개월입니다."
            color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap
        }
    }
}
