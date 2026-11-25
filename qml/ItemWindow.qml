import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Window

// 항목 목록을 본 창에서 떼어 따로 띄우는 창.
//
// 본 창 안에서는 요약·그래프와 자리를 나눠 쓰느라 목록이 몇 줄밖에 안 보인다.
// 항목이 스무 개를 넘으면 그 안에서 고치기가 불편해서, 목록만 크게 띄운다.
// **'미래 목록' 도 여기에 나란히 선다** — 두 목록을 함께 보려면 폭이 필요한데,
// 본 창에서는 요약 칸까지 셋이 자리를 다퉈 어느 쪽도 좁았다.
//
// 같은 backend 를 보므로 여기서 고친 것이 본 창 숫자에 바로 비친다.
//
// Material 색은 창마다 따로 세워야 한다 — ApplicationWindow 밖이라
// 본 창의 설정이 여기까지 내려오지 않는다.
Window {
    id: w
    objectName: "itemWindow"

    // 닫기(X)를 눌렀을 때 본 창이 목록을 다시 품도록 알린다
    signal putBack()

    property alias pane: inner

    // 이 창에서 미래 보기를 켰는지. **켜고 끄기만** 따로 논다 — 견줄 시점은
    // 위쪽 '기간' 하나뿐이라 두 창이 같은 달을 본다.
    property bool futureOpen: false

    title: "항목 목록 — 자본금 계산기"
    width: 1100; height: 760
    minimumWidth: 560; minimumHeight: 380
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

    // 칸 두 개가 더 서려면 폭이 든다. 창이 좁을 때만 넓혀 준다
    // (사람이 줄여 놓은 창을 제멋대로 키우지 않도록, 켜는 순간에만 한 번).
    function setFuture(on) {
        w.futureOpen = on
        if (on && w.width < 1180) {
            var scr = w.screen
            var room = scr ? scr.desktopAvailableWidth - 40 : 1180
            w.width = Math.min(1180, Math.max(w.width, room))
        }
    }

    onClosing: function (close) {
        w.putBack()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pad
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "항목 목록"; color: Theme.text; font.pixelSize: 17; font.bold: true }
            Text {
                text: backend.scenarioNames[backend.activeScenario] || ""
                color: Theme.accent; font.pixelSize: 12
            }
            Text {
                Layout.fillWidth: true
                text: "같은 계획을 봅니다 — 여기서 고친 것도 본 창에 바로 비칩니다"
                color: Theme.textDim; font.pixelSize: 11; elide: Text.ElideRight
            }
            Button {
                objectName: "itemWindowAdd"
                text: "＋ 항목 추가"
                highlighted: true
                onClicked: inner.openAdd()
            }
            Button {
                objectName: "itemWindowDock"
                text: "본 창으로"
                flat: true; leftPadding: 10; rightPadding: 10
                onClicked: w.putBack()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "항목 목록을 본 창 안으로 다시 넣습니다 (Ctrl+Shift+1). 창을 닫아도 같습니다"
            }
        }

        ItemListPane {
            id: inner
            objectName: "itemWindowPane"
            Layout.fillWidth: true
            Layout.fillHeight: true
            futureOpen: w.futureOpen
            onFutureToggled: (on) => w.setFuture(on)
        }
    }
}
