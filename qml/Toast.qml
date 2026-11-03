import QtQuick
import QtQuick.Controls

// 화면 아래 가운데에 잠깐 떠오르는 알림. show(text, kind) 로 호출.
// kind: "ok" | "error" | "info"
Item {
    id: toast
    property string text: ""
    property string kind: "ok"
    property int duration: 2800
    z: 1000
    anchors.fill: parent

    function show(msg, k) {
        toast.text = msg
        toast.kind = k || "ok"
        hideTimer.restart()
        box.visibleState = true
    }

    Timer { id: hideTimer; interval: toast.duration; onTriggered: box.visibleState = false }

    Rectangle {
        id: box
        property bool visibleState: false
        anchors.horizontalCenter: parent.horizontalCenter
        y: visibleState ? parent.height - height - 28 : parent.height + 10
        opacity: visibleState ? 1 : 0
        width: Math.min(parent.width - 40, row.implicitWidth + 36)
        height: 46
        radius: 23
        color: Theme.card
        border.width: 1
        border.color: toast.kind === "error" ? Theme.red : (toast.kind === "info" ? Theme.accent : Theme.green)

        Behavior on y { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }

        // 클릭하면 바로 닫힘
        TapHandler { onTapped: box.visibleState = false }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 10
            Rectangle {
                width: 10; height: 10; radius: 5
                anchors.verticalCenter: parent.verticalCenter
                color: box.border.color
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: toast.text
                color: Theme.text
                font.pixelSize: 13
                elide: Text.ElideMiddle
                width: Math.min(implicitWidth, toast.width - 100)
            }
        }
    }
}
