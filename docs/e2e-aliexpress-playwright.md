**목표**
- 알리익스프레스 상품 페이지에서 이미지 스크롤 캡처 → 에셋 등록 → 이미지/텍스트 클립 배치 → 대본(스크립트) 설정 → TTS 내레이션 포함 렌더 → 결과 파일 확인까지 전 과정을 Playwright로 검증.

**사전 준비**
- Node 18+, Python 3.10+ 설치
- 의존성 설치: `pip install -r backend/requirements.txt`
- Playwright 런타임 설치: `python -m playwright install --with-deps`
- 환경 변수: 기본값 사용 시 불필요. 필요 시 `NEXT_PUBLIC_BACKEND_URL`로 UI→백엔드 주소를 바꿀 수 있음.

**테스트 대상 URL**
- `https://ko.aliexpress.com/item/1005007222475363.html`

**서버 기동**
- 명령: `npm run dev`  (백엔드 8000, 웹 3100)
- 포트 충돌 시: `kill -9 $(lsof -ti tcp:3100)` 또는 `fuser -k 3100/tcp`

**검증 시나리오(요약)**
- 새 프로젝트 생성 → URL 스크롤 캡처로 이미지 수집/에셋화 → 텍스트/이미지 클립 추가 → 타임라인 저장 → 프리셋(9:16/16:9 + 1080p) 적용 → 대본 입력 → 렌더(SSE) 진행 → 출력 파일 경로 확인.

**수동 테스트 절차**
- 새 프로젝트: 상단바 [새 프로젝트] → 이름 입력(예: `E2E-ALI`) → 프로젝트 선택 드롭다운에서 방금 생성 선택.
- 이미지 수집: Asset 패널 [URL 스크롤 가져오기] → 위 URL 입력 → 알림에 표시된 개수 확인(기본 최대 12장). 에셋 카드가 목록에 나타나야 함.
- 타임라인 배치:
  - [이미지 클립 추가] 클릭 → 이미지 트랙에 블록이 나타남.
  - [텍스트 클립 추가] 클릭 → 텍스트 트랙에 블록이 나타남.
  - [타임라인 저장] 클릭 → 백엔드 `/projects/{id}` 저장 성공.
- 프리셋: 상단바 [16:9] → 해상도 드롭다운 [1080p] 선택 → 상단 미리보기 정보가 `1920x1080`으로 갱신됨.
- 대본 입력: Script 패널에
  - 제목: “초강력 무선 미니청소기”
  - 특징: 여러 줄로 입력(예: “강력 흡입\nType-C 충전\n초경량 디자인”) → 자동으로 리스트 저장.
- 렌더: 상단바 [렌더(SSE)] → 진행바가 100% 도달 → 완료 알림의 경로 확인.
- 결과: `projects/<프로젝트ID>/renders/*.mp4` 파일 생성.

**검증 포인트**
- 에셋: 에셋 카드 1개 이상 표시, 각 카드에 [보기/선택/삭제] 컨트롤 노출.
- 트랙: 이미지/텍스트 트랙 각각에 최소 1개 클립 존재, 길이/시작값 표시.
- 해상도/비율: 상단 미리보기 정보가 선택한 프리셋과 일치(예: 1920x1080, 30fps).
- 렌더 진행: SSE 진행바가 증가하고 완료 이벤트로 닫힘.
- 결과 파일: mp4 생성, 파일 크기 > 0.

**API 기반 확인(선택)**
- 프로젝트 ID 조회: `curl -s http://localhost:8000/projects | jq -r '.projects[0].id'`
- 프로젝트 상태: `curl -s http://localhost:8000/projects/<id> | jq '{w:.width,h:.height,images:(.tracks[]|select(.kind=="image")|.clips|length),texts:(.tracks[]|select(.kind=="text")|.clips|length)}'`

**Playwright 자동화 스크립트 예시**
- 파일 경로: `tests/e2e.aliexpress.spec.ts` (원하면 프로젝트에 추가하세요)
- 실행 전 서버 기동 필요(`npm run dev`).

```
import { test, expect } from '@playwright/test';

const WEB = process.env.WEB_URL || 'http://localhost:3100';
const BACKEND = process.env.API_URL || 'http://localhost:8000';
const URL = 'https://ko.aliexpress.com/item/1005007222475363.html';

test('aliexpress full e2e', async ({ page }) => {
  // 1) UI 접속
  await page.goto(WEB);

  // 2) 새 프로젝트 생성
  page.once('dialog', (d) => d.accept('E2E-ALI'));
  await page.getByRole('button', { name: '새 프로젝트' }).click();

  // 3) 프로젝트 선택 (첫 옵션 또는 방금 생성)
  await page.getByRole('combobox').first().selectOption({ label: 'E2E-ALI' });

  // 4) 스크롤 캡처로 이미지 수집→에셋 등록
  page.once('dialog', (d) => d.accept(URL));
  await page.getByRole('button', { name: 'URL 스크롤 가져오기' }).click();
  // 에셋 목록 생성 대기
  await expect(page.getByText(/보기/)).toBeVisible({ timeout: 120000 });

  // 5) 클립 추가(이미지, 텍스트)
  await page.getByRole('button', { name: '이미지 클립 추가' }).click();
  await page.getByRole('button', { name: '텍스트 클립 추가' }).click();

  // 6) 타임라인 저장
  await page.getByRole('button', { name: '타임라인 저장' }).click();

  // 7) 프리셋 적용 (16:9 + 1080p)
  await page.getByRole('button', { name: '16:9' }).click();
  await page.getByRole('combobox').nth(1).selectOption({ label: '1080p' });

  // 8) 대본 입력
  await page.getByLabel('제목').fill('초강력 무선 미니청소기');
  await page.getByText('특징(줄바꿈으로 구분)').locator('xpath=..').getByRole('textbox').fill('강력 흡입\nType-C 충전\n초경량 디자인');

  // 9) 렌더(SSE)
  await page.getByRole('button', { name: '렌더(SSE)' }).click();
  // 진행바 100% 근처까지 대기
  await page.waitForTimeout(1000);
  await expect(page.getByRole('progressbar')).toBeVisible({ timeout: 120000 });

  // 10) 백엔드에서 결과 파일 확인 (선택: API 폴링)
  // 실제 파일 경로는 알림/로그로도 확인 가능
});
```

**주의/트러블슈팅**
- 포트 충돌: `ss -lptn 'sport = :3100'`로 프로세스 확인 후 종료.
- Playwright 브라우저 미설치: `python -m playwright install --with-deps` 실행.
- 이미지 수집 수량: 사이트 구조나 로딩에 따라 변동(기본 최대 12장). 필요 시 백엔드 `ScrollCaptureReq.max_images` 조정 가능.
- TTS: `edge-tts` 사용 시 네트워크 필요. 실패 시 `pyttsx3`로 폴백할 수 있음(로컬 음성엔진 필요).
- Next 경고: `experimental.appDir` 경고는 기능에 영향 없음.

**완료 기준**
- 프로젝트 상세 조회 시 `image >= 1`, `text >= 1` 클립, 해상도 1920x1080.
- 렌더 완료 알림 또는 `/projects/<id>/renders/*.mp4` 파일 생성.

