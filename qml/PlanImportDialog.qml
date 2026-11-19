import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Controls.Material

// 계획 항목 가져오기: CSV · 엑셀 · 메모장 파일, 또는 그냥 붙여넣은 글
// (가계부 가져오기와 같은 흐름 — 먼저 미리보기, 그다음에 넣기)
Popup {
    id: dlg
    objectName: "planImportDialog"

    property bool skipDupes: true
    property bool replaceAll: false
    readonly property var info: backend.planImportInfo

    function start() {
        backend.cancelPlanImport()
        pasteArea.text = ""
        dlg.skipDupes = true
        dlg.replaceAll = false
        open()
    }

    function readPasted() {
        if (pasteArea.text.trim() !== "")
            backend.previewPlanImportText(pasteArea.text)
    }

    // 함수로 두면 info 가 바뀌어도 단추가 다시 계산되지 않는다 (바인딩은 함수 안을 못 본다)
    readonly property int addCount: dlg.replaceAll
        ? (dlg.info.count || 0)
        : ((dlg.skipDupes ? dlg.info.fresh : dlg.info.count) || 0)

    function apply() {
        if (backend.applyPlanImport(dlg.skipDupes, dlg.replaceAll) > 0)
            close()
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 760
    padding: Theme.pad + 4
    closePolicy: Popup.CloseOnEscape
    onClosed: backend.cancelPlanImport()

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
        title: "계획 항목 가져오기"
        fileMode: FileDialog.OpenFile
        nameFilters: ["가져올 수 있는 파일 (*.csv *.xlsx *.xlsm *.txt *.tsv)",
                      "CSV (*.csv)", "엑셀 (*.xlsx *.xlsm)", "텍스트 (*.txt *.tsv)",
                      "모든 파일 (*)"]
        onAccepted: backend.previewPlanImportFile(selectedFile.toString())
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "계획 가져오기"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            Layout.fillWidth: true
            text: "엑셀·CSV·메모장에 적어 둔 항목을 읽어 옵니다. 머리글(이름·분류·금액·연이율·시작일…)을 "
                  + "찾아 짝지어 읽습니다. 이 앱에서 엑셀로 내보낸 파일의 '항목' 시트도 그대로 들어옵니다."
            color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                objectName: "planImportPickFile"
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
                    objectName: "planImportReadPasted"
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
                        objectName: "planImportPasteArea"
                        placeholderText: "월급  월 수입  3,200,000\n청약  적금  200,000  2.1%\n전세 보증금  주거  150,000,000"
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
                text: dlg.info.count + "개"
                color: Theme.text; font.pixelSize: 15; font.bold: true
            }
            Text {
                text: "새로 " + dlg.info.fresh + "개"
                      + (dlg.info.dupes > 0 ? "  ·  이미 있는 " + dlg.info.dupes + "개" : "")
                color: Theme.textDim; font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Text {
                visible: dlg.info.capital > 0
                text: "자본 " + backend.won(dlg.info.capital); color: Theme.text; font.pixelSize: 12
            }
            Text {
                visible: dlg.info.income > 0
                text: "수입 " + backend.won(dlg.info.income); color: Theme.green; font.pixelSize: 12
            }
            Text {
                visible: dlg.info.cost > 0
                text: "지출 " + backend.won(dlg.info.cost); color: Theme.red; font.pixelSize: 12
            }
        }

        Text {
            Layout.fillWidth: true
            visible: dlg.info.ok === false && dlg.info.problemCount > 0
            // 바인딩은 visible 과 상관없이 계산된다 — 아직 아무것도 안 읽었으면 info 가 {} 다
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
                objectName: "planImportPreview"
                anchors.fill: parent
                anchors.margins: 6
                clip: true
                spacing: 2
                model: backend.planImportRows
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                delegate: Rectangle {
                    id: prow
                    required property var modelData
                    width: previewList.width - 8
                    height: 28
                    radius: 6
                    color: modelData.dupe === true ? "transparent" : Theme.rowHover
                    readonly property bool known: modelData.dupe === true || modelData.sameName === true
                    opacity: known && dlg.skipDupes && !dlg.replaceAll ? 0.45 : 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8; anchors.rightMargin: 8
                        spacing: 8
                        Text {
                            text: modelData.name
                            color: Theme.text; font.pixelSize: 12
                            Layout.preferredWidth: 150; elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.categoryLabel
                            color: modelData.side === "income" ? Theme.green
                                 : (modelData.side === "cost" ? Theme.red : Theme.textDim)
                            font.pixelSize: 11; Layout.preferredWidth: 110; elide: Text.ElideRight
                        }
                        Text {
                            text: modelData.tail
                            color: Theme.textDim; font.pixelSize: 11
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        Text {
                            visible: prow.known
                            // 똑같은 것과 '이름만 같은 것' 을 갈라 보여 준다 —
                            // 뒤엣것은 가져온 뒤에 금액·분류를 고쳐 둔 항목이다
                            text: modelData.dupe ? "이미 있음" : "이름이 같음"
                            color: Theme.yellow; font.pixelSize: 10
                        }
                        Text {
                            text: modelData.amountText
                            color: Theme.text; font.pixelSize: 12; font.bold: true
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
                objectName: "planImportSkipDupes"
                text: "이미 있는 항목은 건너뛰기"
                enabled: !dlg.replaceAll
                checked: dlg.skipDupes
                onToggled: dlg.skipDupes = checked
            }
            CheckBox {
                objectName: "planImportReplace"
                text: "지금 항목을 모두 지우고 새로 채우기"
                checked: dlg.replaceAll
                onToggled: dlg.replaceAll = checked
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "엑셀에서 고쳐 온 것을 통째로 되돌려 넣을 때 씁니다 (Ctrl+Z 로 되돌릴 수 있습니다)"
            }
            Item { Layout.fillWidth: true }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.fillWidth: true
                visible: dlg.info.count > 0
                text: dlg.replaceAll
                      ? "지금 시나리오의 항목을 모두 지우고 읽어 온 것으로 채웁니다."
                      : "분류를 못 알아본 줄은 건너뜁니다. 목표·기간·시나리오는 건드리지 않습니다."
                color: dlg.replaceAll ? Theme.yellow : Theme.textDim
                font.pixelSize: 11; wrapMode: Text.Wrap
            }
            Button { text: "취소"; flat: true; onClicked: dlg.close() }
            Button {
                objectName: "planImportApply"
                text: dlg.addCount > 0 ? dlg.addCount + "개 가져오기" : "가져오기"
                highlighted: true
                enabled: dlg.addCount > 0
                onClicked: dlg.apply()
            }
        }
    }
}
