// Second live pass: reuse the EXISTING session (skip an 8-min graph rebuild) and drive the
// remediation flow on a node that has never been touched, so the before/after diff is clean:
// open its lesson, submit a deliberately wrong solution, and check whether existing nodes glide
// vs snap, whether the new remedial node's entrance class fires, and whether the failed node locks.
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const OUT = '/private/tmp/claude-501/-Users-tarungupta-Making-It-Big-Claude-content-machine/dc73124d-928d-43ba-beee-bd90fcccd3db/scratchpad/live-ollama';
const SESSION_ID = '5377c914a7934906aea77e2076a0c1da';
const USER_ID = 'tarungupta.medium@gmail.com';
const TARGET_LABEL = 'Control Flow Statements'; // untouched, available node

const timings = {};
function mark(label, seconds) {
  timings[label] = seconds;
  console.log(`[TIMING] ${label}: ${seconds.toFixed(2)}s`);
}

async function nodePositions(page) {
  return page.evaluate(() => {
    const out = {};
    document.querySelectorAll('.react-flow__node').forEach((el) => {
      const id = el.getAttribute('data-id');
      const r = el.getBoundingClientRect();
      out[id] = { x: r.x, y: r.y };
    });
    return out;
  });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: OUT, size: { width: 1280, height: 800 } },
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));

  // Seed identity via localStorage (same key useUser.ts reads), then load the session directly.
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.evaluate((uid) => localStorage.setItem('mindmorph.userId', uid), USER_ID);
  await page.goto(`http://localhost:3000/session/${SESSION_ID}`, { waitUntil: 'networkidle' });

  await page.waitForSelector('.react-flow__node', { timeout: 30000 });
  await page.waitForTimeout(2500); // let the post-commit "seen ids" effect register this mount's nodes
  await page.screenshot({ path: `${OUT}/r00_session_loaded.png`, fullPage: true });

  const before = await nodePositions(page);
  fs.writeFileSync(`${OUT}/r_positions_before.json`, JSON.stringify(before, null, 2));
  console.log('[POSITIONS BEFORE]', JSON.stringify(before));

  // --- open the lesson on the untouched node ---
  const t0Lesson = Date.now();
  const targetNode = page.locator('.react-flow__node', { hasText: TARGET_LABEL }).first();
  await targetNode.click();
  await page.waitForSelector('article', { timeout: 20 * 60 * 1000 }); // generous: ~8min observed once already
  await page.waitForTimeout(500);
  mark('lesson_generation_2 (node click -> lesson panel)', (Date.now() - t0Lesson) / 1000);
  await page.screenshot({ path: `${OUT}/r01_lesson.png`, fullPage: true });

  const hasMarkdown = await page.locator('article .prose').count();
  const hasCode = await page.locator('pre code, code.hljs').count();
  const hasMermaid = await page.locator('.mermaid, svg[id*="mermaid"]').count();
  console.log(`[LESSON CHECK 2] markdown=${hasMarkdown} code=${hasCode} mermaid=${hasMermaid}`);

  // --- submit a deliberately wrong solution ---
  const t0Grade = Date.now();
  let gradeSubmitted = false;
  let exerciseFormat = 'unknown';
  const monacoEditor = page.locator('.monaco-editor').first();
  const textArea = page.getByLabel('Your analysis');
  if (await monacoEditor.count() > 0) {
    exerciseFormat = 'coding_challenge';
    await monacoEditor.click();
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.type(
      'def totally_unrelated():\n    return 3.14159  # deliberately wrong, unrelated to the exercise\n',
      { delay: 5 },
    );
  } else if (await textArea.count() > 0) {
    exerciseFormat = 'free_response';
    await textArea.fill('Bananas are yellow and the sky is blue. This has nothing to do with the exercise.');
  } else {
    console.log('WARNING: no exercise input found (no Monaco editor, no textarea).');
  }
  await page.screenshot({ path: `${OUT}/r02_wrong_answer_typed.png` });

  const gradeBtn = page.getByRole('button', { name: /grade my submission/i });
  if (await gradeBtn.count() > 0 && await gradeBtn.isEnabled()) {
    await gradeBtn.click();
    gradeSubmitted = true;
    await page.waitForSelector('text=/%$/', { timeout: 10 * 60 * 1000 });
  } else {
    console.log('WARNING: Grade button missing/disabled.');
  }
  mark('grading_2 (submit -> result)', (Date.now() - t0Grade) / 1000);

  // Screenshot the INSTANT the grade result exists — before any settling wait — to catch the
  // transition close to when it fires.
  await page.screenshot({ path: `${OUT}/r03_immediately_after_grade.png`, fullPage: true });
  const immediateEnterClasses = await page.locator('.skill-node-enter').count().catch(() => 0);

  // Let CSS transitions/animations (300-380ms) settle, then measure the final state.
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/r04_settled_after_grade.png`, fullPage: true });

  const after = await nodePositions(page);
  fs.writeFileSync(`${OUT}/r_positions_after.json`, JSON.stringify(after, null, 2));
  console.log('[POSITIONS AFTER]', JSON.stringify(after));

  const beforeIds = new Set(Object.keys(before));
  const afterIds = new Set(Object.keys(after));
  const newIds = [...afterIds].filter((id) => !beforeIds.has(id));
  const movedExisting = [...beforeIds].filter((id) => afterIds.has(id)).map((id) => {
    const b = before[id], a = after[id];
    const dx = Math.abs(b.x - a.x), dy = Math.abs(b.y - a.y);
    return { id, dx, dy, moved: dx > 2 || dy > 2 };
  });
  console.log('[NEW NODE IDS]', JSON.stringify(newIds));
  console.log('[MOVED EXISTING]', JSON.stringify(movedExisting));

  // Grab feedback text + which node the backend flagged as needing remediation.
  const feedbackText = await page.locator('text=/%$/').first().locator('..').textContent().catch(() => null);

  // --- click the (now expected-locked) failed node and look for the lock message ---
  await page.waitForTimeout(500);
  const failedNode = page.locator('.react-flow__node', { hasText: TARGET_LABEL }).first();
  await failedNode.click({ force: true }).catch(() => {});
  await page.waitForTimeout(500);
  const bodyTextAfterClick = await page.textContent('body').catch(() => '');
  const lockMessageShown = /locked — first complete/i.test(bodyTextAfterClick ?? '');
  await page.screenshot({ path: `${OUT}/r05_locked_click.png`, fullPage: true });

  const finalNodeLabels = await page.locator('.react-flow__node').allTextContents();

  fs.writeFileSync(`${OUT}/r_timings.json`, JSON.stringify(timings, null, 2));
  fs.writeFileSync(`${OUT}/r_console_errors.json`, JSON.stringify(consoleErrors, null, 2));
  fs.writeFileSync(
    `${OUT}/r_run_meta.json`,
    JSON.stringify(
      {
        exerciseFormat,
        gradeSubmitted,
        hasMarkdown,
        hasCode,
        hasMermaid,
        newIds,
        movedExisting,
        immediateEnterClassCount: immediateEnterClasses,
        settledEnterClassCount: await page.locator('.skill-node-enter').count().catch(() => 0),
        lockMessageShown,
        finalNodeLabels,
        feedbackText,
      },
      null,
      2,
    ),
  );

  await context.close();
  await browser.close();
  const videoPath = fs.readdirSync(OUT).filter((f) => f.endsWith('.webm')).sort().pop();
  console.log('VIDEO_FILE=' + (videoPath ? `${OUT}/${videoPath}` : 'NONE'));
}

main().catch((e) => {
  console.error('FATAL', e);
  process.exit(1);
});
