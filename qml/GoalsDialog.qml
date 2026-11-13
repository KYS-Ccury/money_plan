import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

// 중간 목표 관리: 최종 목표로 가는 길에 거쳐 갈 지점들
Popup {
    id: dlg
    objectName: "goalsDialog"

    function money(text) {
        return parseFloat(String(text).replace(/[^\d.]/g, "")) || 0
    }

    function addGoal() {
        var amount = dlg.money(newAmount.text)
        if (amount <= 0) return
        backend.addGoal(newName.text, amount)
        newName.text = ""
        newAmount.text = ""
        newName.forceActiveFocus()
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 560
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

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "중간 목표"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            Layout.fillWidth: true
            text: "최종 목표(" + backend.won(backend.target) + ") 로 가는 길에 거쳐 갈 지점을 적어 둡니다. "
                  + "'1차 전세금' · '2차 매수' 처럼요. 그래프에 선이 그어지고, 목표 카드에 언제 닿는지 나옵니다."
            color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        Text {
            visible: backend.goalCount === 0
            Layout.fillWidth: true
            text: "아직 중간 목표가 없습니다."
            color: Theme.textDim; font.pixelSize: 12
        }

        // 적어 둔 중간 목표
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6

            Repeater {
                model: backend.goalEditRows
                delegate: RowLayout {
                    id: goalRow
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 8

                    TextField {
                        id: nameField
                        Layout.fillWidth: true
                        text: goalRow.modelData.name
                        placeholderText: "이름 (1차 전세금 …)"
                        onEditingFinished: backend.updateGoal(goalRow.modelData.index, text,
                                                              dlg.money(amountField.text))
                    }
                    TextField {
                        id: amountField
                        Layout.preferredWidth: 150
                        horizontalAlignment: Text.AlignRight
                        text: Number(goalRow.modelData.amount).toLocaleString(Qt.locale(), "f", 0)
                        inputMethodHints: Qt.ImhDigitsOnly
                        onEditingFinished: backend.updateGoal(goalRow.modelData.index,
                                                              nameField.text, dlg.money(text))
                    }
                    Text { text: "원"; color: Theme.textDim; font.pixelSize: 12 }
                    ToolButton {
                        text: "✕"
                        implicitWidth: 32
                        Material.foreground: Theme.red
                        onClicked: backend.removeGoal(goalRow.modelData.index)
                        ToolTip.visible: hovered; ToolTip.delay: 600
                        ToolTip.text: "이 중간 목표를 지웁니다"
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        // 새로 넣기
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            TextField {
                id: newName
                objectName: "newGoalName"
                Layout.fillWidth: true
                placeholderText: "새 중간 목표 이름"
                onAccepted: dlg.addGoal()
            }
            TextField {
                id: newAmount
                objectName: "newGoalAmount"
                Layout.preferredWidth: 150
                horizontalAlignment: Text.AlignRight
                placeholderText: "금액"
                inputMethodHints: Qt.ImhDigitsOnly
                onAccepted: dlg.addGoal()
            }
            Text { text: "원"; color: Theme.textDim; font.pixelSize: 12 }
            Button {
                objectName: "addGoalButton"
                text: "추가"
                highlighted: true
                enabled: dlg.money(newAmount.text) > 0
                onClicked: dlg.addGoal()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "최종 목표 금액은 위쪽 '목표 자본금' 에서 정합니다."
                color: Theme.textDim; font.pixelSize: 11
            }
            Button { text: "닫기"; highlighted: true; onClicked: dlg.close() }
        }
    }
}
