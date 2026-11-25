import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 계획 화면 맨 위의 짙은 초록 카드 (피그마 시안 '모아' 의 그 카드).
//
// 가장 먼저 봐야 하는 값 — 기간이 끝났을 때의 순 자본과 목표까지의 거리 —
// 하나만 큼직하게 세운다. 보유 자금·월 지출·월 수입을 숫자 카드 셋으로 함께
// 세워 봤지만, 오른쪽 '요약' 카드에 같은 숫자가 그대로 있어 두 번 읽히기만
// 했다. 그래서 뺐다.
ColumnLayout {
    id: hero
    spacing: 10

    readonly property real progress: Math.max(0, Math.min(1, backend.progress))
    readonly property bool reached: backend.gap >= 0

    // ───────────── 짙은 초록 카드
    Rectangle {
        Layout.fillWidth: true
        // 목록이 서야 하므로 꼭 필요한 만큼만 높이를 쓴다
        Layout.preferredHeight: Math.max(128, heroGrid.implicitHeight + 40)
        radius: Theme.radiusBig
        color: Theme.heroBg
        clip: true

        // 오른쪽 위 얇은 원 (시안의 그 장식)
        Rectangle {
            width: 230; height: 230; radius: 115
            color: "transparent"
            border.color: Qt.rgba(1, 1, 1, 0.07); border.width: 1
            anchors { right: parent.right; top: parent.top; rightMargin: -45; topMargin: -145 }
        }

        GridLayout {
            id: heroGrid
            anchors.fill: parent
            anchors.leftMargin: 30; anchors.rightMargin: 30
            anchors.topMargin: 18; anchors.bottomMargin: 18
            columns: hero.width > 820 ? 2 : 1
            columnSpacing: 46
            rowSpacing: 24

            // 왼쪽: 큰 숫자
            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: 6
                Text {
                    text: backend.months + "개월 후 순 자본"
                    color: Theme.heroLabel; font.pixelSize: 11
                }
                AnimatedMoney {
                    value: backend.net
                    color: Theme.heroText
                    font.pixelSize: 32
                    font.bold: true
                }
                Text {
                    Layout.fillWidth: true
                    text: backend.target <= 0
                          ? "목표 자본금을 정하면 달성률이 여기에 섭니다."
                          : (hero.reached
                             ? "목표를 <b>" + backend.won(backend.gap) + "</b> 넘어섰습니다."
                             : "목표의 <b>" + Math.round(hero.progress * 100) + "%</b> 까지 왔습니다  ·  "
                               + backend.won(-backend.gap) + " 남음")
                    textFormat: Text.RichText
                    color: Theme.heroDim; font.pixelSize: 10
                    wrapMode: Text.Wrap
                }
            }

            // 오른쪽: 진행 막대
            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                spacing: 16
                Rectangle {
                    Layout.fillWidth: true
                    height: 13
                    radius: 7
                    color: Qt.rgba(0, 0, 0, 0.18)
                    Rectangle {
                        height: parent.height
                        width: parent.width * hero.progress
                        radius: 7
                        color: Theme.lime
                        Behavior on width { NumberAnimation { duration: Theme.normal; easing.type: Easing.OutCubic } }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Rectangle { width: 7; height: 7; radius: 4; color: Theme.lime }
                    Text { text: "지금 보유"; color: Theme.heroLabel; font.pixelSize: 10 }
                    Text {
                        text: backend.won(backend.capital)
                        color: Theme.heroText; font.pixelSize: 12; font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Rectangle { width: 7; height: 7; radius: 4; color: "#7fa791" }
                    Text { text: "목표"; color: Theme.heroLabel; font.pixelSize: 10 }
                    Text {
                        text: backend.target > 0 ? backend.won(backend.target) : "없음"
                        color: Theme.heroText; font.pixelSize: 12; font.bold: true
                    }
                }
            }
        }
    }
}
