# Pia Carrot he Youkoso!! 2.2 (GBC) 한글화 도구

> **Piaキャロットへようこそ!! 2.2** Game Boy Color 한글화 프로젝트 도구 세트

---

## 📋 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 게임 | Pia Carrot he Youkoso!! 2.2 (GBC) |
| 장르 | 연애 시뮬레이션 / 비주얼 노벨 |
| 원본 언어 | 일본어 |
| ROM 크기 | 4MB (MBC5 + SRAM) |
| 텍스트 블록 | 15,410개 |
| 고유 문자 | 1,420자 |

---

## 🛠️ 도구 구성

```
tools/
├── text_dumper.py      # 텍스트 추출기
├── text_inserter.py    # 텍스트 삽입기
└── font_generator.py   # 한글 폰트 생성기
```

---

## 🚀 빠른 시작 (Quick Start)

### 필수 환경
- Python 3.7 이상
- 원본 ROM 파일: `Pia Carrot he Youkoso!! 2.2.gbc` (4,194,304 bytes)

### 전체 작업 흐름

```
[1단계] 텍스트 추출  →  [2단계] 번역  →  [3단계] 폰트 생성  →  [4단계] 삽입  →  [5단계] 테스트
```

---

## 📖 단계별 상세 가이드

### 1단계: 텍스트 추출

ROM에서 모든 일본어 텍스트를 추출합니다.

```bash
python tools/text_dumper.py "Pia Carrot he Youkoso!! 2.2.gbc" ./dump
```

**출력 파일:**
| 파일 | 설명 |
|------|------|
| `dump/bank_152.json` ~ `bank_195.json` | 뱅크별 텍스트 (JSON) |
| `dump/bank_152.txt` ~ `bank_195.txt` | 뱅크별 텍스트 (읽기용) |
| `dump/char_table.json` | 문자 인코딩 테이블 |
| `dump/script_map.json` | 스크립트→텍스트 매핑 |

---

### 2단계: 번역

추출된 텍스트 파일을 한국어로 번역합니다.

#### 2-1. 번역 디렉토리 준비

```bash
# 샘플 번역 파일 생성 (예시 포함)
python tools/text_inserter.py --sample ./dump ./translated
```

#### 2-2. 번역 파일 편집

`translated/bank_XXX.json` 파일을 열어 각 블록의 `"translation"` 필드에 한국어를 입력합니다.

**번역 형식 예시:**

```json
{
  "id": "B152_0001",
  "rom_offset": "0x26002D",
  "size": 56,
  "text": "<04><3F:1E>...",
  "raw_hex": "...",
  "translation": "혹시 모르니까[LINE_END_10][NEWLINE]확인해 봐야지[LINE_END_11][END]"
}
```

#### 2-3. 번역 시 사용하는 제어코드

| 코드 | 의미 | 필수 여부 |
|------|------|-----------|
| `[END]` | 텍스트 블록 종료 | ✅ 모든 블록 끝에 필수 |
| `[NEWLINE]` | 줄바꿈 | 선택 |
| `[PAGE]` | 페이지 넘김 (버튼 대기 후 화면 전환) | 선택 |
| `[WAIT]` | 입력 대기 | 선택 |
| `[PAUSE]` | 짧은 대기 | 선택 |
| `[PLAYER_NAME]` | 플레이어 이름 삽입 | 원본과 동일하게 |
| `[LINE_END_10]` | 줄 끝 명령 (타입 10) | ✅ 줄 끝에 필수 |
| `[LINE_END_11]` | 줄 끝 명령 (타입 11) | ✅ 줄 끝에 필수 |

#### 2-4. 번역 규칙

1. **모든 텍스트 블록은 반드시 `[END]`로 끝나야 합니다**
2. **줄 끝에는 `[LINE_END_XX]`를 넣어야 합니다** (원본과 같은 타입 사용 권장)
3. 줄바꿈: `[LINE_END_XX][NEWLINE]` 순서로 사용
4. 페이지 넘김: `[LINE_END_XX][PAGE]` 순서로 사용
5. 한 줄에 최대 약 10-12자 (8x8 폰트 기준 화면 폭 제한)
6. `[PLAYER_NAME]`은 원본에 있는 위치와 동일하게 유지

**예시 (완전한 텍스트 블록):**
```
이번 여름방학은[LINE_END_10][NEWLINE]아르바이트를 하자[LINE_END_11][END]
```

```
응, 알겠어[LINE_END_10][PAGE]그럼 어디서 일할까?[LINE_END_11][END]
```

---

### 3단계: 한글 폰트 생성

게임에서 사용할 한글 폰트 타일 데이터를 생성합니다.

```bash
# 기본 폰트 생성 (445자)
python tools/font_generator.py --output ./font_data.bin --preview

# 커스텀 문자 테이블 기반 생성
python tools/font_generator.py --chars ./translated/korean_table.json --output ./font_data.bin
```

**옵션:**
| 옵션 | 설명 |
|------|------|
| `--output <파일>` | 출력 바이너리 파일 |
| `--preview` | 터미널에 글자 미리보기 |
| `--chars <json>` | 커스텀 문자 테이블 사용 |
| `--rom <파일>` | 폰트를 ROM에 직접 삽입 |
| `--rom-output <파일>` | 폰트 삽입된 ROM 출력 |
| `--font-bank <번호>` | 폰트 저장 뱅크 (기본: 196) |

---

### 4단계: 한글화 ROM 빌드

번역된 텍스트와 폰트를 ROM에 삽입하여 최종 한글화 ROM을 생성합니다.

```bash
# 텍스트 삽입
python tools/text_inserter.py "Pia Carrot he Youkoso!! 2.2.gbc" ./translated ./output_kr.gbc

# 폰트 삽입 (위에서 생성된 ROM에 추가)
python tools/font_generator.py --output ./font_data.bin \
    --rom ./output_kr.gbc \
    --rom-output ./Pia_Carrot_Korean.gbc \
    --font-bank 196
```

---

### 5단계: 테스트

생성된 ROM을 GBC 에뮬레이터에서 테스트합니다.

**추천 에뮬레이터:**
- [BGB](https://bgb.bircd.org/) - 디버깅에 최적 (VRAM 뷰어 포함)
- [mGBA](https://mgba.io/) - 정확한 에뮬레이션

**확인 사항:**
- [ ] 게임이 정상 부팅되는가
- [ ] 텍스트가 깨짐 없이 표시되는가
- [ ] 줄바꿈/페이지 넘김이 정상 작동하는가
- [ ] 이름 입력/표시가 정상인가
- [ ] 모든 루트의 텍스트가 정상인가

---

## 📐 ROM 구조 정보

### 뱅크 맵

| 범위 | 뱅크 | 내용 |
|------|------|------|
| 0x000000-0x03FFFF | 0-15 | 코드 + 시스템 |
| 0x040000 | 16 | 이벤트/CG 포인터 |
| 0x044000-0x097FFF | 17-37 | 데이터/코드 |
| 0x098000-0x0B7FFF | 38-45 | 캐릭터 CG 그래픽 |
| 0x0B8000-0x0E3FFF | 46-56 | 스크립트 엔진 |
| 0x0E4000-0x25FFFF | 57-151 | 그래픽 데이터 |
| 0x260000-0x30FFFF | 152-195 | **텍스트 데이터** |
| 0x310000-0x3FFFFF | 196-255 | 여유/폰트 삽입 가능 |

### 텍스트 인코딩

- **2바이트 고정 길이**: `[문자코드][페이지]`
- Page 0x00: 히라가나/기호 (81자)
- Page 0x01: 카타카나 (78자)
- Page 0x02+: 한자 (약 1,260자)
- 제어코드: `XX 03` (줄 끝), `00 FE/FF/FC/FA` (흐름 제어)

### 스크립트 포인터

```
형식: 19 [addr_lo] [addr_hi] [text_bank] 1B
예시: 19 A5 4E 98 1B → Bank 0x98(152)의 주소 0x4EA5
```

---

## ⚠️ 주의사항

1. **뱅크 용량 제한**: 각 텍스트 뱅크는 16KB입니다. 번역이 원본보다 길면 오버플로우가 발생할 수 있습니다. 삽입기가 경고를 출력하니 확인하세요.

2. **폰트 렌더링 연동**: 현재 폰트 생성기는 타일 데이터만 생성합니다. 게임 내 폰트 렌더링 루틴이 새 폰트를 로드하도록 **ASM 패치가 추가로 필요**할 수 있습니다. (텍스트 엔진이 기존 일본어 폰트 뱅크를 참조하므로, 해당 참조를 새 뱅크 196으로 변경해야 합니다.)

3. **8x8 한글의 한계**: 8x8 픽셀에 한글을 넣으면 가독성이 떨어질 수 있습니다. 게임이 8x16 복합 타일을 지원한다면 더 좋은 폰트를 만들 수 있습니다.

4. **문자 테이블 정확도**: 추정된 일본어↔바이트 매핑은 약간의 오차가 있을 수 있습니다. 에뮬레이터에서 실제 화면과 대조하여 보정이 필요합니다.

5. **원본 ROM 백업**: 작업 전 반드시 원본 ROM을 백업하세요.

---

## 📁 디렉토리 구조

```
.
├── Pia Carrot he Youkoso!! 2.2.gbc   # 원본 ROM
├── README.md                           # 이 파일
├── tools/
│   ├── text_dumper.py                  # 텍스트 추출기
│   ├── text_inserter.py                # 텍스트 삽입기
│   └── font_generator.py              # 한글 폰트 생성기
├── dump/                               # 추출된 텍스트 (자동 생성)
│   ├── bank_152.json ~ bank_195.json
│   ├── bank_152.txt ~ bank_195.txt
│   ├── char_table.json
│   └── script_map.json
├── translated/                         # 번역 파일 (사용자 작성)
│   ├── bank_152.json ~ bank_195.json
│   └── korean_table.json
├── font_data.bin                       # 생성된 폰트 데이터
└── output_kr.gbc                       # 한글화된 ROM 출력
```

---

## 🤝 기여 방법

1. 텍스트 번역: `translated/` 디렉토리의 JSON 파일 편집
2. 문자 테이블 보정: 에뮬레이터에서 문자 대조 후 `char_table.json` 수정
3. 폰트 개선: `font_generator.py`의 비트맵 데이터 수정
4. ASM 패치: 폰트 로드 루틴 수정 (고급)

---

## 📜 라이선스

이 도구는 비상업적 팬 번역 프로젝트를 위해 제작되었습니다.
원본 게임의 저작권은 (주)칵테일소프트/F&C에 있습니다.
