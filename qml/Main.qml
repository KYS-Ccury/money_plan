import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Window

ApplicationWindow {
    id: win
    visible: true
    width: 1280; height: 840
    minimumWidth: 1100; minimumHeight: 640
    title: "자본금 계산기"
    color: Theme.bg

    // 화면 전환: "plan"(계획) | "ledger"(가계부) | "overview"(한눈에)
    property string mode: "plan"
    // 한눈에 보기를 한 번이라도 만들었는가. 한 번 만들면 안 지운다 (아래 Loader)
    property bool overviewReady: false

    // 어느 길로 들어와도 (탭·단축키·저장해 둔 화면) 그때 만들어진다
    onModeChanged: if (win.mode === "overview") win.overviewReady = true

    // 왼쪽 사이드바를 세울 자리가 있는가. 좁으면 접고, 그때는 상단 바의
    // 전환 단추가 대신 선다 (화면을 못 바꾸게 되면 안 되므로).
    readonly property bool sideBarShown: win.width >= 900

    // 미래 보기를 켜 두었는가. 이제 칸을 따로 세우지 않고 목록의 줄에
    // '그때 금액 · 달라지는 만큼' 두 칸이 더해진다.
    property bool futureOpen: false

    // ───────────── 가계부를 따로 띄우기
    // 계획을 고치면서 가계부를 같이 봐야 할 때가 있다. 그래서 가계부만 떼어
    // 다른 창으로 내보낸다. 같은 backend 를 보므로 양쪽 숫자가 저절로 맞는다.
    // 띄워 둔 동안에는 본 창 안의 가계부를 숨긴다 (같은 것이 두 군데 보이면 헷갈린다).
    property bool ledgerPopped: false
    property var ledgerWindow: null
    Component { id: ledgerWindowComp; LedgerWindow { } }

    // ── 항목 목록 따로 띄우기 ──
    // 본 창 안에서는 요약·그래프와 자리를 나눠 쓰느라 목록이 몇 줄뿐이다.
    // 항목이 많아지면 목록만 큰 창으로 떼어 낸다 (가계부와 같은 방식).
    property bool itemsPopped: false
    property var itemWindow: null
    Component { id: itemWindowComp; ItemWindow { } }

    // 항목 목록이 지금 어디에 있든 그것을 가리킨다
    function itemPane() {
        if (win.itemsPopped && win.itemWindow)
            return win.itemWindow.pane
        return itemListPane
    }

    function focusItemWindow() {
        if (win.itemsPopped && win.itemWindow)
            win.itemWindow.focusHere()
    }

    // gx, gy 를 주면 (끌어서 떼어 냈을 때) 그 자리에 창을 띄운다.
    function popItemsOut(gx, gy) {
        if (win.itemsPopped)
            return
        if (!win.itemWindow) {
            win.itemWindow = itemWindowComp.createObject(win)
            if (!win.itemWindow) {             // 못 만들면 그냥 본 창에 둔다
                toast.show("항목 창을 띄우지 못했습니다.", "error")
                return
            }
            win.itemWindow.putBack.connect(win.popItemsIn)
            var st = backend.itemWindowState()
            if (st.has) {
                win.itemWindow.width = Math.max(win.itemWindow.minimumWidth, st.width)
                win.itemWindow.height = Math.max(win.itemWindow.minimumHeight, st.height)
                var scr = win.screen
                if (st.x > -10000 && st.y > -10000 && scr
                    && st.x + 100 < scr.virtualX + scr.desktopAvailableWidth
                    && st.y + 60 < scr.virtualY + scr.desktopAvailableHeight
                    && st.x + st.width > scr.virtualX && st.y + st.height > scr.virtualY) {
                    win.itemWindow.x = st.x
                    win.itemWindow.y = st.y
                }
            }
        }
        // 끌어서 떼어 냈으면 손이 놓인 자리에 창을 둔다 (화면 밖으로는 안 나가게).
        // 좌표를 못 받았으면(단추로 띄운 경우) 지난번 자리를 그대로 쓴다.
        if (gx !== undefined && gy !== undefined && gx > 0 && gy > 0) {
            var scr = win.screen
            var x = gx - win.itemWindow.width / 2
            var y = gy - 28
            if (scr) {
                x = Math.max(scr.virtualX + 10,
                             Math.min(x, scr.virtualX + scr.desktopAvailableWidth
                                         - win.itemWindow.width - 10))
                y = Math.max(scr.virtualY + 10,
                             Math.min(y, scr.virtualY + scr.desktopAvailableHeight
                                         - win.itemWindow.height - 10))
            }
            win.itemWindow.x = x
            win.itemWindow.y = y
        }
        win.itemsPopped = true
        win.mode = "plan"                      // 본 창은 계획 화면에 둔다
        win.itemWindow.focusHere()
        win.rememberItemWindow(true)
    }

    function popItemsIn() {
        if (!win.itemsPopped && !win.itemWindow)
            return
        win.rememberItemWindow(false)
        win.itemsPopped = false
        if (win.itemWindow) {
            var old = win.itemWindow
            win.itemWindow = null
            old.hide()
            old.destroy(1)      // 제 신호(putBack) 안에서 불릴 수 있어 한 박자 뒤에 지운다
        }
    }

    function toggleItemWindow() {
        if (win.itemsPopped)
            win.popItemsIn()
        else
            win.popItemsOut()
    }

    function rememberItemWindow(popped) {
        if (win.itemWindow)
            backend.saveItemWindowState(win.itemWindow.x, win.itemWindow.y,
                                        win.itemWindow.width, win.itemWindow.height, popped)
        else
            backend.saveItemWindowState(popped)
    }

    // 가계부가 지금 어디에 있든 그것을 가리킨다 (단축키·외부 호출은 이것만 쓴다)
    function ledgerPane() {
        if (win.ledgerPopped && win.ledgerWindow)
            return win.ledgerWindow.view
        return ledgerView
    }

    function showLedger() {
        if (win.ledgerPopped && win.ledgerWindow)
            win.ledgerWindow.focusHere()
        else
            win.mode = "ledger"
    }

    function popLedgerOut() {
        if (win.ledgerPopped)
            return
        if (!win.ledgerWindow) {
            win.ledgerWindow = ledgerWindowComp.createObject(win)
            if (!win.ledgerWindow) {           // 못 만들면 그냥 본 창에 둔다
                toast.show("가계부 창을 띄우지 못했습니다.", "error")
                win.mode = "ledger"
                return
            }
            win.ledgerWindow.putBack.connect(win.popLedgerIn)
            var st = backend.ledgerWindowState()
            if (st.has) {
                win.ledgerWindow.width = Math.max(win.ledgerWindow.minimumWidth, st.width)
                win.ledgerWindow.height = Math.max(win.ledgerWindow.minimumHeight, st.height)
                var scr = win.screen
                if (st.x > -10000 && st.y > -10000 && scr
                    && st.x + 100 < scr.virtualX + scr.desktopAvailableWidth
                    && st.y + 60 < scr.virtualY + scr.desktopAvailableHeight
                    && st.x + st.width > scr.virtualX && st.y + st.height > scr.virtualY) {
                    win.ledgerWindow.x = st.x
                    win.ledgerWindow.y = st.y
                }
            }
        }
        win.ledgerPopped = true
        if (win.mode === "ledger")             // 본 창은 빈 자리가 되지 않게 계획으로
            win.mode = "plan"
        win.ledgerWindow.focusHere()
        win.rememberLedgerWindow(true)
    }

    function popLedgerIn() {
        if (!win.ledgerPopped && !win.ledgerWindow)
            return
        win.rememberLedgerWindow(false)
        win.ledgerPopped = false
        win.mode = "ledger"
        if (win.ledgerWindow) {
            var old = win.ledgerWindow
            win.ledgerWindow = null
            old.hide()
            old.destroy(1)      // 제 신호(putBack) 안에서 불릴 수 있어 한 박자 뒤에 지운다
        }
    }

    function toggleLedgerWindow() {
        if (win.ledgerPopped)
            win.popLedgerIn()
        else
            win.popLedgerOut()
    }

    function rememberLedgerWindow(popped) {
        var it = win.ledgerWindow
        if (it)
            backend.saveLedgerWindowState(it.x, it.y, it.width, it.height, popped)
        else
            backend.saveLedgerWindowState(-1, -1, -1, -1, popped)
    }

    // 지난번 창 크기·위치·화면을 그대로 띄운다.
    // 모니터를 바꿨을 수도 있으니 화면 밖으로 나가면 가운데로 되돌린다.
    Component.onCompleted: {
        // 색 먼저 — 창 상태가 없어서 아래에서 일찍 빠져나가도 색은 들어가야 한다
        var look = backend.appearance()
        if (look.mode)
            Theme.mode = look.mode
        Theme.customBg = look.bg || ""

        var st = backend.windowState()
        if (!st.has)
            return
        win.width = Math.max(win.minimumWidth, st.width)
        win.height = Math.max(win.minimumHeight, st.height)
        var scr = win.screen
        if (st.x > -10000 && st.y > -10000 && scr
            && st.x + 100 < scr.virtualX + scr.desktopAvailableWidth
            && st.y + 60 < scr.virtualY + scr.desktopAvailableHeight
            && st.x + st.width > scr.virtualX && st.y + st.height > scr.virtualY) {
            win.x = st.x
            win.y = st.y
        }
        if (st.maximized)
            win.visibility = Window.Maximized
        win.mode = st.mode
        if (backend.ledgerWindowState().popped)   // 지난번에 띄워 두었으면 그대로 띄운다
            win.popLedgerOut()
        if (backend.itemWindowState().popped)
            win.popItemsOut()
    }

    function rememberWindow() {
        var maxed = win.visibility === Window.Maximized || win.visibility === Window.FullScreen
        backend.saveWindowState(win.x, win.y, win.width, win.height, maxed, win.mode)
        win.rememberLedgerWindow(win.ledgerPopped)
        win.rememberItemWindow(win.itemsPopped)
    }

    Material.theme: Theme.light ? Material.Light : Material.Dark
    Material.accent: Theme.accent
    Material.primary: Theme.accent
    Material.background: Theme.bg
    Material.foreground: Theme.text

    function openAddDialog() { win.itemPane().openAdd() }   // 테스트/외부 호출용
    function showToast(msg) { toast.show(msg, "ok") }       // 테스트/외부 호출용
    function openEditDialog(row) {                          // 테스트/외부 호출용: 해당 행의 수정 팝업
        win.itemPane().openEdit(row)
    }

    function openEntryDialog() {                            // 테스트/외부 호출용
        win.showLedger()
        win.ledgerPane().openAdd()
    }
    function openBudgetDialog() {                           // 테스트/외부 호출용
        win.showLedger()
        win.ledgerPane().openBudget()
    }
    function openOverview() {                               // 테스트/외부 호출용
        win.overviewReady = true
        win.mode = "overview"
    }

    GoalsDialog { id: goalsDialog }
    ThemeDialog { id: themeDialog }

    // 단축키 (창 어디서나)
    Shortcut { sequences: ["Ctrl+Z"]; onActivated: backend.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; onActivated: backend.redo() }
    Shortcut { sequences: ["Ctrl+S"]; onActivated: backend.save() }
    Shortcut { sequences: ["Ctrl+Shift+S"]; onActivated: saveDialog.open() }
    Shortcut { sequences: ["Ctrl+O"]; onActivated: openDialog.open() }
    // 가져오기: 계획 화면에서는 항목을, 가계부 화면에서는 내역을 가져온다
    Shortcut {
        sequences: ["Ctrl+I"]
        onActivated: {
            if (win.mode === "ledger") win.ledgerPane().openImport()
            else planImportDialog.start()
        }
    }
    // 지금 보고 있는 화면에 맞는 '새로 추가'
    Shortcut {
        sequences: ["Ctrl+N"]
        onActivated: {
            if (win.mode === "ledger") win.ledgerPane().openAdd()
            else if (win.mode === "plan") win.itemPane().openAdd()
        }
    }
    // 가계부 검색칸으로 (다른 화면이면 가계부로 넘어가면서)
    Shortcut {
        sequences: ["Ctrl+F"]
        onActivated: { win.showLedger(); win.ledgerPane().focusSearch() }
    }
    Shortcut { sequences: ["Ctrl+1"]; onActivated: win.mode = "plan" }
    Shortcut { sequences: ["Ctrl+2"]; onActivated: win.showLedger() }
    Shortcut { sequences: ["Ctrl+3"]; onActivated: win.openOverview() }
    // 가계부를 따로 띄우기 / 본 창으로 되돌리기
    Shortcut { sequences: ["Ctrl+Shift+2"]; onActivated: win.toggleLedgerWindow() }
    Shortcut { sequences: ["Ctrl+Shift+1"]; onActivated: win.toggleItemWindow() }

    // 저장 안 된 채로 닫으려 할 때. forceClose 를 세워 두고 다시 닫는다
    property bool forceClose: false
    onClosing: function(close) {
        win.rememberWindow()
        if (backend.dirty && !win.forceClose) {
            close.accepted = false
            exitDialog.open()
            return
        }
        // 따로 띄운 가계부 창이 남아 있으면 프로그램이 끝나지 않는다
        if (win.ledgerWindow) {
            var old = win.ledgerWindow
            win.ledgerWindow = null
            old.hide()
            old.destroy(1)
        }
    }

    Popup {
        id: exitDialog
        objectName: "exitDialog"
        modal: true
        focus: true
        anchors.centerIn: Overlay.overlay
        padding: Theme.pad + 4
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            color: Theme.card; radius: Theme.radius
            border.color: Theme.cardBorder; border.width: 1
        }
        Overlay.modal: Rectangle { color: "#99000000" }

        function saveAndClose() {
            backend.saveIfDirty()
            win.forceClose = true
            exitDialog.close()
            win.close()
        }
        function closeAnyway() {
            win.forceClose = true
            exitDialog.close()
            win.close()
        }

        ColumnLayout {
            spacing: 14
            Text { text: "저장하지 않고 닫을까요?"; color: Theme.text; font.pixelSize: 17; font.bold: true }
            Text {
                text: "저장 안 된 변경이 있습니다.\n" + backend.dataPath
                color: Theme.textDim; font.pixelSize: 13
                wrapMode: Text.Wrap; Layout.maximumWidth: 420
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                Button { text: "취소"; flat: true; onClicked: exitDialog.close() }
                Button {
                    objectName: "closeAnyway"
                    text: "저장 않고 닫기"; flat: true
                    Material.foreground: Theme.red
                    onClicked: exitDialog.closeAnyway()
                }
                Button {
                    objectName: "saveAndClose"
                    text: "저장하고 닫기"; highlighted: true
                    onClicked: exitDialog.saveAndClose()
                }
            }
        }
    }

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
    // ── 그림(PNG) · PDF 로 내보내기 ──
    // 그래프는 QML 이 그린 것을 그대로 떠서 쓴다 (다시 그리면 화면과 달라진다).
    FileDialog {
        id: pngDialog
        title: "그래프를 그림으로 저장"
        fileMode: FileDialog.SaveFile
        nameFilters: ["PNG 그림 (*.png)"]
        defaultSuffix: "png"
        currentFolder: backend.dataDirUrl
        selectedFile: backend.pngDefaultUrl
        onAccepted: win.grabChart(backend.toLocalPath(selectedFile.toString()), function (ok, path) {
            if (ok) backend.pngSaved(path)
        })
    }
    FileDialog {
        id: pdfDialog
        title: "요약·그래프를 PDF 로 저장"
        fileMode: FileDialog.SaveFile
        nameFilters: ["PDF 문서 (*.pdf)"]
        defaultSuffix: "pdf"
        currentFolder: backend.dataDirUrl
        selectedFile: backend.pdfDefaultUrl
        onAccepted: {
            var target = selectedFile.toString()
            var tmp = backend.tempImagePath()
            win.grabChart(tmp, function (ok, path) {
                backend.exportPdf(target, ok ? path : "")
            })
        }
    }

    // 그래프 카드를 그림 파일로 뜬다. 계획 화면이 아니면 그래프 없이 넘어간다.
    function grabChart(path, done) {
        var card = win.mode === "plan" ? chartCard : null
        if (!card || card.width <= 0) {
            done(false, path)
            return
        }
        // 화면보다 두 배 크게 떠서 인쇄·확대에 견디게 한다
        var ok = card.grabToImage(function (result) {
            done(result.saveToFile(path), path)
        }, Qt.size(card.width * 2, card.height * 2))
        if (!ok)
            done(false, path)
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
    PlanImportDialog { id: planImportDialog }
    ConfirmDialog {
        id: clearDialog
        title: "전체 삭제"
        okText: "전체 삭제"
        message: "모든 항목을 삭제할까요? (목표·기간은 유지됩니다)"
        onAccepted: backend.clearItems()
    }

    // 왼쪽 사이드바 + 본문. 시안('모아')처럼 화면 전환과 시나리오를 세로로 세운다.
    RowLayout {
        anchors.fill: parent
        spacing: 0

        SideBar {
            id: sideBar
            objectName: "sideBar"
            visible: win.sideBarShown
            Layout.fillHeight: true
            Layout.preferredWidth: 230
            Layout.minimumWidth: 230
            Layout.maximumWidth: 230
            mode: win.mode
            ledgerPopped: win.ledgerPopped
            itemsPopped: win.itemsPopped
            onItemsPopRequested: win.toggleItemWindow()
            onModePicked: (m) => {
                if (m === "ledger") win.showLedger()
                else win.mode = m
            }
            onLedgerPopRequested: win.toggleLedgerWindow()
            onRenameRequested: (i, n) => renameDialog.openFor(i, n)
            onSettingsRequested: themeDialog.start()
        }

        ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.margins: Theme.pad
        spacing: 12

        // ───────────── 상단 바: 제목 + 버튼, 그 아래 슬라이더 입력
        Card {
            objectName: "headerCard"
            Layout.fillWidth: true
            Layout.preferredHeight: headerCol.implicitHeight + Theme.pad * 2
            // 창이 낮아지면 이 카드가 눌려서 **맨 아랫줄(목표 자본금)이 잘렸다.**
            // 최소 높이를 정해 두면 대신 아래쪽(목록·그래프)이 줄어든다.
            Layout.minimumHeight: headerCol.implicitHeight + Theme.pad * 2
            ColumnLayout {
                id: headerCol
                anchors.fill: parent
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    // 사이드바가 서면 이름·전환 단추는 거기 있으므로 여기선 숨긴다
                    Text {
                        text: "자본금 계산기"; color: Theme.text; font.pixelSize: 20; font.bold: true
                        visible: !win.sideBarShown
                    }
                    Text {
                        text: "v" + backend.version
                        color: Theme.textDim; font.pixelSize: 11
                        visible: !win.sideBarShown
                        Layout.alignment: Qt.AlignBottom
                        Layout.bottomMargin: 3
                        ToolTip.visible: verHover.hovered; ToolTip.delay: 500
                        ToolTip.text: "무엇이 바뀌었는지는 CHANGELOG.md 에 적혀 있습니다"
                        HoverHandler { id: verHover }
                    }

                    // 계획 / 가계부 전환 (사이드바가 접혔을 때만 — 좁은 창)
                    Row {
                        visible: !win.sideBarShown
                        spacing: 0
                        leftPadding: 12
                        Repeater {
                            model: [{ m: "plan", t: "계획" }, { m: "ledger", t: "가계부" },
                                    { m: "overview", t: "한눈에" }]
                            delegate: Rectangle {
                                required property var modelData
                                // 따로 띄워 둔 가계부는 본 창의 '화면' 이 아니지만,
                                // 켜져 있다는 것은 보여 줘야 한다 (⧉ 를 붙인다)
                                readonly property bool popped: modelData.m === "ledger" && win.ledgerPopped
                                readonly property bool on: win.mode === modelData.m || popped
                                width: 72; height: 32
                                radius: 8
                                color: on ? (popped ? Theme.accentSoft : Theme.accent)
                                          : (tabHover.hovered ? Theme.rowHover : "transparent")
                                border.color: on ? Theme.accent : Theme.cardBorder
                                Behavior on color { ColorAnimation { duration: Theme.fast } }
                                HoverHandler { id: tabHover }
                                TapHandler {
                                    onTapped: {
                                        if (modelData.m === "ledger") win.showLedger()
                                        else win.mode = modelData.m
                                    }
                                }
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.t + (parent.popped ? " ⧉" : "")
                                    color: parent.popped ? Theme.text
                                         : (parent.on ? Theme.card : Theme.textDim)
                                    font.pixelSize: 13
                                    font.bold: parent.on
                                }
                                ToolTip.visible: tabHover.hovered && popped
                                ToolTip.text: "가계부는 따로 띄운 창에 있습니다 (눌러 그 창으로)"
                            }
                        }
                    }

                    Button {
                        objectName: "ledgerWindowButton"
                        text: win.ledgerPopped ? "가계부 본 창으로" : "가계부 따로 띄우기"
                        visible: !win.sideBarShown
                        flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: win.ledgerPopped ? Theme.accent : Theme.textDim
                        onClicked: win.toggleLedgerWindow()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: win.ledgerPopped
                            ? "가계부를 본 창 안으로 다시 넣습니다 (Ctrl+Shift+2)"
                            : "가계부만 다른 창으로 떼어 냅니다 — 계획과 나란히 놓고 볼 때 (Ctrl+Shift+2)"
                    }
                }

                // 단추 줄. Flow 라서 창이 좁아지면 **다음 줄로 내려간다** —
                // RowLayout 이던 때는 줄바꿈이 없어 오른쪽 단추가 창 밖으로 밀려 잘렸다.
                Flow {
                    objectName: "toolbarFlow"
                    Layout.fillWidth: true
                    spacing: 4
                    Button {
                        text: "＋ 항목 추가"; highlighted: true
                        visible: win.mode === "plan"
                        onClicked: win.itemPane().openAdd()
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
                    Text {
                        objectName: "saveState"
                        text: backend.dirty ? "● 저장 안 됨"
                                            : (backend.savedAt !== ""
                                               ? (backend.autosaveOn ? "자동 저장 " : "저장 ") + backend.savedAt
                                               : "")
                        color: backend.dirty ? Theme.yellow : Theme.textDim
                        font.pixelSize: 11
                        height: 40                     // 단추들과 줄을 맞춘다
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 6; rightPadding: 6
                        ToolTip.visible: saveStateHover.hovered
                        ToolTip.text: backend.autosaveOn
                                      ? "고치고 몇 초 지나면 저절로 저장합니다 (" + backend.dataPath + ")"
                                      : "아직 저장한 파일이 없어 자동 저장이 꺼져 있습니다. 한 번 저장하면 켜집니다."
                        HoverHandler { id: saveStateHover }
                    }
                    Button {
                        objectName: "saveButton"
                        text: backend.dirty ? "저장 ●" : "저장"
                        flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: backend.dirty ? Theme.yellow : Theme.text
                        onClicked: backend.save()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "현재 파일에 저장 (Ctrl+S):\n" + backend.dataPath
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
                        objectName: "planImportButton"
                        text: "가져오기"; flat: true; leftPadding: 10; rightPadding: 10
                        visible: win.mode !== "ledger"
                        onClicked: planImportDialog.start()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "엑셀·CSV·메모장에 적어 둔 항목을 계획으로 읽어 옵니다 (Ctrl+I)"
                    }
                    Button {
                        text: "엑셀"; flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: Theme.green
                        onClicked: excelDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500; ToolTip.text: "요약·항목·월별 추이·비중을 .xlsx 로 내보내기"
                    }
                    Button {
                        objectName: "pngButton"
                        text: "그림"; flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: Theme.green
                        visible: win.mode === "plan"
                        onClicked: pngDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "순 자본 추이 그래프를 PNG 그림으로 저장합니다 (화면의 두 배 크기)"
                    }
                    Button {
                        objectName: "pdfButton"
                        text: "PDF"; flat: true; leftPadding: 10; rightPadding: 10
                        Material.foreground: Theme.green
                        onClicked: pdfDialog.open()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "요약·목표·그래프·항목을 A4 한 장으로 저장합니다"
                    }
                    Button { text: "예시 데이터"; flat: true; leftPadding: 10; rightPadding: 10; onClicked: backend.loadSample() }
                    Button { text: "전체 삭제"; flat: true; leftPadding: 10; rightPadding: 10; Material.foreground: Theme.red; onClicked: clearDialog.open() }
                    Button {
                        objectName: "themeButton"
                        // 사이드바가 접혔을 때만 — 평소에는 사이드바 아래 '설정' 이 연다
                        visible: !win.sideBarShown
                        text: "모양"; flat: true; leftPadding: 10; rightPadding: 10
                        onClicked: themeDialog.start()
                        ToolTip.visible: hovered; ToolTip.delay: 500
                        ToolTip.text: "바탕색을 고릅니다 (이 PC 에만 저장됩니다)"
                    }
                }

                // 시나리오 탭: 클릭 = 전환, 더블클릭 = 이름 변경
                // 여기도 Flow — 시나리오가 늘어나면 단추가 창 밖으로 밀려 나간다
                Flow {
                    Layout.fillWidth: true
                    // 시나리오도 사이드바로 옮겼다 (좁을 때만 여기 선다)
                    visible: win.mode === "plan" && !win.sideBarShown
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
                    Text {
                        visible: backend.scenarioCount > 1
                        text: "그래프에서 다른 시나리오는 점선으로 겹쳐 보입니다"
                        color: Theme.textDim; font.pixelSize: 11
                        height: 30; verticalAlignment: Text.AlignVCenter
                        leftPadding: 8
                    }
                }

                // 기준일 · 종료일 · 기간 · 목표 자본금.
                // 창이 좁아지면 넷 → 둘 → 하나로 줄을 나눠 내려앉는다
                // (GridLayout 은 columns 가 바뀌면 알아서 다시 배치한다).
                GridLayout {
                    objectName: "settingsGrid"
                    Layout.fillWidth: true
                    visible: win.mode === "plan"
                    columns: win.width >= 1180 ? 4 : (win.width >= 820 ? 2 : 1)
                    columnSpacing: 24
                    rowSpacing: 10
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
                    // 기간은 기준일과 종료일 사이에서 나온다. 치는 칸과 ± 와 단추가
                    // 모두 같은 `backend.months` 를 밀고, 그러면 종료일이 따라 움직인다.
                    //
                    // 읽기만 하던 `기간 N개월` 글씨 자리에 **입력칸을 앉혔다.** 폭이
                    // 모자라 단추 줄에 끼울 수가 없었고(이 칸은 넷이 한 줄에 서는
                    // 그리드 안이다), 읽던 숫자와 고치는 숫자가 같은 자리에 있는 편이
                    // 눈이 덜 움직인다.
                    ColumnLayout {
                        id: periodBox
                        Layout.fillWidth: false
                        Layout.alignment: Qt.AlignBottom
                        spacing: 2

                        // 600개월(50년)에서 끊는다. 기간은 달마다 수지를 다시 세므로
                        // 손이 미끄러져 99999 가 들어가면 그 자리에서 한참 멈춘다.
                        readonly property int maxMonths: 600
                        // 18 → "1년 6개월". 12 로 안 떨어지면 개월로만 읽는다
                        function periodText(m) {
                            if (m < 12) return m + "개월"
                            var y = Math.floor(m / 12), r = m % 12
                            return r === 0 ? y + "년" : y + "년 " + r + "개월"
                        }
                        function commit(v) {
                            // 칸을 비우면 parseInt 가 NaN 을 준다. 그대로 넘기면 파이썬
                            // 쪽 int(NaN) 에서 터지므로, 여기서 막고 쓰던 값을 되비친다.
                            if (isNaN(v)) { monthsField.sync(); return }
                            v = Math.max(0, Math.min(periodBox.maxMonths, Math.round(v)))
                            if (v !== backend.months) backend.months = v
                            monthsField.sync()      // 걸러진 값(600 넘김 등)을 칸에 되비친다
                        }

                        RowLayout {
                            spacing: 4
                            Text {
                                text: "기간"
                                color: Theme.textDim; font.pixelSize: 12
                            }
                            TextField {
                                id: monthsField
                                objectName: "monthsField"
                                Layout.preferredWidth: 54
                                implicitHeight: 32
                                topPadding: 4; bottomPadding: 4
                                font.pixelSize: 14
                                horizontalAlignment: TextInput.AlignHCenter
                                inputMethodHints: Qt.ImhDigitsOnly
                                validator: IntValidator { bottom: 0; top: periodBox.maxMonths }
                                text: backend.months
                                // 치는 중간값("1" → "18")으로 기간이 출렁이지 않게 잠깐 기다린다.
                                // DateField 도 같은 수를 쓴다.
                                Timer {
                                    id: monthsTimer
                                    interval: 250
                                    onTriggered: periodBox.commit(parseInt(monthsField.text, 10))
                                }
                                function sync() {
                                    if (!activeFocus) text = String(backend.months)
                                }
                                onTextEdited: monthsTimer.restart()
                                onEditingFinished: {
                                    monthsTimer.stop()
                                    periodBox.commit(parseInt(text, 10))
                                }
                                // 칸 안에서 ↑↓ 는 한 달, PageUp/PageDown 은 한 해씩
                                Keys.onUpPressed: periodBox.commit(backend.months + 1)
                                Keys.onDownPressed: periodBox.commit(backend.months - 1)
                                Keys.onPressed: function (e) {
                                    if (e.key === Qt.Key_PageUp) { periodBox.commit(backend.months + 12); e.accepted = true }
                                    else if (e.key === Qt.Key_PageDown) { periodBox.commit(backend.months - 12); e.accepted = true }
                                }
                                Connections {
                                    target: backend
                                    function onMonthsChanged() { monthsField.sync() }
                                }
                                ToolTip.visible: hovered && !activeFocus; ToolTip.delay: 700
                                ToolTip.text: "개월 수를 바로 칩니다  ·  ↑↓ 한 달, PageUp/PageDown 한 해"
                            }
                            Text {
                                text: "개월"
                                color: Theme.textDim; font.pixelSize: 12
                            }
                            // 12 가 넘으면 몇 년 몇 달인지 같이 읽어 준다 (18 → 1년 6개월)
                            Text {
                                visible: backend.months >= 12
                                text: "· " + periodBox.periodText(backend.months)
                                color: Theme.accent; font.pixelSize: 12
                            }
                        }
                        RowLayout {
                            spacing: 4
                            ToolButton {
                                text: "−"
                                font.pixelSize: 16
                                implicitWidth: 34; implicitHeight: 40
                                enabled: backend.months > 0
                                // 꾹 누르면 계속 줄어들어 기간이 저도 모르게 멀리 가 버린다 → 한 번에 한 달
                                onClicked: periodBox.commit(backend.months - 1)
                                ToolTip.visible: hovered; ToolTip.delay: 700
                                ToolTip.text: "종료일을 한 달 당기기"
                            }
                            Repeater {
                                model: [{t: "3개월", m: 3}, {t: "6개월", m: 6}, {t: "1년", m: 12},
                                        {t: "2년", m: 24}, {t: "3년", m: 36}, {t: "5년", m: 60}]
                                ToolButton {
                                    required property var modelData
                                    text: modelData.t
                                    font.pixelSize: 12
                                    implicitHeight: 40
                                    // checkable 을 쓰면 누르는 순간 바인딩이 끊겨 기간이 바뀌어도
                                    // 계속 켜진 채로 남는다. 바인딩만으로 지금 기간을 표시한다.
                                    highlighted: backend.months === modelData.m
                                    onClicked: periodBox.commit(modelData.m)
                                    ToolTip.visible: hovered; ToolTip.delay: 700
                                    ToolTip.text: "종료일을 기준일 + " + modelData.t + " 로"
                                }
                            }
                            ToolButton {
                                text: "＋"
                                font.pixelSize: 14
                                implicitWidth: 34; implicitHeight: 40
                                enabled: backend.months < periodBox.maxMonths
                                onClicked: periodBox.commit(backend.months + 1)
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
        // ───────────── 맨 위 큰 숫자 (짙은 초록 카드 + 숫자 카드 셋)
        // 높이를 '필요한 만큼' 으로 못 박는다. 안 그러면 ColumnLayout 이 남는
        // 자리를 여기에도 나눠 주어 **목록이 두 줄만 보였다.**
        HeroSummary {
            id: heroSummary
            Layout.fillWidth: true
            Layout.fillHeight: false
            Layout.preferredHeight: implicitHeight
            visible: win.mode === "plan"
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            // 남는 세로 자리는 전부 목록 줄이 갖는다
            Layout.minimumHeight: 260
            visible: win.mode === "plan"
            spacing: 12

            // 왼쪽: 항목 리스트 (따로 띄웠으면 여기엔 안내만 둔다)
            ItemListPane {
                id: itemListPane
                objectName: "itemListPane"
                visible: !win.itemsPopped
                Layout.fillWidth: true
                Layout.fillHeight: true
                futureOpen: win.futureOpen
                onFutureToggled: (on) => win.futureOpen = on
                detachable: true
                onDetachRequested: (gx, gy) => win.popItemsOut(gx, gy)
            }

            Card {
                visible: win.itemsPopped
                Layout.fillWidth: true
                Layout.fillHeight: true
                title: "항목 목록"
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    Item { Layout.fillHeight: true }
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "항목 목록은 따로 띄운 창에 있습니다."
                        color: Theme.textDim; font.pixelSize: 13
                    }
                    Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: "그 창으로 가기"
                        flat: true
                        onClicked: win.focusItemWindow()
                    }
                    Button {
                        Layout.alignment: Qt.AlignHCenter
                        text: "본 창으로 되돌리기"
                        highlighted: true
                        onClicked: win.popItemsIn()
                    }
                    Item { Layout.fillHeight: true }
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
                        // 보증금을 자산으로 보면 보유 자금에 그 돈이 들어 있다.
                        // 그게 다 현금인 줄 알면 계획을 잘못 세우므로 갈라 적는다.
                        Text {
                            visible: backend.tiedCapital > 0
                            text: "쓸 수 있는 돈 " + backend.won(backend.capital - backend.tiedCapital)
                                  + "  ·  보증금에 묶인 돈 " + backend.won(backend.tiedCapital)
                            color: Theme.textDim; font.pixelSize: 11
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true; Layout.preferredWidth: 1
                        }
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

                        // ── 물가: 그 돈이 지금 돈으로 얼마인지 ──
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            spacing: 6
                            Text { text: "물가"; color: Theme.textDim; font.pixelSize: 12 }
                            TextField {
                                id: inflationField
                                objectName: "inflationField"
                                Layout.preferredWidth: 64
                                horizontalAlignment: Text.AlignRight
                                placeholderText: "0.0"
                                text: backend.inflation > 0 ? String(backend.inflation) : ""
                                inputMethodHints: Qt.ImhFormattedNumbersOnly
                                Timer {
                                    id: inflationTimer
                                    interval: 300
                                    onTriggered: backend.inflation = parseFloat(inflationField.text) || 0
                                }
                                onTextEdited: inflationTimer.restart()
                                onEditingFinished: {
                                    inflationTimer.stop()
                                    backend.inflation = parseFloat(text) || 0
                                }
                                ToolTip.visible: hovered; ToolTip.delay: 600
                                ToolTip.text: "연 물가 상승률. 넣으면 기간 끝의 돈이 지금 돈으로 얼마인지 보여 줍니다"
                            }
                            Text { text: "%"; color: Theme.textDim; font.pixelSize: 12 }
                            Item { Layout.fillWidth: true }
                            Text {
                                visible: backend.inflation > 0
                                text: "지금 돈으로 " + backend.won(backend.netReal)
                                color: Theme.textDim; font.pixelSize: 12
                            }
                        }
                        Text {
                            visible: backend.inflation > 0 && backend.target > 0
                            Layout.fillWidth: true
                            text: "목표 " + backend.won(backend.target) + " 는 "
                                  + backend.months + "개월 뒤 지금 돈 " + backend.won(backend.targetReal) + " 만큼입니다."
                            color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap
                        }
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
                            text: warnCard.sf.dateText + " (" + warnCard.sf.month + "개월 뒤) 부터 쓸 수 있는 돈이 마이너스입니다"
                            color: Theme.red; font.pixelSize: 14; font.bold: true
                        }
                        StatRow {
                            label: "그 시점 쓸 수 있는 돈"
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
                                  + (backend.tiedCapital > 0
                                     ? "보증금에 묶인 돈은 여기서 빼고 셉니다. 입주 시점을 미루거나 보증금을 줄여 보세요."
                                     : "대출 상환 시점을 미루거나 월 지출을 줄여 보세요.")
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

                        RowLayout {
                            Layout.fillWidth: true
                            StatRow { label: "목표 자본금"; value: backend.target; Layout.fillWidth: true }
                            Button {
                                objectName: "goalsButton"
                                text: backend.goalCount > 0 ? "중간 목표 " + backend.goalCount : "중간 목표"
                                flat: true; leftPadding: 8; rightPadding: 8
                                Material.foreground: backend.goalCount > 0 ? Theme.accent : Theme.textDim
                                onClicked: goalsDialog.open()
                                ToolTip.visible: hovered; ToolTip.delay: 500
                                ToolTip.text: "'1차 전세금' 처럼 거쳐 갈 지점을 적어 둡니다"
                            }
                        }

                        // 진행 바
                        Rectangle {
                            Layout.fillWidth: true
                            height: 26; radius: 13
                            color: Theme.row
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
                        // ── 목표 사다리 (중간 목표가 있을 때만) ──
                        ColumnLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            visible: backend.goalCount > 0
                            spacing: 5

                            Repeater {
                                model: backend.goalRows
                                delegate: ColumnLayout {
                                    id: ladderRow
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 1

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Rectangle {
                                            width: 7; height: 7; radius: 4
                                            color: ladderRow.modelData.reached ? Theme.green
                                                 : (ladderRow.modelData.inPeriod ? Theme.accent : Theme.textDim)
                                        }
                                        Text {
                                            text: ladderRow.modelData.name
                                            color: ladderRow.modelData.final ? Theme.text : Theme.textDim
                                            font.pixelSize: 12
                                            font.bold: ladderRow.modelData.final
                                            Layout.preferredWidth: 96; elide: Text.ElideRight
                                        }
                                        Text {
                                            text: backend.won(ladderRow.modelData.amount)
                                            color: Theme.textDim; font.pixelSize: 11
                                            Layout.fillWidth: true; horizontalAlignment: Text.AlignRight
                                        }
                                        Text {
                                            text: ladderRow.modelData.month < 0 ? "못 닿음"
                                                : ladderRow.modelData.reached ? "이미 달성"
                                                : ladderRow.modelData.dateText
                                                  + " (" + ladderRow.modelData.month + "개월)"
                                            color: ladderRow.modelData.month < 0 ? Theme.red
                                                 : (ladderRow.modelData.inPeriod ? Theme.green : Theme.yellow)
                                            font.pixelSize: 11
                                            Layout.preferredWidth: 150
                                            horizontalAlignment: Text.AlignRight
                                            elide: Text.ElideRight
                                        }
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 4; radius: 2; color: Theme.row
                                        Rectangle {
                                            width: parent.width * Math.max(0, Math.min(1, ladderRow.modelData.progress))
                                            height: parent.height; radius: 2
                                            color: ladderRow.modelData.reached ? Theme.green : Theme.accent
                                            Behavior on width { NumberAnimation { duration: Theme.normal } }
                                        }
                                    }
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: "노랑은 기간(" + backend.months + "개월) 뒤에 닿는 목표입니다."
                                color: Theme.textDim; font.pixelSize: 10
                                visible: backend.goalRows.some(function (g) { return !g.inPeriod && g.month >= 0 })
                            }
                        }

                        // ── 달성 예측 ──
                        Rectangle {
                            visible: backend.target > 0
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            implicitHeight: predCol.implicitHeight + 20
                            radius: 8
                            color: backend.goalMonth < 0 ? Theme.redSoft
                                 : (backend.goalMonth <= backend.months ? Theme.greenSoft : Theme.row)
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

                    // 미래 보기를 켜 두면 그 시점의 비중을 그린다. 끄면 오늘.
                    //
                    // 시점은 위쪽 '기간' 하나로 모았다 — 큰 숫자(`n개월 후 순 자본`)·
                    // 요약·그래프가 보는 달과 같은 달을 본다. 머리에 몇 월 기준인지
                    // 적어 두어 '오늘 것' 으로 잘못 읽지 않게 한다.
                    readonly property int atMonth: win.futureOpen ? backend.months : 0
                    // '목표 구성' 은 기간 전체(앞으로 들어올 돈까지)를 그리는 그림이라
                    // 한 달을 집어 봐야 뜻이 없다 — 시점을 따르지 않는다.
                    readonly property bool followsMonth: pieCard.group !== "목표 구성"
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
                            out.push({ label: "아직 모자람", value: pi.shortfall, color: Theme.cardBorder })
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
                            Text {
                                visible: pieCard.atMonth > 0
                                // backend.net 을 끼워 둔다 — 기준일이 바뀌면 이 글씨도 따라가야 한다
                                text: pieCard.followsMonth
                                      ? (backend.net, backend.monthText(pieCard.atMonth)) + " 기준"
                                      : "기간 전체"
                                color: pieCard.followsMonth ? Theme.accent : Theme.textDim
                                font.pixelSize: 11
                                elide: Text.ElideRight
                                Layout.maximumWidth: 120
                            }
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
                                    : (backend.net, backend.compositionOf(pieCard.group, pieCard.atMonth))
                            total: pieCard.group === "목표 구성"
                                   ? (backend.net, backend.target, pieCard.goalTotal())
                                   : (backend.net, backend.compositionTotal(pieCard.group, pieCard.atMonth))
                            // 모자랄 때는 조각 합이 목표와 같고, 넘칠 때는 목표보다 크다
                            centerTitle: pieCard.followsMonth
                                       ? (pieCard.atMonth > 0
                                          ? pieCard.group + " (" + pieCard.atMonth + "개월 뒤)"
                                          : pieCard.group)
                                       : (backend.pendingInflow.shortfall > 0 ? "목표" : "다 모으면")
                        }

                        // 그 시점에 셀 것이 하나도 없으면 도넛이 빈다 — 왜 비었는지 적는다
                        Text {
                            visible: pieCard.followsMonth && pieCard.atMonth > 0
                                     && backend.compositionTotal(pieCard.group, pieCard.atMonth) <= 0
                            text: (backend.net, backend.monthText(pieCard.atMonth)) + " 에는 " + pieCard.group
                                  + " 으로 잡히는 항목이 없습니다."
                            color: Theme.textDim; font.pixelSize: 11
                            wrapMode: Text.Wrap
                            Layout.fillWidth: true; Layout.preferredWidth: 1
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
                    objectName: "chartCard"
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
                            goals: (backend.net, backend.goalAmounts)
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
                                    color: modelData.month === chartCard.horizon ? Theme.accentSoft : Theme.row
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
        //
        // 예전에는 보지 않을 때 아예 지웠다 (active: mode === "overview").
        // 그러면 들어갈 때마다 카드 열몇 개와 그래프 세 개를 **한 프레임에** 다
        // 만들고 백엔드를 열두 번 부르느라 창이 멈춘다.
        //
        // 그래서 지우지 않고, 대신 OverviewView 가 **안 보이는 동안에는 값을
        // 새로 뜨지 않는다**. 숨겨만 두면 느려졌던 까닭이 그 '다시 계산' 이었으므로
        // 둘을 같이 해야 뜻이 있다.
        Loader {
            id: overviewLoader
            Layout.fillWidth: true
            Layout.fillHeight: true
            asynchronous: true                 // 한 프레임에 몰아 만들지 않는다
            active: win.overviewReady
            visible: win.mode === "overview"
            sourceComponent: OverviewView { }
        }

        // 아직 만들어지는 중일 때 (거의 첫 실행 한 번뿐이다)
        Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: win.mode === "overview" && overviewLoader.status !== Loader.Ready
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: "한눈에 보기를 준비하는 중…"
            color: Theme.textDim; font.pixelSize: 13
        }

        // 시작하고 조금 뒤에 조용히 미리 만들어 둔다. 안 보이는 동안에는 값을
        // 새로 뜨지 않으니 셈하는 값은 없고, 처음 들어갈 때도 바로 뜬다.
        Timer {
            interval: 1500
            running: !win.overviewReady
            onTriggered: win.overviewReady = true
        }

        // ───────────── 본문 (가계부)
        LedgerView {
            objectName: "ledgerView"
            id: ledgerView
            Layout.fillWidth: true
            Layout.fillHeight: true
            // 따로 띄워 두었으면 본 창 안에서는 숨는다 (같은 것이 두 군데 보이면 헷갈린다)
            visible: win.mode === "ledger" && !win.ledgerPopped
        }

        // 가계부를 따로 띄운 동안 '가계부' 자리에 뜨는 안내
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: win.mode === "ledger" && win.ledgerPopped
            Item { Layout.fillHeight: true }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "가계부는 따로 띄운 창에 있습니다"
                color: Theme.textDim; font.pixelSize: 14
            }
            Button {
                Layout.alignment: Qt.AlignHCenter
                text: "본 창으로 다시 넣기"
                flat: true
                onClicked: win.popLedgerIn()
            }
            Item { Layout.fillHeight: true }
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
}
