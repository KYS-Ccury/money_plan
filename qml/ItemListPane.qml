import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts

// 항목 목록 한 판. 본 창 안에도 서고, '따로 띄우기' 로 제 창에도 선다.
//
// 떼어 낸 까닭: 항목이 스무 개를 넘으면 본 창 안에서는 줄 몇 개밖에 안 보여
// 고치기가 불편하다. 같은 backend 를 보므로 어느 쪽에서 고치든 숫자가 함께 간다.
Card {
    id: pane

    // '미래 목록' 스위치는 바깥(본 창)이 쥐고 있다 — 따로 띄운 창에는 그 칸이 없다
    property bool futureOpen: false
    property bool futureSwitchVisible: true
    signal futureToggled(bool on)

    // 미래 보기 — **같은 줄에** '그때 금액' 과 '오늘 대비' 칸을 더한다.
    //
    // 처음에는 목록을 한 벌 더 옆에 세웠다. 그런데 두 목록은 줄이 서로 맞지
    // 않아(분류 머리글·접힘·스크롤이 따로 논다) 무엇이 얼마나 달라졌는지
    // 짚으려면 눈이 양쪽을 오가야 했고, 폭도 둘로 갈라 양쪽 다 좁았다.
    // 한 줄에 두면 눈이 가로로만 움직이고 폭도 덜 든다.
    // 견줄 시점은 **위쪽 '기간'** 이다. 전에는 여기 칩 줄(`언제와 견줄까요`)로
    // 따로 골랐는데, 그러면 한 화면에서 큰 숫자·요약·그래프는 기간을 보고 목록만
    // 다른 달을 보는 일이 생겼다. 바꾸려면 위의 ＋/− 나 1년·2년 단추를 쓴다.
    readonly property int futureMonths: backend.months
    property var futureRows: []
    property var futureSnap: ({ dateText: "", capital: 0, tied: 0, spendable: 0, net: 0 })
    // 견줄 바탕 — 오늘(0개월)의 같은 숫자들
    property var nowSnap: ({ dateText: "", capital: 0, tied: 0, spendable: 0, net: 0 })

    // 미래 보기 머리의 숫자 한 벌: 그때 값 + 오늘 대비.
    // 떼어 낸 창에는 본 창의 '요약' 카드가 없어서, 시점을 눌러도 무엇이 달라졌는지
    // 알 수가 없었다. 그래서 요약을 목록 안으로 들여왔다 — 양쪽 창에 다 선다.
    component SnapFigure: Column {
        id: fig
        required property string label
        required property real value
        required property real base
        property bool warnNegative: false
        property bool neutral: false          // 묶인 돈처럼 늘어난 게 좋은 일도 나쁜 일도 아닌 값
        readonly property real diff: fig.value - fig.base
        spacing: 1
        Text { text: fig.label; color: Theme.textDim; font.pixelSize: 11 }
        Text {
            text: backend.won(fig.value)
            color: (fig.warnNegative && fig.value < 0) ? Theme.red : Theme.text
            font.pixelSize: 15; font.bold: true
        }
        Text {
            text: Math.round(fig.diff) === 0
                  ? "오늘과 같음"
                  : (fig.diff > 0 ? "+" : "−") + backend.won(Math.abs(fig.diff))
            color: (fig.neutral || Math.round(fig.diff) === 0) ? Theme.textDim
                   : (fig.diff > 0 ? Theme.green : Theme.red)
            font.pixelSize: 11
        }
    }

    // 기간이 그대로 시점이 되었으므로 어떤 수든 들어온다 (12 의 배수면 '해' 로 읽는다)
    function futureLabel(k) {
        if (k <= 0) return "오늘"
        return k % 12 === 0 ? (k / 12) + "년 뒤" : k + "개월 뒤"
    }
    function reloadFuture() {
        if (!pane.futureOpen)
            return
        pane.futureRows = backend.itemsAt(pane.futureMonths)
        pane.futureSnap = backend.monthSnapshot(pane.futureMonths)
        pane.nowSnap = backend.monthSnapshot(0)
    }
    // 그 줄의 '그때' 값 (없으면 빈 칸)
    function futureAt(sourceRow) {
        var r = pane.futureRows[sourceRow]
        return r !== undefined ? r : null
    }

    onFutureOpenChanged: reloadFuture()
    onFutureMonthsChanged: reloadFuture()
    Component.onCompleted: reloadFuture()
    Connections {
        target: backend
        function onSummaryChanged() { pane.reloadFuture() }
        function onItemsChanged() { pane.reloadFuture() }
    }

    // 끌어서 떼어 내기. 손잡이를 쥐고 조금 끌면 제 창으로 나간다 (브라우저 탭처럼).
    // 떼어 낸 창에서는 손잡이를 숨긴다 (이미 나와 있으므로).
    property bool detachable: false
    signal detachRequested(real gx, real gy)

    function openAdd() { itemDialog.openForAdd() }
    function openEdit(row) {
        var m = backend.items, idx = m.index(row, 0)
        itemDialog.openForEdit(row, m.data(idx, Qt.UserRole + 1), m.data(idx, Qt.UserRole + 3),
                               m.data(idx, Qt.UserRole + 4), m.data(idx, Qt.UserRole + 6), m.data(idx, Qt.UserRole + 10),
                               m.data(idx, Qt.UserRole + 12), m.data(idx, Qt.UserRole + 13), m.data(idx, Qt.UserRole + 14),
                               m.data(idx, Qt.UserRole + 16), m.data(idx, Qt.UserRole + 18),
                               m.data(idx, Qt.UserRole + 19), m.data(idx, Qt.UserRole + 20),
                               m.data(idx, Qt.UserRole + 21), m.data(idx, Qt.UserRole + 22),
                               m.data(idx, Qt.UserRole + 23), m.data(idx, Qt.UserRole + 27),
                               m.data(idx, Qt.UserRole + 28), m.data(idx, Qt.UserRole + 29),
                               m.data(idx, Qt.UserRole + 30), m.data(idx, Qt.UserRole + 31),
                               m.data(idx, Qt.UserRole + 32), m.data(idx, Qt.UserRole + 33))
    }

    // 팝업은 이 부품이 들고 있는다 — 그래야 본 창에 있든 따로 띄운 창에 있든
    // 같은 몸짓으로 움직인다 (창마다 제 팝업이 뜬다).
    ItemDialog { id: itemDialog }
    ConfirmDialog {
        id: deleteDialog
        property int row: -1
        title: "항목 삭제"
        okText: "삭제"
        onAccepted: backend.removeItem(deleteDialog.row)
    }
    title: "항목 목록  (" + backend.itemCount + "개"
           + (backend.offCount > 0 ? ", " + backend.offCount + "개 꺼짐" : "") + ")"
    ColumnLayout {
        anchors.fill: parent
        spacing: 6
        // 보기 옵션
        Flow {
            Layout.fillWidth: true
            spacing: 8

            // ⠿ 를 쥐고 끌면 목록이 제 창으로 나간다.
            //
            // **끌린 거리는 끄는 동안에 재 둬야 한다.** DragHandler 의
            // activeTranslation 과 centroid 는 손을 떼는 순간 0 으로 돌아가므로,
            // 손을 뗀 뒤에 읽으면 늘 '안 움직였다' 가 된다 (그래서 아무 일도
            // 일어나지 않았다). 여기서는 centroid 가 움직일 때마다 가장 멀리
            // 간 거리와 그때의 화면 좌표를 적어 두고, 뗄 때 그것을 쓴다.
            Item {
                id: grip
                visible: pane.detachable
                implicitWidth: 26; implicitHeight: 28

                property real moved: 0             // 끄는 동안 가장 멀리 간 거리
                property real dropX: 0             // 그때 손이 있던 화면 좌표
                property real dropY: 0
                readonly property int threshold: 40

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: 6
                    color: dragOut.active ? Theme.accentSoft
                                          : (gripHover.hovered ? Theme.rowHover : "transparent")
                    Text {
                        anchors.centerIn: parent
                        text: "⠿"
                        color: dragOut.active ? Theme.accent
                                              : (gripHover.hovered ? Theme.text : Theme.textDim)
                        font.pixelSize: 15
                    }
                }
                HoverHandler {
                    id: gripHover
                    cursorShape: dragOut.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                }
                DragHandler {
                    id: dragOut
                    target: null                   // 아무것도 안 끈다 — 거리만 잰다
                    onCentroidChanged: {
                        if (!dragOut.active)
                            return
                        var t = dragOut.activeTranslation
                        grip.moved = Math.max(grip.moved, Math.abs(t.x) + Math.abs(t.y))
                        var g = grip.mapToGlobal(dragOut.centroid.position.x,
                                                 dragOut.centroid.position.y)
                        grip.dropX = g.x
                        grip.dropY = g.y
                    }
                    onActiveChanged: {
                        if (dragOut.active) {
                            grip.moved = 0         // 새로 쥐었다
                            return
                        }
                        if (grip.moved >= grip.threshold)
                            pane.detachRequested(grip.dropX, grip.dropY)
                    }
                }
                ToolTip.visible: gripHover.hovered && !dragOut.active
                ToolTip.delay: 400
                ToolTip.text: "끌어서 목록만 제 창으로 떼어 냅니다 (Ctrl+Shift+1)"
            }

            // 짝(이름 + 스위치)은 Row 로 묶어 둔다 — 줄이 접혀도 따로 떨어지지 않게
            Row {
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "분류별로 묶기"; color: Theme.textDim; font.pixelSize: 12
                }
                Switch {
                    anchors.verticalCenter: parent.verticalCenter
                    checked: backend.groupByCategory
                    onToggled: backend.groupByCategory = checked
                    implicitHeight: 28
                }
            }
            Row {
                visible: pane.futureSwitchVisible
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "미래 보기"; color: Theme.textDim; font.pixelSize: 12
                }
                Switch {
                    objectName: "futureSwitch"
                    anchors.verticalCenter: parent.verticalCenter
                    checked: pane.futureOpen
                    onToggled: pane.futureToggled(checked)
                    implicitHeight: 28
                    ToolTip.visible: hovered; ToolTip.delay: 500
                    ToolTip.text: "줄마다 '그때 금액' 과 '달라지는 만큼' 칸을 더해 보여 줍니다"
                }
            }
            Text {
                visible: backend.groupByCategory && !pane.futureOpen
                height: 28
                verticalAlignment: Text.AlignVCenter
                text: "헤더를 누르면 접기/펼치기  ·  ▲▼ 는 같은 분류 안에서 옮깁니다"
                color: Theme.textDim; font.pixelSize: 11
            }
            // 시점을 바꾸는 자리는 하나뿐이다 — 어디인지 적어 둔다
            Text {
                visible: pane.futureOpen
                height: 28
                verticalAlignment: Text.AlignVCenter
                text: "위 " + backend.months + "개월 기간과 견줍니다  ·  바꾸려면 위쪽 ＋ / − 를 누르세요"
                color: Theme.textDim; font.pixelSize: 11
                elide: Text.ElideRight
            }
        }
        // 그때의 요약 — 시점을 누르면 이 띠가 함께 바뀐다.
        // (본 창 오른쪽 '요약' 카드는 계획 전체 기간을 보는 것이어서 여기 시점을
        //  따라가지 않는다. 떼어 낸 창에는 그 카드조차 없다.)
        Rectangle {
            Layout.fillWidth: true
            visible: pane.futureOpen
            implicitHeight: band.implicitHeight + 20
            radius: Theme.radius
            color: Theme.accentSoft
            border.width: 1
            border.color: Theme.cardBorder

            Flow {
                id: band
                anchors.left: parent.left; anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 14; anchors.rightMargin: 14
                spacing: 22
                Column {
                    spacing: 1
                    Text { text: "그때"; color: Theme.textDim; font.pixelSize: 11 }
                    Text {
                        text: pane.futureLabel(pane.futureMonths)
                        color: Theme.accent; font.pixelSize: 15; font.bold: true
                    }
                    Text { text: pane.futureSnap.dateText; color: Theme.textDim; font.pixelSize: 11 }
                }
                SnapFigure {
                    label: "보유 자금"; value: pane.futureSnap.capital; base: pane.nowSnap.capital
                }
                SnapFigure {
                    label: "묶인 돈 (보증금)"; neutral: true
                    value: pane.futureSnap.tied; base: pane.nowSnap.tied
                }
                SnapFigure {
                    label: "쓸 수 있는 돈"; warnNegative: true
                    value: pane.futureSnap.spendable; base: pane.nowSnap.spendable
                }
                SnapFigure {
                    label: "순 자본"; value: pane.futureSnap.net; base: pane.nowSnap.net
                }
            }
        }

        // 헤더
        RowLayout {
            Layout.fillWidth: true
            Layout.rightMargin: 12
            spacing: 8
            Text { text: "이름"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 180 }
            Text { text: "분류"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 110 }
            Text { text: "금액"; color: Theme.textDim; font.pixelSize: 12; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
            Text {
                text: "연이율"; color: Theme.textDim; font.pixelSize: 12
                // 줄과 같은 눈금 (줄 폭 = 목록 폭 − 14)
                visible: list.width > 614 && !pane.futureOpen
                Layout.preferredWidth: 64; horizontalAlignment: Text.AlignRight
            }
            Text { text: "월 환산"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 150; horizontalAlignment: Text.AlignRight }
            Text {
                visible: pane.futureOpen
                text: pane.futureLabel(pane.futureMonths)
                color: Theme.accent; font.pixelSize: 12
                Layout.preferredWidth: 120; horizontalAlignment: Text.AlignRight
            }
            Text {
                visible: pane.futureOpen
                text: "달라지는 만큼"; color: Theme.textDim; font.pixelSize: 12
                Layout.preferredWidth: 104; horizontalAlignment: Text.AlignRight
            }
            Item { Layout.preferredWidth: list.width > 614 ? 104 : 56 }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            // 모델은 바꾸지 않는다. 묶기를 끄면 프록시가 원본 순서로 돌아간다
            // (model 이나 section.property 를 런타임에 바꾸면 델리게이트가 파괴되면서 앱이 죽는다)
            model: backend.groupedItems
            boundsBehavior: Flickable.StopAtBounds
            // 분류별 묶기: 같은 분류가 연속으로 오도록 프록시가 정렬하고, 섹션 헤더가 그룹을 나눈다
            // section.property 는 바꾸지 않는다 (바꾸면 섹션 델리게이트가 파괴되면서 앱이 죽는다).
            // 묶기를 끄면 헤더만 숨긴다.
            section.property: "category"
            section.criteria: ViewSection.FullString
            section.labelPositioning: ViewSection.InlineLabels | ViewSection.CurrentLabelAtStart
            section.delegate: Rectangle {
                id: secHeader
                required property string section
                readonly property bool grouped: backend.groupByCategory
                // backend.net / groupsChanged 참조로 값이 바뀔 때마다 다시 계산
                property var info: (backend.net, backend.itemCount, backend.groupSummary(section))
                property bool collapsed: (backend.groupByCategory, backend.isGroupCollapsed(info.catIndex))
                Connections {
                    target: backend
                    function onGroupsChanged() {
                        if (secHeader.info)
                            secHeader.collapsed = backend.isGroupCollapsed(secHeader.info.catIndex)
                    }
                }
                // ListView 가 섹션 아이템의 visible 을 되돌려 놓기 때문에 opacity 로 숨긴다
                opacity: grouped ? 1 : 0
                enabled: grouped
                width: ListView.view.width - 14
                height: grouped ? 36 : 0
                radius: 8
                color: secHover.hovered ? Theme.rowHover : Theme.accentSoft
                border.color: Theme.cardBorder
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                HoverHandler { id: secHover }
                // 탭을 처리하는 도중에 모델을 건드리면 이 헤더 자신이 파괴될 수 있다. 한 박자 미룬다
                TapHandler { onTapped: Qt.callLater(backend.toggleGroup, secHeader.info.catIndex) }
                RowLayout {
                    anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                    spacing: 10
                    Text {
                        text: "▾"
                        color: Theme.accent; font.pixelSize: 13
                        rotation: secHeader.collapsed ? -90 : 0
                        Behavior on rotation { NumberAnimation { duration: Theme.fast } }
                    }
                    Text {                       // 1차 분류 (주거·생활·금융…)
                        text: secHeader.info.group || ""
                        visible: text !== ""
                        color: Theme.textDim; font.pixelSize: 10
                    }
                    Text {
                        text: secHeader.section; color: Theme.text; font.pixelSize: 13; font.bold: true
                        Layout.maximumWidth: 150
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        width: cntText.implicitWidth + 12; height: 18; radius: 9
                        color: Theme.accentSoft
                        Text { id: cntText; anchors.centerIn: parent; text: secHeader.info.count + "개"; color: Theme.text; font.pixelSize: 10 }
                    }
                    Item { Layout.fillWidth: true }
                    Text { text: "합계 " + backend.won(secHeader.info.total); color: Theme.text; font.pixelSize: 12 }
                    Text {
                        visible: secHeader.info.monthly !== 0
                        text: "월 " + (secHeader.info.monthly > 0 ? "+" : "") + backend.won(secHeader.info.monthly)
                        color: secHeader.info.monthly > 0 ? Theme.green : Theme.red
                        font.pixelSize: 12
                    }
                }
            }
            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                visible: list.contentHeight > list.height
                contentItem: Rectangle {
                    implicitWidth: 6; radius: 3
                    color: parent.pressed ? Theme.accent : Theme.accentSoft
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                }
            }
            // 추가 / 삭제 / 이동 애니메이션
            add: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.normal }
                NumberAnimation { property: "x"; from: -40; to: 0; duration: Theme.normal; easing.type: Easing.OutCubic }
            }
            remove: Transition {
                NumberAnimation { property: "opacity"; to: 0; duration: Theme.fast }
                NumberAnimation { property: "x"; to: 60; duration: Theme.fast; easing.type: Easing.InCubic }
            }
            displaced: Transition {
                NumberAnimation { properties: "x,y"; duration: Theme.normal; easing.type: Easing.OutCubic }
            }
            move: Transition {
                NumberAnimation { properties: "x,y"; duration: Theme.normal; easing.type: Easing.OutCubic }
            }
            delegate: Rectangle {
                id: rowItem
                objectName: "itemRow"
                required property int index
                required property string name
                required property string category
                required property int categoryIndex
                required property real amount
                required property string amountText
                required property real rate
                required property string rateText
                required property string monthlyText
                required property string monthlyKind
                required property bool includePrincipal
                required property string startDate
                required property string endDate
                required property var repayments
                required property string subText
                required property real monthlyRepayRate
                required property string repayMethod
                required property string housingType
                required property real monthly
                required property real growth
                required property real support
                required property bool locked
                required property int sourceRow
                required property int groupPos      // 같은 분류 안에서 몇 번째
                required property int groupCount    // 같은 분류가 몇 개
                required property bool active       // 꺼 두면 계산에서 빠진다
                required property int every        // 몇 달마다 되풀이 (0 = 한 번만)
                required property string ledgerCategory   // 가계부에서 볼 분류
                required property bool afterTax    // 이자에서 세금을 떼는가
                required property bool compound    // 복리인가
                required property int payDay       // 매달 며칠에 오가는지
                required property bool asAsset    // 보증금을 자산으로 보는가
                required property string page     // 어느 장에 있는 항목인가
                required property string warn     // 줄에 띄울 경고 ("" = 없음)
                // 접힌 분류의 줄은 목록에서 빼지 않고 높이만 0 으로 접는다
                // (빼 버리면 그 분류의 섹션 헤더까지 사라져 다시 펼 수가 없다)
                property bool folded: backend.groupByCategory && backend.isGroupCollapsed(rowItem.categoryIndex)
                Connections {
                    target: backend
                    function onGroupsChanged() {
                        rowItem.folded = backend.groupByCategory
                                         && backend.isGroupCollapsed(rowItem.categoryIndex)
                    }
                }
                width: ListView.view.width - 14
                // 좁아지면 덜 급한 칸(연이율·▲▼)을 접는다. 안 접으면 칸들이
                // 줄보다 넓어져 **오른쪽 끝의 ✕ 가 잘려 나간다** (줄은 clip 이다).
                readonly property bool roomy: width > 600
                height: folded ? 0 : (subText !== "" ? 54 : 44)
                opacity: folded ? 0 : (rowItem.active ? 1 : 0.45)
                enabled: !folded
                clip: true
                Behavior on height { NumberAnimation { duration: Theme.fast } }
                Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                radius: 8
                color: hover.hovered ? Theme.rowHover : Theme.row
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                // 분류별 왼쪽 색 띠
                Rectangle {
                    width: 4; radius: 2
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom; margins: 8 }
                    color: rowItem.monthlyKind === "income" ? Theme.green
                         : rowItem.monthlyKind === "cost" ? Theme.red
                         : rowItem.monthlyKind === "once" ? Theme.yellow : Theme.accent
                }
                HoverHandler { id: hover }
                TapHandler {
                    onDoubleTapped: itemDialog.openForEdit(backend.sourceRowAt(rowItem.index), rowItem.name, rowItem.categoryIndex,
                                                           rowItem.amount, rowItem.rate, rowItem.includePrincipal,
                                                           rowItem.startDate, rowItem.endDate, rowItem.repayments,
                                                           rowItem.monthlyRepayRate, rowItem.repayMethod,
                                                           rowItem.housingType, rowItem.monthly,
                                                           rowItem.growth, rowItem.support,
                                                           rowItem.locked, rowItem.every,
                                                           rowItem.ledgerCategory,
                                                           rowItem.afterTax, rowItem.compound,
                                                           rowItem.payDay, rowItem.asAsset,
                                                           rowItem.page)
                }
                // 이름 아래 작은 글씨 — 줄 전체 폭을 쓴다
                // (이름 칸 170px 안에 가두면 이자·지원금 같은 금액이 잘려 안 보인다)
                Text {
                    visible: rowItem.subText !== "" && !rowItem.folded
                    text: rowItem.subText
                    color: Theme.textDim; font.pixelSize: 10
                    elide: Text.ElideRight
                    anchors {
                        left: parent.left; right: parent.right; bottom: parent.bottom
                        leftMargin: 18; rightMargin: 12; bottomMargin: 5
                    }
                }
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 18; anchors.rightMargin: 8
                    anchors.bottomMargin: rowItem.subText !== "" ? 14 : 0
                    spacing: 8
                    Text {
                        // 칸이 모자라면 이름이 먼저 줄어든다 (금액이 잘리면 쓸모가 없다)
                        Layout.fillWidth: true
                        Layout.maximumWidth: 170
                        Layout.minimumWidth: 70
                        text: rowItem.name
                        color: Theme.text; font.pixelSize: 14
                        font.strikeout: !rowItem.active      // 계산에서 빠져 있다
                        elide: Text.ElideRight
                    }
                    // 만기 없는 적금처럼 '이대로 두면 숫자가 틀어지는' 설정을 알린다.
                    // 작은 글씨에도 적지만 그 줄은 길어서 묻히므로, 이름 옆에 세운다.
                    Text {
                        visible: rowItem.warn !== ""
                        text: "⚠"
                        color: Theme.yellow; font.pixelSize: 14
                        Layout.preferredWidth: visible ? 16 : 0
                        horizontalAlignment: Text.AlignHCenter
                        HoverHandler { id: warnHover }
                        ToolTip.visible: warnHover.hovered
                        ToolTip.text: rowItem.warn
                    }
                    Rectangle {
                        // 칩은 글자만큼만 (창이 좁아도 금액 칸을 덜 빼앗는다)
                        Layout.preferredWidth: Math.min(104, catText.implicitWidth + 18)
                        Layout.minimumWidth: 48
                        height: 22; radius: 11
                        color: Theme.accentSoft
                        clip: true
                        Text {
                            id: catText
                            anchors.centerIn: parent
                            width: Math.min(implicitWidth, parent.width - 8)
                            text: rowItem.category; color: Theme.text; font.pixelSize: 11
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                    Text {
                        text: rowItem.amountText; color: Theme.text; font.pixelSize: 14
                        Layout.preferredWidth: 120
                        Layout.minimumWidth: 92
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft          // 금액은 뒷자리가 중요하다
                    }
                    Text {
                        text: rowItem.rateText; color: Theme.textDim; font.pixelSize: 13
                        // 좁으면 접는다 (줄 아래 작은 글씨에도 있다).
                        // 미래 보기를 켜면 그 두 칸에 자리를 내준다.
                        visible: rowItem.roomy && !pane.futureOpen
                        Layout.preferredWidth: 60
                        Layout.minimumWidth: 34
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                    }
                    Text {
                        text: rowItem.monthlyText
                        font.pixelSize: 13
                        Layout.preferredWidth: 150
                        Layout.minimumWidth: 70
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft
                        color: rowItem.monthlyKind === "income" ? Theme.green
                             : rowItem.monthlyKind === "cost" ? Theme.red
                             : rowItem.monthlyKind === "once" ? Theme.yellow : Theme.textDim
                    }
                    // ── 미래 보기: 그때 금액과 달라지는 만큼 ──
                    // 같은 줄이라 눈이 가로로만 움직인다
                    Text {
                        visible: pane.futureOpen
                        text: {
                            var f = pane.futureAt(rowItem.sourceRow)
                            return f ? f.amountText : ""
                        }
                        color: Theme.text; font.pixelSize: 14
                        opacity: {
                            var f = pane.futureAt(rowItem.sourceRow)
                            return (f && f.off) ? 0.45 : 1
                        }
                        Layout.preferredWidth: 120
                        Layout.minimumWidth: 80
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideLeft
                    }
                    Text {
                        visible: pane.futureOpen
                        text: {
                            var f = pane.futureAt(rowItem.sourceRow)
                            return f ? f.tail : ""
                        }
                        font.pixelSize: 13
                        color: {
                            var f = pane.futureAt(rowItem.sourceRow)
                            if (!f)
                                return Theme.textDim
                            return f.tone === "plus" ? Theme.green
                                 : f.tone === "minus" ? Theme.red
                                 : f.tone === "warn" ? Theme.yellow : Theme.textDim
                        }
                        Layout.preferredWidth: 104
                        Layout.minimumWidth: 60
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                    }
                    RowLayout {
                        spacing: 0
                        // 단추 칸은 줄어들지 않는다 — 줄어들면 ✕ 가 밖으로 밀린다
                        Layout.preferredWidth: rowItem.roomy ? 160 : 96
                        Layout.minimumWidth: rowItem.roomy ? 160 : 96
                        ToolButton {
                            text: rowItem.active ? "⏸" : "▶"
                            font.pixelSize: 11; implicitWidth: 32
                            Material.foreground: rowItem.active ? Theme.textDim : Theme.yellow
                            onClicked: backend.toggleItemActive(backend.sourceRowAt(rowItem.index))
                            ToolTip.visible: hovered; ToolTip.delay: 500
                            ToolTip.text: rowItem.active
                                          ? "잠시 끕니다 (지우지 않고 계산에서만 뺍니다)"
                                          : "다시 켭니다"
                        }
                        ToolButton {
                            text: "▤"; font.pixelSize: 12; implicitWidth: 32
                            Material.foreground: Theme.accent
                            onClicked: backend.toLedger(backend.sourceRowAt(rowItem.index))
                            ToolTip.visible: hovered; ToolTip.delay: 500
                            ToolTip.text: "이 항목을 가계부에 기록 (이름이 겹치면 넣지 않습니다)"
                        }
                        // 묶어 보면 보이는 차례와 원본 차례가 달라서, 같은 분류 안에서만 옮긴다
                        ToolButton {
                            text: "▲"; font.pixelSize: 11; implicitWidth: 32
                            visible: rowItem.roomy
                            enabled: backend.groupByCategory ? rowItem.groupPos > 0
                                                             : rowItem.index > 0
                            ToolTip.visible: hovered; ToolTip.delay: 700
                            ToolTip.text: backend.groupByCategory ? "같은 분류 안에서 위로" : "위로"
                            onClicked: {
                                var r = backend.sourceRowAt(rowItem.index)
                                if (backend.groupByCategory) backend.moveInGroup(r, -1)
                                else backend.moveItem(r, -1)
                            }
                        }
                        ToolButton {
                            text: "▼"; font.pixelSize: 11; implicitWidth: 32
                            visible: rowItem.roomy
                            enabled: backend.groupByCategory ? rowItem.groupPos < rowItem.groupCount - 1
                                                             : rowItem.index < backend.itemCount - 1
                            ToolTip.visible: hovered; ToolTip.delay: 700
                            ToolTip.text: backend.groupByCategory ? "같은 분류 안에서 아래로" : "아래로"
                            onClicked: {
                                var r = backend.sourceRowAt(rowItem.index)
                                if (backend.groupByCategory) backend.moveInGroup(r, 1)
                                else backend.moveItem(r, 1)
                            }
                        }
                        ToolButton {
                            text: "✕"; font.pixelSize: 12; implicitWidth: 32
                            Material.foreground: Theme.red
                            onClicked: {
                                // 저장해 둔 번호는 그 사이 삭제가 있었으면 밀려 있다. 누르는 순간 다시 확인한다
                                deleteDialog.row = backend.sourceRowAt(rowItem.index)
                                deleteDialog.message = "'" + rowItem.name + "' 항목을 삭제할까요?"
                                deleteDialog.open()
                            }
                        }
                    }
                }
            }
            // 비어 있을 때
            Text {
                anchors.centerIn: parent
                visible: backend.itemCount === 0
                text: "항목이 없습니다.  ＋ 항목 추가 를 눌러 시작하세요."
                color: Theme.textDim
            }
        }
        // 장(페이지) 탭 — 엑셀 시트처럼 목록 아래에 둔다
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }
        PageTabs {
            objectName: "pageTabs"
            Layout.fillWidth: true
        }
        Text {
            text: "행 더블클릭: 수정   ⏸: 잠시 끄기   ▤: 가계부에 기록   ▲▼: 순서   ✕: 삭제"
            color: Theme.textDim; font.pixelSize: 11
        }
    }
}
