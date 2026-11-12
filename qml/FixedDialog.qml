import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

// 고정 지출·수입 팝업: 달마다 저절로 적히는 내역을 관리한다
Popup {
    id: dlg
    objectName: "fixedDialog"

    property string editRid: ""              // 비어 있으면 '새로 만들기'
    property string formKind: "cost"         // 지금 고른 분류가 수입인지 지출인지 (표시용)
    property bool formOpen: false

    function thisMonth() {
        return backend.today.substring(0, 7)
    }

    function openNew() {
        dlg.editRid = ""
        nameField.text = ""
        setCategory("주거/관리비")
        amountField.text = ""
        dayBox.value = 1
        noteField.text = ""
        startField.text = dlg.thisMonth()
        endField.text = ""
        dlg.formOpen = true
        if (!dlg.visible) open()
        nameField.forceActiveFocus()
    }

    function openEdit(row) {
        dlg.editRid = row.rid
        nameField.text = row.name
        setCategory(row.category)
        amountField.text = String(row.amount)
        dayBox.value = row.day
        noteField.text = row.note
        startField.text = row.start
        endField.text = row.end
        dlg.formOpen = true
        if (!dlg.visible) open()
        amountField.forceActiveFocus()
    }

    function setCategory(c) {
        var i = catBox.indexOfValue(c)
        catBox.currentIndex = i >= 0 ? i : 0
        dlg.formKind = backend.ledgerKindOf(catBox.currentValue)
    }

    function save() {
        var amount = parseFloat(amountField.text.replace(/,/g, "")) || 0
        var why = dlg.editRid === ""
            ? backend.addFixed(nameField.text, String(catBox.currentValue), amount,
                               dayBox.value, noteField.text, startField.text, endField.text)
            : backend.updateFixed(dlg.editRid, nameField.text, String(catBox.currentValue), amount,
                                  dayBox.value, noteField.text, startField.text, endField.text)
        if (why !== "") return
        dlg.formOpen = false
        dlg.editRid = ""
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

    // 규칙을 지울 때. 이미 적어 둔 내역을 함께 지울지 고를 수 있다.
    Popup {
        id: removeFixedDialog
        objectName: "removeFixedDialog"
        property string rid: ""
        property string label: ""
        property int made: 0
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

        function ask(row) {
            removeFixedDialog.rid = row.rid
            removeFixedDialog.label = row.label
            removeFixedDialog.made = row.made
            purgeBox.checked = false
            open()
        }

        ColumnLayout {
            spacing: 14
            Text { text: "고정 항목 삭제"; color: Theme.text; font.pixelSize: 17; font.bold: true }
            Text {
                text: "'" + removeFixedDialog.label + "' 을 더 이상 자동으로 적지 않습니다."
                color: Theme.textDim; font.pixelSize: 14
                wrapMode: Text.Wrap; Layout.maximumWidth: 360
            }
            CheckBox {
                id: purgeBox
                objectName: "purgeFixedEntries"
                visible: removeFixedDialog.made > 0
                text: "이미 적어 둔 내역 " + removeFixedDialog.made + "건도 함께 지우기"
            }
            Text {
                visible: removeFixedDialog.made > 0 && !purgeBox.checked
                text: "그냥 지우면 지금까지 적힌 내역은 실제로 쓴 돈이므로 그대로 남습니다."
                color: Theme.textDim; font.pixelSize: 11
                wrapMode: Text.Wrap; Layout.maximumWidth: 360
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                Button { text: "취소"; flat: true; onClicked: removeFixedDialog.close() }
                Button {
                    text: "삭제"; highlighted: true
                    Material.accent: Theme.red
                    onClicked: {
                        backend.removeFixed(removeFixedDialog.rid, purgeBox.checked)
                        removeFixedDialog.close()
                    }
                }
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "고정 지출·수입"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            text: "월세·통신비·급여처럼 달마다 똑같이 오가는 돈입니다. 한 번 적어 두면 "
                  + "달이 바뀔 때마다 가계부에 저절로 적힙니다 (앱을 열 때 밀린 달까지 한꺼번에)."
            color: Theme.textDim; font.pixelSize: 12
            wrapMode: Text.Wrap; Layout.fillWidth: true
        }

        // 한 달 합계
        RowLayout {
            Layout.fillWidth: true
            visible: backend.fixedTotals.count > 0
            spacing: 12
            Text {
                text: "한 달 " + backend.fixedTotals.count + "건"
                color: Theme.textDim; font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: backend.fixedTotals.income > 0
                text: "+" + backend.won(backend.fixedTotals.income)
                color: Theme.green; font.pixelSize: 13
            }
            Text {
                visible: backend.fixedTotals.cost > 0
                text: "-" + backend.won(backend.fixedTotals.cost)
                color: Theme.red; font.pixelSize: 13
            }
            Text {
                text: (backend.fixedTotals.net >= 0 ? "+" : "") + backend.won(backend.fixedTotals.net)
                color: backend.fixedTotals.net >= 0 ? Theme.green : Theme.red
                font.pixelSize: 14; font.bold: true
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        Text {
            visible: backend.fixedCount === 0
            Layout.fillWidth: true
            text: "아직 고정 항목이 없습니다. 아래 '＋ 고정 항목 추가' 로 만들거나, "
                  + "가계부 내역의 ⟳ 를 눌러 그 내역을 고정으로 올릴 수 있습니다."
            color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        // 규칙 목록
        Flickable {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(fixedCol.implicitHeight, 300)
            visible: backend.fixedCount > 0
            contentHeight: fixedCol.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            ColumnLayout {
                id: fixedCol
                width: parent.width
                spacing: 4

                Repeater {
                    model: backend.fixedRows
                    delegate: Rectangle {
                        id: fixedRow
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 46
                        radius: 8
                        color: fixedHover.hovered ? Theme.rowHover : Theme.row
                        opacity: modelData.active ? 1 : 0.55
                        HoverHandler { id: fixedHover }
                        TapHandler { onDoubleTapped: dlg.openEdit(fixedRow.modelData) }

                        Rectangle {
                            width: 4; radius: 2
                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 }
                            color: fixedRow.modelData.kind === "income" ? Theme.green : Theme.red
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 18
                            anchors.rightMargin: 8
                            spacing: 8

                            Rectangle {
                                radius: 10
                                color: Theme.accentSoft
                                implicitWidth: fixedCat.implicitWidth + 14
                                implicitHeight: 22
                                Text {
                                    id: fixedCat
                                    anchors.centerIn: parent
                                    text: fixedRow.modelData.category
                                    color: Theme.text; font.pixelSize: 11
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0
                                Text {
                                    text: fixedRow.modelData.label
                                          + (fixedRow.modelData.active ? "" : "  (쉬는 중)")
                                    color: Theme.text; font.pixelSize: 13
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                                Text {
                                    text: "매달 " + fixedRow.modelData.day + "일  ·  "
                                          + fixedRow.modelData.periodText
                                          + (fixedRow.modelData.made > 0
                                             ? "  ·  적은 내역 " + fixedRow.modelData.made + "건" : "")
                                    color: Theme.textDim; font.pixelSize: 10
                                    elide: Text.ElideRight; Layout.fillWidth: true
                                }
                            }
                            Text {
                                text: fixedRow.modelData.amountText
                                color: fixedRow.modelData.kind === "income" ? Theme.green : Theme.red
                                font.pixelSize: 14; font.bold: true
                            }
                            ToolButton {
                                text: fixedRow.modelData.active ? "⏸" : "▶"
                                implicitWidth: 30; implicitHeight: 30
                                ToolTip.visible: hovered; ToolTip.delay: 600
                                ToolTip.text: fixedRow.modelData.active
                                              ? "잠시 쉬게 합니다 (지우지는 않습니다)"
                                              : "다시 돌립니다 (밀린 달도 적습니다)"
                                onClicked: backend.toggleFixed(fixedRow.modelData.rid)
                            }
                            ToolButton {
                                text: "수정"
                                font.pixelSize: 11
                                implicitWidth: 44; implicitHeight: 30
                                ToolTip.visible: hovered; ToolTip.delay: 600
                                ToolTip.text: "이 고정 항목을 고칩니다"
                                onClicked: dlg.openEdit(fixedRow.modelData)
                            }
                            ToolButton {
                                text: "✕"
                                implicitWidth: 30; implicitHeight: 30
                                Material.foreground: Theme.red
                                ToolTip.visible: hovered; ToolTip.delay: 600
                                ToolTip.text: "이 고정 항목을 지웁니다"
                                onClicked: removeFixedDialog.ask(fixedRow.modelData)
                            }
                        }
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; visible: dlg.formOpen }

        // 만들기 / 고치기
        ColumnLayout {
            Layout.fillWidth: true
            visible: dlg.formOpen
            spacing: 10

            Text {
                text: dlg.editRid === "" ? "새 고정 항목" : "고정 항목 고치기"
                color: Theme.text; font.pixelSize: 14; font.bold: true
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: nameField
                    objectName: "fixedName"
                    Layout.fillWidth: true
                    placeholderText: "이름 (월세, 통신비 …)"
                }
                ComboBox {
                    id: catBox
                    objectName: "fixedCategory"
                    Layout.preferredWidth: 150
                    model: backend.ledgerCategories
                    textRole: "value"
                    valueRole: "value"
                    onActivated: dlg.formKind = backend.ledgerKindOf(String(currentValue))
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: amountField
                    objectName: "fixedAmount"
                    Layout.fillWidth: true
                    placeholderText: "금액"
                    horizontalAlignment: Text.AlignRight
                    inputMethodHints: Qt.ImhDigitsOnly
                    onAccepted: dlg.save()
                }
                Text { text: "원  ·  매달"; color: Theme.textDim; font.pixelSize: 12 }
                SpinBox {
                    id: dayBox
                    objectName: "fixedDay"
                    from: 1; to: 31; value: 1
                    editable: true
                    Layout.preferredWidth: 130
                }
                Text { text: "일"; color: Theme.textDim; font.pixelSize: 12 }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Text { text: "기간"; color: Theme.textDim; font.pixelSize: 12 }
                TextField {
                    id: startField
                    objectName: "fixedStart"
                    Layout.preferredWidth: 110
                    placeholderText: "2026-11"
                    maximumLength: 7
                }
                Text { text: "~"; color: Theme.textDim; font.pixelSize: 12 }
                TextField {
                    id: endField
                    objectName: "fixedEnd"
                    Layout.preferredWidth: 110
                    placeholderText: "비우면 계속"
                    maximumLength: 7
                }
                TextField {
                    id: noteField
                    objectName: "fixedNote"
                    Layout.fillWidth: true
                    placeholderText: "메모 (없어도 됩니다)"
                }
            }

            Text {
                Layout.fillWidth: true
                text: "말일을 넘는 날짜는 그 달의 말일로 맞춥니다 (31일 → 2월 28일). "
                      + "적힌 내역을 지우면 그 달은 다시 적지 않습니다."
                color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Button {
                    text: "취소"; flat: true
                    onClicked: { dlg.formOpen = false; dlg.editRid = "" }
                }
                Button {
                    objectName: "fixedSave"
                    text: dlg.editRid === "" ? "추가" : "저장"
                    highlighted: true
                    onClicked: dlg.save()
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                objectName: "fixedAddToggle"
                text: "＋ 고정 항목 추가"
                flat: true; leftPadding: 10; rightPadding: 10
                Material.foreground: Theme.accent
                visible: !dlg.formOpen || dlg.editRid !== ""
                onClicked: dlg.openNew()
            }
            Item { Layout.fillWidth: true }
            Button { text: "닫기"; highlighted: true; onClicked: dlg.close() }
        }
    }
}
