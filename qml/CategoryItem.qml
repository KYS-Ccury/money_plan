import QtQuick
import QtQuick.Controls

// 분류 고르는 콤보박스의 한 줄. 묶음(1차)의 첫 줄 위에 1차 이름을 얹어
// 평평한 목록을 두 단으로 보이게 한다.
//
// 네 군데(항목·내역·고정·한꺼번에 바꾸기)가 같은 모양을 쓰도록 떼어 두었다.
// 계획 쪽 줄은 이름이 label, 가계부 쪽 줄은 value 라서 둘 다 받는다.
ItemDelegate {
    id: row

    required property var modelData
    required property int index
    property ComboBox box: null

    readonly property string label: modelData.value !== undefined
                                    ? modelData.value : (modelData.label || "")
    readonly property bool heads: modelData.first === true

    width: box ? box.width : implicitWidth
    text: row.label
    highlighted: box ? box.highlightedIndex === row.index : false
    topPadding: row.heads ? 24 : 7      // 1차 이름이 들어갈 자리
    bottomPadding: 7

    Text {
        visible: row.heads
        x: 12; y: 4
        text: row.modelData.group || ""
        color: Theme.accent; font.pixelSize: 10; font.bold: true
    }
}
