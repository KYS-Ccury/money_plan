import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 슬라이더 + 직접 입력칸이 서로 동기화되는 숫자 입력
// - 슬라이더를 끌면 입력칸이 따라오고, 입력칸에 숫자를 치면 슬라이더가 따라간다.
// - 슬라이더 범위보다 큰 값을 입력하면 범위가 자동으로 늘어난다.
ColumnLayout {
    id: root
    property string label: ""
    property real value: 0
    property real from: 0
    property real to: 100
    property real stepSize: 1
    property int decimals: 0
    property string suffix: ""           // "개월", "%" 등
    property bool money: false           // true 면 오른쪽 표시값을 1,234원 형식으로
    property int fieldWidth: 130
    // 끄는 동안 계산이 무거운 값(기간·목표)은 이 값을 주면
    // 손을 멈출 때까지 기다렸다가 한 번만 반영한다 (0 이면 끄는 내내 바로 반영)
    property int dragDelay: 0
    // 화면에 보이는 값. 기다리는 동안에는 슬라이더를 따라가고, 반영되면 value 와 같아진다
    property real shown: value
    property alias inputField: field     // 테스트에서 입력칸을 직접 건드릴 때
    signal edited(real newValue)

    spacing: 2
    Layout.fillWidth: true

    function fmt(v) {
        return money ? backend.won(v) : (fmtNum(v) + suffix)
    }
    // 입력칸용: 천 단위 콤마 (예: 30,000,000 / 3.5)
    function fmtNum(v) {
        return Number(v).toLocaleString(Qt.locale("en_US"), "f", decimals)
    }
    // 주의: 여기서 value 에 직접 대입하면 부모의 `value: xxx` 바인딩이 끊긴다.
    // 그래서 edited 신호만 보내고, 값 반영은 부모(backend / dialog)가 하도록 한다.
    function commit(v) {
        v = Math.max(from, isNaN(v) ? from : v)
        if (v > slider.to) slider.to = v * 1.25        // 범위 자동 확장
        if (Math.abs(v - value) > 1e-9) edited(v)
        else sync()                                     // 값이 같으면 표시만 되돌림
    }
    // − / + 버튼: 한 눈금씩. 슬라이더로 미세 조정이 어려울 때 쓴다
    function stepBy(dir) {
        var s = root.stepSize > 0 ? root.stepSize : 1
        var v = root.value + dir * s
        v = Math.round(v / s) * s               // 0.1 + 0.2 같은 소수점 오차 보정
        root.commit(Math.max(root.from, v))
    }
    function sync() {
        if (!field.activeFocus) field.text = fmtNum(shown)
        if (value > slider.to) slider.to = value * 1.25
        slider.value = value                            // 드래그로 끊긴 슬라이더 바인딩 보정
    }
    onValueChanged: { shown = value; sync() }
    // 기다리는 동안에도 입력칸은 손을 따라간다
    onShownChanged: if (!field.activeFocus) field.text = fmtNum(shown)
    Component.onCompleted: { shown = value; field.text = fmtNum(value) }

    // 끄는 동안 잠깐 멈추면 그때 한 번 반영한다
    Timer {
        id: dragTimer
        interval: root.dragDelay
        onTriggered: root.commit(root.shown)
    }

    // 치는 동안에도 반영한다. 글자마다 바로 계산하면 "2 → 20 → 200" 처럼
    // 중간값이 쏟아지므로 잠깐 멈출 때까지만 기다린다.
    Timer {
        id: liveTimer
        interval: 350
        onTriggered: root.commitText()
    }
    function commitText() {
        liveTimer.stop()
        var raw = field.text.replace(/,/g, "")
        if (raw === "" || raw === ".") return
        var v = parseFloat(raw)
        if (!isNaN(v)) root.commit(v)
    }

    RowLayout {
        Layout.fillWidth: true
        Text { text: root.label; color: Theme.textDim; font.pixelSize: 12; visible: root.label !== "" }
        Item { Layout.fillWidth: true }
        Text {
            text: root.fmt(root.shown)
            color: Theme.text; font.pixelSize: 12; font.bold: true
            // 아직 반영 전이면 살짝 흐리게 — 기다리는 중이라는 표시
            opacity: dragTimer.running ? 0.65 : 1
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10

        Slider {
            id: slider
            Layout.fillWidth: true
            from: root.from
            to: root.to
            stepSize: root.stepSize
            value: root.value
            snapMode: Slider.SnapAlways
            onMoved: {
                root.shown = value
                if (root.dragDelay > 0) dragTimer.restart()   // 멈출 때까지 기다린다
                else root.commit(value)
            }
            // 손을 떼면 기다리지 않고 바로 반영한다
            onPressedChanged: {
                if (pressed) return
                dragTimer.stop()
                root.commit(value)
            }

            // 값 라벨이 핸들 위에 따라다닌다 (드래그 중에만)
            Rectangle {
                visible: slider.pressed || dragTimer.running
                x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                y: -height - 4
                width: tip.implicitWidth + 12; height: tip.implicitHeight + 6
                radius: 6; color: Theme.accent
                opacity: slider.pressed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                Text { id: tip; anchors.centerIn: parent; text: root.fmt(slider.value); color: "white"; font.pixelSize: 11 }
            }
        }

        ToolButton {
            text: "−"
            font.pixelSize: 16
            implicitWidth: 34; implicitHeight: 34
            enabled: root.value > root.from
            autoRepeat: true                     // 누르고 있으면 계속 줄어든다
            onClicked: root.stepBy(-1)
            ToolTip.visible: hovered; ToolTip.delay: 700
            ToolTip.text: "한 눈금 줄이기 (" + root.fmt(root.stepSize) + ")"
        }

        TextField {
            id: field
            Layout.preferredWidth: root.fieldWidth
            implicitHeight: 40
            topPadding: 8; bottomPadding: 8
            horizontalAlignment: Text.AlignRight
            validator: RegularExpressionValidator { regularExpression: root.decimals > 0 ? /[0-9,]*\.?[0-9]*/ : /[0-9,]*/ }
            inputMethodHints: Qt.ImhFormattedNumbersOnly
            font.pixelSize: 14
            // 정수 입력은 타이핑 중에도 콤마를 바로 넣어준다
            onTextEdited: {
                liveTimer.restart()
                if (root.decimals > 0) return
                var raw = text.replace(/,/g, "")
                if (raw === "") return
                var n = parseInt(raw)
                if (isNaN(n)) return
                var f = root.fmtNum(n)
                if (f !== text) { text = f; cursorPosition = text.length }
            }
            onEditingFinished: root.commitText()          // 엔터·포커스 이동은 기다리지 않고 바로
            onActiveFocusChanged: if (!activeFocus) text = root.fmtNum(root.value)
            // 마우스 휠로도 조정
            WheelHandler {
                onWheel: (ev) => root.commit(root.value + (ev.angleDelta.y > 0 ? 1 : -1) * root.stepSize)
            }
        }

        ToolButton {
            text: "＋"
            font.pixelSize: 14
            implicitWidth: 34; implicitHeight: 34
            autoRepeat: true                     // 누르고 있으면 계속 늘어난다
            onClicked: root.stepBy(1)
            ToolTip.visible: hovered; ToolTip.delay: 700
            ToolTip.text: "한 눈금 늘리기 (" + root.fmt(root.stepSize) + ")"
        }

        Text { text: root.suffix; color: Theme.textDim; visible: root.suffix !== "" }
    }
}
