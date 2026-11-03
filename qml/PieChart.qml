import QtQuick
import QtQuick.Layouts

// 도넛형 비중 그래프 + 범례. slices: [{label, value, share, color}]
Item {
    id: chart
    property var slices: []
    property string centerTitle: ""
    property real total: 0
    property real reveal: 1.0            // 0 → 1 로 원이 그려지는 애니메이션
    property int hovered: -1

    readonly property var palette: [Theme.accent, Theme.green, Theme.yellow, Theme.red, "#b57bee", "#4fc3dc", "#ff9f5a", "#8a90a3"]

    onSlicesChanged: { reveal = 0; revealAnim.restart(); canvas.requestPaint() }
    onRevealChanged: canvas.requestPaint()
    onHoveredChanged: canvas.requestPaint()
    NumberAnimation { id: revealAnim; target: chart; property: "reveal"; from: 0; to: 1; duration: 800; easing.type: Easing.OutCubic }

    function colorOf(i) { return (slices[i] && slices[i].color) ? slices[i].color : palette[i % palette.length] }

    RowLayout {
        anchors.fill: parent
        spacing: 14

        Item {
            id: pieArea
            Layout.preferredWidth: Math.min(parent.height, 190)
            Layout.fillHeight: true

            Canvas {
                id: canvas
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    var cx = width / 2, cy = height / 2
                    var R = Math.min(width, height) / 2 - 6, r = R * 0.6
                    var s = chart.slices || []
                    var total = 0
                    for (var i = 0; i < s.length; i++) total += Number(s[i].value) || 0
                    // 배경 링
                    ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.arc(cx, cy, r, Math.PI * 2, 0, true)
                    ctx.closePath(); ctx.fillStyle = "#1c2030"; ctx.fill()
                    if (total <= 0) return
                    var a0 = -Math.PI / 2, sweepTotal = Math.PI * 2 * chart.reveal
                    for (i = 0; i < s.length; i++) {
                        var frac = (Number(s[i].value) || 0) / total
                        var a1 = a0 + frac * Math.PI * 2
                        var drawEnd = Math.min(a1, -Math.PI / 2 + sweepTotal)
                        if (drawEnd <= a0) break
                        var grow = chart.hovered === i ? 5 : 0
                        ctx.beginPath()
                        ctx.arc(cx, cy, R + grow, a0, drawEnd)
                        ctx.arc(cx, cy, r, drawEnd, a0, true)
                        ctx.closePath()
                        ctx.fillStyle = chart.colorOf(i); ctx.fill()
                        ctx.strokeStyle = "#171a23"; ctx.lineWidth = 2; ctx.stroke()
                        a0 = a1
                    }
                }
                // 마우스가 올라간 조각 찾기
                HoverHandler {
                    onPointChanged: {
                        var cx = canvas.width / 2, cy = canvas.height / 2
                        var dx = point.position.x - cx, dy = point.position.y - cy
                        var d = Math.sqrt(dx * dx + dy * dy)
                        var R = Math.min(canvas.width, canvas.height) / 2 - 6
                        if (d > R + 6 || d < R * 0.6) { chart.hovered = -1; return }
                        var ang = Math.atan2(dy, dx) + Math.PI / 2
                        if (ang < 0) ang += Math.PI * 2
                        var s = chart.slices || [], total = 0, acc = 0
                        for (var i = 0; i < s.length; i++) total += Number(s[i].value) || 0
                        for (i = 0; i < s.length; i++) {
                            acc += (Number(s[i].value) || 0) / total * Math.PI * 2
                            if (ang <= acc) { chart.hovered = i; return }
                        }
                        chart.hovered = -1
                    }
                    onHoveredChanged: if (!hovered) chart.hovered = -1
                }
            }

            // 가운데 글자: 호버 중이면 그 조각, 아니면 합계
            Column {
                anchors.centerIn: parent
                spacing: 2
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: chart.hovered >= 0 && chart.slices[chart.hovered] ? chart.slices[chart.hovered].label : chart.centerTitle
                    color: Theme.textDim; font.pixelSize: 11
                    elide: Text.ElideRight; width: pieArea.width * 0.5; horizontalAlignment: Text.AlignHCenter
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: chart.hovered >= 0 && chart.slices[chart.hovered]
                          ? (chart.slices[chart.hovered].share * 100).toFixed(1) + "%"
                          : backend.won(chart.total)
                    color: Theme.text; font.pixelSize: chart.hovered >= 0 ? 18 : 12; font.bold: true
                }
            }
        }

        // 범례
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 4
            Repeater {
                model: chart.slices
                delegate: RowLayout {
                    required property int index
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8
                    opacity: chart.hovered < 0 || chart.hovered === index ? 1 : 0.45
                    Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                    HoverHandler { onHoveredChanged: chart.hovered = hovered ? index : -1 }
                    Rectangle { width: 10; height: 10; radius: 3; color: chart.colorOf(index) }
                    Text { text: modelData.label; color: Theme.text; font.pixelSize: 12; elide: Text.ElideRight; Layout.fillWidth: true }
                    Text { text: (modelData.share * 100).toFixed(1) + "%"; color: Theme.text; font.pixelSize: 12; font.bold: true }
                    Text { text: backend.won(modelData.value); color: Theme.textDim; font.pixelSize: 11 }
                }
            }
            Text {
                visible: !chart.slices || chart.slices.length === 0
                text: "표시할 항목이 없습니다"
                color: Theme.textDim; font.pixelSize: 12
            }
            Item { Layout.fillHeight: true }
        }
    }
}
