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

    // 화면 전환: "plan"(계획) | "ledger"(가계부)
    property string mode: "plan"

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
                               m.data(idx, Qt.UserRole + 16), m.data(idx, Qt.UserRole + 18),
                               m.data(idx, Qt.UserRole + 19), m.data(idx, Qt.UserRole + 20),
                               m.data(idx, Qt.UserRole + 21), m.data(idx, Qt.UserRole + 22),
                               m.data(idx, Qt.UserRole + 23))
    }

    function openEntryDialog() {                            // 테스트/외부 호출용
        win.mode = "ledger"
        ledgerView.openAdd()
    }
    function openBudgetDialog() {                           // 테스트/외부 호출용
        win.mode = "ledger"
        ledgerView.openBudget()
    }
    function openOverview() {                               // 테스트/외부 호출용
        win.mode = "overview"
    }

    ItemDialog { id: itemDialog }

    // 되돌리기 / 다시 실행 (창 어디서나)
    Shortcut { sequences: ["Ctrl+Z"]; onActivated: backend.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; onActivated: backend.redo() }

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

                    // 계획 / 가계부 전환
                    Row {
                        spacing: 0
                        leftPadding: 12
                        Repeater {
                            model: [{ m: "plan", t: "계획" }, { m: "ledger", t: "가계부" },
                                    { m: "overview", t: "한눈에" }]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on: win.mode === modelData.m
                                width: 72; height: 32
                                radius: 8
                                color: on ? Theme.accent : (tabHover.hovered ? Theme.rowHover : "transparent")
                                border.color: on ? Theme.accent : Theme.cardBorder
                                Behavior on color { ColorAnimation { duration: Theme.fast } }
                                HoverHandler { id: tabHover }
                                TapHandler { onTapped: win.mode = modelData.m }
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.t
                                    color: parent.on ? "#ffffff" : Theme.textDim
                                    font.pixelSize: 13
                                    font.bold: parent.on
                                }
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }
                    Button {
                        text: "＋ 항목 추가"; highlighted: true
                        visible: win.mode === "plan"
                        onClicked: itemDialog.openForAdd()
                    }
                    Button {
                        objectName: "undoButton"
                        text: "되돌리기"; flat: true; leftPadding: 10; rightPadding: 10
                        enabled: backend.canUndo
                        onClicked: backend.undo()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: backend.canUndo
                                      ? "되돌리기 (Ctrl+Z)
방금 한 일: " + backend.undoLabel
                                      : "되돌릴 것이 없습니다"
                    }
                    Button {
                        objectName: "redoButton"
                        text: "다시"; flat: true; leftPadding: 10; rightPadding: 10
                        visible: backend.canRedo
                        onClicked: backend.redo()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "다시 실행 (Ctrl+Shift+Z)
" + backend.redoLabel
                    }
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
                    visible: win.mode === "plan"
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
                    visible: win.mode === "plan"
                    spacing: 24
                    DateField {
                        label: "기준일 (0개월)"
                        objectName: "basisField"
                        Layout.fillWidth: false
                        Layout.preferredWidth: 150
                        Layout.alignment: Qt.AlignBottom
                        value: backend.basisDate
                        onEdited: (v) => backend.basisDate = v
                    }
                    DateField {
                        label: "종료일"
                        objectName: "endField"
                        Layout.fillWidth: false
                        Layout.preferredWidth: 150
                        Layout.alignment: Qt.AlignBottom
                        value: backend.endDate
                        onEdited: (v) => backend.endDate = v
                    }
                    // 기간은 기준일과 종료일 사이에서 나온다. 직접 치는 칸은 없고,
                    // 자주 쓰는 길이만 단추로 두고 ±는 종료일을 한 달씩 민다.
                    ColumnLayout {
                        Layout.fillWidth: false
                        Layout.alignment: Qt.AlignBottom
                        spacing: 2
                        Text {
                            text: "기간  " + backend.months + "개월"
                            color: Theme.textDim; font.pixelSize: 12
                        }
                        RowLayout {
                            spacing: 4
                            ToolButton {
                                text: "−"
                                font.pixelSize: 16
                                implicitWidth: 34; implicitHeight: 40
                                enabled: backend.months > 0
                                // 꾹 누르면 계속 줄어들어 기간이 저도 모르게 멀리 가 버린다 → 한 번에 한 달
                                onClicked: backend.months = backend.months - 1
                                ToolTip.visible: hovered; ToolTip.delay: 700
                                ToolTip.text: "종료일을 한 달 당기기"
                            }
                            Repeater {
                                model: [{t: "6개월", m: 6}, {t: "1년", m: 12},
                                        {t: "2년", m: 24}, {t: "3년", m: 36}, {t: "5년", m: 60}]
                                ToolButton {
                                    required property var modelData
                                    text: modelData.t
                                    font.pixelSize: 12
                                    implicitHeight: 40
                                    // checkable 을 쓰면 누르는 순간 바인딩이 끊겨 기간이 바뀌어도
                                    // 계속 켜진 채로 남는다. 바인딩만으로 지금 기간을 표시한다.
                                    highlighted: backend.months === modelData.m
                                    onClicked: backend.months = modelData.m
                                    ToolTip.visible: hovered; ToolTip.delay: 700
                                    ToolTip.text: "종료일을 기준일 + " + modelData.t + " 로"
                                }
                            }
                            ToolButton {
                                text: "＋"
                                font.pixelSize: 14
                                implicitWidth: 34; implicitHeight: 40
                                onClicked: backend.months = backend.months + 1
                                ToolTip.visible: hovered; ToolTip.delay: 700
                                ToolTip.text: "종료일을 한 달 미루기"
                            }
                        }
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

        // ───────────── 본문 (계획)
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: win.mode === "plan"
            spacing: 12

            // 왼쪽: 항목 리스트
            Card {
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "항목 목록  (" + backend.itemCount + "개"
                       + (backend.offCount > 0 ? ", " + backend.offCount + "개 꺼짐" : "") + ")"

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
                            text: "헤더를 누르면 접기/펼치기  ·  ▲▼ 는 같은 분류 안에서 옮깁니다"
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
                            color: secHover.hovered ? "#232a44" : "#1a1f33"
                            border.color: Theme.accentSoft
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
                                                                       rowItem.locked)
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
                                    Layout.minimumWidth: 90
                                    text: rowItem.name
                                    color: Theme.text; font.pixelSize: 14
                                    font.strikeout: !rowItem.active      // 계산에서 빠져 있다
                                    elide: Text.ElideRight
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
                                    Layout.minimumWidth: 104
                                    horizontalAlignment: Text.AlignRight
                                    elide: Text.ElideLeft          // 금액은 뒷자리가 중요하다
                                }
                                Text {
                                    text: rowItem.rateText; color: Theme.textDim; font.pixelSize: 13
                                    Layout.preferredWidth: 60
                                    Layout.minimumWidth: 34
                                    horizontalAlignment: Text.AlignRight
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: rowItem.monthlyText
                                    font.pixelSize: 13
                                    Layout.preferredWidth: 150
                                    Layout.minimumWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                    elide: Text.ElideLeft
                                    color: rowItem.monthlyKind === "income" ? Theme.green
                                         : rowItem.monthlyKind === "cost" ? Theme.red
                                         : rowItem.monthlyKind === "once" ? Theme.yellow : Theme.textDim
                                }
                                RowLayout {
                                    spacing: 0
                                    Layout.preferredWidth: 168
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
                    Text {
                        text: "행 더블클릭: 수정   ⏸: 잠시 끄기   ▤: 가계부에 기록   ▲▼: 순서   ✕: 삭제"
                        color: Theme.textDim; font.pixelSize: 11
                    }
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
                        StatRow { label: "보유 자금 (지금)"; value: backend.capital; valueColor: Theme.green }
                        // 적금은 매달 '월 지출' 로 빠져나가지만 그만큼 통장에 쌓인다.
                        // 그 쌓인 돈이 어디로 갔는지 보이지 않아 숫자가 안 맞아 보였다.
                        StatRow {
                            label: backend.months + "개월 후 보유 자금"
                            value: backend.capitalAtEnd; valueColor: Theme.green
                            visible: Math.round(backend.capitalGrowth) !== 0
                        }
                        Text {
                            visible: Math.round(backend.capitalGrowth) !== 0
                            text: "적금 적립 · 예금 이자 · 대출 원금이 더해져 "
                                  + (backend.capitalGrowth >= 0 ? "+" : "-")
                                  + backend.won(Math.abs(backend.capitalGrowth))
                            color: Theme.textDim; font.pixelSize: 11
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true; Layout.preferredWidth: 1
                        }
                        StatRow {
                            label: "일시 지출"; value: backend.onceCost; prefix: "-"; valueColor: Theme.red
                            visible: backend.onceCost > 0
                        }
                        StatRow {
                            label: "일시 수입"; value: backend.onceIncome; prefix: "+"; valueColor: Theme.green
                            visible: backend.onceIncome > 0
                        }
                        // 월 수지는 기간 전체를 반영한다 (기간 중에 시작하는 이자·월세도 센다)
                        StatRow {
                            label: backend.monthlyVaries ? "월 지출 (평균)" : "월 지출"
                            value: backend.avgMonthlyCost; prefix: "-"; valueColor: Theme.red
                        }
                        StatRow {
                            label: backend.monthlyVaries ? "월 수입 (평균)" : "월 수입"
                            value: backend.avgMonthlyIncome; prefix: "+"; valueColor: Theme.green
                        }
                        StatRow {
                            label: backend.monthlyVaries ? "월 순수입 (평균)" : "월 순수입"
                            value: backend.avgMonthlyNet
                            valueColor: backend.avgMonthlyNet >= 0 ? Theme.green : Theme.red
                        }
                        // 기간 중에 달라지면 시작과 끝을 같이 보여 준다
                        Text {
                            visible: backend.monthlyVaries && backend.months > 0
                            text: "지금 " + (backend.monthlyNet >= 0 ? "+" : "-") + backend.won(Math.abs(backend.monthlyNet))
                                  + "  →  " + backend.months + "개월째 "
                                  + (backend.lastMonthlyNet >= 0 ? "+" : "-") + backend.won(Math.abs(backend.lastMonthlyNet))
                            color: Theme.textDim; font.pixelSize: 11
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true; Layout.preferredWidth: 1
                        }
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
                            // 아직 묶여 있지만 돌려받을 보증금 — 다른 색으로 이어 붙인다
                            // 아직 안 들어왔지만 들어올 돈 — 종류마다 색을 달리해 이어 붙인다
                            Repeater {
                                model: backend.pendingInflow.groups
                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    readonly property var pi: backend.pendingInflow
                                    readonly property real fromFrac:
                                        Math.min(1, index === 0 ? pi.progress : pi.groups[index - 1].progressTo)
                                    readonly property real toFrac: Math.min(1, modelData.progressTo)
                                    visible: backend.target > 0 && toFrac > fromFrac
                                    x: Math.max(bar.width, parent.width * fromFrac)
                                    width: Math.max(0, parent.width * toFrac - x)
                                    height: parent.height
                                    radius: height / 2
                                    color: Theme.pendingColor(modelData.kind)
                                    opacity: 0.5
                                    Behavior on width { NumberAnimation { duration: 800; easing.type: Easing.OutCubic } }
                                }
                            }
                            Text {
                                anchors.centerIn: parent
                                text: backend.target <= 0 ? "목표 자본금을 입력하세요"
                                    : backend.pendingInflow.has
                                      ? (backend.progress * 100).toFixed(1) + "%  →  "
                                        + (backend.pendingInflow.progressWith * 100).toFixed(1) + "%"
                                      : (backend.progress * 100).toFixed(1) + "%"
                                color: Theme.text; font.pixelSize: 13; font.bold: true
                                style: Text.Outline; styleColor: "#80000000"
                            }
                        }

                        // ── 앞으로 들어올 돈 ──
                        ColumnLayout {
                            readonly property var pi: backend.pendingInflow
                            Layout.fillWidth: true
                            visible: pi.has && backend.target > 0
                            spacing: 3

                            Repeater {
                                model: backend.pendingInflow.groups
                                delegate: ColumnLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 0

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Rectangle {
                                            width: 10; height: 10; radius: 2
                                            color: Theme.pendingColor(modelData.kind); opacity: 0.6
                                        }
                                        Text {
                                            text: modelData.label
                                            color: Theme.textDim; font.pixelSize: 12
                                        }
                                        Item { Layout.fillWidth: true }
                                        Text {
                                            text: "+" + backend.won(modelData.total)
                                            color: Theme.pendingColor(modelData.kind)
                                            font.pixelSize: 13; font.bold: true
                                        }
                                    }
                                    Text {
                                        text: modelData.name + "  ·  " + modelData.dateText
                                              + " (" + modelData.month + "개월 뒤)"
                                        color: Theme.textDim; font.pixelSize: 11
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true; Layout.preferredWidth: 1
                                        Layout.bottomMargin: 2
                                    }
                                }
                            }

                            Text {
                                text: parent.pi.shortfall <= 0
                                      ? "다 들어오면 목표를 넘어섭니다"
                                      : "다 들어와도 " + backend.won(parent.pi.shortfall) + " 모자랍니다"
                                color: parent.pi.shortfall <= 0 ? Theme.green : Theme.text
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true; Layout.preferredWidth: 1
                                Layout.topMargin: 2
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
                    property string group: "목표 구성"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 310
                    title: "비중"

                    // 목표를 무엇으로 채우는지 — 목표 바와 같은 색을 쓴다
                    function goalSlices() {
                        var pi = backend.pendingInflow
                        var out = []
                        var net = Math.max(0, backend.net)
                        if (net > 0)
                            out.push({ label: "순 자본", value: net, color: Theme.green })
                        // 범례 칸이 좁아 짧은 이름을 쓴다
                        var shortName = { deposit: "보증금 반환", saving: "적금 만기", loan: "받을 대출" }
                        for (var i = 0; i < pi.groups.length; i++)
                            out.push({ label: shortName[pi.groups[i].kind] || pi.groups[i].label,
                                       value: pi.groups[i].total,
                                       color: Theme.pendingColor(pi.groups[i].kind) })
                        if (pi.shortfall > 0)
                            out.push({ label: "아직 모자람", value: pi.shortfall, color: "#39405a" })
                        var total = 0
                        for (var j = 0; j < out.length; j++) total += out[j].value
                        for (var k = 0; k < out.length; k++)
                            out[k].share = total > 0 ? out[k].value / total : 0
                        return out
                    }
                    function goalTotal() {
                        var t = 0
                        var sl = goalSlices()
                        for (var i = 0; i < sl.length; i++) t += sl[i].value
                        return t
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text { text: "구성"; color: Theme.textDim; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Repeater {
                                model: ["목표 구성", "보유 자금", "월 지출", "월 수입"]
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
                            slices: pieCard.group === "목표 구성"
                                    ? (backend.net, backend.target, pieCard.goalSlices())
                                    : (backend.net, backend.compositionOf(pieCard.group))
                            total: pieCard.group === "목표 구성"
                                   ? (backend.net, backend.target, pieCard.goalTotal())
                                   : (backend.net, backend.compositionTotal(pieCard.group))
                            // 모자랄 때는 조각 합이 목표와 같고, 넘칠 때는 목표보다 크다
                            centerTitle: pieCard.group !== "목표 구성" ? pieCard.group
                                       : (backend.pendingInflow.shortfall > 0 ? "목표" : "다 모으면")
                        }

                        // 목표가 없으면 도넛이 비므로 그때만 안내한다
                        Text {
                            visible: pieCard.group === "목표 구성" && backend.target <= 0
                            text: "목표 자본금을 넣으면 무엇으로 채우는지 보여 줍니다."
                            color: Theme.textDim; font.pixelSize: 11
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true; Layout.preferredWidth: 1
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
                            objectName: "trendChart"
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

        // ───────────── 본문 (한눈에 보기)
        OverviewView {
            objectName: "overviewView"
            id: overviewView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: win.mode === "overview"
        }

        // ───────────── 본문 (가계부)
        LedgerView {
            objectName: "ledgerView"
            id: ledgerView
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: win.mode === "ledger"
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
