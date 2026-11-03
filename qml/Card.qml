import QtQuick

// 둥근 모서리 + 테두리 + 등장 애니메이션이 있는 패널
Rectangle {
    id: card
    property string title: ""
    default property alias content: body.data

    color: Theme.card
    radius: Theme.radius
    border.color: Theme.cardBorder
    border.width: 1

    opacity: 0
    scale: 0.97
    Component.onCompleted: { opacity = 1; scale = 1 }
    Behavior on opacity { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutCubic } }
    Behavior on scale { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutBack } }

    Text {
        id: titleText
        text: card.title
        visible: card.title !== ""
        color: Theme.text
        font.pixelSize: 16
        font.bold: true
        anchors { top: parent.top; left: parent.left; margins: Theme.pad }
    }

    Item {
        id: body
        anchors {
            top: titleText.visible ? titleText.bottom : parent.top
            left: parent.left; right: parent.right; bottom: parent.bottom
            margins: Theme.pad
            topMargin: titleText.visible ? 10 : Theme.pad
        }
    }
}
