import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 항목 목록 아래의 장(페이지) 탭 — 엑셀 시트 탭과 같은 자리, 같은 몸짓이다.
//
// 장은 **보기 묶음**이다. 어느 장을 펴 두든 요약·그래프·순 자본은 모든 장의
// 항목을 함께 센다 (통째로 견주는 것은 시나리오가 한다). 그래서 장을 지워도
// 항목은 사라지지 않고 첫 장으로 옮겨 간다.
Flow {
    id: tabs
    spacing: 4

    // 이름 바꾸기 / 지우기 확인
    Popup {
        id: renamePop
        property string target: ""
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        width: 320
        padding: Theme.pad
        background: Rectangle {
            color: Theme.card; radius: Theme.radius
            border.color: Theme.cardBorder; border.width: 1
        }
        Overlay.modal: Rectangle { color: "#99000000" }

        function openFor(name) {
            renamePop.target = name
            nameField.text = name
            renamePop.open()
            nameField.forceActiveFocus()
            nameField.selectAll()
        }
        function commit() {
            if (backend.renamePage(renamePop.target, nameField.text))
                renamePop.close()
        }

        contentItem: ColumnLayout {
            spacing: 10
            Text { text: "장 이름 바꾸기"; color: Theme.text; font.pixelSize: 15; font.bold: true }
            TextField {
                id: nameField
                objectName: "pageNameField"
                Layout.fillWidth: true
                onAccepted: renamePop.commit()
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Button { text: "취소"; flat: true; onClicked: renamePop.close() }
                Button {
                    text: "바꾸기"; highlighted: true
                    enabled: nameField.text.trim().length > 0
                    onClicked: renamePop.commit()
                }
            }
        }
    }

    ConfirmDialog {
        id: removePop
        property string target: ""
        title: "장 삭제"
        okText: "장 삭제"
        onAccepted: backend.removePage(removePop.target)
    }

    // ── '전체' 탭 ──
    component Tab: Rectangle {
        id: tab
        property string name: ""
        property int count: -1
        property bool on: false
        property bool removable: false
        property bool renamable: false
        signal picked()
        signal renameAsked()
        signal removeAsked()

        width: tabRow.implicitWidth + 20
        height: 30
        radius: 8
        color: on ? Theme.card : (tabHover.hovered ? Theme.rowHover : "transparent")
        border.width: 1
        border.color: on ? Theme.accent : Theme.cardBorder

        RowLayout {
            id: tabRow
            anchors.centerIn: parent
            spacing: 6
            Text {
                text: tab.name
                color: tab.on ? Theme.text : Theme.textDim
                font.pixelSize: 12; font.bold: tab.on
            }
            Text {
                visible: tab.count >= 0
                text: tab.count
                color: Theme.textDim; font.pixelSize: 10
            }
            Text {
                visible: tab.removable && (tabHover.hovered || tab.on)
                text: "✕"
                color: Theme.textDim; font.pixelSize: 10
                TapHandler { onTapped: tab.removeAsked() }
            }
        }
        HoverHandler { id: tabHover }
        TapHandler {
            onTapped: tab.picked()
            onDoubleTapped: if (tab.renamable) tab.renameAsked()
        }
        ToolTip.visible: tabHover.hovered; ToolTip.delay: 700
        ToolTip.text: tab.removable
                      ? "클릭: 이 장만 보기  ·  더블클릭: 이름 바꾸기  ·  ✕: 장 삭제(항목은 첫 장으로)"
                      : (tab.renamable
                         ? "클릭: 이 장만 보기  ·  더블클릭: 이름 바꾸기  (첫 장은 지울 수 없습니다)"
                         : "모든 장의 항목을 함께 봅니다")
    }

    Tab {
        name: "전체"
        count: backend.itemCount
        on: backend.activePage === ""
        onPicked: backend.activePage = ""
    }

    Repeater {
        model: backend.pages
        delegate: Tab {
            required property int index
            required property string modelData
            name: modelData
            count: (backend.pageCounts[index] !== undefined) ? backend.pageCounts[index] : 0
            on: backend.activePage === modelData
            // 첫 장도 이름은 바꿀 수 있다. 다만 지울 수는 없다 —
            // 지운 항목이 돌아갈 자리가 하나는 있어야 한다.
            renamable: true
            removable: index > 0
            onPicked: backend.activePage = modelData
            onRenameAsked: renamePop.openFor(modelData)
            onRemoveAsked: {
                removePop.target = modelData
                removePop.message = "'" + modelData + "' 장을 지울까요?\n"
                                    + "그 장의 항목 " + count + "개는 '기본' 장으로 옮겨집니다 (지워지지 않습니다)."
                removePop.open()
            }
        }
    }

    Button {
        objectName: "addPageButton"
        text: "＋ 장"
        flat: true
        implicitHeight: 30
        leftPadding: 10; rightPadding: 10
        font.pixelSize: 12
        onClicked: backend.addPage()
        ToolTip.visible: hovered; ToolTip.delay: 500
        ToolTip.text: "새 장을 만듭니다. 항목을 나눠 담아 두는 묶음일 뿐이라 숫자는 바뀌지 않습니다"
    }
}
