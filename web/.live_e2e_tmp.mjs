// Live E2E driver for MindMorph — no mocks, hits the real backend + real Ollama model.
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const OUT = '/private/tmp/claude-501/-Users-tarungupta-Making-It-Big-Claude-content-machine/dc73124d-928d-43ba-beee-bd90fcccd3db/scratchpad/live-ollama';
const timings = {};

function mark(label, seconds) {
  timings[label] = seconds;
  console.log(`[TIMING] ${label}: ${seconds.toFixed(2)}s`);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    recordVideo: { dir: OUT, size: { width: 1280, height: 800 } },
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));

  console.log('Navigating to http://localhost:3000 ...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle', timeout: 60000 });
  await page.screenshot({ path: `${OUT}/00_login_gate.png` });

  // --- Step 1: login gate (localStorage identity, no backend call) ---
  const emailInput = page.getByLabel('Email');
  await emailInput.fill('tarungupta.medium@gmail.com');
  await page.getByRole('button', { name: /enter/i }).click();
  await page.waitForSelector('text=Start a new path', { timeout: 15000 });
  await page.screenshot({ path: `${OUT}/01_dashboard.png` });

  // --- Step 2: submit the roadmap query ---
  const query = 'I want to learn Python list comprehensions — create a roadmap for me';
  const queryInput = page.getByLabel('What do you want to learn?');
  await queryInput.fill(query);
  await page.screenshot({ path: `${OUT}/02_query_typed.png` });

  const t0Graph = Date.now();
  await page.getByRole('button', { name: /generate/i }).click();

  // --- Step 3: poll for SSE stage labels while the Dashboard shows "Building…" ---
  const stageMatchers = {
    Orchestrator: /routing your request/i,
    Scout: /scout/i,
    Academic: /academic/i,
    Market: /market/i,
    Practical: /practical/i,
    Consensus: /consensus/i,
    Reviewer: /reviewing the skill graph/i,
  };
  const seenStages = new Set();
  // Single loop, one deadline: local multi-agent construction (orchestrator -> scout -> academic/
  // market/practical -> consensus -> reviewer) legitimately takes many minutes on a 14B model on a
  // laptop. Never cut this short on a tight cap.
  const stageDeadline = Date.now() + 20 * 60 * 1000;
  let navigatedToSession = false;

  while (Date.now() < stageDeadline) {
    const url = page.url();
    if (/\/session\//.test(url)) { navigatedToSession = true; break; }
    const bodyText = await page.textContent('body').catch(() => '');
    for (const [name, re] of Object.entries(stageMatchers)) {
      if (bodyText && re.test(bodyText) && !seenStages.has(name)) {
        seenStages.add(name);
        console.log(`[STAGE SEEN] ${name} at +${((Date.now() - t0Graph) / 1000).toFixed(1)}s: "${bodyText.match(re)?.[0]}"`);
        await page.screenshot({ path: `${OUT}/stage_${String(seenStages.size).padStart(2, '0')}_${name}.png` }).catch(() => {});
      }
    }
    await page.waitForTimeout(1500);
  }
  const graphConstructionSeconds = (Date.now() - t0Graph) / 1000;
  mark('graph_construction (submit -> /session/<id> navigation)', graphConstructionSeconds);
  await page.screenshot({ path: `${OUT}/03_post_create.png`, fullPage: true });

  fs.writeFileSync(`${OUT}/stages_seen.json`, JSON.stringify([...seenStages], null, 2));

  if (!navigatedToSession) {
    console.log('WARNING: never navigated to a /session/<id> URL — query likely routed to CONTENT/EXERCISE, not SCOUT.');
    const bodyText = await page.textContent('body').catch(() => '');
    console.log('[PAGE TEXT SNAPSHOT]', bodyText?.slice(0, 2000));
    finish();
    return;
  }

  // --- Step 4: assessment quiz gate — skip it to reach the graph directly ---
  const skipBtn = page.getByRole('button', { name: /skip for now/i });
  if (await skipBtn.count() > 0) {
    await skipBtn.click();
    await page.waitForTimeout(1000);
  }

  // --- Step 5: wait for the skill graph (react-flow nodes) to render ---
  await page.waitForSelector('.react-flow__node', { timeout: 60000 }).catch((e) => {
    console.log('WARNING: react-flow node wait failed: ' + e.message);
  });
  await page.screenshot({ path: `${OUT}/04_graph_rendered.png`, fullPage: true });
  const initialNodeLabels = await page.locator('.react-flow__node').allTextContents();
  console.log('[GRAPH NODES]', JSON.stringify(initialNodeLabels));
  fs.writeFileSync(`${OUT}/initial_nodes.json`, JSON.stringify(initialNodeLabels, null, 2));

  // --- Step 6: open the first (foundational, unlocked) node's lesson ---
  const t0Lesson = Date.now();
  const firstNode = page.locator('.react-flow__node').first();
  await firstNode.click();
  await page.waitForSelector('article', { timeout: 5 * 60 * 1000 }).catch((e) => {
    console.log('WARNING: lesson <article> wait failed: ' + e.message);
  });
  await page.waitForTimeout(1000);
  mark('lesson_generation (node click -> lesson panel)', (Date.now() - t0Lesson) / 1000);
  await page.screenshot({ path: `${OUT}/05_lesson.png`, fullPage: true });

  const hasMarkdown = await page.locator('article .prose').count().catch(() => 0);
  const hasCode = await page.locator('pre code, code.hljs').count().catch(() => 0);
  const hasMermaid = await page.locator('.mermaid, svg[id*="mermaid"]').count().catch(() => 0);
  console.log(`[LESSON CHECK] markdown containers=${hasMarkdown} code blocks=${hasCode} mermaid=${hasMermaid}`);

  // --- Step 7: submit a deliberately wrong (valid syntax, unrelated logic) coding solution ---
  const t0Grade = Date.now();
  let gradeSubmitted = false;
  const monacoEditor = page.locator('.monaco-editor').first();
  if (await monacoEditor.count() > 0) {
    await monacoEditor.click();
    await page.keyboard.press('ControlOrMeta+A');
    await page.keyboard.type('def unrelated():\n    return 3.14159  # deliberately wrong, unrelated to the exercise\n', { delay: 5 });
    await page.screenshot({ path: `${OUT}/06_wrong_answer_typed.png` });
    const gradeBtn = page.getByRole('button', { name: /grade my submission/i });
    if (await gradeBtn.count() > 0 && await gradeBtn.isEnabled()) {
      await gradeBtn.click();
      gradeSubmitted = true;
      await page.waitForSelector('text=/%$/', { timeout: 5 * 60 * 1000 }).catch((e) => {
        console.log('WARNING: grade-result wait failed: ' + e.message);
      });
    } else {
      console.log('WARNING: Grade button not found/enabled.');
    }
  } else {
    console.log('WARNING: no Monaco editor found — exercise may not be a coding_challenge, or lesson had no exercise.');
  }
  mark('grading (submit -> result)', (Date.now() - t0Grade) / 1000);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/07_after_grade.png`, fullPage: true });

  // --- Step 8: check the four remediation claims ---
  await page.waitForTimeout(2000); // let the graph re-render with any remedial node
  const afterNodeLabels = await page.locator('.react-flow__node').allTextContents();
  const newNodeAppeared = afterNodeLabels.length > initialNodeLabels.length;
  console.log('[GRAPH NODES AFTER GRADE]', JSON.stringify(afterNodeLabels));

  const enterAnimClass = await page.locator('.skill-node-enter').count().catch(() => 0);
  await page.screenshot({ path: `${OUT}/08_graph_after_grade.png`, fullPage: true });

  let lockedNodeFound = false;
  let lockMessageShown = false;
  const lockedCandidate = page.locator('.react-flow__node[style*="cursor: not-allowed"]').first();
  if (await lockedCandidate.count() > 0) {
    lockedNodeFound = true;
    await lockedCandidate.click({ force: true }).catch(() => {});
    await page.waitForTimeout(500);
    const bodyText = await page.textContent('body').catch(() => '');
    lockMessageShown = /locked — first complete/i.test(bodyText ?? '');
  }
  await page.screenshot({ path: `${OUT}/09_locked_node_click.png`, fullPage: true });

  fs.writeFileSync(`${OUT}/timings.json`, JSON.stringify(timings, null, 2));
  fs.writeFileSync(`${OUT}/console_errors.json`, JSON.stringify(consoleErrors, null, 2));
  fs.writeFileSync(
    `${OUT}/run_meta.json`,
    JSON.stringify(
      {
        navigatedToSession,
        seenStages: [...seenStages],
        gradeSubmitted,
        newNodeAppeared,
        initialNodeCount: initialNodeLabels.length,
        afterNodeCount: afterNodeLabels.length,
        skillNodeEnterClassCount: enterAnimClass,
        lockedNodeFound,
        lockMessageShown,
      },
      null,
      2,
    ),
  );

  await finish();

  async function finish() {
    await context.close();
    await browser.close();
    const videoPath = fs.readdirSync(OUT).find((f) => f.endsWith('.webm'));
    console.log('VIDEO_FILE=' + (videoPath ? `${OUT}/${videoPath}` : 'NONE'));
  }
}

main().catch(async (e) => {
  console.error('FATAL', e);
  process.exit(1);
});
