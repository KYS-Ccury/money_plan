import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// YYYY-MM-DD 날짜 입력칸. 비워도 되고(optional), 형식이 틀리면 빨간 테두리.
ColumnLayout {
    id: root
    property string label: ""
    property string value: ""            // "" 또는 "YYYY-MM-DD"
    property bool optional: false
    property string placeholder: (label !== "" ? label : "YYYY-MM-DD") + (optional ? " (비우면 계속)" : "")
    readonly property bool valid: backend.isValidDate(field.text) && (optional || field.text.trim() !== "")
    signal edited(string newValue)

    // 다 쳤는데 엔터를 안 누르면 반영되지 않아, 저장 버튼이 잠긴 채로 남는 일이 있었다.
    // 손을 멈추고 0.2초면 (날짜가 온전할 때만) 반영한다.
    Timer {
        id: liveTimer
        interval: 200
        onTriggered: root.commitIfReady()
    }
    function commitIfReady() {
        liveTimer.stop()
        var t = field.text.trim()
        if (t === "") {
            if (root.optional && root.value !== "") root.edited("")
            return
        }
        // YYYY-MM 또는 YYYY-MM-DD 가 다 채워졌을 때만 (치는 중간값으로 바뀌지 않게)
        if ((t.length === 7 || t.length === 10) && backend.isValidDate(t) && t !== root.value)
            root.edited(t)
    }

    spacing: 2

    TextField {
        id: field
        Layout.fillWidth: true
        font.pixelSize: 14
        placeholderText: root.placeholder
        text: root.value
        inputMask: ""
        validator: RegularExpressionValidator { regularExpression: /[0-9-]{0,10}/ }
        color: root.valid ? Theme.text : Theme.red
        onTextEdited: {
            // 숫자만 치면 하이픈을 자동으로 넣어준다 (20260401 → 2026-04-01)
            var digits = text.replace(/[^0-9]/g, "")
            var out = digits.substring(0, 4)
            if (digits.length > 4) out += "-" + digits.substring(4, 6)
            if (digits.length > 6) out += "-" + digits.substring(6, 8)
            if (out !== text) { text = out; cursorPosition = text.length }
            liveTimer.restart()
        }
        onEditingFinished: root.commitIfReady()
        Connections {
            target: root
            function onValueChanged() { if (!field.activeFocus) field.text = root.value }
        }
    }
}
