# 네이버 블로그 자동화 (피부과 전문)

피부과 전문의를 위한 네이버 블로그 운영 자동화 도구입니다. AI가 **트렌드 기반으로 주제를 발굴**하고,
**의료법을 준수하는 고품질 SEO 글**을 작성하며, **이미지(AI 비임상 이미지 · 인포그래픽 자동생성 ·
직접 올린 사진)**를 넣고, **사람이 타이핑하듯 OS 레벨로 네이버 스마트에디터에 입력·발행**합니다.

> 네이버는 일반 브라우저 자동화(Selenium/Playwright)를 탐지·차단하므로, 봇처럼 보이지 않게
> **실제 마우스/키보드 입력을 흉내내는 방식**을 씁니다. 한글은 클립보드 붙여넣기로 입력합니다.

---

## ⚠️ 꼭 읽어주세요 (법적·정책 고지)
- **의료광고(의료법 제56·57조)**: 피부과 진료·시술 글은 의료광고 사전심의 대상일 수 있습니다.
  이 프로그램은 과장·치료효과 보장 표현을 자동 점검하지만, **최종 책임은 작성자(의료진)에게** 있습니다.
  발행 전 **검토·승인 단계가 기본값으로 필수**입니다.
- **AI 가짜 임상사진 금지**: AI 이미지는 **비임상 개념/일러스트/스킨케어 모델 느낌**만 생성합니다.
  실제 시술 전·후/환자 사진은 **환자 동의를 받은 본인 촬영본만** 직접 올려 사용하세요.
- **네이버 약관**: 자동 포스팅은 계정 제재 위험이 있습니다. 사람같은 딜레이, 하루 발행 수 제한,
  발행 전 확인을 기본값으로 두었지만 위험을 완전히 없애지는 못합니다. 본인 책임하에 사용하세요.

---

## 설치
```bash
pip install -r requirements.txt
```
- Windows 데스크톱에서 실행합니다(OS 입력 자동화 때문). 콘텐츠 생성/SEO/주제발굴은 다른 OS에서도 가능.

## 글 작성 AI — 무료로 쓰기 (제공자 선택)
글 생성에 쓰는 AI는 **교체 가능**합니다. `config.json` 의 `content.provider` 로 고르세요.

| 제공자 | 비용 | 준비물 | 추천 상황 |
|---|---|---|---|
| **`gemini`** (기본·권장) | **무료 등급** | https://aistudio.google.com/apikey 에서 무료 키 발급 → `.env` 의 `GEMINI_API_KEY` | 설치 부담 없이 무료로 좋은 한국어 품질 |
| **`ollama`** | **완전 무료**(로컬) | https://ollama.com 설치 → `ollama pull qwen2.5:7b` (키 불필요) | 인터넷/가입 없이 내 PC에서 비공개로. PC 사양 어느 정도 필요 |
| `anthropic` | 유료 | `ANTHROPIC_API_KEY` | 최고 품질을 원하고 비용 감수 가능할 때 |

- Gemini: `config.json` → `"content": { "provider": "gemini", "model": "gemini-2.0-flash" }`
- Ollama: `"content": { "provider": "ollama", "model": "qwen2.5:7b" }` (모델은 취향껏 변경)

## 설정
1. `.env.example` → `.env` 복사 후 키 입력
   - 위 표에서 고른 제공자의 키 (Gemini면 `GEMINI_API_KEY`, Ollama면 키 불필요)
   - `NAVER_DATALAB_CLIENT_ID/SECRET` (선택, 검색량 교차검증)
   - `IMAGE_API_PROVIDER/KEY` (선택, AI 비임상 이미지 생성)
2. `config.example.json` → `config.json` 복사 후 제공자/블로그 정보 수정
   - `content.provider`, `blog.naver_id`, `blog.write_url`, 발행 시간·하루 제한·공개여부 등
3. 환경 점검: `python -m src.main doctor` (선택한 제공자/키 상태를 알려줌)

### 버튼 캡처 1회 셋업 (OS 자동화)
좌표 하드코딩 대신 화면에서 버튼 이미지를 찾습니다. `assets/` 폴더에 본인 화면의 캡처를 넣으세요:
- `title_area.png`(제목 영역), `body_area.png`(본문 영역), `image_button.png`(사진 첨부),
  `tag_area.png`(태그 입력), `publish_button.png`(발행 버튼)
- (선택, 예약발행) `schedule_toggle.png`(예약 토글), `schedule_date.png`(날짜 입력칸),
  `schedule_time.png`(시간 입력칸), `confirm_button.png`(발행 확정)
  - 예약 날짜/시간 입력 포맷은 `config.json` 의 `automation.schedule_date_format`(기본
    `%Y.%m.%d`), `schedule_time_format`(기본 `%H:%M`)으로 맞추세요. 캡처가 없으면 예약 토글까지만
    자동화하고 시각은 직접 지정합니다.

> 네이버 로그인은 자동화하지 않습니다. 평소 쓰는 Chrome 으로 **직접 로그인**한 뒤 글쓰기 페이지를
> 열어두고 프로그램을 실행하세요.

---

## 📦 .exe 로 만들어 더블클릭으로 쓰기 (파이썬 설치 없이 배포)
명령어가 부담되면 한 번만 .exe 로 빌드해두고, 이후엔 더블클릭으로 실행하세요.

**빌드(개발자/최초 1회, Windows)**
```bat
build_exe.bat
```
→ `dist\NaverBlogAutomation.exe` 가 생성됩니다. (내부적으로 PyInstaller 로 묶음)

**실행(사용자)** — `dist` 폴더 안에서 아래만 준비하면 됩니다(빌드 PC가 아니어도 됨):
1. `.env.example` → `.env` 로 복사 후 무료 키 입력 (Gemini면 `GEMINI_API_KEY`, Ollama면 키 불필요)
2. `config.example.json` → `config.json` 으로 복사 후 `content.provider`·블로그 정보 입력
3. `assets\` 폴더에 에디터 버튼 캡처 PNG 넣기(실제 발행 자동화 시)
4. **`NaverBlogAutomation.exe` 더블클릭** → GUI 실행

> .exe 는 `config.json`/`.env`/`assets/`/`blog.db`/생성 이미지를 **exe 와 같은 폴더**에서
> 읽고 씁니다. exe 와 이 파일들을 같은 폴더에 두세요. (.exe 빌드/실행은 Windows 전용)

## 🖥️ 가장 쉬운 사용법 — 데스크톱 GUI (파이썬으로 직접 실행)
명령어가 어렵다면 GUI 를 쓰세요. 클릭만으로 전체 과정을 진행합니다.
```bash
python -m src.gui
```
- 탭 순서대로: **1.주제 → 2.생성 → 3.이미지 → 4.검토·발행**.
- 상단 목록에서 글을 선택하고, 각 탭의 버튼을 누르면 됩니다. 하단 로그에 진행 상황이 표시됩니다.
- 발행 전 **드라이런(계획만)** 으로 동작을 먼저 확인하고, **비공개**로 발행해 결과를 본 뒤 공개하세요.
- (Windows 파이썬은 tkinter 가 기본 포함되어 추가 설치가 필요 없습니다.)

### AI 비임상 이미지 (선택)
- `.env` 에 `IMAGE_API_PROVIDER=openai`, `IMAGE_API_KEY=...` 를 넣고 `pip install openai`,
  `config.json` 의 `images.ai_images_enabled=true` 로 설정하면 **비임상** 개념/모델/일러스트 이미지를
  생성합니다. 크기는 `images.ai_size`(기본 `1024x1024`).
- 의료법 가드: 설명에 환자/시술 전후/병변 등 임상 의도가 있으면 생성을 거부하고 인포그래픽으로
  폴백합니다. **실제 임상사진은 환자 동의를 받은 직접 촬영본만** 사용하세요.

## 사용법 (CLI 파이프라인)
```bash
# 1) 주제 발굴 — 자동(트렌드) 또는 수동
python -m src.main topics --auto                 # 웹검색+데이터랩으로 수요 높은 주제 발굴
python -m src.main topics --manual "여드름 흉터 치료"
python -m src.main topics --list

# 2) 콘텐츠 생성 (+SEO 최적화 루프 +의료광고 점검)
python -m src.main generate --all                # 또는 --post-id 1

# 3) 이미지 준비 (인포그래픽 자동생성 + AI 비임상 이미지 + 내 사진)
python -m src.main images --post-id 1 --list-photos        # 사진/자리 목록 확인
python -m src.main images --post-id 1 --photos "0:2"       # 본문 0번 자리에 user_photos 2번 사진

# 4) 검토/승인 (의사 확인 — 기본 필수)
python -m src.main review --post-id 1            # 미리보기 + SEO/컴플라이언스 경고
python -m src.main review --post-id 1 --approve  # 승인

# 5) 발행 — 먼저 드라이런으로 동작 계획 확인 → 비공개로 실제 발행 → 공개
python -m src.main publish --post-id 1 --dry-run
python -m src.main publish --post-id 1                       # 비공개 발행(기본)
python -m src.main publish --post-id 1 --public --schedule 2026-06-22T09:00
python -m src.main publish --due                            # 예약 도래분 일괄(스케줄러용)

python -m src.main list                          # 전체 상태 확인
```

상태 흐름: `topic → draft → media_ready → approved → published`

### 내 사진 넣기
`config.json` 의 `images.user_photo_dir`(기본 `user_photos/`)에 사진을 넣고,
`images --post-id N --list-photos` 로 인덱스를 확인한 뒤 `--photos "본문자리:사진번호"` 로 매핑합니다.

### 스케줄링
- **권장**: 네이버 네이티브 예약발행(`--schedule`)을 쓰면 네이버가 시각에 맞춰 공개해 PC 가 항상
  켜져 있을 필요가 없습니다.
- 또는 **Windows 작업 스케줄러**가 `python -m src.main publish --due` 를 주기 실행하도록 등록
  (`python -m src.main doctor` 가 등록 방법을 안내).

---

## 검증(권장 순서)
1. `topics --auto` 로 주제 후보·수요 점수 확인
2. `generate` 후 SEO 점수·컴플라이언스 경고 확인
3. `images --list-photos` 로 이미지 매핑 확인
4. `publish --dry-run` 으로 입력 계획 확인 → **비공개 발행**으로 에디터 결과 눈으로 검증
5. 문제 없으면 공개로 전환

## 테스트
```bash
python -m pytest        # 규칙기반 컴플라이언스 / SEO 점수 / 본문 파싱 (네트워크·GUI 불필요)
```

## 프로젝트 구조
```
src/
  topics/    주제 발굴 (discovery=웹검색+데이터랩, manual=수동, datalab=API)
  content/   생성 (generator), 프롬프트(prompts), 의료광고 점검(compliance)
  seo/       SEO 점수(scorer) + 최적화 루프(optimizer)
  images/    AI 비임상(ai_image), 인포그래픽(infographic), 내 사진(user_photos), alt(alt_text)
  automation/ 에디터 구동(naver_editor), 사람같은 동작(humanize), 버튼 인식(ui_locator)
  storage/   SQLite(db)
  review.py  검토/승인   scheduler.py 발행/예약
  main.py    CLI 엔트리   gui.py 데스크톱 GUI(Tkinter)   config.py/llm.py 공통
run_gui.py             .exe/GUI 진입점
build_exe.bat          Windows .exe 원클릭 빌드
packaging/naver_blog.spec   PyInstaller 스펙
```
