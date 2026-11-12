import QtQuick
import QtQuick.Layouts

// 달마다 수입·지출을 나란한 막대로, 그 위에 수지를 점선으로.
// rows: [{label, income, cost, net, count, isThis}]
//
// 그리기는 평범한 Rectangle 이다 (장면 그래프가 GPU 로 올린다). 막대 몇십 개라
// Shapes 까지 갈 일이 아니다.
Item {
    id: chart
    property var rows: []
    property int hovered: -1

    readonly property int count: rows ? rows.length : 0
    readonly property real maxValue: {
        var m = 0
        for (var i = 0; i < chart.count; i++) {
            m = Math.max(m, Number(rows[i].income) || 0, Number(rows[i].cost) || 0)
        }
        return m
    }
    readonly property real labelH: 18
    readonly property real plotH: Math.max(10, height - labelH - 6)

    // 값이 바뀌면 막대가 아래에서 자란다
    property real reveal: 1.0
    onRowsChanged: { revealAnim.stop(); reveal = 0; revealAnim.restart() }
    NumberAnimation {
        id: revealAnim
        target: chart; property: "reveal"; from: 0; to: 1
        duration: Theme.slow; easing.type: Easing.OutCubic
    }

    Text {
        anchors.centerIn: parent
        visible: chart.maxValue <= 0
        text: "아직 가계부 기록이 없습니다"
        color: Theme.textDim; font.pixelSize: 12
    }

    Row {
        id: plot
        anchors.fill: parent
        visible: chart.maxValue > 0
        spacing: 0

        Repeater {
            model: chart.rows
            delegate: Item {
                id: col
                required property var modelData
                required property int index
                width: plot.width / Math.max(1, chart.count)
                height: plot.height

                readonly property bool on: chart.hovered === col.index
                readonly property real incomeH: chart.maxValue > 0
                    ? chart.plotH * (Number(modelData.income) || 0) / chart.maxValue * chart.reveal : 0
                readonly property real costH: chart.maxValue > 0
                    ? chart.plotH * (Number(modelData.cost) || 0) / chart.maxValue * chart.reveal : 0

                Rectangle {
                    anchors.fill: parent
                    anchors.bottomMargin: chart.labelH
                    radius: 6
                    color: col.on ? Theme.rowHover : (modelData.isThis ? Theme.accentSoft : "transparent")
                    opacity: modelData.isThis && !col.on ? 0.35 : 1
                }

                // 수입 · 지출 막대
                Row {
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: chart.labelH
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 3
                    Rectangle {
                        width: Math.max(4, col.width * 0.22)
                        height: Math.max(modelData.income > 0 ? 2 : 0, col.incomeH)
                        radius: 3
                        color: Theme.green
                        opacity: col.on ? 1 : 0.85
                    }
                    Rectangle {
                        width: Math.max(4, col.width * 0.22)
                        height: Math.max(modelData.cost > 0 ? 2 : 0, col.costH)
                        radius: 3
                        color: Theme.red
                        opacity: col.on ? 1 : 0.85
                    }
                }

                Text {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: modelData.label
                    color: modelData.isThis || col.on ? Theme.text : Theme.textDim
                    font.pixelSize: 10
                    font.bold: modelData.isThis === true
                }

                HoverHandler {
                    onHoveredChanged: chart.hovered = hovered ? col.index : -1
                }
            }
        }
    }

    // 마우스가 올라간 달
    Rectangle {
        visible: chart.hovered >= 0 && chart.hovered < chart.count
        z: 2
        radius: 8
        color: Theme.card
        border.color: Theme.cardBorder
        width: tipCol.implicitWidth + 16
        height: tipCol.implicitHeight + 12
        y: 2
        x: {
            var w = plot.width / Math.max(1, chart.count)
            var want = (chart.hovered + 0.5) * w - width / 2
            return Math.max(0, Math.min(chart.width - width, want))
        }

        ColumnLayout {
            id: tipCol
            anchors.centerIn: parent
            spacing: 1
            readonly property var row: chart.hovered >= 0 && chart.hovered < chart.count
                                       ? chart.rows[chart.hovered] : null
            Text {
                text: tipCol.row ? tipCol.row.ym : ""
                color: Theme.text; font.pixelSize: 11; font.bold: true
            }
            Text {
                text: tipCol.row ? "수입 +" + backend.won(tipCol.row.income) : ""
                color: Theme.green; font.pixelSize: 11
            }
            Text {
                text: tipCol.row ? "지출 -" + backend.won(tipCol.row.cost) : ""
                color: Theme.red; font.pixelSize: 11
            }
            Text {
                text: tipCol.row ? "수지 " + (tipCol.row.net >= 0 ? "+" : "") + backend.won(tipCol.row.net) : ""
                color: tipCol.row && tipCol.row.net >= 0 ? Theme.green : Theme.red
                font.pixelSize: 11; font.bold: true
            }
        }
    }
}
