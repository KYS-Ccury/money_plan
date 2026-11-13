# 이 저장소에서 일할 때 지킬 것

## 측정·확인용으로 앱 창을 띄우지 말 것 (중요)

Git-Bash(MSYS/Cygwin)에서 **창을 띄우고 금방 끝나지 않는** 파이썬을 돌리면
PC 전체가 멈춘다. 실제로 두 번 터졌다.

무슨 일이 일어나는가:

1. 측정/스크린샷 스크립트가 `win.show()` 로 진짜 창을 띄우고 제때 안 끝난다.
   (예: `onClosing` 의 '저장 안 됨' 팝업이 `app.quit()` 를 막는다.)
2. bash 가 그 자식을 계속 기다린다.
3. 그 상태에서 명령을 더 보내면 `fork` 가 필요한데, Cygwin 의 fork 흉내는
   메모리 복사가 실패하면(`child_copy: cygheap read copy failed`, Win32 error 299)
   **무한히 재시도**한다. 재시도마다 반쯤 태어난 프로세스가 남고, 그게 메모리를
   먹어 다음 재시도를 더 실패하게 만든다 — 눈덩이처럼 수백~수천 개가 된다.
4. 로그에 이렇게 찍힌다: `/usr/bin/bash: fork: retry: Resource temporarily unavailable`

그래서:

- **성능은 창을 띄우지 말고 따진다.** 호출 횟수·알고리즘·바인딩 구조를 보면 된다.
- 눈으로 꼭 봐야 하면 스크린샷 한 장만, 그리고 **다음 셋을 모두** 건다:
  - `QT_QPA_PLATFORM=offscreen` (창을 아예 만들지 않는다)
  - 스크립트 안에 감시 타이머 → 시간이 지나면 `os._exit(0)`
  - 닫기 전에 `win.setProperty("forceClose", True)` (`main.py --screenshot` 은 이미 한다)
  - 10초 안에 끝나는 것만.
- 테스트는 안전하다. `tests/conftest.py` 가 `QT_QPA_PLATFORM=offscreen` 을 세우고
  데이터 파일도 임시 폴더로 돌린다.
- 터미널이 `fork: retry` 를 뱉기 시작하면 **그 자리에서 멈추고** 사용자에게
  프로세스 정리를 부탁한다. 명령을 더 보내면 더 나빠진다.

## 데이터 파일을 건드리지 말 것

`capital_data.json` 은 사용자의 실제 재무 데이터다.

- 테스트·실험은 `CAPITAL_DATA_FILE` 환경변수로 임시 경로를 가리킨다
  (`tests/conftest.py` 가 그렇게 한다).
- 자동 저장은 **이 실행에서 실제로 불러왔거나 저장한 파일**에만 한다.
  파일이 거기 있다는 것만으로 쓰면 안 된다 — 그렇게 해서 한 번 날린 적이 있다.

## 파이썬

- `C:\Users\hns\AppData\Local\Programs\Python\Python312\python.exe` 를 쓴다.
  MSYS 의 python 은 PySide6 가 없다.
- 테스트: `QT_QPA_PLATFORM=offscreen python -m pytest tests -q -p no:faulthandler`

## 여러 파일을 고칠 때

스크래치패드에 패치 스크립트를 쓰고, 바꿀 때마다 `s.count(old) == 1` 을 확인한 뒤
마지막에 한 번만 파일을 쓴다. 중간에 어긋나면 파일이 손상되지 않는다.
