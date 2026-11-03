"""예전 OpenGL(GLFW + Dear ImGui) 버전 실행 파일. 기본 버전은 main.py (QML) 입니다.

    python main_imgui.py
"""
import argparse
import sys

from capital_calc.app import run


def main() -> int:
    parser = argparse.ArgumentParser(description="자본금 계산기 (OpenGL + ImGui)")
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--screenshot", type=str, default=None)
    args = parser.parse_args()
    return run(max_frames=args.frames, screenshot=args.screenshot)


if __name__ == "__main__":
    sys.exit(main())
