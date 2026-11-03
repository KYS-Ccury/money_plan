import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 삭제 확인 등 예/아니오 팝업. 페이드 + 살짝 커지는 등장 효과.
Popup {
    id: dlg
    property string title: "확인"
    property string message: ""
    property string okText: "확인"
    signal accepted()

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    padding: Theme.pad + 4
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: Theme.card; radius: Theme.radius
        border.color: Theme.cardBorder; border.width: 1
    }
    Overlay.modal: Rectangle { color: "#99000000" }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
        NumberAnimation { property: "scale"; from: 0.92; to: 1; duration: Theme.normal; easing.type: Easing.OutBack }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast }
        NumberAnimation { property: "scale"; from: 1; to: 0.95; duration: Theme.fast }
    }

    ColumnLayout {
        spacing: 14
        Text { text: dlg.title; color: Theme.text; font.pixelSize: 17; font.bold: true }
        Text { text: dlg.message; color: Theme.textDim; font.pixelSize: 14; wrapMode: Text.Wrap; Layout.maximumWidth: 360 }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8
            Button { text: "취소"; flat: true; onClicked: dlg.close() }
            Button {
                text: dlg.okText
                highlighted: true
                Material.accent: Theme.red
                onClicked: { dlg.accepted(); dlg.close() }
            }
        }
    }
}
