pragma Singleton
import QtQuick

// 색·간격·애니메이션 시간을 한 곳에서 관리하는 테마 싱글톤.
//
// **색 모드 하나를 고르면 전부 따라간다.** 모드는 다섯 가지 색만 들고 있다 —
// 바탕(bg)·강조(accent)·포인트(point)·들어오는 돈(inc)·나가는 돈(exp). 카드·줄·
// 테두리·사이드바는 바탕에서 한 겹씩 떠올려 만들고(밝은 바탕에서는 카드가 더
// 희어지고 줄이 가라앉는다), 글자색은 바탕 밝기로 뒤집는다. 그래서 모드를
// 더하려면 아래 modes 에 한 줄만 적으면 된다.
//
// 기본 모드('미색 초록')의 색은 피그마 시안('모아')의 styles.css 값 그대로다.
QtObject {
    id: theme

    // ── 고를 수 있는 모드 ──
    readonly property var modes: [
        { key: "ivory",   name: "미색 초록",   hint: "피그마 시안 기본",
          bg: "#f5f3ed", accent: "#145f43", point: "#cbea6d", inc: "#145f43", exp: "#c0563a", warm: "#d98456" },
        { key: "paper",   name: "흰 종이 쪽빛", hint: "밝고 차분하게",
          bg: "#fbfbf9", accent: "#2f5fd0", point: "#8fb8ff", inc: "#1a7f52", exp: "#c0453a", warm: "#d9734f" },
        { key: "olive",   name: "연둣빛 올리브", hint: "눈이 편한 연두",
          bg: "#eef3e8", accent: "#4a6b1f", point: "#cbea6d", inc: "#3d6b2a", exp: "#b4543f", warm: "#c2763c" },
        { key: "sand",    name: "모래 팥죽",   hint: "따뜻한 종이 느낌",
          bg: "#f6f1ea", accent: "#8c3b36", point: "#e6b35a", inc: "#2f6b4a", exp: "#a8402f", warm: "#b4543f" },
        { key: "night",   name: "밤 남색",     hint: "예전 어두운 모습",
          bg: "#0f1117", accent: "#5b8def", point: "#86a9f3", inc: "#4cd48a", exp: "#f06a6a", warm: "#e8976a" },
        { key: "ink",     name: "먹색 라임",   hint: "가장 어둡게",
          bg: "#000000", accent: "#9fd356", point: "#cbea6d", inc: "#8fd36a", exp: "#e86a6a", warm: "#e8976a" },
        { key: "forest",  name: "숲 녹색",     hint: "어두운 초록",
          bg: "#0d1512", accent: "#4fb286", point: "#9ae6c0", inc: "#4cd48a", exp: "#ef7a6a", warm: "#e8976a" },
        { key: "plum",    name: "자줏빛 보라", hint: "어두운 보라",
          bg: "#141018", accent: "#a07bd8", point: "#d7c2f5", inc: "#5fd3a3", exp: "#f0707f", warm: "#e8976a" }
    ]

    property string mode: "ivory"
    // 모드의 바탕색 대신 직접 고른 색 (설정의 '직접 고르기'). 비우면 모드 색을 쓴다.
    property string customBg: ""

    function modeAt(key) {
        for (var i = 0; i < modes.length; i++)
            if (modes[i].key === key)
                return modes[i]
        return modes[0]
    }
    readonly property var cur: modeAt(mode)

    readonly property color bgBase: customBg !== "" ? customBg : cur.bg

    // 밝기 (0~1). 밝은 바탕인가 어두운 바탕인가로 모든 것이 갈린다.
    readonly property real lum: 0.299 * bgBase.r + 0.587 * bgBase.g + 0.114 * bgBase.b
    readonly property bool light: lum > 0.5

    // 바탕과 흰색/검정 사이를 t 만큼 섞는다.
    function mixTo(white, t) {
        var to = white ? 1.0 : 0.0
        return Qt.rgba(bgBase.r + (to - bgBase.r) * t,
                       bgBase.g + (to - bgBase.g) * t,
                       bgBase.b + (to - bgBase.b) * t, 1)
    }
    // 어떤 색을 바탕에 살짝 풀어 놓은 면 색 (경고 칸·칩 배경)
    function soft(c) {
        var t = light ? 0.16 : 0.26
        return Qt.rgba(bgBase.r + (c.r - bgBase.r) * t,
                       bgBase.g + (c.g - bgBase.g) * t,
                       bgBase.b + (c.b - bgBase.b) * t, 1)
    }

    readonly property color bg: bgBase
    // 밝은 바탕에서는 카드가 **더 희고**(종이), 줄은 살짝 가라앉는다.
    // 어두운 바탕에서는 반대로 카드·줄이 바탕에서 떠오른다.
    readonly property color card: light ? mixTo(true, 0.78) : mixTo(true, 0.045)
    readonly property color cardBorder: light ? mixTo(false, 0.12) : mixTo(true, 0.11)
    readonly property color row: light ? mixTo(false, 0.035) : mixTo(true, 0.075)
    readonly property color rowHover: light ? mixTo(false, 0.07) : mixTo(true, 0.115)
    readonly property color sidebar: light ? mixTo(true, 0.45) : mixTo(true, 0.02)

    readonly property color text: light ? "#19251f" : "#e8eaf0"
    readonly property color textDim: light ? "#778079" : "#8a90a3"

    readonly property color accent: cur.accent
    readonly property color accentSoft: soft(cur.accent)
    readonly property color green: cur.inc
    readonly property color red: cur.exp
    readonly property color orange: cur.warm
    readonly property color lime: cur.point
    readonly property color yellow: light ? "#8a6100" : "#f2c14e"
    readonly property color greenSoft: soft(cur.inc)
    readonly property color redSoft: soft(cur.exp)
    readonly property color violet: light ? "#7b3fc4" : "#b57bee"   // 받을 대출 구간
    readonly property color teal: light ? "#117a8c" : "#4fc3dc"     // 만기에 받을 적금 구간

    // 짙은 강조색 카드(히어로) 안에서 쓰는 색. 강조색이 밝으면 글자를 어둡게.
    readonly property color heroBg: cur.accent
    readonly property real heroLum: 0.299 * heroBg.r + 0.587 * heroBg.g + 0.114 * heroBg.b
    readonly property color heroText: heroLum > 0.6 ? "#14201a" : "#ffffff"
    readonly property color heroDim: heroLum > 0.6 ? Qt.rgba(0.08, 0.13, 0.10, 0.75)
                                                   : Qt.rgba(1, 1, 1, 0.72)
    readonly property color heroLabel: heroLum > 0.6 ? Qt.rgba(0.08, 0.13, 0.10, 0.6)
                                                     : Qt.rgba(1, 1, 1, 0.6)

    readonly property string defaultMode: "ivory"

    // 시나리오별 선·점 색 (1번부터). 모드의 색 넷으로 시작한다.
    readonly property var scenarioColors: [cur.accent, cur.warm, cur.inc, violet, teal, cur.exp, yellow, textDim]
    function scenarioColor(i) { return scenarioColors[((i % scenarioColors.length) + scenarioColors.length) % scenarioColors.length] }

    // 앞으로 들어올 돈의 종류별 색 (목표 바 구간)
    function pendingColor(kind) {
        return kind === "loan" ? violet : (kind === "saving" ? teal : accent)
    }

    readonly property int radius: 16
    readonly property int radiusBig: 20
    readonly property int pad: 16
    readonly property int fast: 160
    readonly property int normal: 320
    readonly property int slow: 600
}
