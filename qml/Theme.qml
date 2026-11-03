pragma Singleton
import QtQuick

// 색상·간격·애니메이션 시간을 한 곳에서 관리하는 테마 싱글톤
QtObject {
    readonly property color bg: "#0f1117"
    readonly property color card: "#171a23"
    readonly property color cardBorder: "#262a36"
    readonly property color row: "#1c2030"
    readonly property color rowHover: "#232838"
    readonly property color text: "#e8eaf0"
    readonly property color textDim: "#8a90a3"
    readonly property color accent: "#5b8def"
    readonly property color accentSoft: "#2b3b62"
    readonly property color green: "#4cd48a"
    readonly property color red: "#f06a6a"
    readonly property color yellow: "#f2c14e"

    // 시나리오별 선·점 색 (1번부터)
    readonly property var scenarioColors: ["#5b8def", "#4cd48a", "#f2c14e", "#b57bee", "#ff9f5a", "#4fc3dc", "#f06a6a", "#8a90a3"]
    function scenarioColor(i) { return scenarioColors[((i % scenarioColors.length) + scenarioColors.length) % scenarioColors.length] }

    readonly property int radius: 12
    readonly property int pad: 16
    readonly property int fast: 160
    readonly property int normal: 320
    readonly property int slow: 600
}
