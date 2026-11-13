import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 항목 추가 / 수정 팝업
Popup {
    id: dlg
    objectName: "itemDialog"
    property int editRow: -1                 // -1 이면 추가, 아니면 수정
    property var info: backend.categoryInfo(0)
    property real amount: 0
    property real rate: 0
    property string startDate: ""
    property string onceDate: ""        // 일시 지출·일시 수입의 지출일/수입일
    property int every: 0               // 일시 지출·수입이 몇 개월마다 되풀이되는지 (0 = 한 번만)
    // 되풀이를 정할 수 있는가 — 일시 지출·일시 수입만 (보증금은 돌려받는 돈이라 뺀다)
    readonly property bool canRepeat: dlg.info.dateMode === "once" && !dlg.info.isHousing
                                      && !dlg.info.returnable
    property string endDate: ""
    property real monthlyRepayRate: 0
    property string repayMethod: "bullet"
    property string housingType: "jeonse"   // 전세 / 반전세 / 월세 / 매매
    property real monthly: 0                // 주거의 월세
    property real growth: 0                 // 연 상승률 % (급여 인상, 물가·월세 인상)
    property real support: 0                // 적금 월 지원금 (청년도약계좌처럼 보태 주는 돈)
    property bool locked: false             // 만기 전까지 못 쓰는 돈으로 볼지 (적금)
    // 주거 형태별 입력 안내 (금액 이름, 월세 사용 여부, 반환 가능 여부)
    readonly property var houseInfo: backend.housingInfo(housingType)
    // 대출 상환 미리보기 (원금·이율·방식·기간이 바뀌면 다시 계산)
    readonly property var loanInfo: backend.loanPreview(amount, rate, repayMethod, startDate, endDate, monthlyRepayRate)

    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 500
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

    // 중도 상환 목록 (팝업 안에서만 쓰는 임시 모델)
    ListModel { id: repModel }

    function repaymentsJson() {
        var arr = []
        for (var i = 0; i < repModel.count; i++) {
            var r = repModel.get(i)
            arr.push({ date: r.date, amount: parseFloat(String(r.amount).replace(/,/g, "")) || 0 })
        }
        return JSON.stringify(arr)
    }
    function loadRepayments(list) {
        repModel.clear()
        if (!list) return
        for (var i = 0; i < list.length; i++)
            repModel.append({ date: String(list[i].date || ""), amount: Number(list[i].amount || 0) })
    }

    function openForAdd() {
        editRow = -1
        nameField.text = ""
        catBox.currentIndex = 0   // 현금/자산
        amount = 0
        rate = 0
        startDate = backend.basisDate
        endDate = ""
        onceDate = ""
        every = 0
        principalCheck.checked = true
        monthlyRepayRate = 0
        setRepayMethod("bullet")
        setHousingType("jeonse")
        monthly = 0
        growth = 0
        support = 0
        locked = false
        repModel.clear()
        open(); nameField.forceActiveFocus()
    }
    function setHousingType(v) {
        dlg.housingType = v || "jeonse"
        houseBox.currentIndex = Math.max(0, houseBox.indexOfValue(dlg.housingType))
    }
    function setRepayMethod(v) {
        dlg.repayMethod = v || "bullet"
        methodBox.currentIndex = Math.max(0, methodBox.indexOfValue(dlg.repayMethod))
    }
    function openForEdit(row, name, catIndex, amount, rate, includePrincipal, startDate, endDate, repayments,
                         monthlyRepayRate, repayMethod, housingType, monthly, growth, support, locked, every) {
        editRow = row
        nameField.text = name
        catBox.currentIndex = catIndex
        dlg.amount = amount
        dlg.rate = rate
        dlg.startDate = startDate || backend.basisDate
        dlg.endDate = endDate || ""
        dlg.onceDate = startDate || ""
        principalCheck.checked = includePrincipal
        dlg.monthlyRepayRate = monthlyRepayRate || 0
        setRepayMethod(repayMethod)
        setHousingType(housingType)
        dlg.monthly = monthly || 0
        dlg.growth = growth || 0
        dlg.support = support || 0
        dlg.locked = locked === true
        dlg.every = every || 0
        loadRepayments(repayments)
        open(); nameField.forceActiveFocus()
    }
    function datesValid() {
        if (dlg.info.dateMode === "range" && !(startField.valid && endField.valid)) return false
        if (dlg.info.dateMode === "once" && !onceField.valid) return false
        if (returnField.visible && !returnField.valid) return false
        if (dlg.info.isLoan && dlg.loanInfo.needsEnd) return false      // 원금·원리금 균등은 만기 필요
        return true
    }
    function submit() {
        if (!datesValid()) return
        var sd = dlg.info.dateMode === "range" ? startDate : (dlg.info.dateMode === "once" ? onceDate : "")
        var returnable = dlg.info.isHousing ? dlg.houseInfo.returnable : dlg.info.returnable
        var repeating = dlg.canRepeat && dlg.every > 0
        var ed = (dlg.info.dateMode === "range" || returnable || repeating) ? endDate : ""
        var ht = dlg.info.isHousing ? dlg.housingType : ""
        var mo = (dlg.info.isHousing && dlg.houseInfo.usesRent) ? dlg.monthly : 0
        var gr = dlg.info.usesGrowth ? dlg.growth : 0
        var sp = dlg.info.usesSupport ? dlg.support : 0
        var lk = dlg.info.canLock ? dlg.locked : false
        var method = dlg.info.isLoan ? dlg.repayMethod : ""
        var mr = (dlg.info.isLoan && dlg.repayMethod === "rate") ? monthlyRepayRate : 0
        if (editRow < 0)
            backend.addItem(nameField.text, catBox.currentIndex, amount, rate, principalCheck.checked, sd, ed, repaymentsJson(), mr, method, ht, mo, gr, sp, lk, repeating ? dlg.every : 0)
        else
            backend.updateItem(editRow, nameField.text, catBox.currentIndex, amount, rate, principalCheck.checked, sd, ed, repaymentsJson(), mr, method, ht, mo, gr, sp, lk, repeating ? dlg.every : 0)
        close()
    }

    contentItem: Flickable {
        implicitWidth: col.implicitWidth
        implicitHeight: Math.min(col.implicitHeight, Overlay.overlay ? Overlay.overlay.height - 120 : 600)
        contentHeight: col.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: col
            width: parent.width
            spacing: 12

            Text {
                text: dlg.editRow < 0 ? "항목 추가" : "항목 수정"
                color: Theme.text; font.pixelSize: 18; font.bold: true
            }

            TextField {
                id: nameField
                Layout.fillWidth: true
                placeholderText: "이름 (비우면 분류명 사용)"
                onAccepted: dlg.submit()
            }

            ComboBox {
                id: catBox
                objectName: "itemCategory"
                Layout.fillWidth: true
                model: backend.categories
                onCurrentIndexChanged: dlg.info = backend.categoryInfo(currentIndex)
            }
            Text {
                text: dlg.info.hint
                color: Theme.textDim; font.pixelSize: 12
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }

            // ── 주거 형태 (전세 / 반전세 / 월세 / 매매) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.info.isHousing

                Text { text: "주거 형태"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                ComboBox {
                    id: houseBox
                    objectName: "housingBox"
                    Layout.fillWidth: true
                    model: backend.housingTypes
                    textRole: "label"
                    valueRole: "value"
                    onActivated: dlg.housingType = houseBox.currentValue
                }
                Text {
                    text: dlg.houseInfo.hint
                    color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
                }
            }

            SliderInput {
                objectName: "amountInput"
                label: dlg.info.isHousing ? dlg.houseInfo.amountLabel : dlg.info.amountLabel
                value: dlg.amount
                from: 0; to: 1000000000; stepSize: 100000
                money: true
                suffix: "원"
                onEdited: (v) => dlg.amount = v
            }

            SliderInput {
                objectName: "rentInput"
                visible: dlg.info.isHousing && dlg.houseInfo.usesRent
                label: "월세"
                value: dlg.monthly
                from: 0; to: 5000000; stepSize: 10000
                money: true
                suffix: "원"
                onEdited: (v) => dlg.monthly = v
            }

            // ── 월 지원금 (청년도약계좌처럼 남이 보태 주는 돈) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                visible: dlg.info.usesSupport

                SliderInput {
                    objectName: "supportInput"
                    label: "월 지원금"
                    value: dlg.support
                    from: 0; to: 2000000; stepSize: 10000
                    money: true
                    suffix: "원"
                    onEdited: (v) => dlg.support = v
                }
                Text {
                    text: dlg.support > 0
                          ? "내 돈 " + backend.won(dlg.amount) + " + 지원 " + backend.won(dlg.support)
                            + " = 매달 " + backend.won(dlg.amount + dlg.support) + " 이 쌓입니다. "
                            + "나가는 돈은 내 돈뿐이라 지원금만큼 순 자본이 늘어납니다."
                          : "청년도약계좌처럼 정부·회사가 보태 주는 돈이 있으면 넣으세요. 통장에는 쌓이지만 내 지갑에서는 안 나갑니다."
                    color: dlg.support > 0 ? Theme.green : Theme.textDim
                    font.pixelSize: 11; wrapMode: Text.Wrap
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                }
            }

            // ── 만기 전까지 묶인 돈 (적금) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                visible: dlg.info.canLock

                CheckBox {
                    objectName: "lockedCheck"
                    text: "만기 전까지는 못 쓰는 돈"
                    checked: dlg.locked
                    onToggled: dlg.locked = checked
                }
                Text {
                    text: !dlg.locked
                          ? "켜면 만기가 될 때까지 보유 자금·순 자본·목표에서 빼고, 만기에 한꺼번에 들어오는 것으로 봅니다."
                          : (endField.value === "" || !endField.valid)
                            ? "⚠ 만기(종료일)를 넣어야 묶임이 적용됩니다."
                            : "만기까지 목표 바에 '만기에 받을 적금' 으로 따로 표시됩니다."
                    color: dlg.locked && (endField.value === "" || !endField.valid) ? Theme.yellow : Theme.textDim
                    font.pixelSize: 11; wrapMode: Text.Wrap
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                    Layout.bottomMargin: 4
                }
            }

            // ── 해마다 오르는 금액 (급여 인상, 물가·월세 인상) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                visible: dlg.info.usesGrowth

                SliderInput {
                    objectName: "growthInput"
                    label: "연 상승률"
                    value: dlg.growth
                    from: 0; to: 20; stepSize: 0.5
                    decimals: 1
                    suffix: "%"
                    onEdited: (v) => dlg.growth = v
                }
                Text {
                    readonly property var gp: backend.growthPreview(dlg.amount, dlg.growth, 3)
                    text: dlg.growth > 0
                          ? "1년마다 한 번씩 오릅니다.  " + gp.text
                          : "해마다 오르는 돈이면 상승률을 넣으세요 (급여 인상, 물가·월세 인상)"
                    color: dlg.growth > 0 ? Theme.green : Theme.textDim
                    font.pixelSize: 11; wrapMode: Text.Wrap
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                }
            }

            // ── 지출/수입 시점 (보증금 / 일시 지출 / 일시 수입) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.info.dateMode === "once"

                Text {
                    text: dlg.info.isHousing ? "계약 기간" : dlg.info.onceWord + " 시점"
                    color: Theme.text; font.pixelSize: 13; font.bold: true
                }
                DateField {
                    id: onceField
                    Layout.fillWidth: true
                    label: dlg.info.isHousing ? (dlg.housingType === "buy" ? "잔금일" : "입주일") : dlg.info.onceWord + "일"
                    placeholder: (dlg.info.isHousing ? (dlg.housingType === "buy" ? "잔금일" : "입주일")
                                                     : dlg.info.onceWord + "일") + " (비우면 기준일)"
                    value: dlg.onceDate
                    optional: true
                    onEdited: (v) => dlg.onceDate = v
                }
                DateField {
                    id: returnField
                    Layout.fillWidth: true
                    visible: dlg.info.isHousing ? dlg.houseInfo.returnable : dlg.info.returnable
                    label: dlg.info.isHousing ? "계약 만기" : "반환일"
                    placeholder: (dlg.info.isHousing ? "계약 만기" : "반환일") + " (비우면 계속)"
                    value: dlg.endDate
                    optional: true
                    onEdited: (v) => dlg.endDate = v
                }
                Text {
                    visible: returnField.visible
                    text: "계약이 끝나 보증금을 돌려받는 달입니다. 그 달부터 순 자본에 다시 들어옵니다."
                    color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
                }
                Text {
                    visible: !dlg.info.isHousing
                    text: dlg.info.flow === "income"
                          ? "비우면 기준일 " + backend.basisDate + " 에 들어옵니다. 날짜를 넣으면 그 달에 순 자본이 늘어납니다."
                          : "비우면 기준일 " + backend.basisDate + " 에 나갑니다. 날짜를 넣으면 그 달에 순 자본이 줄어듭니다."
                    color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
                }

                // ── 되풀이 (자동차세·보험 연납처럼 한 달 주기가 아닌 돈) ──
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    visible: dlg.canRepeat
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Text { text: "되풀이"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                        Item { width: 6 }
                        Repeater {
                            model: [{ v: 0, t: "한 번만" }, { v: 3, t: "분기" },
                                    { v: 6, t: "반년" }, { v: 12, t: "해마다" }]
                            delegate: Rectangle {
                                required property var modelData
                                readonly property bool on: dlg.every === modelData.v
                                width: 60; height: 26; radius: 13
                                color: on ? Theme.accent : "transparent"
                                border.color: on ? Theme.accent : Theme.cardBorder
                                TapHandler { onTapped: dlg.every = modelData.v }
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.t
                                    color: parent.on ? "#ffffff" : Theme.textDim
                                    font.pixelSize: 11
                                }
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }

                    DateField {
                        id: repeatEndField
                        objectName: "repeatEnd"
                        Layout.fillWidth: true
                        visible: dlg.every > 0
                        label: "되풀이 끝"
                        placeholder: "되풀이 끝 (비우면 계속)"
                        value: dlg.endDate
                        optional: true
                        onEdited: (v) => dlg.endDate = v
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: dlg.every > 0
                        text: "같은 날짜로 " + (dlg.every === 12 ? "해마다" : dlg.every + "개월마다")
                              + " 되풀이됩니다 (자동차세·보험 연납처럼). "
                              + "기간 안에 들어오는 횟수만큼 더해집니다."
                        color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap
                    }
                }
            }

            // ── 적용 기간 (대출 / 월세 / 관리비 / 고정 지출 / 월 수입) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.info.dateMode === "range"

                Text { text: "적용 기간"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    DateField {
                        id: startField
                        Layout.fillWidth: true
                        label: "시작일"
                        value: dlg.startDate
                        onEdited: (v) => dlg.startDate = v
                    }
                    Text { text: "~"; color: Theme.textDim; Layout.alignment: Qt.AlignVCenter }
                    DateField {
                        id: endField
                        Layout.fillWidth: true
                        label: "종료일"
                        value: dlg.endDate
                        optional: true
                        onEdited: (v) => dlg.endDate = v
                    }
                }
                Text {
                    text: dlg.info.isLoan && dlg.loanInfo.needsEnd
                          ? "기준일 " + backend.basisDate + " 을 0개월로 계산합니다. 이 상환 방식은 종료일(만기)이 있어야 합니다."
                          : "기준일 " + backend.basisDate + " 을 0개월로 계산합니다. 종료일을 비우면 기간 끝까지 계속 적용됩니다."
                    color: dlg.info.isLoan && dlg.loanInfo.needsEnd ? Theme.yellow : Theme.textDim
                    font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
                }
            }

            // ── 이율 (대출 / 예금) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: dlg.info.usesRate

                SliderInput {
                    label: "연이율"
                    value: dlg.rate
                    from: 0; to: 20; stepSize: 0.1; decimals: 1
                    suffix: "%"
                    fieldWidth: 90
                    onEdited: (v) => dlg.rate = v
                }
                Text {
                    // 적금은 매달 쌓이는 돈에 붙으므로 '잔액 × 이율' 이 아니다
                    text: dlg.info.usesSupport
                          ? "이자는 넣은 달수만큼 붙습니다 (첫 회차가 가장 오래, 마지막 회차는 한 달)"
                          : "월 이자: " + backend.won(backend.monthlyInterest(dlg.amount, dlg.rate))
                    color: Theme.textDim; font.pixelSize: 12
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true; Layout.preferredWidth: 1
                }
                CheckBox {
                    id: principalCheck
                    visible: dlg.info.isLoan
                    text: "대출 원금을 보유 자금에 포함"
                }
            }

            // ── 상환 방식 (대출) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.info.isLoan

                Text { text: "상환 방식"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                ComboBox {
                    id: methodBox
                    Layout.fillWidth: true
                    model: backend.repayMethods
                    textRole: "label"
                    valueRole: "value"
                    onActivated: dlg.repayMethod = methodBox.currentValue
                }
                SliderInput {
                    visible: dlg.repayMethod === "rate"
                    label: "매달 원금의"
                    value: dlg.monthlyRepayRate
                    from: 0; to: 10; stepSize: 0.1; decimals: 1
                    suffix: "%"
                    fieldWidth: 90
                    onEdited: (v) => dlg.monthlyRepayRate = v
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: previewText.implicitHeight + 16
                    radius: 8
                    color: dlg.loanInfo.needsEnd ? "#2a2616" : "#111420"
                    border.color: dlg.loanInfo.needsEnd ? Theme.yellow : Theme.cardBorder
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                    Text {
                        id: previewText
                        anchors { fill: parent; margins: 8 }
                        wrapMode: Text.Wrap
                        verticalAlignment: Text.AlignVCenter
                        color: dlg.loanInfo.needsEnd ? Theme.yellow : Theme.textDim
                        font.pixelSize: 12
                        text: dlg.loanInfo.text
                    }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: Theme.textDim; font.pixelSize: 11
                    text: dlg.repayMethod === "bullet" ? "기간 동안 이자만 내고 만기에 원금을 한 번에 갚습니다."
                        : dlg.repayMethod === "equal_principal" ? "매달 같은 원금을 갚아 잔액이 일정하게 줄고, 이자가 줄어 상환액도 매달 줄어듭니다."
                        : dlg.repayMethod === "equal_payment" ? "매달 내는 돈이 같습니다. 은행 대출에서 가장 흔한 방식입니다."
                        : "원금의 일정 비율을 매달 갚습니다. 만기가 없어도 됩니다."
                }
            }

            // ── 중도 상환 (대출) ──
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                visible: dlg.info.isLoan

                RowLayout {
                    Layout.fillWidth: true
                    Text { text: "중도 상환"; color: Theme.text; font.pixelSize: 13; font.bold: true }
                    Text {
                        visible: repModel.count > 0
                        text: repModel.count + "건"
                        color: Theme.textDim; font.pixelSize: 12
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "＋ 상환 추가"
                        flat: true
                        leftPadding: 10; rightPadding: 10
                        onClicked: repModel.append({ date: dlg.startDate || backend.basisDate, amount: 0 })
                    }
                }

                Text {
                    visible: repModel.count === 0
                    text: "상환 일정이 없습니다. 상환하면 그 달부터 잔액이 줄어 이자가 감소합니다."
                    color: Theme.textDim; font.pixelSize: 11; wrapMode: Text.Wrap; Layout.fillWidth: true
                }

                Repeater {
                    model: repModel
                    delegate: Rectangle {
                        id: repRow
                        required property int index
                        required property var model
                        Layout.fillWidth: true
                        height: 64; radius: 8
                        color: "#111420"; border.color: Theme.cardBorder

                        // 등장 애니메이션
                        opacity: 0; Component.onCompleted: opacity = 1
                        Behavior on opacity { NumberAnimation { duration: Theme.normal } }

                        RowLayout {
                            anchors { fill: parent; leftMargin: 10; rightMargin: 6 }
                            spacing: 8
                            DateField {
                                Layout.fillWidth: false
                                Layout.preferredWidth: 160
                                label: "상환일"
                                value: repRow.model.date
                                onEdited: (v) => repModel.setProperty(repRow.index, "date", v)
                            }
                            TextField {
                                Layout.fillWidth: true
                                implicitHeight: 40
                                topPadding: 8; bottomPadding: 8
                                font.pixelSize: 14
                                horizontalAlignment: Text.AlignRight
                                placeholderText: "상환액"
                                validator: RegularExpressionValidator { regularExpression: /[0-9,]*/ }
                                text: Number(repRow.model.amount).toLocaleString(Qt.locale("en_US"), "f", 0)
                                onTextEdited: {
                                    var raw = text.replace(/,/g, "")
                                    var n = parseInt(raw)
                                    if (!isNaN(n)) {
                                        var f = n.toLocaleString(Qt.locale("en_US"), "f", 0)
                                        if (f !== text) { text = f; cursorPosition = text.length }
                                    }
                                }
                                onEditingFinished: repModel.setProperty(repRow.index, "amount", parseFloat(text.replace(/,/g, "")) || 0)
                            }
                            Text { text: "원"; color: Theme.textDim }
                            ToolButton {
                                text: "✕"; implicitWidth: 32
                                Material.foreground: Theme.red
                                onClicked: repModel.remove(repRow.index)
                            }
                        }
                    }
                }

                Text {
                    visible: repModel.count > 0
                    text: {
                        var total = 0
                        for (var i = 0; i < repModel.count; i++) total += Number(repModel.get(i).amount) || 0
                        return "상환 합계 " + backend.won(total) + "  →  잔액 " + backend.won(Math.max(0, dlg.amount - total))
                    }
                    color: Theme.textDim; font.pixelSize: 12
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8
                Button { text: "취소"; flat: true; onClicked: dlg.close() }
                Button {
                    text: dlg.editRow < 0 ? "추가" : "저장"
                    highlighted: true
                    enabled: dlg.datesValid()
                    onClicked: dlg.submit()
                }
            }
        }
    }
}
