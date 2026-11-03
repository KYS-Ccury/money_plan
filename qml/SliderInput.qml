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
    function sync() {
        if (!field.activeFocus) field.text = fmtNum(value)
        if (value > slider.to) slider.to = value * 1.25
        slider.value = value                            // 드래그로 끊긴 슬라이더 바인딩 보정
    }
    onValueChanged: sync()
    Component.onCompleted: field.text = fmtNum(value)

    RowLayout {
        Layout.fillWidth: true
        Text { text: root.label; color: Theme.textDim; font.pixelSize: 12; visible: root.label !== "" }
        Item { Layout.fillWidth: true }
        Text {
            text: root.fmt(root.value)
            color: Theme.text; font.pixelSize: 12; font.bold: true
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
            onMoved: root.commit(value)
            onPressedChanged: if (!pressed) root.sync()

            // 값 라벨이 핸들 위에 따라다닌다 (드래그 중에만)
            Rectangle {
                visible: slider.pressed
                x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                y: -height - 4
                width: tip.implicitWidth + 12; height: tip.implicitHeight + 6
                radius: 6; color: Theme.accent
                opacity: slider.pressed ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                Text { id: tip; anchors.centerIn: parent; text: root.fmt(slider.value); color: "white"; font.pixelSize: 11 }
            }
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
                if (root.decimals > 0) return
                var raw = text.replace(/,/g, "")
                if (raw === "") return
                var n = parseInt(raw)
                if (isNaN(n)) return
                var f = root.fmtNum(n)
                if (f !== text) { text = f; cursorPosition = text.length }
            }
            onEditingFinished: root.commit(parseFloat(text.replace(/,/g, "")))
            onActiveFocusChanged: if (!activeFocus) text = root.fmtNum(root.value)
            // 마우스 휠로도 조정
            WheelHandler {
                onWheel: (ev) => root.commit(root.value + (ev.angleDelta.y > 0 ? 1 : -1) * root.stepSize)
            }
        }
        Text { text: root.suffix; color: Theme.textDim; visible: root.suffix !== "" }
    }
}
