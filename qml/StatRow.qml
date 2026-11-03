import QtQuick
import QtQuick.Layouts

// "라벨 ........ 금액" 한 줄
RowLayout {
    id: row
    property string label: ""
    property real value: 0
    property string prefix: ""
    property color valueColor: Theme.text
    property bool emphasis: false

    Layout.fillWidth: true
    spacing: 8

    Text {
        text: row.label
        color: row.emphasis ? Theme.text : Theme.textDim
        font.pixelSize: row.emphasis ? 15 : 14
        font.bold: row.emphasis
        Layout.fillWidth: true
    }
    AnimatedMoney {
        value: row.value
        prefix: row.value === 0 ? "" : row.prefix        // "-0원" 처럼 보이지 않게
        color: row.valueColor
        font.pixelSize: row.emphasis ? 18 : 15
        Behavior on color { ColorAnimation { duration: Theme.normal } }
    }
}
