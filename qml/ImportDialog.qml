import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls.Material

// 가계부 가져오기: CSV · 엑셀 · 메모장 파일, 또는 그냥 붙여넣은 글
Popup {
    id: dlg
    objectName: "importDialog"

    property bool skipDupes: true
    property string defaultPay: ""
    readonly property var info: backend.importInfo

    function start() {
        backend.cancelImport()
        pasteArea.text = ""
        dlg.skipDupes = true
        dlg.defaultPay = ""
        open()
    }

    function readPasted() {
        if (pasteArea.text.trim() !== "")
            backend.previewImportText(pasteArea.text)
    }

    function apply() {
        if (backend.applyImport(dlg.skipDupes, dlg.defaultPay) > 0)
            close()
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 760
    padding: Theme.pad + 4
    closePolicy: Popup.CloseOnEscape
    onClosed: backend.cancelImport()

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

    FileDialog {
        id: fileDialog
        title: "가계부 내역 가져오기"
        fileMode: FileDialog.OpenFile
        nameFilters: ["가져올 수 있는 파일 (*.csv *.xlsx *.xlsm *.txt *.tsv)",
                      "CSV (*.csv)", "엑셀 (*.xlsx *.xlsm)", "텍스트 (*.txt *.tsv)",
                      "모든 파일 (*)"]
        onAccepted: backend.previewImportFile(selectedFile.toString())
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "가계부 가져오기"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            Layout.fillWidth: true
            text: "은행·카드사에서 내려받은 CSV·엑셀, 메모장에 적어 둔 글을 그대로 읽습니다. "
                  + "머리글(날짜·금액·내용…)을 찾아 짝지어 읽고, 머리글이 없으면 줄마다 날짜와 금액을 찾습니다."
            color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                objectName: "importPickFile"
                text: "파일 고르기…"
                highlighted: true
                onClicked: fileDialog.open()
            }
            Text {
                Layout.fillWidth: true
                text: dlg.info.source ? dlg.info.source + "  ·  " + (dlg.info.how || "")
                                      : "CSV · 엑셀(.xlsx) · 텍스트(.txt)"
                color: Theme.textDim; font.pixelSize: 12; elide: Text.ElideRight
            }
        }

        // 붙여넣기
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            RowLayout {
                Layout.fillWidth: true
                Text { text: "또는 그냥 붙여넣기"; color: Theme.text; font.pixelSize: 13 }
                Item { Layout.fillWidth: true }
                Button {
                    objectName: "importReadPasted"
                    text: "읽기"; flat: true; leftPadding: 10; rightPadding: 10
                    enabled: pasteArea.text.trim() !== ""
                    onClicked: dlg.readPasted()
                }
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 72
                radius: 8
                color: Theme.row
                border.color: Theme.cardBorder
                ScrollView {
                    anchors.fill: parent
                    anchors.margins: 6
                    TextArea {
                        id: pasteArea
                        objectName: "importPasteArea"
                        placeholderText: "11/13  점심  12,000  카드\n11/14  커피  4500"
                        placeholderTextColor: Theme.textDim
                        color: Theme.text
                        font.pixelSize: 12
                        wrapMode: TextArea.NoWrap
                        background: null
                    }
                }
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        // 읽은 결과
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            visible: dlg.info.count > 0
            Text {
                text: dlg.info.count + "건"
                color: Theme.text; font.pixelSize: 15; font.bold: true
            }
            Text {
                text: "새로 " + dlg.info.fresh + "건"
                      + (dlg.info.dupes > 0 ? "  ·  이미 있는 " + dlg.info.dupes + "건" : "")
                color: Theme.textDim; font.pixelSize: 12
            }
            Text {
                text: dlg.info.from + " ~ " + dlg.info.to
                color: Theme.textDim; font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: dlg.info.income > 0
                text: "+" + backend.won(dlg.info.income); color: Theme.green; font.pixelSize: 13
            }
            Text {
                visible: dlg.info.cost > 0
                text: "-" + backend.won(dlg.info.cost); color: Theme.red; font.pixelSize: 13
            }
        }

        Text {
            Layout.fillWidth: true
            visible: dlg.info.ok === false && dlg.info.problemCount > 0
            // 바인딩은 visible 과 상관없이 계산된다. 아직 아무것도 안 읽었으면
            // info 가 {} 라서 problems 가 없다 — 그래서 늘 있는지 보고 꺼낸다
            text: "읽지 못했습니다. "
                  + (dlg.info.problems && dlg.info.problems.length > 0 ? dlg.info.problems[0] : "")
            color: Theme.red; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        // 미리보기
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 240
            visible: dlg.info.count > 0
            radius: 8
            color: Theme.row
            border.color: Theme.cardBorder

            ListView {
                id: previewList
                objectName: "importPreview"
                anchors.fill: parent
                anchors.margins: 6
                clip: true
                spacing: 2
                model: backend.importRows
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    required property var modelData
                    width: previewList.width - 8
                    height: 28
                    radius: 6
                    color: modelData.dupe ? "transparent" : Theme.rowHover
                    opacity: modelData.dupe && dlg.skipDupes ? 0.45 : 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8; anchors.rightMargin: 8
                        spacing: 8
                        Text {
                            text: modelData.date; color: Theme.textDim; font.pixelSize: 11
                            Layout.preferredWidth: 80
                        }
                        Text {
                            text: modelData.category !== "" ? modelData.category : "—"
                            color: modelData.category !== "" ? Theme.text : Theme.textDim
                            font.pixelSize: 11; Layout.preferredWidth: 90; elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.name
                            color: Theme.text; font.pixelSize: 12
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.pay
                            color: Theme.textDim; font.pixelSize: 11
                            Layout.preferredWidth: 80; elide: Text.ElideRight
                        }
                        Text {
                            visible: modelData.dupe
                            text: "이미 있음"; color: Theme.yellow; font.pixelSize: 10
                        }
                        Text {
                            text: modelData.amountText
                            color: modelData.kind === "income" ? Theme.green : Theme.red
                            font.pixelSize: 12; font.bold: true
                        }
                    }
                }
            }
        }

        // 못 읽은 줄
        ColumnLayout {
            Layout.fillWidth: true
            visible: dlg.info.problemCount > 0 && dlg.info.count > 0
            spacing: 2
            Text {
                text: "못 읽은 줄 " + dlg.info.problemCount + "개 (그냥 건너뜁니다)"
                color: Theme.yellow; font.pixelSize: 11
            }
            Repeater {
                model: dlg.info.problems ? dlg.info.problems.slice(0, 3) : []
                delegate: Text {
                    required property string modelData
                    Layout.fillWidth: true
                    text: "· " + modelData
                    color: Theme.textDim; font.pixelSize: 10; elide: Text.ElideRight
                }
            }
        }

        // 고르기
        RowLayout {
            Layout.fillWidth: true
            visible: dlg.info.count > 0
            spacing: 10
            CheckBox {
                objectName: "importSkipDupes"
                text: "이미 있는 내역은 건너뛰기"
                checked: dlg.skipDupes
                onToggled: dlg.skipDupes = checked
            }
            Item { Layout.fillWidth: true }
            Text { text: "결제수단이 비어 있으면"; color: Theme.textDim; font.pixelSize: 12 }
            ComboBox {
                id: payBox
                objectName: "importDefaultPay"
                Layout.preferredWidth: 130
                editable: true
                model: backend.ledgerPays
                onAccepted: dlg.defaultPay = editText.trim()
                onActivated: dlg.defaultPay = editText.trim()
                Component.onCompleted: payBox.editText = ""
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.fillWidth: true
                visible: dlg.info.count > 0
                text: "없는 분류는 새로 만들어 넣습니다 (이름이 길거나 겹치면 '기타' 로 넣고 메모에 남깁니다)."
                color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap
            }
            Button { text: "취소"; flat: true; onClicked: dlg.close() }
            Button {
                objectName: "importApply"
                text: {
                    var n = dlg.skipDupes ? dlg.info.fresh : dlg.info.count
                    return n > 0 ? n + "건 가져오기" : "가져오기"
                }
                highlighted: true
                enabled: (dlg.skipDupes ? dlg.info.fresh : dlg.info.count) > 0
                onClicked: dlg.apply()
            }
        }
    }
}
