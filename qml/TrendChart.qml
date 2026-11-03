import QtQuick

// 월별 순 자본 추이.
// - values : 0..horizon 개월의 순 자본 배열
// - target : 목표선
// - markers: 세로 마커를 그릴 개월 (예: [6, 12])
// 데이터가 바뀌면 선이 왼쪽에서 오른쪽으로 다시 그려진다.
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

    onValuesChanged: { reveal = 0; revealAnim.restart() }
    onSeriesChanged: canvas.requestPaint()
    onLineColorChanged: canvas.requestPaint()
    onTargetChanged: canvas.requestPaint()
    onMarkersChanged: canvas.requestPaint()
    onGoalMonthChanged: canvas.requestPaint()
    onShortfallMonthChanged: canvas.requestPaint()
    onRevealChanged: canvas.requestPaint()
    onHoverMonthChanged: canvas.requestPaint()
    NumberAnimation { id: revealAnim; target: chart; property: "reveal"; from: 0; to: 1; duration: 900; easing.type: Easing.OutCubic }

    Rectangle { anchors.fill: parent; color: "#111420"; radius: 8; border.color: Theme.cardBorder }

    // 그리기 영역 (아래쪽은 축 라벨 공간)
    Canvas {
        id: canvas
        anchors { fill: parent; margins: 10; bottomMargin: 26; topMargin: 14 }

        function lo() {
            var v = chart.values, l = Math.min(0, chart.target)
            for (var i = 0; i < v.length; i++) l = Math.min(l, v[i])
            var ss = chart.series || []
            for (var k = 0; k < ss.length; k++) { var w = ss[k].values || []; for (i = 0; i < w.length && i <= chart.lastMonth; i++) l = Math.min(l, w[i]) }
            return l
        }
        function hi() {
            var v = chart.values, h = Math.max(1, chart.target)
            for (var i = 0; i < v.length; i++) h = Math.max(h, v[i])
            var ss = chart.series || []
            for (var k = 0; k < ss.length; k++) { var w = ss[k].values || []; for (i = 0; i < w.length && i <= chart.lastMonth; i++) h = Math.max(h, w[i]) }
            return h
        }
        function rgba(c, a) { var q = Qt.color(c); return "rgba(" + Math.round(q.r * 255) + "," + Math.round(q.g * 255) + "," + Math.round(q.b * 255) + "," + a + ")" }
        function xOf(m) { return m / Math.max(1, chart.lastMonth) * width }
        function yOf(val) { var l = lo(), s = (hi() - l) || 1; return height - (val - l) / s * height }

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)
            var v = chart.values
            if (!v || v.length < 2) return

            // 격자
            ctx.strokeStyle = "#262a36"; ctx.lineWidth = 1
            for (var g = 0; g <= 4; g++) { var gy = g / 4 * height; ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(width, gy); ctx.stroke() }
            // 0 아래(마이너스) 영역
            if (lo() < 0) {
                ctx.fillStyle = "rgba(240,106,106,0.08)"
                ctx.fillRect(0, yOf(0), width, height - yOf(0))
            }
            // 0 원 기준선
            ctx.strokeStyle = "#3a3f52"; ctx.setLineDash([4, 4])
            ctx.beginPath(); ctx.moveTo(0, yOf(0)); ctx.lineTo(width, yOf(0)); ctx.stroke()
            // 목표선
            if (chart.target > 0) {
                ctx.strokeStyle = Theme.yellow
                ctx.beginPath(); ctx.moveTo(0, yOf(chart.target)); ctx.lineTo(width, yOf(chart.target)); ctx.stroke()
            }
            ctx.setLineDash([])

            // 다른 시나리오 선 (얇게, 주 선 뒤에)
            var ss = chart.series || []
            for (var si = 0; si < ss.length; si++) {
                var sv = ss[si].values || []
                if (ss[si].active || sv.length < 2) continue
                var sEnd = Math.min(sv.length - 1, chart.lastMonth, (sv.length - 1) * chart.reveal)
                ctx.strokeStyle = ss[si].color || "#8a90a3"; ctx.lineWidth = 1.6; ctx.setLineDash([6, 3]); ctx.lineJoin = "round"
                ctx.beginPath()
                for (var sj = 0; sj <= Math.floor(sEnd); sj++) { if (sj === 0) ctx.moveTo(xOf(sj), yOf(sv[sj])); else ctx.lineTo(xOf(sj), yOf(sv[sj])) }
                ctx.stroke(); ctx.setLineDash([])
                ctx.fillStyle = ss[si].color || "#8a90a3"
                ctx.beginPath(); ctx.arc(xOf(Math.floor(sEnd)), yOf(sv[Math.floor(sEnd)]), 3, 0, Math.PI * 2); ctx.fill()
            }

            // 선 + 영역 (reveal 만큼)
            var lastIdx = Math.min(v.length - 1, (v.length - 1) * chart.reveal)
            var pts = []
            for (var i = 0; i < Math.floor(lastIdx); i++) pts.push([xOf(i), yOf(v[i])])
            var fi = Math.floor(lastIdx), t = lastIdx - fi
            var vi = fi < v.length - 1 ? v[fi] + (v[fi + 1] - v[fi]) * t : v[fi]
            pts.push([xOf(lastIdx), yOf(vi)])

            var grad = ctx.createLinearGradient(0, 0, 0, height)
            grad.addColorStop(0, rgba(chart.lineColor, 0.35)); grad.addColorStop(1, rgba(chart.lineColor, 0.0))
            ctx.fillStyle = grad
            ctx.beginPath(); ctx.moveTo(pts[0][0], height)
            for (i = 0; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1])
            ctx.lineTo(pts[pts.length - 1][0], height); ctx.closePath(); ctx.fill()

            ctx.strokeStyle = chart.lineColor; ctx.lineWidth = 2.5; ctx.lineJoin = "round"
            ctx.beginPath()
            for (i = 0; i < pts.length; i++) { if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]); else ctx.lineTo(pts[i][0], pts[i][1]) }
            ctx.stroke()

            // 마커 (6개월, 12개월 …): 세로 점선 + 점 + 값 라벨
            var ms = chart.markers || []
            for (i = 0; i < ms.length; i++) {
                var m = ms[i]
                if (m > chart.lastMonth || m > lastIdx) continue
                var mx = xOf(m), my = yOf(v[m])
                var ok = chart.target <= 0 || v[m] >= chart.target
                var col = ok ? Theme.green : Theme.red
                ctx.strokeStyle = "#4a5068"; ctx.setLineDash([3, 3]); ctx.lineWidth = 1
                ctx.beginPath(); ctx.moveTo(mx, 0); ctx.lineTo(mx, height); ctx.stroke(); ctx.setLineDash([])
                ctx.fillStyle = col
                ctx.beginPath(); ctx.arc(mx, my, 5, 0, Math.PI * 2); ctx.fill()
                ctx.strokeStyle = "#111420"; ctx.lineWidth = 2; ctx.stroke()
                // 라벨
                ctx.font = "bold 11px sans-serif"
                var label = m + "개월 " + backend.won(v[m])
                var tw = ctx.measureText(label).width + 10
                var lx = Math.min(width - tw, Math.max(0, mx - tw / 2)), ly = Math.max(0, my - 26)
                ctx.fillStyle = "#1c2030"; ctx.strokeStyle = col; ctx.lineWidth = 1
                ctx.beginPath(); ctx.roundedRect(lx, ly, tw, 18, 5, 5); ctx.fill(); ctx.stroke()
                ctx.fillStyle = col; ctx.textBaseline = "middle"; ctx.textAlign = "left"
                ctx.fillText(label, lx + 5, ly + 9)
            }

            // 목표 달성 시점: 노란 별표 마커
            var gm = chart.goalMonth
            if (chart.target > 0 && gm > 0 && gm <= chart.lastMonth && gm <= lastIdx) {
                var gx = xOf(gm), gy = yOf(v[gm])
                ctx.strokeStyle = Theme.yellow; ctx.setLineDash([2, 3]); ctx.lineWidth = 1.5
                ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, height); ctx.stroke(); ctx.setLineDash([])
                ctx.fillStyle = Theme.yellow
                ctx.beginPath()
                for (var k = 0; k < 10; k++) {
                    var rr = k % 2 === 0 ? 8 : 3.5, a = -Math.PI / 2 + k * Math.PI / 5
                    var px = gx + Math.cos(a) * rr, py = gy + Math.sin(a) * rr
                    if (k === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py)
                }
                ctx.closePath(); ctx.fill()
                ctx.font = "bold 11px sans-serif"
                var gl = "달성 " + gm + "개월"
                var gw = ctx.measureText(gl).width + 10
                var glx = Math.min(width - gw, Math.max(0, gx - gw / 2)), gly = Math.min(height - 18, gy + 12)
                ctx.fillStyle = "#2a2616"; ctx.strokeStyle = Theme.yellow; ctx.lineWidth = 1
                ctx.beginPath(); ctx.roundedRect(glx, gly, gw, 18, 5, 5); ctx.fill(); ctx.stroke()
                ctx.fillStyle = Theme.yellow; ctx.textBaseline = "middle"; ctx.textAlign = "left"
                ctx.fillText(gl, glx + 5, gly + 9)
            }

            // 현금 부족 시작 지점
            var sm = chart.shortfallMonth
            if (sm >= 0 && sm <= chart.lastMonth && sm <= lastIdx) {
                var sx = xOf(sm)
                ctx.strokeStyle = Theme.red; ctx.setLineDash([2, 3]); ctx.lineWidth = 1.5
                ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, height); ctx.stroke(); ctx.setLineDash([])
                ctx.font = "bold 11px sans-serif"
                var sl = "부족 " + sm + "개월"
                var sw = ctx.measureText(sl).width + 10
                var slx = Math.min(width - sw, Math.max(0, sx - sw / 2))
                ctx.fillStyle = "#2a1618"; ctx.strokeStyle = Theme.red; ctx.lineWidth = 1
                ctx.beginPath(); ctx.roundedRect(slx, height - 20, sw, 18, 5, 5); ctx.fill(); ctx.stroke()
                ctx.fillStyle = Theme.red; ctx.textBaseline = "middle"; ctx.textAlign = "left"
                ctx.fillText(sl, slx + 5, height - 11)
            }

            // 마우스 호버 위치
            if (chart.hoverMonth >= 0 && chart.hoverMonth <= lastIdx) {
                var hx = xOf(chart.hoverMonth), hy = yOf(v[chart.hoverMonth])
                ctx.strokeStyle = "#8a90a3"; ctx.lineWidth = 1
                ctx.beginPath(); ctx.moveTo(hx, 0); ctx.lineTo(hx, height); ctx.stroke()
                ctx.fillStyle = Theme.text
                ctx.beginPath(); ctx.arc(hx, hy, 4, 0, Math.PI * 2); ctx.fill()
            }

            // 끝점
            var ex = pts[pts.length - 1][0], ey = pts[pts.length - 1][1]
            ctx.fillStyle = chart.lineColor
            ctx.beginPath(); ctx.arc(ex, ey, 4, 0, Math.PI * 2); ctx.fill()
        }

        HoverHandler {
            id: hover
            onPointChanged: chart.hoverMonth = Math.round(point.position.x / canvas.width * chart.lastMonth)
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
        x: Math.min(parent.width - width - 6, Math.max(6, canvas.x + canvas.xOf(chart.hoverMonth) - width / 2))
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
