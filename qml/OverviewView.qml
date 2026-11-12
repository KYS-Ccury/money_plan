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

    readonly property var plan: backend.overviewPlan
    readonly property var led: backend.overviewLedger
    readonly property var now: backend.overviewThisMonth
    // 창이 좁으면 두 칸짜리 줄을 한 칸으로 접는다
    readonly property bool wide: width > 1000
    readonly property int horizon: Math.max(12, plan.months)

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
                    values: (backend.net, backend.trendFor(view.horizon))
                    lineColor: Theme.scenarioColor(backend.activeScenario)
                    series: {
                        var dep = backend.net + backend.scenarioCount
                        var s = backend.compareTrends(view.horizon)
                        for (var i = 0; i < s.length; i++) s[i].color = Theme.scenarioColor(s[i].index)
                        return s
                    }
                    target: backend.target
                    goalMonth: backend.goalMonth
                    shortfallMonth: view.plan.shortfallMonth
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
                        rows: backend.overviewMonths
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
                        // ledgerSummary 를 함께 읽어 가계부가 바뀌면 다시 계산되게 한다
                        // (함수 호출만으로는 QML 이 무엇에 기대는지 알 수 없다)
                        slices: (backend.ledgerSummary, backend.overviewByCategory(pieCard.kind))
                        total: pieCard.kind === "cost" ? view.led.cost : view.led.income
                        centerTitle: "12개월"
                    }
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
                        visible: backend.overviewBudgets.length === 0
                        Layout.fillWidth: true
                        text: "정해 둔 예산이 없습니다. 가계부 화면의 '예산' 에서 분류마다 한 달 한도를 정할 수 있습니다."
                        color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
                    }

                    Repeater {
                        // 많이 쓴 순으로 네 개까지만. 전부는 가계부 화면에서 본다.
                        model: backend.overviewBudgets.slice(0, 4)
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
                    model: (backend.net, backend.compareRows())
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
