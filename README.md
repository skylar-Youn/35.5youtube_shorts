# Product Shorts Maker (Link → 9:16 Shorts Video)

Create a YouTube/TikTok/Instagram Shorts-style video from a single product link.

## Features
- Scrapes product **title, price, key features, images** from the URL (uses Open Graph + page HTML).
- Auto-generates a **15–40s script** (hook → features → CTA).
- Builds a **9:16 video (1080×1920)** slideshow with text overlays and optional TTS + background music.
- Creates safe fallbacks if scraping or TTS is blocked (uses placeholder slides and text-only overlays).

---

## Quick Start

```bash
# 1) Create/activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install dependencies
pip install -r requirements.txt

# (Optional) Install Playwright browser binaries for headless fetching
python -m playwright install chromium

# 3) Run (basic)
python shorts_maker.py --url "https://example.com/product" --out out.mp4

# With background music (optional) and fixed duration (e.g., 28s)
python shorts_maker.py --url "https://example.com/product" --music assets/music.mp3 --duration 28 --out out.mp4

# If the site blocks scraping, save the page as HTML and parse locally:
python shorts_maker.py --html saved_page.html --out out.mp4
```

### Notes
- **TTS**: The script uses `pyttsx3` for offline TTS where available. If it fails on your OS, add `--no_tts` to disable, or install a different TTS and replace `synthesize_voice()` accordingly.
- **Images**: If no usable images are found, the script will create simple on-brand slides (solid backgrounds with big text).
- **Duration**: The tool auto-times slides to match your requested duration (default 24s). You can adjust with `--duration` or `--min_slide 2 --max_slide 5`.
- **Music**: Provide an MP3/ WAV via `--music`. It will be mixed under the voice/narration.

---

## CLI Options

```text
python shorts_maker.py [--url URL | --html FILE] [--out OUT.mp4]
                       [--duration SECONDS] [--music MUSIC.mp3]
                       [--no_tts] [--voice_rate 185]
                       [--font_path /path/to/font.ttf]
                       [--min_slide 2] [--max_slide 5]
                       [--cta "더 알아보기는 링크 클릭!"]

  # Network fetching options
                       [--fetch {requests|playwright}] [--timeout 30]
                       [--retries 2] [--proxy http://host:port]
                       [--save_html page.html]
                       [--stealth] [--mobile] [--headful]
                       [--wait_state {load|domcontentloaded|networkidle}]
                       [--sleep_after SECONDS] [--install_browsers]
```

### Fetch examples

```bash
# Basic: requests with retries and headers
python shorts_maker.py --url "https://example.com/product" --timeout 45 --retries 2 --save_html page.html --out out.mp4

# Playwright with stealth and mobile UA (safer for dynamic/guarded pages)
python shorts_maker.py --url "https://example.com/product" \
  --fetch playwright --stealth --mobile --timeout 45 --wait_state networkidle \
  --install_browsers --save_html page.html --out out.mp4

# From saved HTML
python shorts_maker.py --html page.html --out out.mp4
```

---

## How it Works

1. **Scrape**: Pulls Open Graph (`og:title`, `og:image`, `og:description`) + price hints + bullets.
2. **Summarize**: Generates a tight script (hook → 3–5 feature bullets → CTA).
3. **Render**: 
   - Downloads images (or generates placeholders).
   - Builds a 1080×1920 timeline with text overlays, smart crop/fit, subtle zoom.
   - Optional TTS (voiceover) and background music.
4. **Export**: H.264 MP4 ready for Shorts/Reels/TikTok.

---

## Troubleshooting

- **Scraping blocked**: Use `--html saved.html` or paste content manually into `manual_product.json` and run with `--manual manual_product.json`.
- **pyttsx3 errors**: Run with `--no_tts` or switch to your preferred TTS and update `synthesize_voice()`.
- **FFmpeg**: MoviePy requires FFmpeg. Install via your package manager (e.g., `brew install ffmpeg`, `sudo apt-get install ffmpeg`, or use the official binary).

---

## License
MIT

---

## 한국어 안내 (설치/사용법)

### 설치

```bash
# 가상환경 권장
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 필수 패키지 설치
pip install -r requirements.txt

# (선택) Playwright 브라우저 바이너리 설치
python -m playwright install chromium

# (선택) 한글 폰트 설치(Ubuntu 예시)
sudo apt-get install -y fonts-nanum
```

### 빠른 실행 예시

```bash
# 1) Requests 방식 (기본). HTML 저장도 함께.
python shorts_maker.py \
  --url "https://example.com/product" \
  --fetch requests --timeout 45 --retries 2 \
  --save_html page.html --out out.mp4

# 2) Playwright 스텔스(차단/동적 페이지 권장)
python shorts_maker.py \
  --url "https://example.com/product" \
  --fetch playwright --stealth --mobile \
  --timeout 45 --wait_state networkidle \
  --install_browsers --save_html page.html \
  --out out.mp4

# 3) 저장한 HTML에서 생성(완전 안전)
python shorts_maker.py --html page.html --out out.mp4

# 4) 한글 폰트 지정 + TTS 끄기 + 짧게 테스트(8초)
python shorts_maker.py --html page.html \
  --font_path /usr/share/fonts/truetype/nanum/NanumGothic.ttf \
  --no_tts --duration 8 --out out.mp4

# 5) 배경음 추가 (자동 루프)
python shorts_maker.py --html page.html --music assets/music.mp3 --out out.mp4
```

### PDF → MP4 만들기

`shorts_maker2.py`는 PDF 파일을 받아 9:16 MP4 쇼츠 영상으로 변환합니다. 페이지를 이미지로 렌더링하고, 본문에서 핵심 문장을 추출해 자막으로 구성합니다.

```bash
# 기본 사용 (앞에서 최대 6페이지 사용, 24초)
python shorts_maker2.py --pdf sample.pdf --out out.mp4

# 페이지 수/렌더링 해상도/길이 조절
python shorts_maker2.py --pdf sample.pdf --max_pages 8 --zoom 2.5 --duration 30 --out out.mp4

# 한글 폰트 지정 + TTS 끄기 + 배경음
python shorts_maker2.py --pdf sample.pdf \
  --font_path /usr/share/fonts/truetype/nanum/NanumGothic.ttf \
  --no_tts --music assets/music.mp3 --out out.mp4
```

설치 필요 패키지: `pip install -r requirements.txt` (여기에 `pymupdf`, `moviepy`, `Pillow` 포함)

이미지 추출(크롭) 옵션
```bash
# 이미지 블록만 추출해서 사용(자동 탐지)
python shorts_maker2.py --pdf sample.pdf --pdf_mode image --min_img_ratio 0.05 --crop_margin 0.01 --out out.mp4

# 자동(auto): 이미지가 추출되면 이미지 사용, 아니면 전체 페이지 렌더로 대체
python shorts_maker2.py --pdf sample.pdf --pdf_mode auto --out out.mp4
```

### 주요 옵션(요약)

- `--fetch {requests|playwright}`: HTML 수집 방식 선택(기본: requests)
- `--timeout N`, `--retries N`, `--proxy URL`, `--save_html FILE`
- `--stealth`, `--mobile`, `--headful`, `--wait_state`, `--sleep_after`, `--install_browsers`
- `--no_tts`, `--voice_rate`, `--music`, `--font_path`, `--duration`, `--min_slide`, `--max_slide`, `--cta`

참고
- 쿠팡 등은 차단이 잦습니다. `--fetch playwright --stealth` 또는 `--html` 사용을 권장합니다.
- TTS 경고가 거슬리면 `--no_tts`를 사용하세요.
- 최종 영상은 1080×1920 H.264로 내보내집니다.

### HTML 저장 방법

- 스크립트 옵션으로 저장(권장)
  - requests:
    ```bash
    python shorts_maker.py \
      --url "https://example.com/product" \
      --fetch requests --timeout 45 --retries 2 \
      --save_html page.html --out out.mp4
    ```
  - Playwright 스텔스:
    ```bash
    python shorts_maker.py \
      --url "https://example.com/product" \
      --fetch playwright --stealth --mobile \
      --timeout 45 --wait_state networkidle \
      --install_browsers --save_html page.html \
      --out out.mp4
    ```

- 터미널에서 직접 저장
  - curl:
    ```bash
    curl -L --compressed \
      -A "Mozilla/5.0" \
      -H "Referer: https://www.coupang.com/" \
      -H "Accept-Language: ko-KR,ko;q=0.9" \
      "https://example.com/product" -o page.html
    ```
  - wget:
    ```bash
    wget -U "Mozilla/5.0" \
      --header="Referer: https://www.coupang.com/" \
      --header="Accept-Language: ko-KR,ko;q=0.9" \
      -O page.html "https://example.com/product"
    ```

- 브라우저에서 저장
  - 페이지 열기 → Ctrl+S → “웹페이지, 전체” 저장 → `page.html` 사용

- DevTools로 정확히 저장(쿠키/헤더 포함)
  - 크롬 개발자도구 → Network 탭 → 새로고침 → 문서 요청 우클릭 → Copy → “Copy as cURL (bash)” → 명령 끝에 `-o page.html` 추가 후 실행

- Headless Chromium 간단 덤프(동적 요소 누락 가능)
  ```bash
  chromium --headless=new --dump-dom "https://example.com/product" > page.html
  ```

  - 동적/차단 페이지 팁
  - Playwright에 `--wait_state networkidle --sleep_after 3`로 로딩 여유를 주고, 필요 시 `--mobile`, `--headful` 조합

---

## 간단 UI로 실행 (Streamlit)

브라우저 UI에서 URL/HTML, 이미지, PDF를 선택해 바로 MP4를 만들 수 있습니다.

```bash
# 의존성 설치
pip install -r requirements.txt

# UI 실행
streamlit run ui_app.py
```

UI에서 지원하는 기능
- URL/HTML → MP4 (shorts_maker.py 호출)
- 이미지 → MP4 (shorts_maker2.py 호출)
- PDF → MP4 (shorts_maker2.py 호출)
- 공통 옵션: 길이, 슬라이드 길이, 폰트, TTS, 음성 속도, 배경음악, CTA
- URL 모드: requests/Playwright 선택, 스텔스/모바일/대기 조건, HTML 저장 등

결과 파일은 `ui_outputs/`에 저장되며, UI에서 즉시 미리보기 가능합니다.

### Deep Fetch(스크롤/더보기) + 이미지 관리

- Deep Fetch: `Parse URL ➜ Prefill fields` 전에 아래를 설정해 이미지 수집을 강화합니다.
  - `Playwright fallback`: 헤드리스 Chromium 사용.
  - `Stealth`: 봇 차단 우회 보조.
  - `Mobile`: 모바일 UA/뷰포트 사용.
  - `Deep fetch (scroll/expand)`: 페이지를 단계적으로 스크롤하고 “더보기/설명” 토글을 눌러 큰 이미지 로드 유도(더보기 클릭은 최대 2회).
  - `Scroll passes`: 스크롤 횟수(기본 8). 늘릴수록 더 많이 로드됨.
- Prefill 동작: `Parse URL ➜ Prefill fields`를 누르면 제목/가격/특징을 채우고, 수집한 이미지를 다운로드해 아래 리스트에 추가합니다.
- Run 동작: `Fetch URL ➜ Run`도 사용한 이미지를 리스트에 추가합니다.
- Fetched 이미지 관리(하단 "Fetched images ready: N files"):
  - `Add more fetched images`: 이미지 추가 업로드(목록에 Append).
  - `Remove selected`: 선택 삭제(파일도 삭제).
  - `Clear all`: 전체 삭제(파일 삭제 + 목록 초기화).

권장: `pip install playwright playwright-stealth && python -m playwright install chromium`

참고: 차단/동적 페이지(예: AliExpress/일부 커머스)는 Deep Fetch + Stealth + Mobile 조합이 안정적입니다.

### 제목 파싱(한글 우선)

- 여러 후보에서 제목 수집 후 한글이 포함된 값을 우선 선택합니다.
  - 대상: `og:title`, `twitter:title`, `name="title"`, `itemprop="name"`, `<title>`, `h1/h2/.product-title/.prod-buy-header__title`.
  - 다국어 메타가 있을 때 화면에 보이는 한글 제목을 더 잘 선택합니다.

### OpenAI 설정 (.env)

Streamlit UI의 대본 자동생성(\"AI에게 요청하기\") 기능은 OpenAI Chat Completions API를 사용합니다. 루트 폴더의 `.env` 파일에 키를 넣으면 자동으로 읽습니다.

```dotenv
# 필수
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 선택(기본: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# 선택: 커스텀/프록시 엔드포인트 사용 시 (기본: https://api.openai.com/v1)
OPENAI_BASE_URL=https://api.openai.com/v1
```

동작 방식
- `ui_app.py` 시작 시 `.env`를 로드합니다. `python-dotenv`가 있으면 이를 사용하고, 없으면 간단한 수동 파서로 읽습니다.
- 이미 설정된 시스템 환경변수는 `.env` 값으로 덮어쓰지 않습니다(환경변수 우선).
- 키가 없거나 호출 오류 발생 시 UI에 경고가 표시되고, 수동 대본 텍스트를 그대로 사용할 수 있습니다.

동작 확인
1) `streamlit run ui_app.py` 실행
2) Images 탭에서 제목/특징/가격을 입력하고 \"AI에게 요청하기\" 클릭
3) 스크립트가 생성되면 키 인식/호출이 정상입니다.
# 35.5youtube_shorts
