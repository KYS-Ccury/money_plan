import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 분류별 한 달 예산 설정 팝업
Popup {
    id: dlg
    objectName: "budgetDialog"

    // 팝업을 열 때 한 번만 읽어 둔다. 슬라이더를 끌 때마다 목록이 다시 만들어지면 끊기기 때문.
    property var rows: []
    function reload() { dlg.rows = backend.budgetEditRows }
    onOpened: reload()

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 520
    padding: Theme.pad + 4
    closePolicy: Popup.CloseOnEscape

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

    ConfirmDialog {
        id: clearBudgetDialog
        title: "예산 지우기"
        okText: "지우기"
        message: "정해 둔 예산을 모두 지웁니다."
        onAccepted: { backend.clearBudgets(); dlg.reload() }
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "분류별 예산"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            text: "한 달에 이 분류로 얼마까지 쓸지 정합니다. 0 이면 예산 없음입니다."
            color: Theme.textDim; font.pixelSize: 12
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: backend.ledgerPeriodText + " 실적으로 채우기"
                flat: true; leftPadding: 10; rightPadding: 10
                enabled: backend.ledgerSummary.count > 0
                onClicked: { backend.fillBudgetsFromPeriod(); dlg.reload() }
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "그 기간에 실제로 쓴 금액(월평균)을 예산으로 넣습니다"
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "모두 지우기"; flat: true; leftPadding: 10; rightPadding: 10
                Material.foreground: Theme.red
                enabled: backend.hasBudgets
                onClicked: clearBudgetDialog.open()
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        Flickable {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(budgetCol.implicitHeight, 420)
            contentHeight: budgetCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: budgetCol
                width: parent.width
                spacing: 4

                Repeater {
                    model: dlg.rows
                    delegate: RowLayout {
                        id: budgetRow
                        required property var modelData
                        // 이 줄의 현재 값 (백엔드를 다시 읽지 않는다)
                        property real limit: modelData.limit

                        function apply(v) {
                            budgetRow.limit = Math.max(0, v)
                            backend.setBudget(modelData.category, budgetRow.limit)
                        }

                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: modelData.category
                            color: budgetRow.limit > 0 ? Theme.text : Theme.textDim
                            font.pixelSize: 13
                            Layout.preferredWidth: 110
                        }
                        Slider {
                            id: budgetSlider
                            Layout.fillWidth: true
                            from: 0; to: 2000000; stepSize: 10000
                            value: budgetRow.limit
                            // 끄는 동안에는 화면만 따라오고, 손을 떼면 저장한다
                            onMoved: budgetRow.limit = value
                            onPressedChanged: if (!pressed) budgetRow.apply(value)
                        }
                        TextField {
                            Layout.preferredWidth: 130
                            horizontalAlignment: Text.AlignRight
                            text: budgetRow.limit > 0 ? Number(budgetRow.limit).toLocaleString(Qt.locale(), "f", 0) : ""
                            inputMethodHints: Qt.ImhDigitsOnly
                            onEditingFinished: {
                                var v = parseFloat(text.replace(/,/g, "")) || 0
                                budgetRow.apply(v)
                                budgetSlider.value = budgetRow.limit
                            }
                        }
                        Text { text: "원"; color: Theme.textDim; font.pixelSize: 12 }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                text: "한 달 예산 합계"
                color: Theme.textDim; font.pixelSize: 13
            }
            Item { Layout.fillWidth: true }
            Text {
                text: backend.won(backend.ledgerBudgetTotals.limit / Math.max(1, backend.budgetMonths))
                color: Theme.text; font.pixelSize: 15; font.bold: true
            }

        }

        RowLayout {
            Layout.fillWidth: true
            Item { Layout.fillWidth: true }
            Button { text: "닫기"; highlighted: true; onClicked: dlg.close() }
        }
    }
}
