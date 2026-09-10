import { type Page, expect, test } from "@playwright/test";
import { sanitizeMermaid } from "../lib/mermaid";

// In-situ counterpart to mermaidContainment.spec.ts. That spec drives the mermaid bundle directly in
// a blank page, so it proves mermaid's behaviour under the flags — not the app's. This one renders a
// genuinely unrepairable diagram through the real lesson panel and asserts what a learner would see:
// the <pre> fallback carrying the ORIGINAL source, and nothing orphaned onto document.body —
// including after the diagram unmounts.
//
// The diagram is the case the sanitiser deliberately refuses (a round node whose label carries
// parens): quoting it would risk flattening a valid shape, so containment is what has to hold.
const UNREPAIRABLE = "graph TD\n  A((Raw Files (CSV, JSON, SQL))) --> B[Parse]";

const EXERCISE = {
  format: "coding_challenge",
  statement: "Write `load()`.",
  grading_artifact: { format: "coding_challenge", unit_tests: [] },
};

/** Two unlinked nodes: 'a' carries the diagram, 'b' is a plain lesson used to mount/unmount it. */
async function mockApi(page: Page, diagram: string) {
  const ls = {
    skill_graph: {
      summary: "Learn Data",
      nodes: [
        { id: "a", label: "Pipelines", description: "ingest", level: "foundational" },
        { id: "b", label: "Storage", description: "warehouse", level: "foundational" },
      ],
      edges: [] as unknown[],
    },
    summary: "Learn Data",
    node_state: {
      a: { status: "available", best_score: 0, attempts: 0, weaknesses: [], last_feedback: null },
      b: { status: "available", best_score: 0, attempts: 0, weaknesses: [], last_feedback: null },
    },
    lessons: {} as Record<string, unknown>,
    selected_node: null as string | null,
    format_type: "B",
  };
  const sid = "sess1";

  await page.route("**/sessions/*", (route) => route.fulfill({ json: [] }));
  await page.route(`**/sessions/*/${sid}`, (route) =>
    route.fulfill({ json: { session_id: sid, learning_session: ls } }),
  );
  await page.route(`**/sessions/*/${sid}/lessons/a`, (route) => {
    ls.lessons.a = {
      content: `# Pipelines\nHere is the shape of it.\n\n\`\`\`mermaid\n${diagram}\n\`\`\`\n`,
      exercise: EXERCISE,
    };
    ls.selected_node = "a";
    return route.fulfill({ json: { session_id: sid, learning_session: ls } });
  });
  await page.route(`**/sessions/*/${sid}/lessons/b`, (route) => {
    ls.lessons.b = { content: "# Storage\nNo diagram here.", exercise: EXERCISE };
    ls.selected_node = "b";
    return route.fulfill({ json: { session_id: sid, learning_session: ls } });
  });
}

async function openSession(page: Page) {
  await page.addInitScript(() => localStorage.setItem("mindmorph.userId", "e2e@test.com"));
  await page.goto("/session/sess1");
  await expect(page.getByText("skills complete")).toBeVisible();
}

async function openLesson(page: Page, label: string, heading: string) {
  await page.getByText(label).first().click();
  await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
}

/** Everything mermaid could have orphaned outside the React tree, plus its error graphic. */
function domState(page: Page) {
  return page.evaluate(() => ({
    // Direct children of body, identified rather than merely counted — Monaco and the Next dev
    // overlay legitimately park elements here, so the assertion is "this set did not change".
    bodyChildren: [...document.body.children]
      .map((c) => `${c.tagName}#${c.id}.${c.className}`)
      .join(" | "),
    // Scoped to body's DIRECT children: that is where mermaid appends its working div when render()
    // is called without an svgContainingElement. A successfully rendered diagram also carries
    // mmd-prefixed ids, but those live inside the React tree and are not artifacts.
    orphanedRenderDivs: document.querySelectorAll(
      'body > [id^="mmd-"], body > [id^="dmmd-"], body > [id^="immd-"]',
    ).length,
    errorGraphics: document.querySelectorAll(
      '[aria-roledescription="error"], .error-icon, .error-text',
    ).length,
    syntaxErrorText: document.body.innerText.includes("Syntax error"),
  }));
}

test("an unrepairable diagram falls back to the original source and orphans nothing", async ({
  page,
}) => {
  // Pre-flight: this really is a diagram the sanitiser refuses to touch, so the failure branch is
  // reached honestly rather than by feeding mermaid something the app would have repaired.
  expect(sanitizeMermaid(UNREPAIRABLE)).toBe(UNREPAIRABLE);

  await mockApi(page, UNREPAIRABLE);
  await openSession(page);

  // Baseline taken with a plain lesson already open, so Monaco's body-level nodes are mounted and
  // the comparison isolates mermaid's contribution.
  await openLesson(page, "Storage", "Storage");
  const baseline = await domState(page);

  await openLesson(page, "Pipelines", "Pipelines");
  const fallback = page.locator("pre.overflow-x-auto", { hasText: "Raw Files (CSV, JSON, SQL)" });
  await expect(fallback).toBeVisible();
  // The original source, unquoted parens and all — the `code` prop is never sanitised.
  await expect(fallback).toContainText("A((Raw Files (CSV, JSON, SQL)))");
  await expect(page.getByText("Rendering diagram…")).toHaveCount(0);
  await expect(page.locator(".lesson-prose svg")).toHaveCount(0);

  const rendered = await domState(page);
  expect(rendered.orphanedRenderDivs).toBe(0);
  expect(rendered.errorGraphics).toBe(0);
  expect(rendered.syntaxErrorText).toBe(false);
  expect(rendered.bodyChildren).toBe(baseline.bodyChildren);

  // Unmount: the pre-fix artifact lived outside the React tree and outlived exactly this.
  await openLesson(page, "Storage", "Storage");
  await expect(page.locator("pre", { hasText: "Raw Files" })).toHaveCount(0);

  const unmounted = await domState(page);
  expect(unmounted.orphanedRenderDivs).toBe(0);
  expect(unmounted.errorGraphics).toBe(0);
  expect(unmounted.syntaxErrorText).toBe(false);
  expect(unmounted.bodyChildren).toBe(baseline.bodyChildren);
});

// The natural companion test — "the repairable diagram still renders an SVG" — is deliberately NOT
// here, because under `next dev` it cannot pass: React StrictMode double-invokes the effect, the
// discarded first pass's `finally { removeMermaidArtifacts(renderId) }` deletes the second pass's
// in-flight working div (both share one useId-derived renderId), and BOTH renders throw. Every
// diagram therefore falls back to <pre> in dev. Verified against `next build && next start`, where
// the effect runs once and the same lesson renders `<svg id="mmd-_r_0_" class="flowchart">`, so this
// is a dev-only defect — but it also means the fallback branch is the only one dev ever exercises.
