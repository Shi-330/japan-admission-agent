export const meta = {
  name: 'jp-agent-sprint-builder',
  description: 'Spec -> Build -> Evaluate loop for JP Admission Agent sprints. Pass the task via args (string); Plan phase only runs when no task is given.',
  phases: [
    { title: 'Plan', detail: 'Only when no task given: read codebase, produce sprint plan' },
    { title: 'Spec', detail: 'Write component-level spec for the task' },
    { title: 'Build', detail: 'Implement in an isolated worktree, build frontend for eval' },
    { title: 'Evaluate', detail: 'Serve the worktree on :8100, Playwright test, critique' },
  ],
};

// ── Config ──
const REPO = 'C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent';
const MAX_RETRIES = 3;          // retry cap per sprint
const PASS_THRESHOLD = 80;      // score >= 80 -> pass
const EVAL_PORT = 8100;         // eval server port — NEVER the long-running :8000
const EVAL_URL = `http://localhost:${EVAL_PORT}`;
const VENV_PY = `${REPO}/venv/Scripts/python.exe`;

// Injected into every agent prompt. The 2026-07-16 incident: a rollback agent ran
// git checkout/reset in the main working copy and clobbered the user's branch.
const SAFETY = `HARD RULES:
- NEVER run git checkout / git reset / git clean / git stash / git branch -D inside ${REPO} (the user's main working copy). All build work happens ONLY inside the assigned worktree directory.
- NEVER push to any remote. Commits stay on the worktree branch; the user merges manually.
- No emoji in any UI strings, spec text, or critique output.`;

// ── Resolve task list: direct task via args skips the Plan phase entirely ──
const directTask = typeof args === 'string' ? args.trim() : ((args && args.task) || '');
let sprints;

if (directTask) {
  log(`Direct task mode (Plan phase skipped): ${directTask}`);
  sprints = [{ title: directTask, scope: directTask, priority: 'P0' }];
} else {
  phase('Plan');
  const planResult = await agent(
    `Read the Japan Admission Agent codebase at ${REPO}.
    High-level goal: ${(args && args.goal) || 'Improve the user-facing chat and application tracking experience'}.

    Follow the instructions in .claude/workflows/planner.md.
    Write the plan to specs/sprint-plan.md.
    ${SAFETY}`,
    { label: 'planner', schema: {
      type: 'object',
      properties: { sprints: { type: 'array', items: { type: 'object', properties: { title: {type:'string'}, scope: {type:'string'}, deliverables: {type:'string'}, acceptance_criteria: {type:'string'}, priority: {type:'string'} }, required:['title','scope','deliverables','acceptance_criteria'] } } },
      required: ['sprints']
    }}
  );
  if (!planResult) { log('Planner failed'); return; }
  sprints = planResult.sprints;
  log(`Sprint plan created: ${sprints.length} sprints`);
}

// ── For each sprint: Spec -> Build -> Evaluate loop ──
const results = [];
for (const sprint of sprints) {
  const sprintName = sprint.title;
  log(`Sprint: ${sprintName} (${sprint.priority || 'P0'})`);

  // ── Spec ──
  phase('Spec');
  const specResult = await agent(
    `Task: ${sprintName}
    Scope: ${sprint.scope || sprintName}
    ${sprint.deliverables ? 'Deliverables: ' + sprint.deliverables : ''}

    Read the relevant code at ${REPO}. If a spec for this exact task already exists in specs/ (check by content, e.g. specs/feature-schema.md), reuse it and return its path instead of writing a new one.
    Otherwise follow .claude/workflows/spec-writer.md and write a new spec. Pick the next UNUSED filename specs/feature-<n>.md — list existing specs first, never overwrite one.
    Every acceptance criterion must be Playwright-testable against a running app at ${EVAL_URL}.
    LIMIT: at most 10 acceptance criteria — pick the ones that prove the feature works, not exhaustive UI coverage. Prefer API-checkable criteria over browser-interaction ones where possible (they evaluate much faster).
    Return the spec path as spec_path.
    ${SAFETY}`,
    { label: 'spec', schema: { type: 'object', properties: { spec_path: { type: 'string' } }, required: ['spec_path'] } }
  );
  if (!specResult) { log(`Spec failed for ${sprintName}`); continue; }
  const SPEC = specResult.spec_path;
  const critiquePath = `critiques/critique-${(SPEC.match(/feature-([\w.-]+)\.md/) || [,'current'])[1]}.md`;
  log(`Spec: ${SPEC}`);

  // ── Build -> Evaluate loop (first build creates the worktree, retries reuse it) ──
  let passed = false;
  let worktree = null;
  let branch = null;
  for (let retry = 1; retry <= MAX_RETRIES; retry++) {
    phase('Build');
    const buildResult = retry === 1
      ? await agent(
          `Read ${SPEC} (path relative to ${REPO}).
          Follow .claude/workflows/builder.md to implement ALL components and endpoints.
          You are in an isolated git worktree. Steps after implementing:
          1. Copy ${REPO}/.env and ${REPO}/frontend/.env into the same relative locations in the worktree (they are untracked, the worktree does not have them).
          2. In the worktree's frontend/: if node_modules is missing, run npm install. Then build with the eval API base so the SPA calls the eval server, not :8000 — PowerShell: $env:VITE_API_URL='${EVAL_URL}'; npm run build
          3. Commit all changes on the worktree branch (do not push).
          Return worktree_path (absolute path of your worktree) and branch (current branch name).
          ${SAFETY}`,
          { label: 'build', isolation: 'worktree', schema: { type: 'object', properties: { worktree_path: { type: 'string' }, branch: { type: 'string' }, summary: { type: 'string' } }, required: ['worktree_path', 'branch'] } }
        )
      : await agent(
          `Work INSIDE the existing worktree at ${worktree} (cd there; do NOT create a new worktree, do NOT touch ${REPO} itself).
          Read ${REPO}/${critiquePath} — this is retry #${retry}. Fix EVERY issue at the exact file:line.
          Then rebuild the frontend the same way ($env:VITE_API_URL='${EVAL_URL}'; npm run build) and commit on the worktree branch.
          ${SAFETY}`,
          { label: `fix-r${retry}`, schema: { type: 'object', properties: { summary: { type: 'string' } }, required: ['summary'] } }
        );

    if (!buildResult) { log(`Build failed on attempt ${retry}`); break; }
    if (retry === 1) { worktree = buildResult.worktree_path; branch = buildResult.branch; }
    log(`Build complete (attempt ${retry}), worktree: ${worktree}`);

    // ── Evaluate: serve the WORKTREE code, never the long-running :8000 server ──
    phase('Evaluate');
    const evalResult = await agent(
      `You are evaluating the build in the worktree at ${worktree}. Steps:
      1. Start the app FROM THE WORKTREE (this is critical — :8000 runs old code and must not be tested):
         Set-Location ${worktree}; then start in background and record the PID. Start it in a VISIBLE console window (default Start-Process behavior, do NOT use -WindowStyle Hidden) — the user wants to see the eval server running:
         Start-Process -FilePath "${VENV_PY}" -ArgumentList "-m","uvicorn","backend.api.server:app","--port","${EVAL_PORT}" -PassThru
         Poll ${EVAL_URL}/health until it returns healthy (max 30s). If it never comes up, report score 0 with the startup error as the failure.
      2. Read ${SPEC} for acceptance criteria.
      3. Follow .claude/workflows/evaluator.md — use ONLY Playwright/Browser against ${EVAL_URL}, NEVER read code.
      4. Write ${REPO}/${critiquePath} with pass/fail for each criterion and a numerical score. Score format: "Score: X/100".
      5. ALWAYS Stop-Process the uvicorn you started before finishing, even on failure.
      ${SAFETY}`,
      { label: `eval-r${retry}`, schema: {
        type: 'object',
        properties: {
          total: { type: 'number' },
          passed: { type: 'number' },
          failed: { type: 'number' },
          score: { type: 'number' },
          failures: { type: 'array', items: { type: 'object', properties: { criterion: {type:'string'}, expected: {type:'string'}, actual: {type:'string'}, reproduction: {type:'string'} }, required:['criterion','expected','actual'] } }
        },
        required: ['total', 'passed', 'failed', 'score']
      }}
    );

    if (!evalResult) { log('Evaluation failed'); break; }
    log(`Score: ${evalResult.score}/100 (${evalResult.passed}/${evalResult.total} passed)`);

    if (evalResult.score >= PASS_THRESHOLD) {
      // No auto-push, no auto-merge: work stays committed on the worktree branch for the user to review.
      log(`Sprint "${sprintName}" PASSED at ${evalResult.score}/100. Review and merge branch "${branch}" (worktree: ${worktree}).`);
      passed = true;
      results.push({ task: sprintName, score: evalResult.score, branch, worktree, spec: SPEC, critique: critiquePath });
      break;
    }
    log(`Score ${evalResult.score} < ${PASS_THRESHOLD}, retrying (${retry}/${MAX_RETRIES})`);
  }

  if (!passed) {
    // No rollback agent: the main checkout was never touched, so there is nothing to roll back.
    // Keep the worktree for inspection instead of destroying evidence.
    log(`Sprint "${sprintName}" FAILED after ${MAX_RETRIES} attempts. Worktree kept for inspection: ${worktree || 'n/a'} (branch: ${branch || 'n/a'}). Main checkout untouched.`);
    results.push({ task: sprintName, score: 0, branch, worktree, spec: SPEC, critique: critiquePath });
  }

  if (budget.total && budget.remaining() < 50000) { log('Budget low, stopping.'); break; }
}

log('Workflow complete. Nothing was merged or pushed — review the branches listed above.');
return results;
