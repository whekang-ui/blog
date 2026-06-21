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

## 설정
1. `.env.example` → `.env` 복사 후 키 입력
   - `ANTHROPIC_API_KEY` (필수)
   - `NAVER_DATALAB_CLIENT_ID/SECRET` (선택, 검색량 교차검증)
   - `IMAGE_API_PROVIDER/KEY` (선택, AI 비임상 이미지 생성)
2. `config.example.json` → `config.json` 복사 후 블로그 정보/옵션 수정
   - `blog.naver_id`, `blog.write_url`, 발행 시간·하루 제한·공개여부 등
3. 환경 점검: `python -m src.main doctor`

### 버튼 캡처 1회 셋업 (OS 자동화)
좌표 하드코딩 대신 화면에서 버튼 이미지를 찾습니다. `assets/` 폴더에 본인 화면의 캡처를 넣으세요:
- `title_area.png`(제목 영역), `body_area.png`(본문 영역), `image_button.png`(사진 첨부),
  `tag_area.png`(태그 입력), `publish_button.png`(발행 버튼)
- (선택) `schedule_toggle.png`(예약 토글), `confirm_button.png`(발행 확정)

> 네이버 로그인은 자동화하지 않습니다. 평소 쓰는 Chrome 으로 **직접 로그인**한 뒤 글쓰기 페이지를
> 열어두고 프로그램을 실행하세요.

---

## 사용법 (파이프라인)
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
  review.py  검토/승인   scheduler.py 발행/예약   main.py CLI   config.py/llm.py 공통
```
