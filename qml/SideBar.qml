import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 왼쪽 사이드바 — 피그마 시안('모아')의 그 칸이다.
//
// 예전에는 화면 전환(계획·가계부·한눈에)과 시나리오 탭이 **상단 바**에 함께
// 얹혀 있어서, 시나리오가 늘면 단추가 줄바꿈되며 위가 두꺼워졌다. 세로로
// 세우면 시나리오가 몇 개든 아래로 늘어날 뿐이고, 위는 제목만 남는다.
//
// 창이 좁으면 Main.qml 이 이 칸을 접는다 (그때는 상단 바의 전환 단추가 선다).
Rectangle {
    id: bar

    // 바깥에서 연결해 준다 — 이 파일이 Main.qml 의 id 를 직접 모르게 둔다.
    property string mode: "plan"
    signal modePicked(string m)
    signal ledgerPopRequested()
    signal itemsPopRequested()
    property bool itemsPopped: false
    signal renameRequested(int index, string name)
    signal settingsRequested()
    property bool ledgerPopped: false

    implicitWidth: 230
    color: Theme.sidebar

    // 오른쪽 경계선 한 줄
    Rectangle {
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
        width: 1
        color: Theme.cardBorder
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        anchors.rightMargin: 19
        spacing: 0

        // ── 이름표 ──
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 6
            spacing: 10
            Rectangle {
                width: 29; height: 29; radius: 15
                color: "transparent"
                border.color: Theme.text; border.width: 2
                Rectangle {
                    anchors.centerIn: parent
                    width: 10; height: 10; radius: 5
                    color: Theme.lime
                    border.color: Theme.text; border.width: 1
                }
            }
            ColumnLayout {
                spacing: 0
                Text { text: "자본금 계산기"; color: Theme.text; font.pixelSize: 17; font.bold: true }
                Text {
                    text: "v" + backend.version
                    color: Theme.textDim; font.pixelSize: 9
                    ToolTip.visible: verHover.hovered; ToolTip.delay: 500
                    ToolTip.text: "무엇이 바뀌었는지는 CHANGELOG.md 에 적혀 있습니다"
                    HoverHandler { id: verHover }
                }
            }
            Item { Layout.fillWidth: true }
        }

        Item { Layout.preferredHeight: 34 }

        // ── 화면 전환 ──
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5
            Repeater {
                model: [{ m: "plan", t: "계획", g: "▤" },
                        { m: "ledger", t: "가계부", g: "▦" },
                        { m: "overview", t: "한눈에", g: "◎" }]
                delegate: Rectangle {
                    id: nav
                    required property var modelData
                    // 따로 띄워 둔 가계부는 본 창의 '화면' 이 아니지만 켜져 있다는 건 보여 준다
                    readonly property bool popped: modelData.m === "ledger" && bar.ledgerPopped
                    readonly property bool on: bar.mode === modelData.m || popped
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    radius: 10
                    color: on ? Theme.accentSoft : (navHover.hovered ? Theme.rowHover : "transparent")
                    Behavior on color { ColorAnimation { duration: Theme.fast } }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 13; anchors.rightMargin: 13
                        spacing: 12
                        Text {
                            text: nav.modelData.g
                            color: nav.on ? Theme.accent : Theme.textDim
                            font.pixelSize: 14
                        }
                        Text {
                            text: nav.modelData.t + (nav.popped ? "  ⧉" : "")
                            color: nav.on ? Theme.accent : Theme.textDim
                            font.pixelSize: 13; font.bold: nav.on
                            Layout.fillWidth: true
                        }
                    }
                    HoverHandler { id: navHover }
                    TapHandler { onTapped: bar.modePicked(nav.modelData.m) }
                    ToolTip.visible: navHover.hovered && nav.popped
                    ToolTip.text: "가계부는 따로 띄운 창에 있습니다 (눌러 그 창으로)"
                }
            }
        }

        Item { Layout.preferredHeight: 26 }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
        Item { Layout.preferredHeight: 18 }

        // ── 시나리오 ──
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 7; Layout.rightMargin: 4
            spacing: 6
            Text {
                text: "시나리오"
                color: Theme.textDim; font.pixelSize: 10; font.bold: true
            }
            Item { Layout.fillWidth: true }
            ToolButton {
                text: "＋"
                implicitWidth: 24; implicitHeight: 24
                onClicked: backend.addScenario()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "빈 시나리오 추가 (기간·목표·기준일은 지금 것을 이어받습니다)"
            }
        }

        Item { Layout.preferredHeight: 6 }

        ListView {
            id: scenarioList
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 40
            clip: true
            spacing: 3
            model: backend.scenarioNames
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: sc
                required property int index
                required property string modelData
                readonly property bool on: backend.activeScenario === index
                width: ListView.view.width
                height: 44
                radius: 9
                color: on ? Theme.rowHover : (scHover.hovered ? Theme.row : "transparent")
                Behavior on color { ColorAnimation { duration: Theme.fast } }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8; anchors.rightMargin: 8
                    spacing: 9
                    // 시나리오 색 동그라미 (그래프의 그 색과 같다)
                    Rectangle {
                        width: 29; height: 29; radius: 9
                        color: Theme.scenarioColor(sc.index)
                        Text {
                            anchors.centerIn: parent
                            text: sc.modelData.length > 0 ? sc.modelData.charAt(0) : "?"
                            color: "#ffffff"; font.pixelSize: 11; font.bold: true
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: sc.modelData
                            color: Theme.text; font.pixelSize: 11; font.bold: sc.on
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        Text {
                            text: sc.on ? "보는 중" : "누르면 전환"
                            color: Theme.textDim; font.pixelSize: 9
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                    }
                }
                HoverHandler { id: scHover }
                TapHandler {
                    onTapped: backend.activeScenario = sc.index
                    onDoubleTapped: bar.renameRequested(sc.index, sc.modelData)
                }
                ToolTip.visible: scHover.hovered; ToolTip.delay: 600
                ToolTip.text: "클릭: 전환  ·  더블클릭: 이름 변경"
            }
        }

        Item { Layout.preferredHeight: 10 }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
        Item { Layout.preferredHeight: 8 }

        // ── 설정 (바탕색) · 가계부 따로 띄우기 ──
        // 설정은 상단 단추 줄 끝에 묻혀 있어 못 찾았다. 사이드바 아래가 제자리다.
        Rectangle {
            id: settingsRow
            objectName: "settingsRow"
            Layout.fillWidth: true
            Layout.preferredHeight: 40
            radius: 10
            color: setHover.hovered ? Theme.rowHover : "transparent"
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 13; anchors.rightMargin: 13
                spacing: 12
                Text { text: "⚙"; color: Theme.textDim; font.pixelSize: 14 }
                Text {
                    text: "설정  ·  바탕색"
                    color: Theme.textDim; font.pixelSize: 12
                    Layout.fillWidth: true
                }
            }
            HoverHandler { id: setHover }
            TapHandler { onTapped: bar.settingsRequested() }
            ToolTip.visible: setHover.hovered; ToolTip.delay: 500
            ToolTip.text: "바탕색을 고릅니다 (이 PC 에만 저장됩니다)"
        }

        Button {
            objectName: "itemWindowButtonSide"
            Layout.fillWidth: true
            flat: true
            text: bar.itemsPopped ? "항목 목록 본 창으로" : "항목 목록 따로 띄우기"
            font.pixelSize: 10
            onClicked: bar.itemsPopRequested()
            ToolTip.visible: hovered; ToolTip.delay: 500
            ToolTip.text: "목록만 큰 창으로 떼어 냅니다 — 항목이 많을 때 (Ctrl+Shift+1)"
        }

        Button {
            objectName: "ledgerWindowButtonSide"
            Layout.fillWidth: true
            flat: true
            text: bar.ledgerPopped ? "가계부 본 창으로" : "가계부 따로 띄우기"
            font.pixelSize: 10
            onClicked: bar.ledgerPopRequested()
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: 7
            Layout.topMargin: 8
            text: "시나리오를 나란히 두고 비교합니다.\n숫자는 모두 지금 고른 시나리오 기준입니다."
            color: Theme.textDim; font.pixelSize: 9; lineHeight: 1.6
            wrapMode: Text.Wrap
        }
    }
}
