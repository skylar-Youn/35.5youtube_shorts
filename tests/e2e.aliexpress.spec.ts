import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const WEB = process.env.WEB_URL || 'http://localhost:3100';
const BACKEND = process.env.API_URL || 'http://localhost:8000';
const ALI_URL = 'https://ko.aliexpress.com/item/1005007222475363.html';

async function fetchJson(path: string, init?: RequestInit) {
  const res = await fetch(BACKEND + path, init);
  if (!res.ok) throw new Error(`HTTP ${res.status} ${path}`);
  return res.json() as Promise<any>;
}

async function getProjectIdByName(name: string): Promise<string | undefined> {
  const list = await fetchJson('/projects');
  const item = (list.projects || []).find((p: any) => p.name === name);
  return item?.id;
}

test('Aliexpress: 스크롤 캡처 → 에셋 → 클립 → 저장 → 프리셋 → 대본 → 렌더', async ({ page }) => {
  test.setTimeout(600_000);

  // 다이얼로그 일괄 수락 핸들러
  page.on('dialog', async (d) => {
    const msg = d.message();
    if (d.type() === 'prompt' && msg.includes('새 프로젝트 이름')) {
      await d.accept('E2E-ALI');
      return;
    }
    if (d.type() === 'prompt' && msg.includes('이미지 가져올 URL')) {
      await d.accept(ALI_URL);
      return;
    }
    await d.accept();
  });

  // 1) UI 접속
  await page.goto(WEB);

  // 2) 새 프로젝트 생성
  await page.getByRole('button', { name: '새 프로젝트' }).click();
  await expect.poll(async () => (await getProjectIdByName('E2E-ALI')) ? 'ok' : '', { timeout: 60_000 }).toBe('ok');

  // 3) 프로젝트 선택
  await page.getByRole('combobox').first().selectOption({ label: 'E2E-ALI' });

  // 4) URL 스크롤 캡처로 에셋 수집/등록
  await page.getByRole('button', { name: 'URL 스크롤 가져오기' }).click();
  const prjId = await expect.poll(async () => (await getProjectIdByName('E2E-ALI')) || '', { timeout: 10_000 });
  await expect.poll(async () => {
    const prj = await fetchJson(`/projects/${prjId}`);
    return Object.keys(prj.assets || {}).length;
  }, { timeout: 180_000, message: 'assets populated' }).toBeGreaterThan(0);

  // 5) 이미지/텍스트 클립 추가 → 저장
  await page.getByRole('button', { name: '이미지 클립 추가' }).click();
  await page.getByRole('button', { name: '텍스트 클립 추가' }).click();
  await page.getByRole('button', { name: '타임라인 저장' }).click();

  await expect.poll(async () => {
    const prj = await fetchJson(`/projects/${prjId}`);
    const img = (prj.tracks || []).find((t: any) => t.kind === 'image');
    const txt = (prj.tracks || []).find((t: any) => t.kind === 'text');
    return [img?.clips?.length || 0, txt?.clips?.length || 0].join('/');
  }, { timeout: 30_000 }).toBe('1/1');

  // 6) 프리셋(16:9 + 1080p)
  await page.getByRole('button', { name: '16:9' }).click();
  await page.locator('select').nth(1).selectOption({ label: '1080p' });

  await expect.poll(async () => {
    const prj = await fetchJson(`/projects/${prjId}`);
    return `${prj.width}x${prj.height}`;
  }, { timeout: 30_000 }).toBe('1920x1080');

  // 7) 대본 입력(제목 + 특징)
  await page.locator('div:has-text("대본 편집")').locator('input').first().fill('초강력 무선 미니청소기');
  await page.locator('textarea').fill('강력 흡입\nType-C 충전\n초경량 디자인');

  // 8) 렌더(API)
  const outName = `e2e_${Date.now()}.mp4`;
  const res = await fetchJson('/render', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: prjId, out_name: outName }),
  });
  expect(res?.ok).toBeTruthy();
  const outPath = res?.path as string;
  expect(outPath).toContain(outName);
  expect(fs.existsSync(outPath)).toBeTruthy();
});

