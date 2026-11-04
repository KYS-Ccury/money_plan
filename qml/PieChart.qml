import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes

// 도넛형 비중 그래프 + 범례. slices: [{label, value, share, color}]
//
// 그리기는 QtQuick.Shapes 가 맡는다 (장면 그래프가 GPU 로 그린다).
// 예전에는 Canvas 로 그렸는데, Canvas 는 매번 CPU 에서 그림을 그려
// 텍스처로 올리는 방식이라 값이 바뀔 때마다 CPU 가 일했다.
Item {
    id: chart
    property var slices: []
    property string centerTitle: ""
    property real total: 0
    property real reveal: 1.0            // 0 → 1 로 원이 그려지는 애니메이션
    property int hovered: -1

    // 링 크기는 한 곳에서 정한다 (그리기와 마우스 판정이 같은 값을 써야 한다)
    readonly property real ringOuter: Math.min(pieArea.width, pieArea.height) / 2 - 6
    readonly property real ringInner: ringOuter * 0.6

    readonly property var palette: [Theme.accent, Theme.green, Theme.yellow, Theme.red, "#b57bee", "#4fc3dc", "#ff9f5a", "#8a90a3"]

    // 조각마다 시작 각도와 크기를 미리 계산한다 (도 단위, 12시 = -90°, 시계 방향)
    readonly property var wedges: {
        var s = chart.slices || []
        var sum = 0
        for (var i = 0; i < s.length; i++) sum += Number(s[i].value) || 0
        var out = []
        var a = -90
        for (i = 0; i < s.length; i++) {
            var sweep = sum > 0 ? (Number(s[i].value) || 0) / sum * 360 : 0
            out.push({ start: a, sweep: sweep })
            a += sweep
        }
        return out
    }

    // 연달아 바뀔 때는 다시 그리는 애니메이션을 건너뛴다 (슬라이더를 끄는 중 등)
    property double lastChange: 0
    onSlicesChanged: {
        var now = Date.now()
        var rapid = now - lastChange < 1200
        lastChange = now
        revealAnim.stop()
        if (rapid) reveal = 1
        else { reveal = 0; revealAnim.restart() }
    }
    NumberAnimation { id: revealAnim; target: chart; property: "reveal"; from: 0; to: 1; duration: 800; easing.type: Easing.OutCubic }

    function colorOf(i) { return (slices[i] && slices[i].color) ? slices[i].color : palette[i % palette.length] }

    // 도넛 가운데에서 (dx, dy) 만큼 떨어진 곳이 몇 번째 조각인가. 링 밖이면 -1.
    // (마우스 판정에 쓰고, 따로 떼어 두어 검사하기 쉽게 한다)
    function sliceAt(dx, dy) {
        var d = Math.sqrt(dx * dx + dy * dy)
        if (d > ringOuter + 6 || d < ringInner) return -1
        var ang = Math.atan2(dy, dx) * 180 / Math.PI + 90      // 12시 = 0도, 시계 방향
        if (ang < 0) ang += 360
        var w = chart.wedges
        for (var i = 0; i < w.length; i++) {
            var from = w[i].start + 90
            if (ang >= from && ang <= from + w[i].sweep) return i
        }
        return -1
    }

    RowLayout {
        anchors.fill: parent
        spacing: 14

        Item {
            id: pieArea
            Layout.preferredWidth: Math.min(parent.height, 190)
            Layout.fillHeight: true

            readonly property real cx: width / 2
            readonly property real cy: height / 2
            // 애니메이션으로 지금까지 그려진 끝 각도
            readonly property real revealEnd: -90 + 360 * chart.reveal

            // 배경 링
            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    fillColor: "#1c2030"
                    strokeColor: "transparent"
                    fillRule: ShapePath.OddEvenFill
                    PathAngleArc {
                        centerX: pieArea.cx; centerY: pieArea.cy
                        radiusX: chart.ringOuter; radiusY: chart.ringOuter
                        startAngle: 0; sweepAngle: 360
                    }
                    PathAngleArc {
                        centerX: pieArea.cx; centerY: pieArea.cy
                        radiusX: chart.ringInner; radiusY: chart.ringInner
                        startAngle: 0; sweepAngle: 360
                        moveToStart: true
                    }
                }
            }

            // 조각
            Repeater {
                model: chart.wedges
                delegate: Shape {
                    id: wedge
                    required property var modelData
                    required property int index
                    // 애니메이션 중에는 끝 각도까지만 그린다
                    readonly property real drawn:
                        Math.max(0, Math.min(modelData.sweep, pieArea.revealEnd - modelData.start))
                    readonly property real grow: chart.hovered === index ? 5 : 0

                    anchors.fill: parent
                    visible: drawn > 0.01
                    preferredRendererType: Shape.CurveRenderer

                    ShapePath {
                        fillColor: chart.colorOf(wedge.index)
                        strokeColor: "#171a23"
                        strokeWidth: 2
                        PathAngleArc {
                            centerX: pieArea.cx; centerY: pieArea.cy
                            radiusX: chart.ringOuter + wedge.grow; radiusY: chart.ringOuter + wedge.grow
                            startAngle: wedge.modelData.start; sweepAngle: wedge.drawn
                            moveToStart: true
                        }
                        PathAngleArc {
                            // moveToStart 를 꺼야 바깥 호 끝에서 선으로 이어져 가운데가 뚫린 조각이 된다
                            moveToStart: false
                            centerX: pieArea.cx; centerY: pieArea.cy
                            radiusX: chart.ringInner; radiusY: chart.ringInner
                            startAngle: wedge.modelData.start + wedge.drawn; sweepAngle: -wedge.drawn
                        }
                    }
                }
            }

            // 마우스가 올라간 조각 찾기
            HoverHandler {
                onPointChanged: chart.hovered = chart.sliceAt(point.position.x - pieArea.cx,
                                                              point.position.y - pieArea.cy)
                onHoveredChanged: if (!hovered) chart.hovered = -1
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
