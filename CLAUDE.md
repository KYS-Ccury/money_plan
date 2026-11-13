# 이 저장소에서 일할 때 지킬 것

## 명령을 돌리는 것은 사람이 한다 (가장 중요)

이 PC 에서 **Claude 가 Qt(PySide6) 를 올리는 파이썬을 돌리면 PC 가 멈춘다.**
세 번 겪었고, 매번 재부팅해야 돌아왔다. 창을 띄우든 안 띄우든 똑같다.

그래서:

- **Claude 는 파일만 고친다.** 코드를 쓰고, 왜 그렇게 고쳤는지 설명한다.
- **테스트·실행·스크린샷은 사람이 자기 터미널에서** 한다:
  ```
  python -m pytest tests -q -p no:faulthandler
  ```
  결과를 붙여 주면 Claude 가 읽고 고친다.
- 성능은 **창을 띄우지 말고** 따진다 — 호출 횟수·알고리즘·바인딩 구조를 읽으면 된다.
- 눈으로 봐야 하는 것은 **사람에게 부탁한다.** Claude 가 스크린샷을 찍지 않는다.

### 무슨 일이 일어나는가 (왜 이 규칙이 있는지)

1. Qt 를 올린 파이썬이 제때 안 끝나면 bash 가 그 자식을 계속 기다린다.
2. 그 상태에서 명령을 더 보내면 `fork` 가 필요한데, Git-Bash(MSYS/Cygwin) 의 fork
   흉내는 메모리 복사가 실패하면(`child_copy: cygheap read copy failed`,
   Win32 error 299) **무한히 재시도**한다.
3. 재시도마다 반쯤 태어난 프로세스가 남고, 그게 메모리를 먹어 다음 재시도를 더
   실패하게 만든다 — 눈덩이처럼 수백~수천 개가 된다.
4. 로그에 `/usr/bin/bash: fork: retry: Resource temporarily unavailable` 이 찍힌다.
5. 프로세스를 다 지워도 **커밋 메모리가 돌아오지 않아** 재부팅해야 한다.

터미널이 `fork: retry` 를 뱉거나 `uv_spawn` 오류가 나면 **그 자리에서 멈추고**
사람에게 알린다. 명령을 더 보내면 더 나빠진다.

남아 있는 것을 보는 법 (사람이 PowerShell 에서):

```
Get-Process bash,sh,python,git -ErrorAction SilentlyContinue | Group-Object ProcessName | Select-Object Name, Count
Get-Counter '\Memory\Committed Bytes','\Memory\Available MBytes'
```

## 데이터 파일을 건드리지 말 것

`capital_data.json` 은 사용자의 실제 재무 데이터다.

- 테스트·실험은 `CAPITAL_DATA_FILE` 환경변수로 임시 경로를 가리킨다
  (`tests/conftest.py` 가 그렇게 한다).
- 자동 저장은 **이 실행에서 실제로 불러왔거나 저장한 파일**에만 한다.
  파일이 거기 있다는 것만으로 쓰면 안 된다 — 그렇게 해서 한 번 날린 적이 있다.

## 파이썬

- `C:\Users\hns\AppData\Local\Programs\Python\Python312\python.exe` 를 쓴다.
  MSYS 의 python 은 PySide6 가 없다.
- 테스트는 `tests/conftest.py` 가 `QT_QPA_PLATFORM=offscreen` 과 임시 데이터
  파일을 세워 준다.

## 여러 파일을 고칠 때

스크래치패드에 패치 스크립트를 쓰고, 바꿀 때마다 `s.count(old) == 1` 을 확인한 뒤
마지막에 한 번만 파일을 쓴다. 중간에 어긋나면 파일이 손상되지 않는다.
