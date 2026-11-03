import QtQuick

// 값이 바뀌면 숫자가 부드럽게 굴러가는 금액 텍스트
Text {
    id: root
    property real value: 0
    property string prefix: ""
    property real shown: value           // 애니메이션되는 내부 값
    Behavior on shown { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }

    text: prefix + backend.won(shown)
    color: Theme.text
    font.pixelSize: 15
    font.bold: true
    horizontalAlignment: Text.AlignRight
}
