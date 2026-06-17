import { type Page, expect, test } from "@playwright/test";

// A 2-node path: 'a' (root, available) → 'b' (locked behind a). Mutated in place across mock calls so
// grading 'a' makes it mastered and 'b' unlocks — exercising the full adaptive loop in the UI.
function makeSession() {
  return {
    skill_graph: {
      summary: "Learn Python",
      nodes: [
        { id: "a", label: "Python Basics", description: "vars", level: "foundational" },
        { id: "b", label: "Data Structures", description: "lists", level: "intermediate" },
      ],
      edges: [{ source: "a", target: "b", relation: "prerequisite" }],
    },
    summary: "Learn Python",
    node_state: {
      a: { status: "available", best_score: 0, attempts: 0, weaknesses: [], last_feedback: null },
      b: { status: "available", best_score: 0, attempts: 0, weaknesses: [], last_feedback: null },
    },
    lessons: {} as Record<string, unknown>,
    selected_node: null as string | null,
    format_type: "B",
  };
}

async function mockApi(page: Page) {
  const ls = makeSession();
  const sid = "sess1";

  await page.route("**/sessions", async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ json: { route: "SCOUT", session_id: sid, learning_session: ls } });
    }
    return route.fallback();
  });

  await page.route("**/sessions/*", async (route) => {
    // GET /sessions/{user} → list
    return route.fulfill({ json: [{ session_id: sid, title: "Learn Python", updated_at: null }] });
  });

  await page.route(`**/sessions/*/${sid}`, async (route) => {
    return route.fulfill({ json: { session_id: sid, learning_session: ls } });
  });

  await page.route(`**/sessions/*/${sid}/lessons/a`, async (route) => {
    ls.lessons.a = {
      content: "# Python Basics\nVariables hold values.",
      exercise: {
        format: "coding_challenge",
        statement: "Write `add(a, b)`.",
        grading_artifact: { format: "coding_challenge", unit_tests: [] },
      },
    };
    ls.selected_node = "a";
    return route.fulfill({ json: { session_id: sid, learning_session: ls } });
  });

  await page.route(`**/sessions/*/${sid}/lessons/b`, async (route) => {
    return route.fulfill({ status: 409, json: { detail: { error: "locked", pending: ["Python Basics"] } } });
  });

  await page.route(`**/sessions/*/${sid}/grade**`, async (route) => {
    ls.node_state.a = { ...ls.node_state.a, status: "mastered", best_score: 100, attempts: 1,
      last_feedback: { score: 100, passed: 1, total: 1 } };
    return route.fulfill({ json: { session_id: sid, learning_session: ls } });
  });
}

test("full loop: login → graph → lesson → grade → mastery", async ({ page }) => {
  await mockApi(page);

  await page.goto("/");
  await page.getByLabel("Email").fill("e2e@test.com");
  await page.getByRole("button", { name: "Enter" }).click();

  // Dashboard → start a path
  await page.getByLabel("What do you want to learn?").fill("Learn Python");
  await page.getByRole("button", { name: "Generate" }).click();

  // Lands on the session page; the mastery counter starts at 0/2.
  await expect(page.getByText("skills complete")).toBeVisible();
  await expect(page.getByText("/2")).toBeVisible();

  // Open the root node's lesson.
  await page.getByText("Python Basics").first().click();
  // The lesson leads with the markdown's own h1 (the panel no longer renders a duplicate title).
  await expect(page.getByRole("heading", { name: "Python Basics", level: 1 })).toBeVisible();
  await expect(page.getByText("Variables hold values.")).toBeVisible();

  // Grade a (mocked perfect score) → node becomes complete, counter ticks to 1/2.
  // Monaco's real input is .inputarea; click the editor then type so onChange enables the button.
  await page.locator(".monaco-editor").first().click();
  await page.keyboard.type("def add(a,b): return a+b");
  await page.getByRole("button", { name: "Grade my submission" }).click();
  await expect(page.getByText("100%")).toBeVisible();
  await expect(page.getByText("1/2")).toBeVisible();
});

test("locked node shows a lock message", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByLabel("Email").fill("e2e@test.com");
  await page.getByRole("button", { name: "Enter" }).click();
  await page.getByLabel("What do you want to learn?").fill("Learn Python");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("skills complete")).toBeVisible();

  // 'Data Structures' is locked behind 'Python Basics'.
  await page.getByText("Data Structures").first().click();
  await expect(page.getByText(/Locked — first complete: Python Basics/)).toBeVisible();
});
