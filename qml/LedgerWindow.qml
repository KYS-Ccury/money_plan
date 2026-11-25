import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Window

// 가계부를 본 창에서 떼어 따로 띄우는 창.
//
// 계획을 고치면서 가계부를 같이 보고 싶을 때가 있다. 같은 backend 를 보므로
// 양쪽 숫자가 저절로 맞고, 이쪽에서 고친 것도 바로 본 창에 비친다.
//
// Material 색은 창마다 따로 세워야 한다 — ApplicationWindow 밖이라
// 본 창의 설정이 여기까지 내려오지 않는다.
Window {
    id: w
    objectName: "ledgerWindow"

    // 닫기(X)를 눌렀을 때 본 창이 가계부를 다시 품도록 알린다
    signal putBack()

    property alias view: inner

    title: "가계부 — 자본금 계산기"
    width: 1000; height: 700
    minimumWidth: 640; minimumHeight: 420
    color: Theme.bg

    // 본 창에 매달지 않는다. 매달아 두면 늘 위에 떠 있어서 나란히 놓고 보기 불편하다
    transientParent: null

    Material.theme: Theme.light ? Material.Light : Material.Dark
    Material.accent: Theme.accent
    Material.primary: Theme.accent
    Material.background: Theme.bg
    Material.foreground: Theme.text

    function focusHere() {
        w.show()
        w.raise()
        w.requestActivate()
    }

    onClosing: function (close) {
        w.putBack()
    }

    // 머리줄 + 가계부. 겹치지 않게 위아래로 쌓는다
    // (가계부 쪽에도 제 단추가 많아서 띄워 놓고 겹치면 못 누른다)
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pad
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "가계부"; color: Theme.text; font.pixelSize: 17; font.bold: true }
            Text {
                Layout.fillWidth: true
                text: "같은 자료를 봅니다 — 여기서 고친 것도 본 창에 바로 비칩니다"
                color: Theme.textDim; font.pixelSize: 11; elide: Text.ElideRight
            }
            Text {
                text: backend.status
                color: Theme.textDim; font.pixelSize: 11
                elide: Text.ElideMiddle
                Layout.maximumWidth: 320
            }
            Button {
                objectName: "ledgerWindowDock"
                text: "본 창으로"
                flat: true; leftPadding: 10; rightPadding: 10
                onClicked: w.putBack()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "가계부를 본 창 안으로 다시 넣습니다 (Ctrl+Shift+2). 창을 닫아도 같습니다"
            }
        }

        LedgerView {
            id: inner
            objectName: "ledgerWindowView"
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
