import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 가계부 내역 추가 / 수정 팝업
Popup {
    id: dlg
    objectName: "entryDialog"
    property int editRow: -1                 // -1 이면 추가
    property string entryDate: ""
    property string category: "식비"
    property real amount: 0
    property int repeatMonths: 1             // 1 이면 한 번만, 2 이상이면 다음 달부터 반복
    readonly property string kind: backend.ledgerKindOf(category)

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 460
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

    function setCategory(c) {
        dlg.category = c || "식비"
        catBox.currentIndex = Math.max(0, catBox.indexOfValue(dlg.category))
    }

    function openForAdd(defaultDate) {
        editRow = -1
        entryDate = defaultDate || backend.today
        setCategory("식비")
        amount = 0
        repeatMonths = 1
        nameField.text = ""
        noteField.text = ""
        open(); amountInput.forceActiveFocus()
    }

    function openForEdit(row, date, category, amount, name, note) {
        editRow = row
        repeatMonths = 1
        entryDate = date || backend.today
        setCategory(category)
        dlg.amount = amount
        nameField.text = name || ""
        noteField.text = note || ""
        open(); amountInput.forceActiveFocus()
    }

    function save() {
        if (!dateField.valid || dlg.amount <= 0) return false
        if (editRow < 0) {
            if (dlg.repeatMonths > 1)
                backend.addEntryRepeat(dlg.entryDate, dlg.category, dlg.amount,
                                       nameField.text, noteField.text, dlg.repeatMonths)
            else
                backend.addEntry(dlg.entryDate, dlg.category, dlg.amount, nameField.text, noteField.text)
        } else {
            backend.updateEntry(editRow, dlg.entryDate, dlg.category, dlg.amount, nameField.text, noteField.text)
        }
        return true
    }
    function submit() {
        if (save()) close()
    }
    // 저장하고 팝업을 열어 둔 채 다음 내역을 받는다 (날짜·분류는 그대로)
    function submitAndNext() {
        if (!save()) return
        dlg.amount = 0
        dlg.repeatMonths = 1
        nameField.text = ""
        noteField.text = ""
        amountInput.forceActiveFocus()
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            text: dlg.editRow < 0 ? "내역 추가" : "내역 수정"
            color: Theme.text; font.pixelSize: 18; font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            DateField {
                id: dateField
                Layout.fillWidth: true
                label: "날짜"
                value: dlg.entryDate
                onEdited: (v) => dlg.entryDate = v
            }
            ComboBox {
                id: catBox
                objectName: "entryCategory"
                Layout.preferredWidth: 180
                model: backend.ledgerCategories
                textRole: "value"
                valueRole: "value"
                onActivated: dlg.category = catBox.currentValue
            }
        }

        // 수입/지출 표시 (분류로 정해진다)
        Rectangle {
            Layout.fillWidth: true
            height: 30; radius: 6
            color: dlg.kind === "income" ? Theme.greenSoft : Theme.redSoft
            Text {
                anchors.centerIn: parent
                text: dlg.kind === "income" ? "수입으로 기록됩니다" : "지출로 기록됩니다"
                color: dlg.kind === "income" ? Theme.green : Theme.red
                font.pixelSize: 12
            }
        }

        SliderInput {
            id: amountInput
            objectName: "entryAmount"
            label: "금액"
            value: dlg.amount
            from: 0; to: 10000000; stepSize: 10000
            money: true
            suffix: "원"
            onEdited: (v) => dlg.amount = v
        }

        TextField {
            id: nameField
            Layout.fillWidth: true
            placeholderText: "쓴 곳 / 받은 곳 (선택)"
            onAccepted: dlg.submit()
        }
        TextField {
            id: noteField
            Layout.fillWidth: true
            placeholderText: "메모 (선택)"
            onAccepted: dlg.submit()
        }

        // ── 반복 (추가할 때만) ──
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: dlg.editRow < 0

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text { text: "반복"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                Item { width: 6 }
                Repeater {
                    model: [1, 2, 3, 6, 12]
                    delegate: Rectangle {
                        required property int modelData
                        readonly property bool on: dlg.repeatMonths === modelData
                        width: 46; height: 26; radius: 13
                        color: on ? Theme.accent : "transparent"
                        border.color: on ? Theme.accent : Theme.cardBorder
                        TapHandler { onTapped: dlg.repeatMonths = modelData }
                        Text {
                            anchors.centerIn: parent
                            text: modelData === 1 ? "한 번" : modelData + "달"
                            color: parent.on ? "#ffffff" : Theme.textDim
                            font.pixelSize: 11
                        }
                    }
                }
                Item { Layout.fillWidth: true }
            }
            Text {
                visible: dlg.repeatMonths > 1
                text: "같은 날짜로 " + dlg.repeatMonths + "개월치가 한 번에 들어갑니다 (말일은 그 달 마지막 날로)."
                color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            Button { text: "취소"; flat: true; onClicked: dlg.close() }
            Button {
                text: "저장하고 계속"; flat: true
                visible: dlg.editRow < 0
                enabled: dateField.valid && dlg.amount > 0
                onClicked: dlg.submitAndNext()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "저장한 뒤 팝업을 열어 둡니다 (날짜·분류 유지)"
            }
            Button {
                text: "저장"; highlighted: true
                enabled: dateField.valid && dlg.amount > 0
                onClicked: dlg.submit()
            }
        }
    }
}
