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
        }
        onEditingFinished: if (backend.isValidDate(text)) root.edited(text.trim())
        Connections {
            target: root
            function onValueChanged() { if (!field.activeFocus) field.text = root.value }
        }
    }
}
