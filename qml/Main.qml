import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: win
    visible: true
    width: 1280; height: 840
    minimumWidth: 1100; minimumHeight: 640
    title: "자본금 계산기"
    color: Theme.bg

    Material.theme: Material.Dark
    Material.accent: Theme.accent
    Material.primary: Theme.accent
    Material.background: Theme.bg

    function openAddDialog() { itemDialog.openForAdd() }   // 테스트/외부 호출용
    function showToast(msg) { toast.show(msg, "ok") }       // 테스트/외부 호출용
    function openEditDialog(row) {                          // 테스트/외부 호출용: 해당 행의 수정 팝업
        var m = backend.items, idx = m.index(row, 0)
        itemDialog.openForEdit(row, m.data(idx, Qt.UserRole + 1), m.data(idx, Qt.UserRole + 3),
                               m.data(idx, Qt.UserRole + 4), m.data(idx, Qt.UserRole + 6), m.data(idx, Qt.UserRole + 10),
                               m.data(idx, Qt.UserRole + 12), m.data(idx, Qt.UserRole + 13), m.data(idx, Qt.UserRole + 14),
                               m.data(idx, Qt.UserRole + 16), m.data(idx, Qt.UserRole + 18))
    }

    ItemDialog { id: itemDialog }

    Toast { id: toast }

    // 저장/불러오기 결과를 토스트로 알림
    Connections {
        target: backend
        function onSaved(path) { toast.show("저장되었습니다  ·  " + path, "ok") }
        function onLoaded(path) { toast.show("불러왔습니다  ·  " + path, "info") }
        function onExported(path) { toast.show("엑셀로 내보냈습니다  ·  " + path, "ok") }
        function onFailed(msg) { toast.show(msg, "error") }
    }

    FileDialog {
        id: saveDialog
        title: "다른 이름으로 저장"
        fileMode: FileDialog.SaveFile
        nameFilters: ["JSON 파일 (*.json)"]
        defaultSuffix: "json"
        currentFolder: backend.dataDirUrl
        onAccepted: backend.saveTo(selectedFile.toString())
    }
    FileDialog {
        id: excelDialog
        title: "엑셀로 내보내기"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Excel 파일 (*.xlsx)"]
        defaultSuffix: "xlsx"
        currentFolder: backend.dataDirUrl
        selectedFile: backend.excelDefaultUrl
        onAccepted: backend.exportExcel(selectedFile.toString())
    }
    FileDialog {
        id: openDialog
        title: "불러오기"
        fileMode: FileDialog.OpenFile
        nameFilters: ["JSON 파일 (*.json)"]
        currentFolder: backend.dataDirUrl
        onAccepted: backend.loadFrom(selectedFile.toString())
    }
    ConfirmDialog {
        id: deleteDialog
        property int row: -1
        title: "항목 삭제"
        okText: "삭제"
        onAccepted: backend.removeItem(row)
    }
    ConfirmDialog {
        id: removeScenarioDialog
        title: "시나리오 삭제"
        okText: "삭제"
        message: "\"" + (backend.scenarioNames[backend.activeScenario] || "") + "\" 시나리오와 그 안의 항목을 모두 삭제할까요?"
        onAccepted: backend.removeScenario(backend.activeScenario)
    }
    Popup {
        id: renameDialog
        property int row: -1
        modal: true; focus: true
        anchors.centerIn: Overlay.overlay
        width: 380
        padding: Theme.pad + 4
        background: Rectangle { color: Theme.card; radius: Theme.radius; border.color: Theme.cardBorder; border.width: 1 }
        Overlay.modal: Rectangle { color: "#99000000" }
        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast }
            NumberAnimation { property: "scale"; from: 0.92; to: 1; duration: Theme.normal; easing.type: Easing.OutBack }
        }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
        function openFor(i, name) { row = i; nameField.text = name; open(); nameField.forceActiveFocus(); nameField.selectAll() }
        function commit() { if (nameField.text.trim().length > 0) { backend.renameScenario(row, nameField.text); close() } }
        ColumnLayout {
            anchors.fill: parent
            spacing: 12
            Text { text: "시나리오 이름 변경"; color: Theme.text; font.pixelSize: 17; font.bold: true }
            TextField { id: nameField; Layout.fillWidth: true; placeholderText: "예: 월세 유지 / 전세 이사"; onAccepted: renameDialog.commit() }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                Button { text: "취소"; flat: true; onClicked: renameDialog.close() }
                Button { text: "저장"; highlighted: true; enabled: nameField.text.trim().length > 0; onClicked: renameDialog.commit() }
            }
        }
    }
    ConfirmDialog {
        id: clearDialog
        title: "전체 삭제"
        okText: "전체 삭제"
        message: "모든 항목을 삭제할까요? (목표·기간은 유지됩니다)"
        onAccepted: backend.clearItems()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.pad
        spacing: 12

        // ───────────── 상단 바: 제목 + 버튼, 그 아래 슬라이더 입력
        Card {
            Layout.fillWidth: true
            Layout.preferredHeight: headerCol.implicitHeight + Theme.pad * 2
            ColumnLayout {
                id: headerCol
                anchors.fill: parent
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Text { text: "자본금 계산기"; color: Theme.text; font.pixelSize: 20; font.bold: true }
                    Item { Layout.fillWidth: true }
                    Button { text: "＋ 항목 추가"; highlighted: true; onClicked: itemDialog.openForAdd() }
                    Button {
                        text: "저장"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: backend.save()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "현재 파일에 저장:\n" + backend.dataPath
                    }
                    Button {
                        text: "다른 이름으로"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: saveDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "원하는 위치와 이름으로 저장"
                    }
                    Button {
                        text: "불러오기"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: openDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "JSON 파일 선택해서 불러오기"
                    }
                    Button {
                        text: "엑셀"; flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: Theme.green
                        onClicked: excelDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "요약·항목·월별 추이·비중을 .xlsx 로 내보내기"
                    }
                    Button { text: "예시 데이터"; flat: true; leftPadding: 10; rightPadding: 10; onClicked: backend.loadSample() }
                    Button { text: "전체 삭제"; flat: true; leftPadding: 10; rightPadding: 10; Material.foreground: Theme.red; onClicked: clearDialog.open() }
                }

                // 시나리오 탭: 클릭 = 전환, 더블클릭 = 이름 변경
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text { text: "시나리오"; color: Theme.textDim; font.pixelSize: 12; rightPadding: 4 }
                    Repeater {
                        model: backend.scenarioNames
                        delegate: Rectangle {
                            required property int index
                            required property string modelData
                            readonly property bool on: backend.activeScenario === index
                            width: tabRow.implicitWidth + 24; height: 30; radius: 15
                            color: on ? Theme.accentSoft : (tabHover.hovered ? Theme.rowHover : "transparent")
                            border.color: on ? Theme.scenarioColor(index) : Theme.cardBorder
                            border.width: on ? 1.5 : 1
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                            Behavior on border.color { ColorAnimation { duration: Theme.fast } }
                            Row {
                                id: tabRow
                                anchors.centerIn: parent
                                spacing: 7
                                Rectangle { width: 9; height: 9; radius: 5; color: Theme.scenarioColor(index); anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modelData; color: on ? Theme.text : Theme.textDim; font.pixelSize: 12; font.bold: on }
                            }
                            HoverHandler { id: tabHover }
                            TapHandler {
                                onTapped: backend.activeScenario = index
                                onDoubleTapped: renameDialog.openFor(index, modelData)
                            }
                            ToolTip.visible: tabHover.hovered; ToolTip.delay: 600
                            ToolTip.text: "클릭: 전환  ·  더블클릭: 이름 변경"
                        }
                    }
                    Button {
                        text: "＋ 시나리오"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: backend.addScenario()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "빈 시나리오 추가 (기간·목표·기준일은 현재 것을 이어받음)"
                    }
                    Button {
                        text: "복제"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: backend.duplicateScenario()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "현재 시나리오를 항목까지 통째로 복사"
                    }
                    Button {
                        text: "이름"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: renameDialog.openFor(backend.activeScenario, backend.scenarioNames[backend.activeScenario])
                    }
                    Button {
                        text: "시나리오 삭제"; flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: Theme.red
                        enabled: backend.scenarioCount > 1
                        onClicked: removeScenarioDialog.open()
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        visible: backend.scenarioCount > 1
                        text: "그래프에서 다른 시나리오는 점선으로 겹쳐 보입니다"
                        color: Theme.textDim; font.pixelSize: 11
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 24
                    DateField {
                        label: "기준일 (0개월)"
                        Layout.fillWidth: false
                        Layout.preferredWidth: 170
                        Layout.alignment: Qt.AlignBottom
                        value: backend.basisDate
                        onEdited: (v) => backend.basisDate = v
                    }
                    SliderInput {
                        label: "기간"
                        value: backend.months
                        from: 0; to: 120; stepSize: 1
                        suffix: "개월"
                        fieldWidth: 90
                        Layout.preferredWidth: 1
                        onEdited: (v) => backend.months = Math.round(v)
                    }
                    SliderInput {
                        label: "목표 자본금"
                        value: backend.target
                        from: 0; to: 1000000000; stepSize: 1000000
                        money: true
                        suffix: "원"
                        fieldWidth: 150
                        Layout.preferredWidth: 2
                        onEdited: (v) => backend.target = v
                    }
                }
            }
        }

        // ───────────── 본문
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // 왼쪽: 항목 리스트
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "항목 목록  (" + backend.itemCount + "개)"

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 6

                    // 보기 옵션
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: "분류별로 묶기"; color: Theme.textDim; font.pixelSize: 12 }
                        Switch {
                            checked: backend.groupByCategory
                            onToggled: backend.groupByCategory = checked
                            Layout.preferredHeight: 28
                        }
                        Text {
                            visible: backend.groupByCategory
                            text: "헤더를 누르면 접기/펼치기  ·  묶기 중엔 순서 변경 비활성"
                            color: Theme.textDim; font.pixelSize: 11
                        }
                        Item { Layout.fillWidth: true }
                    }

                    // 헤더
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.rightMargin: 12
                        spacing: 8
                        Text { text: "이름"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 180 }
                        Text { text: "분류"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 110 }
                        Text { text: "금액"; color: Theme.textDim; font.pixelSize: 12; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                        Text { text: "연이율"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 64; horizontalAlignment: Text.AlignRight }
                        Text { text: "월 환산"; color: Theme.textDim; font.pixelSize: 12; Layout.preferredWidth: 150; horizontalAlignment: Text.AlignRight }
                        Item { Layout.preferredWidth: 104 }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder }

                    ListView {
                        id: list
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        spacing: 6
                        model: backend.groupByCategory ? backend.groupedItems : backend.items
                        boundsBehavior: Flickable.StopAtBounds

                        // 분류별 묶기: 같은 분류가 연속으로 오도록 프록시가 정렬하고, 섹션 헤더가 그룹을 나눈다
                        section.property: backend.groupByCategory ? "category" : ""
                        section.criteria: ViewSection.FullString
                        section.labelPositioning: ViewSection.InlineLabels | ViewSection.CurrentLabelAtStart
                        section.delegate: Rectangle {
                            id: secHeader
                            required property string section
                            // backend.net / groupsChanged 참조로 값이 바뀔 때마다 다시 계산
                            property var info: (backend.net, backend.itemCount, backend.groupSummary(section))
                            property bool collapsed: (backend.groupByCategory, backend.isGroupCollapsed(info.catIndex))
                            Connections {
                                target: backend
                                function onGroupsChanged() { secHeader.collapsed = backend.isGroupCollapsed(secHeader.info.catIndex) }
                            }
                            width: ListView.view.width - 14
                            height: 36
                            radius: 8
                            color: secHover.hovered ? "#232a44" : "#1a1f33"
                            border.color: Theme.accentSoft
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                            HoverHandler { id: secHover }
                            TapHandler { onTapped: backend.toggleGroup(secHeader.info.catIndex) }

                            RowLayout {
                                anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                                spacing: 10
                                Text {
                                    text: "▾"
                                    color: Theme.accent; font.pixelSize: 13
                                    rotation: secHeader.collapsed ? -90 : 0
                                    Behavior on rotation { NumberAnimation { duration: Theme.fast } }
                                }
                                Text { text: secHeader.section; color: Theme.text; font.pixelSize: 13; font.bold: true }
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
                            required property int sourceRow

                            width: ListView.view.width - 14
                            height: subText !== "" ? 54 : 44
                            Behavior on height { NumberAnimation { duration: Theme.fast } }
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
                                onDoubleTapped: itemDialog.openForEdit(rowItem.sourceRow, rowItem.name, rowItem.categoryIndex,
                                                                       rowItem.amount, rowItem.rate, rowItem.includePrincipal,
                                                                       rowItem.startDate, rowItem.endDate, rowItem.repayments,
                                                                       rowItem.monthlyRepayRate, rowItem.repayMethod)
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 18; anchors.rightMargin: 8
                                spacing: 8
                                Column {
                                    Layout.preferredWidth: 170
                                    spacing: 1
                                    Text { width: 170; text: rowItem.name; color: Theme.text; font.pixelSize: 14; elide: Text.ElideRight }
                                    Text { width: 170; visible: rowItem.subText !== ""; text: rowItem.subText; color: Theme.textDim; font.pixelSize: 10; elide: Text.ElideRight }
                                }
                                Rectangle {
                                    Layout.preferredWidth: 104; height: 22; radius: 11
                                    color: Theme.accentSoft
                                    Text { anchors.centerIn: parent; text: rowItem.category; color: Theme.text; font.pixelSize: 11 }
                                }
                                Text { text: rowItem.amountText; color: Theme.text; font.pixelSize: 14; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
                                Text { text: rowItem.rateText; color: Theme.textDim; font.pixelSize: 13; Layout.preferredWidth: 64; horizontalAlignment: Text.AlignRight }
                                Text {
                                    text: rowItem.monthlyText
                                    font.pixelSize: 13
                                    Layout.preferredWidth: 150
                                    horizontalAlignment: Text.AlignRight
                                    color: rowItem.monthlyKind === "income" ? Theme.green
                                         : rowItem.monthlyKind === "cost" ? Theme.red
                                         : rowItem.monthlyKind === "once" ? Theme.yellow : Theme.textDim
                                }
                                RowLayout {
                                    spacing: 0
                                    Layout.preferredWidth: 104
                                    ToolButton { text: "▲"; font.pixelSize: 11; implicitWidth: 32; enabled: !backend.groupByCategory && rowItem.sourceRow > 0; onClicked: backend.moveItem(rowItem.sourceRow, -1) }
                                    ToolButton { text: "▼"; font.pixelSize: 11; implicitWidth: 32; enabled: !backend.groupByCategory && rowItem.sourceRow < backend.itemCount - 1; onClicked: backend.moveItem(rowItem.sourceRow, 1) }
                                    ToolButton {
                                        text: "✕"; font.pixelSize: 12; implicitWidth: 32
                                        Material.foreground: Theme.red
                                        onClicked: {
                                            deleteDialog.row = rowItem.sourceRow
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
                    Text { text: "행 더블클릭: 수정   ▲▼: 순서   ✕: 삭제"; color: Theme.textDim; font.pixelSize: 11 }
                }
            }

            // 오른쪽: 요약 + 목표 + 그래프 (세로 스크롤)
            Flickable {
                id: rightFlick
                Layout.fillHeight: true
                Layout.fillWidth: false
                Layout.preferredWidth: 430
                Layout.minimumWidth: 400
                Layout.maximumWidth: 480
                clip: true
                contentWidth: width
                contentHeight: rightCol.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {
                    policy: ScrollBar.AsNeeded
                    visible: rightFlick.contentHeight > rightFlick.height
                    contentItem: Rectangle { implicitWidth: 6; radius: 3; color: Theme.accentSoft }
                }

            ColumnLayout {
                id: rightCol
                width: rightFlick.width - (rightFlick.contentHeight > rightFlick.height ? 10 : 0)
                spacing: 12

                Card {
                    Layout.fillWidth: true
                    Layout.preferredHeight: summaryCol.implicitHeight + Theme.pad * 2 + 30
                    title: "요약"
                    ColumnLayout {
                        id: summaryCol
                        anchors.fill: parent
                        spacing: 6
                        StatRow { label: "보유 자금"; value: backend.capital; valueColor: Theme.green }
                        StatRow {
                            label: "일시 지출"; value: backend.onceCost; prefix: "-"; valueColor: Theme.red
                            visible: backend.onceCost > 0
                        }
                        StatRow {
                            label: "일시 수입"; value: backend.onceIncome; prefix: "+"; valueColor: Theme.green
                            visible: backend.onceIncome > 0
                        }
                        StatRow { label: "월 지출"; value: backend.monthlyCost; prefix: "-"; valueColor: Theme.red }
                        StatRow { label: "월 수입"; value: backend.monthlyIncome; prefix: "+"; valueColor: Theme.green }
                        StatRow { label: "월 순수입"; value: backend.monthlyNet; valueColor: backend.monthlyNet >= 0 ? Theme.green : Theme.red }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                        StatRow { label: backend.months + "개월 필요 자금"; value: backend.required; prefix: "-"; valueColor: Theme.red }
                        StatRow { label: backend.months + "개월 수입"; value: backend.periodIncome; prefix: "+"; valueColor: Theme.green }
                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.cardBorder; Layout.topMargin: 4; Layout.bottomMargin: 4 }
                        StatRow { label: backend.months + "개월 후 순 자본"; value: backend.net; emphasis: true; valueColor: backend.net >= 0 ? Theme.green : Theme.red }
                    }
                }

                // ───────────── 현금 부족 경고
                Card {
                    id: warnCard
                    readonly property var sf: backend.shortfall
                    visible: sf.has
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? warnCol.implicitHeight + Theme.pad * 2 + 30 : 0
                    title: "⚠  현금 부족 경고"
                    border.color: Theme.red

                    ColumnLayout {
                        id: warnCol
                        anchors.fill: parent
                        spacing: 6

                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: warnCard.sf.dateText + " (" + warnCard.sf.month + "개월 뒤) 부터 순 자본이 마이너스입니다"
                            color: Theme.red; font.pixelSize: 14; font.bold: true
                        }
                        StatRow {
                            label: "그 시점 순 자본"
                            value: warnCard.sf.net
                            valueColor: Theme.red
                        }
                        StatRow {
                            label: "최저 " + warnCard.sf.minDateText + " (" + warnCard.sf.minMonth + "개월 뒤)"
                            value: warnCard.sf.minNet
                            valueColor: Theme.red
                            emphasis: true
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            text: warnCard.sf.horizon + "개월 중 " + warnCard.sf.months + "개월이 부족합니다.  "
                                  + "대출 상환 시점을 미루거나 월 지출을 줄여 보세요."
                            color: Theme.textDim; font.pixelSize: 11
                        }
                    }
                }

                Card {
                    Layout.fillWidth: true
                    Layout.preferredHeight: goalCol.implicitHeight + Theme.pad * 2 + 30
                    title: "목표"
                    ColumnLayout {
                        id: goalCol
                        anchors.fill: parent
                        spacing: 8

                        StatRow { label: "목표 자본금"; value: backend.target }

                        // 진행 바
                        Rectangle {
                            Layout.fillWidth: true
                            height: 26; radius: 13
                            color: "#111420"
                            border.color: Theme.cardBorder
                            Rectangle {
                                id: bar
                                property real frac: Math.min(1, backend.progress)
                                Behavior on frac { NumberAnimation { duration: 800; easing.type: Easing.OutCubic } }
                                width: Math.max(height, parent.width * frac)
                                height: parent.height; radius: height / 2
                                color: backend.gap >= 0 ? Theme.green : (backend.progress >= 0.7 ? Theme.yellow : Theme.red)
                                Behavior on color { ColorAnimation { duration: Theme.normal } }
                                // 흐르는 하이라이트
                                Rectangle {
                                    id: shine
                                    width: 60; height: parent.height; radius: parent.radius
                                    opacity: 0.25
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0; color: "transparent" }
                                        GradientStop { position: 0.5; color: "white" }
                                        GradientStop { position: 1; color: "transparent" }
                                    }
                                    SequentialAnimation on x {
                                        loops: Animation.Infinite
                                        NumberAnimation { from: -60; to: bar.width; duration: 1800; easing.type: Easing.InOutSine }
                                        PauseAnimation { duration: 1200 }
                                    }
                                }
                            }
                            Text {
                                anchors.centerIn: parent
                                text: backend.target > 0 ? (backend.progress * 100).toFixed(1) + "%" : "목표 자본금을 입력하세요"
                                color: Theme.text; font.pixelSize: 13; font.bold: true
                                style: Text.Outline; styleColor: "#80000000"
                            }
                        }

                        StatRow {
                            visible: backend.target > 0
                            label: backend.gap >= 0 ? "목표 초과" : "목표 부족"
                            value: Math.abs(backend.gap)
                            prefix: backend.gap >= 0 ? "+" : "-"
                            valueColor: backend.gap >= 0 ? Theme.green : Theme.red
                        }
                        // ── 달성 예측 ──
                        Rectangle {
                            visible: backend.target > 0
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            implicitHeight: predCol.implicitHeight + 20
                            radius: 8
                            color: backend.goalMonth < 0 ? "#2a1b1f" : (backend.goalMonth <= backend.months ? "#17302a" : "#2a2616")
                            border.color: backend.goalMonth < 0 ? Theme.red : (backend.goalMonth <= backend.months ? Theme.green : Theme.yellow)
                            Behavior on color { ColorAnimation { duration: Theme.normal } }
                            Behavior on border.color { ColorAnimation { duration: Theme.normal } }

                            ColumnLayout {
                                id: predCol
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                spacing: 3
                                Text {
                                    text: "달성 예측"
                                    color: Theme.textDim; font.pixelSize: 11
                                }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: 16; font.bold: true
                                    color: parent.parent.border.color
                                    text: backend.goalMonth < 0 ? "현재 입력으로는 50년 안에 도달하지 못합니다"
                                        : backend.goalMonth === 0 ? "이미 목표를 달성했습니다"
                                        : backend.goalDateText + " 달성 예상"
                                }
                                Text {
                                    Layout.fillWidth: true
                                    wrapMode: Text.Wrap
                                    font.pixelSize: 12
                                    color: Theme.textDim
                                    text: backend.goalMonth < 0
                                          ? "최대 " + backend.won(backend.peakNet) + "까지 모입니다. 월 순수입을 " + backend.won(Math.max(0, -backend.gap) / Math.max(1, backend.months)) + " 이상 늘리면 기간 안에 도달합니다."
                                        : backend.goalMonth === 0 ? "기준일 " + backend.basisDate + " 시점에 이미 목표 이상입니다."
                                        : "기준일 " + backend.basisDate + " 로부터 " + backend.goalMonth + "개월 뒤"
                                          + (backend.goalMonth <= backend.months ? "  ·  설정 기간(" + backend.months + "개월) 안에 달성"
                                                                               : "  ·  설정 기간보다 " + (backend.goalMonth - backend.months) + "개월 더 필요")
                                }
                            }
                        }
                    }
                }

                Card {
                    id: pieCard
                    property string group: "보유 자금"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 250
                    title: "비중"

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text { text: "구성"; color: Theme.textDim; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Repeater {
                                model: ["보유 자금", "월 지출", "월 수입"]
                                delegate: Rectangle {
                                    required property string modelData
                                    readonly property bool on: pieCard.group === modelData
                                    width: pieChipText.implicitWidth + 18; height: 24; radius: 12
                                    color: on ? Theme.accent : "transparent"
                                    border.color: on ? Theme.accent : Theme.cardBorder
                                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                                    Text { id: pieChipText; anchors.centerIn: parent; text: modelData; color: on ? "white" : Theme.textDim; font.pixelSize: 11 }
                                    TapHandler { onTapped: pieCard.group = modelData }
                                }
                            }
                        }

                        PieChart {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            // backend.net 참조로 요약이 바뀔 때마다 다시 계산
                            slices: (backend.net, backend.compositionOf(pieCard.group))
                            total: (backend.net, backend.compositionTotal(pieCard.group))
                            centerTitle: pieCard.group
                        }
                    }
                }

                Card {
                    id: chartCard
                    property int horizon: Math.max(12, backend.months)   // 그래프 보기 기간
                    Layout.fillWidth: true
                    Layout.preferredHeight: 400
                    title: backend.scenarioCount > 1 ? "월별 순 자본 추이  ·  시나리오 비교" : "월별 순 자본 추이"

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8

                        // 보기 기간 선택 칩
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text { text: "보기 기간"; color: Theme.textDim; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Repeater {
                                model: [6, 12, 24, 36]
                                delegate: Rectangle {
                                    required property int modelData
                                    readonly property bool on: chartCard.horizon === modelData
                                    width: chipText.implicitWidth + 18; height: 24; radius: 12
                                    color: on ? Theme.accent : "transparent"
                                    border.color: on ? Theme.accent : Theme.cardBorder
                                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                                    Text { id: chipText; anchors.centerIn: parent; text: modelData + "개월"; color: on ? "white" : Theme.textDim; font.pixelSize: 11 }
                                    TapHandler { onTapped: chartCard.horizon = modelData }
                                }
                            }
                        }

                        TrendChart {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 180
                            // backend.net 을 참조해 요약이 바뀔 때마다 다시 계산되게 한다
                            values: (backend.net, backend.trendFor(chartCard.horizon))
                            lineColor: Theme.scenarioColor(backend.activeScenario)
                            series: {
                                var dep = backend.net + backend.scenarioCount          // 요약·시나리오 변경 시 다시 계산
                                var s = backend.compareTrends(chartCard.horizon)
                                for (var i = 0; i < s.length; i++) s[i].color = Theme.scenarioColor(s[i].index)
                                return s
                            }
                            target: backend.target
                            goalMonth: backend.goalMonth
                            shortfallMonth: backend.shortfall.has ? backend.shortfall.month : -1
                            markers: [6, 12, 24, 36].filter(function(m) { return m <= chartCard.horizon })
                        }

                        // 시점별 지표 표: 6 / 12 / 24 / 36 개월
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Repeater {
                                model: backend.milestones
                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    height: 58; radius: 8
                                    color: modelData.month === chartCard.horizon ? Theme.accentSoft : "#111420"
                                    border.color: modelData.month === chartCard.horizon ? Theme.accent : Theme.cardBorder
                                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                                    TapHandler { onTapped: chartCard.horizon = modelData.month }
                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 2
                                        Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.month + "개월"; color: Theme.textDim; font.pixelSize: 11 }
                                        AnimatedMoney {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            value: modelData.net
                                            font.pixelSize: 13
                                            color: modelData.net >= 0 ? Theme.text : Theme.red
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            visible: backend.target > 0
                                            text: (modelData.reached ? "달성 +" : "부족 -") + backend.won(Math.abs(modelData.gap))
                                            color: modelData.reached ? Theme.green : Theme.red
                                            font.pixelSize: 10
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // ───────────── 시나리오 비교표 (2개 이상일 때)
                Card {
                    id: compareCard
                    visible: backend.scenarioCount > 1
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? compareCol.implicitHeight + 20 + 10 + Theme.pad * 2 : 0
                    title: "시나리오 비교  (" + backend.months + "개월 후 기준)"

                    ColumnLayout {
                        id: compareCol
                        anchors.fill: parent
                        spacing: 4

                        Repeater {
                            model: (backend.net, backend.scenarioCount, backend.compareRows())
                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                height: 56; radius: 8
                                color: modelData.active ? Theme.accentSoft : (cmpHover.hovered ? Theme.rowHover : "transparent")
                                border.color: modelData.active ? Theme.scenarioColor(modelData.index) : "transparent"
                                Behavior on color { ColorAnimation { duration: Theme.fast } }
                                HoverHandler { id: cmpHover }
                                TapHandler { onTapped: backend.activeScenario = modelData.index }
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10; anchors.rightMargin: 10
                                    anchors.topMargin: 6; anchors.bottomMargin: 6
                                    spacing: 3
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        Rectangle { width: 10; height: 10; radius: 5; color: Theme.scenarioColor(modelData.index) }
                                        Text { text: modelData.name; color: Theme.text; font.pixelSize: 13; font.bold: modelData.active; elide: Text.ElideRight; Layout.fillWidth: true }
                                        AnimatedMoney { value: modelData.net; font.pixelSize: 14; font.bold: true; color: modelData.net >= 0 ? Theme.text : Theme.red }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10
                                        Text {
                                            text: modelData.active ? "현재 보는 시나리오"
                                                                   : "현재 대비 " + (modelData.diff >= 0 ? "+" : "-") + backend.won(Math.abs(modelData.diff))
                                            color: modelData.active ? Theme.textDim : (modelData.diff >= 0 ? Theme.green : Theme.red)
                                            font.pixelSize: 11
                                        }
                                        Text {
                                            text: "월 " + (modelData.monthlyNet >= 0 ? "+" : "-") + backend.won(Math.abs(modelData.monthlyNet))
                                            color: Theme.textDim; font.pixelSize: 11
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text { text: "달성 " + modelData.goalText; color: Theme.textDim; font.pixelSize: 11; elide: Text.ElideLeft }
                                    }
                                }
                            }
                        }
                        Text {
                            text: "행을 누르면 그 시나리오로 전환됩니다. '현재 대비' 는 지금 보고 있는 시나리오와의 순 자본 차이입니다."
                            color: Theme.textDim; font.pixelSize: 11
                            Layout.fillWidth: true; Layout.preferredWidth: 1
                            wrapMode: Text.Wrap
                        }
                    }
                }
            }   // rightCol
            }   // rightFlick
        }

        // ───────────── 상태 표시줄 (메시지가 바뀔 때 살짝 깜빡)
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                text: "파일: " + backend.dataPath
                color: Theme.textDim
                font.pixelSize: 12
                elide: Text.ElideMiddle
                Layout.maximumWidth: 520
                ToolTip.visible: pathHover.hovered; ToolTip.text: backend.dataPath
                HoverHandler { id: pathHover }
            }
        Text {
            id: statusText
            Layout.fillWidth: true
            text: backend.status
            color: Theme.textDim
            font.pixelSize: 12
            elide: Text.ElideMiddle
            Connections {
                target: backend
                function onStatusChanged() { statusFlash.restart() }
            }
            SequentialAnimation {
                id: statusFlash
                NumberAnimation { target: statusText; property: "opacity"; to: 0.2; duration: 80 }
                NumberAnimation { target: statusText; property: "opacity"; to: 1; duration: 300 }
            }
        }
        }
    }
}
