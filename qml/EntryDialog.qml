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
        nameField.text = ""
        noteField.text = ""
        open(); amountInput.forceActiveFocus()
    }

    function openForEdit(row, date, category, amount, name, note) {
        editRow = row
        entryDate = date || backend.today
        setCategory(category)
        dlg.amount = amount
        nameField.text = name || ""
        noteField.text = note || ""
        open(); amountInput.forceActiveFocus()
    }

    function submit() {
        if (!dateField.valid || dlg.amount <= 0) return
        if (editRow < 0)
            backend.addEntry(dlg.entryDate, dlg.category, dlg.amount, nameField.text, noteField.text)
        else
            backend.updateEntry(editRow, dlg.entryDate, dlg.category, dlg.amount, nameField.text, noteField.text)
        close()
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

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Item { Layout.fillWidth: true }
            Button { text: "취소"; flat: true; onClicked: dlg.close() }
            Button {
                text: "저장"; highlighted: true
                enabled: dateField.valid && dlg.amount > 0
                onClicked: dlg.submit()
            }
        }
    }
}
