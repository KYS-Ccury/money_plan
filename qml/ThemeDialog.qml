import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

// 설정 — 색 모드 고르기.
//
// 고르는 즉시 화면에 적용된다. 모드 하나가 바탕·강조·포인트·수입·지출 색을
// 함께 정하므로(Theme.modes), 여기서는 고르기만 한다.
// 저장은 계획 파일이 아니라 창 상태 ini 에 한다 — 그 PC 의 취향이지 그 계획의
// 내용이 아니기 때문이다.
Popup {
    id: dlg
    objectName: "themeDialog"

    // 열 때의 상태. '되돌리기' 를 누르면 여기로 돌아간다.
    // 이름을 opened 로 두면 안 된다 — Popup 에 같은 이름의 FINAL 속성이 있다.
    property string startMode: Theme.mode
    property string startCustom: Theme.customBg

    function start() {
        dlg.startMode = Theme.mode
        dlg.startCustom = Theme.customBg
        open()
    }

    function apply(modeKey, custom) {
        Theme.mode = modeKey
        Theme.customBg = custom
        backend.saveAppearance(custom, modeKey)
    }

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 560
    padding: Theme.pad + 4
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

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

    ColorDialog {
        id: picker
        objectName: "themeColorPicker"
        title: "바탕색 직접 고르기"
        selectedColor: Theme.bgBase
        onAccepted: dlg.apply(Theme.mode, String(selectedColor))
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text { text: "설정  ·  색"; color: Theme.text; font.pixelSize: 18; font.bold: true }
        Text {
            Layout.fillWidth: true
            text: "모드 하나가 바탕·강조·수입·지출 색을 함께 정합니다. "
                  + "밝은 모드에서는 카드가 바탕보다 희어지고, 어두운 모드에서는 바탕에서 떠오릅니다."
            color: Theme.textDim; font.pixelSize: 12; wrapMode: Text.Wrap
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 10
            rowSpacing: 10

            Repeater {
                model: Theme.modes
                delegate: Rectangle {
                    id: modeCard
                    required property var modelData
                    readonly property bool picked: Theme.mode === modelData.key && Theme.customBg === ""
                    objectName: "mode_" + modelData.key
                    Layout.fillWidth: true
                    Layout.preferredHeight: 74
                    radius: 12
                    color: modelData.bg
                    border.width: picked ? 2 : 1
                    border.color: picked ? modelData.accent
                                         : (cardHover.hovered ? Theme.textDim : Theme.cardBorder)

                    // 그 모드의 바탕 위에서 글자가 어떻게 보이는지 그대로 보여 준다
                    readonly property bool dark:
                        (0.299 * modelData.bg.r + 0.587 * modelData.bg.g + 0.114 * modelData.bg.b) <= 0.5
                    readonly property color ink: dark ? "#e8eaf0" : "#19251f"
                    readonly property color inkDim: dark ? "#8a90a3" : "#778079"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 7
                            Text {
                                text: modeCard.modelData.name
                                color: modeCard.ink; font.pixelSize: 13; font.bold: true
                                Layout.fillWidth: true; elide: Text.ElideRight
                            }
                            Rectangle { width: 11; height: 11; radius: 6; color: modeCard.modelData.accent }
                            Rectangle { width: 11; height: 11; radius: 6; color: modeCard.modelData.point }
                            Rectangle { width: 11; height: 11; radius: 6; color: modeCard.modelData.exp }
                        }
                        Text {
                            text: modeCard.modelData.hint
                            color: modeCard.inkDim; font.pixelSize: 10
                            Layout.fillWidth: true; elide: Text.ElideRight
                        }
                        // 카드와 줄이 그 바탕에서 어떻게 떠오르는지 (작은 미리보기)
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            spacing: 5
                            Rectangle {
                                Layout.fillWidth: true
                                height: 12; radius: 4
                                color: modeCard.dark ? Qt.lighter(modeCard.modelData.bg, 1.5)
                                                     : Qt.lighter(modeCard.modelData.bg, 1.04)
                                border.color: modeCard.dark ? Qt.lighter(modeCard.modelData.bg, 2.0)
                                                            : Qt.darker(modeCard.modelData.bg, 1.08)
                                border.width: 1
                            }
                            Rectangle {
                                width: 46; height: 12; radius: 6
                                color: modeCard.modelData.accent
                            }
                        }
                    }
                    HoverHandler { id: cardHover }
                    TapHandler { onTapped: dlg.apply(modeCard.modelData.key, "") }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "지금 바탕색"; color: Theme.textDim; font.pixelSize: 12 }
            Rectangle {
                width: 22; height: 22; radius: 5
                color: Theme.bgBase
                border.color: Theme.cardBorder; border.width: 1
            }
            Text {
                text: String(Theme.bgBase).toUpperCase()
                      + (Theme.customBg !== "" ? "  (직접 고른 색)" : "")
                color: Theme.text; font.pixelSize: 12
            }
            Item { Layout.fillWidth: true }
            Button {
                objectName: "bgPickCustom"
                text: "바탕색만 직접 고르기…"
                flat: true
                onClicked: picker.open()
                ToolTip.visible: hovered; ToolTip.delay: 500
                ToolTip.text: "고른 모드의 강조·수입·지출 색은 그대로 두고 바탕만 바꿉니다"
            }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                objectName: "bgReset"
                text: "기본 모드로"
                flat: true
                enabled: Theme.mode !== Theme.defaultMode || Theme.customBg !== ""
                onClicked: dlg.apply(Theme.defaultMode, "")
            }
            Button {
                objectName: "bgRevert"
                text: "되돌리기"
                flat: true
                enabled: Theme.mode !== dlg.startMode || Theme.customBg !== dlg.startCustom
                onClicked: dlg.apply(dlg.startMode, dlg.startCustom)
            }
            Item { Layout.fillWidth: true }
            Button {
                objectName: "themeDialogClose"
                text: "닫기"
                highlighted: true
                onClicked: dlg.close()
            }
        }
    }
}
