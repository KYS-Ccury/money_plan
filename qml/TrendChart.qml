import QtQuick
import QtQuick.Shapes

// 월별 순 자본 추이.
// - values : 0..horizon 개월의 순 자본 배열
// - target : 목표선
// - markers: 세로 마커를 그릴 개월 (예: [6, 12])
// 데이터가 바뀌면 선이 왼쪽에서 오른쪽으로 다시 그려진다.
//
// 그리기는 QtQuick.Shapes 와 평범한 Rectangle·Text 가 맡는다 (장면 그래프가 GPU 로 그린다).
// 예전에는 Canvas 로 그렸는데, Canvas 는 매번 CPU 에서 그림을 그려 텍스처로 올리는 방식이라
// 마우스를 움직이거나 값이 바뀔 때마다 CPU 가 화면 전체를 다시 칠했다.
Item {
    id: chart
    property var values: []
    property real target: 0
    property color lineColor: Theme.accent   // 주 선 색
    property var series: []                  // 비교용 다른 시나리오: [{name, values, color, active}] (active 는 그리지 않음)
    property var markers: [6, 12]
    property int goalMonth: -1           // 목표 달성 개월 (-1 이면 없음)
    property int shortfallMonth: -1      // 순 자본이 처음 마이너스가 되는 개월 (-1 이면 없음)
    property int hoverMonth: -1          // 마우스가 올라간 개월 (-1 이면 없음)
    property real reveal: 1.0

    readonly property int lastMonth: values ? values.length - 1 : 0
    readonly property bool ready: values && values.length >= 2

    onValuesChanged: { reveal = 0; revealAnim.restart() }
    NumberAnimation { id: revealAnim; target: chart; property: "reveal"; from: 0; to: 1; duration: 900; easing.type: Easing.OutCubic }

    // ---- 값 → 화면 좌표 ----
    readonly property real loV: {
        var v = chart.values || [], l = Math.min(0, chart.target)
        for (var i = 0; i < v.length; i++) l = Math.min(l, v[i])
        var ss = chart.series || []
        for (var k = 0; k < ss.length; k++) {
            var w = ss[k].values || []
            for (i = 0; i < w.length && i <= chart.lastMonth; i++) l = Math.min(l, w[i])
        }
        return l
    }
    readonly property real hiV: {
        var v = chart.values || [], h = Math.max(1, chart.target)
        for (var i = 0; i < v.length; i++) h = Math.max(h, v[i])
        var ss = chart.series || []
        for (var k = 0; k < ss.length; k++) {
            var w = ss[k].values || []
            for (i = 0; i < w.length && i <= chart.lastMonth; i++) h = Math.max(h, w[i])
        }
        return h
    }
    function xOf(m) { return m / Math.max(1, chart.lastMonth) * plot.width }
    function yOf(val) { var s = (chart.hiV - chart.loV) || 1; return plot.height - (val - chart.loV) / s * plot.height }

    // 지금까지 그려진 마지막 지점 (애니메이션)
    readonly property real lastIdx: {
        var v = chart.values || []
        return v.length < 2 ? 0 : Math.min(v.length - 1, (v.length - 1) * chart.reveal)
    }
    // 주 선의 꺾은선 점들 — plot 크기·값·reveal 이 바뀌면 다시 계산된다
    readonly property var linePts: {
        var v = chart.values || []
        if (v.length < 2 || plot.width <= 0) return []
        var pts = []
        var fi = Math.floor(chart.lastIdx)
        for (var i = 0; i < fi; i++) pts.push(Qt.point(chart.xOf(i), chart.yOf(v[i])))
        var t = chart.lastIdx - fi
        var vi = fi < v.length - 1 ? v[fi] + (v[fi + 1] - v[fi]) * t : v[fi]
        pts.push(Qt.point(chart.xOf(chart.lastIdx), chart.yOf(vi)))
        return pts
    }
    // 선 아래 영역 (아래쪽 모서리까지 닫는다)
    readonly property var areaPts: {
        var p = chart.linePts
        if (p.length < 2) return []
        var out = [Qt.point(p[0].x, plot.height)]
        for (var i = 0; i < p.length; i++) out.push(p[i])
        out.push(Qt.point(p[p.length - 1].x, plot.height))
        return out
    }

    Rectangle { anchors.fill: parent; color: "#111420"; radius: 8; border.color: Theme.cardBorder }

    // 그리기 영역 (아래쪽은 축 라벨 공간)
    Item {
        id: plot
        anchors { fill: parent; margins: 10; bottomMargin: 26; topMargin: 14 }
        clip: true

        // ---- 격자 ----
        Repeater {
            model: 5
            delegate: Rectangle {
                required property int index
                x: 0; width: plot.width; height: 1
                y: index / 4 * plot.height
                color: "#262a36"
            }
        }

        // ---- 0원 아래(마이너스) 영역 ----
        Rectangle {
            visible: chart.ready && chart.loV < 0
            x: 0; width: plot.width
            y: chart.yOf(0); height: Math.max(0, plot.height - chart.yOf(0))
            color: "#14f06a6a"                 // 빨강 8%
        }

        // ---- 0원 기준선 / 목표선 (점선) ----
        Shape {
            anchors.fill: parent
            visible: chart.ready
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: "#3a3f52"; strokeWidth: 1; fillColor: "transparent"
                strokeStyle: ShapePath.DashLine; dashPattern: [4, 4]
                startX: 0; startY: chart.yOf(0)
                PathLine { x: plot.width; y: chart.yOf(0) }
            }
            ShapePath {
                strokeColor: chart.target > 0 ? Theme.yellow : "transparent"
                strokeWidth: 1; fillColor: "transparent"
                strokeStyle: ShapePath.DashLine; dashPattern: [4, 4]
                startX: 0; startY: chart.yOf(chart.target)
                PathLine { x: plot.width; y: chart.yOf(chart.target) }
            }
        }

        // ---- 다른 시나리오 선 (얇은 점선, 주 선 뒤에) ----
        Repeater {
            model: chart.series || []
            delegate: Item {
                id: sItem
                required property var modelData
                anchors.fill: parent
                visible: !modelData.active && modelData.values && modelData.values.length >= 2

                readonly property real endIdx: {
                    var sv = modelData.values || []
                    if (sv.length < 2) return 0
                    return Math.min(sv.length - 1, chart.lastMonth, (sv.length - 1) * chart.reveal)
                }
                readonly property var pts: {
                    var sv = modelData.values || []
                    if (sv.length < 2 || plot.width <= 0) return []
                    var out = []
                    for (var j = 0; j <= Math.floor(sItem.endIdx); j++)
                        out.push(Qt.point(chart.xOf(j), chart.yOf(sv[j])))
                    return out
                }

                Shape {
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: sItem.modelData.color || "#8a90a3"
                        strokeWidth: 1.6
                        fillColor: "transparent"
                        joinStyle: ShapePath.RoundJoin
                        strokeStyle: ShapePath.DashLine; dashPattern: [4, 2]
                        PathPolyline { path: sItem.pts }
                    }
                }
                Rectangle {
                    visible: sItem.pts.length > 0
                    width: 6; height: 6; radius: 3
                    color: sItem.modelData.color || "#8a90a3"
                    x: (sItem.pts.length ? sItem.pts[sItem.pts.length - 1].x : 0) - 3
                    y: (sItem.pts.length ? sItem.pts[sItem.pts.length - 1].y : 0) - 3
                }
            }
        }

        // ---- 선 아래 영역 + 주 선 ----
        Shape {
            anchors.fill: parent
            visible: chart.ready
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: "transparent"
                fillGradient: LinearGradient {
                    x1: 0; y1: 0; x2: 0; y2: plot.height
                    GradientStop { position: 0; color: Qt.rgba(chart.lineColor.r, chart.lineColor.g, chart.lineColor.b, 0.35) }
                    GradientStop { position: 1; color: Qt.rgba(chart.lineColor.r, chart.lineColor.g, chart.lineColor.b, 0.0) }
                }
                PathPolyline { path: chart.areaPts }
            }
            ShapePath {
                strokeColor: chart.lineColor
                strokeWidth: 2.5
                fillColor: "transparent"
                joinStyle: ShapePath.RoundJoin
                capStyle: ShapePath.RoundCap
                PathPolyline { path: chart.linePts }
            }
        }

        // ---- 세로 점선 (마커 · 목표 달성 · 현금 부족 · 호버) ----
        component VLine: Shape {
            id: vline
            property real px: 0
            property color strokeTint: "#4a5068"
            property var pattern: [3, 3]
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: vline.strokeTint; strokeWidth: 1; fillColor: "transparent"
                strokeStyle: vline.pattern.length ? ShapePath.DashLine : ShapePath.SolidLine
                dashPattern: vline.pattern
                startX: vline.px; startY: 0
                PathLine { x: vline.px; y: plot.height }
            }
        }

        // ---- 마커 (6개월, 12개월 …) ----
        Repeater {
            model: chart.markers || []
            delegate: Item {
                id: mk
                required property var modelData
                anchors.fill: parent
                readonly property int m: Number(modelData)
                readonly property bool show: chart.ready && m <= chart.lastMonth && m <= chart.lastIdx
                readonly property bool ok: chart.target <= 0 || chart.values[m] >= chart.target
                readonly property color col: ok ? Theme.green : Theme.red
                visible: show

                VLine { px: mk.show ? chart.xOf(mk.m) : 0 }

                Rectangle {
                    width: 10; height: 10; radius: 5
                    color: mk.col; border.color: "#111420"; border.width: 2
                    x: (mk.show ? chart.xOf(mk.m) : 0) - 5
                    y: (mk.show ? chart.yOf(chart.values[mk.m]) : 0) - 5
                }
                Rectangle {
                    id: mkLabel
                    width: mkText.implicitWidth + 10; height: 18; radius: 5
                    color: "#1c2030"; border.color: mk.col; border.width: 1
                    x: Math.min(plot.width - width, Math.max(0, (mk.show ? chart.xOf(mk.m) : 0) - width / 2))
                    y: Math.max(0, (mk.show ? chart.yOf(chart.values[mk.m]) : 0) - 26)
                    Text {
                        id: mkText
                        anchors.centerIn: parent
                        text: mk.m + "개월 " + backend.won(chart.values[mk.m])
                        color: mk.col; font.pixelSize: 11; font.bold: true
                    }
                }
            }
        }

        // ---- 목표 달성 시점: 노란 별표 ----
        Item {
            id: goal
            anchors.fill: parent
            readonly property bool show: chart.ready && chart.target > 0 && chart.goalMonth > 0
                                         && chart.goalMonth <= chart.lastMonth && chart.goalMonth <= chart.lastIdx
            readonly property real gx: show ? chart.xOf(chart.goalMonth) : 0
            readonly property real gy: show ? chart.yOf(chart.values[chart.goalMonth]) : 0
            visible: show

            VLine { px: goal.gx; strokeTint: Theme.yellow; pattern: [2, 3] }

            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    fillColor: Theme.yellow; strokeColor: "transparent"
                    PathPolyline {
                        path: {
                            var p = []
                            for (var k = 0; k < 10; k++) {
                                var rr = k % 2 === 0 ? 8 : 3.5
                                var a = -Math.PI / 2 + k * Math.PI / 5
                                p.push(Qt.point(goal.gx + Math.cos(a) * rr, goal.gy + Math.sin(a) * rr))
                            }
                            p.push(p[0])
                            return p
                        }
                    }
                }
            }
            Rectangle {
                width: goalText.implicitWidth + 10; height: 18; radius: 5
                color: "#2a2616"; border.color: Theme.yellow; border.width: 1
                x: Math.min(plot.width - width, Math.max(0, goal.gx - width / 2))
                y: Math.min(plot.height - 18, goal.gy + 12)
                Text {
                    id: goalText
                    anchors.centerIn: parent
                    text: "달성 " + chart.goalMonth + "개월"
                    color: Theme.yellow; font.pixelSize: 11; font.bold: true
                }
            }
        }

        // ---- 현금 부족 시작 지점 ----
        Item {
            id: shortfall
            anchors.fill: parent
            readonly property bool show: chart.ready && chart.shortfallMonth >= 0
                                         && chart.shortfallMonth <= chart.lastMonth && chart.shortfallMonth <= chart.lastIdx
            readonly property real sx: show ? chart.xOf(chart.shortfallMonth) : 0
            visible: show

            VLine { px: shortfall.sx; strokeTint: Theme.red; pattern: [2, 3] }

            Rectangle {
                width: sfText.implicitWidth + 10; height: 18; radius: 5
                color: "#2a1618"; border.color: Theme.red; border.width: 1
                x: Math.min(plot.width - width, Math.max(0, shortfall.sx - width / 2))
                y: plot.height - 20
                Text {
                    id: sfText
                    anchors.centerIn: parent
                    text: "부족 " + chart.shortfallMonth + "개월"
                    color: Theme.red; font.pixelSize: 11; font.bold: true
                }
            }
        }

        // ---- 마우스 호버 위치 ----
        Item {
            id: hoverMark
            anchors.fill: parent
            readonly property bool show: chart.ready && chart.hoverMonth >= 0 && chart.hoverMonth <= chart.lastIdx
            visible: show
            VLine { px: hoverMark.show ? chart.xOf(chart.hoverMonth) : 0; strokeTint: "#8a90a3"; pattern: [] }
            Rectangle {
                width: 8; height: 8; radius: 4; color: Theme.text
                x: (hoverMark.show ? chart.xOf(chart.hoverMonth) : 0) - 4
                y: (hoverMark.show ? chart.yOf(chart.values[chart.hoverMonth]) : 0) - 4
            }
        }

        // ---- 끝점 ----
        Rectangle {
            visible: chart.linePts.length > 0
            width: 8; height: 8; radius: 4; color: chart.lineColor
            x: (chart.linePts.length ? chart.linePts[chart.linePts.length - 1].x : 0) - 4
            y: (chart.linePts.length ? chart.linePts[chart.linePts.length - 1].y : 0) - 4
        }

        HoverHandler {
            onPointChanged: chart.hoverMonth = Math.round(point.position.x / plot.width * chart.lastMonth)
            onHoveredChanged: if (!hovered) chart.hoverMonth = -1
        }
    }

    // 시나리오 범례 (비교 중일 때)
    Row {
        visible: chart.series && chart.series.length > 1
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; margins: 6 }
        spacing: 10
        Repeater {
            model: chart.series
            delegate: Row {
                required property var modelData
                spacing: 4
                Rectangle { width: 8; height: 8; radius: 4; color: modelData.color || Theme.textDim; anchors.verticalCenter: parent.verticalCenter }
                Text { text: modelData.name; color: modelData.active ? Theme.text : Theme.textDim; font.pixelSize: 11; font.bold: modelData.active }
            }
        }
    }

    // 호버 툴팁
    Rectangle {
        visible: chart.hoverMonth >= 0 && chart.values && chart.hoverMonth < chart.values.length
        x: Math.min(parent.width - width - 6, Math.max(6, plot.x + chart.xOf(chart.hoverMonth) - width / 2))
        y: 4
        width: tipText.implicitWidth + 14; height: tipText.implicitHeight + 8
        radius: 6; color: Theme.card; border.color: Theme.cardBorder
        Text {
            id: tipText
            anchors.centerIn: parent
            text: {
                if (!(chart.hoverMonth >= 0 && chart.values && chart.hoverMonth < chart.values.length)) return ""
                var t = chart.hoverMonth + "개월: " + backend.won(chart.values[chart.hoverMonth])
                var ss = chart.series || []
                for (var i = 0; i < ss.length; i++) {
                    if (ss[i].active || !ss[i].values || chart.hoverMonth >= ss[i].values.length) continue
                    t += "\n" + ss[i].name + ": " + backend.won(ss[i].values[chart.hoverMonth])
                }
                return t
            }
            color: Theme.text; font.pixelSize: 11
        }
    }

    // 축 라벨
    Text {
        anchors { left: parent.left; bottom: parent.bottom; margins: 6 }
        text: "0개월"; color: Theme.textDim; font.pixelSize: 11
    }
    Text {
        anchors { right: parent.right; bottom: parent.bottom; margins: 6 }
        text: chart.lastMonth + "개월"; color: Theme.textDim; font.pixelSize: 11
    }
    Text {
        visible: chart.target > 0
        anchors { right: parent.right; top: parent.top; margins: 4 }
        text: "— 목표선"; color: Theme.yellow; font.pixelSize: 11
    }
}
