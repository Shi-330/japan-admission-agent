export const meta = {
  name: 'jp-agent-sprint-builder',
  description: 'Planner → Spec → Builder → Evaluator loop for JP Admission Agent sprints',
  phases: [
    { title: 'Plan', detail: 'Read codebase, produce sprint plan' },
    { title: 'Spec', detail: 'Write component-level specs for each sprint' },
    { title: 'Build', detail: 'Implement sprints in worktree' },
    { title: 'Evaluate', detail: 'Playwright browser testing, critique output' },
  ],
};

// ── Config ──
const REPO = 'C:/Users/86158/Documents/PythonProject/Japan-Admission-Agent';
const MAX_RETRIES = 3;          // retry cap per sprint
const PASS_THRESHOLD = 80;      // score >= 80 → pass
const APP_URL = 'http://localhost:8000';

// ── Phase 1: Plan ──
phase('Plan');

const planResult = await agent(
  `Read the Japan Admission Agent codebase at ${REPO}.
  High-level goal: ${args.goal || 'Improve the user-facing chat and application tracking experience'}.

  Follow the instructions in .claude/workflows/planner.md.
  Write the plan to specs/sprint-plan.md.`,
  { label: 'planner', schema: {
    type: 'object',
    properties: { sprints: { type: 'array', items: { type: 'object', properties: { title: {type:'string'}, scope: {type:'string'}, deliverables: {type:'string'}, acceptance_criteria: {type:'string'}, priority: {type:'string'} }, required:['title','scope','deliverables','acceptance_criteria'] } } },
    required: ['sprints']
  }}
);

if (!planResult) { log('❌ Planner failed'); return; }
log(`✅ Sprint plan created: ${planResult.sprints.length} sprints`);

// ── Phase 2-4: For each sprint, Spec → Build → Evaluate loop ──
for (const sprint of planResult.sprints) {
  const sprintName = sprint.title;
  log(`\n🏃 Sprint: ${sprintName} (${sprint.priority})`);

  // ── Phase 2: Spec ──
  phase('Spec');
  const featureIndex = planResult.sprints.indexOf(sprint) + 1;
  const specResult = await agent(
    `Read specs/sprint-plan.md and find "${sprintName}".
    Read the relevant code referenced in this sprint's scope at ${REPO}.
    Follow .claude/workflows/spec-writer.md to write specs/feature-${featureIndex}.md.
    Every acceptance criterion must be Playwright-testable.`,
    { label: `spec:${featureIndex}` }
  );
  if (!specResult) { log(`❌ Spec failed for ${sprintName}`); continue; }
  log(`✅ Spec written: specs/feature-${featureIndex}.md`);

  // ── Phase 3-4: Build → Evaluate loop ──
  let passed = false;
  for (let retry = 1; retry <= MAX_RETRIES; retry++) {
    // ── Phase 3: Build ──
    phase('Build');
    const buildLabel = retry === 1 ? `build:${featureIndex}` : `fix:${featureIndex}-r${retry}`;
    const buildResult = await agent(
      retry === 1
        ? `Read specs/feature-${featureIndex}.md.
           Follow .claude/workflows/builder.md to implement ALL components and API endpoints.
           Write specs/feature-${featureIndex}-DONE.md after completion.`
        : `Read critiques/critique-${featureIndex}.md — this is retry #${retry}.
           Follow .claude/workflows/builder.md to fix EVERY issue at the exact file:line.
           Write critiques/critique-${featureIndex}-FIXED.md after fixing.`,
      { label: buildLabel, isolation: 'worktree' }
    );

    if (!buildResult) { log(`❌ Build failed on retry ${retry}`); break; }
    log(`✅ Build complete (retry ${retry})`);

    // ── Phase 4: Evaluate ──
    phase('Evaluate');
    const evalResult = await agent(
      `Read specs/feature-${featureIndex}.md for acceptance criteria.
      The app should be running at ${APP_URL}.
      Follow .claude/workflows/evaluator.md — use ONLY Playwright/Browser, NEVER read code.
      Write critiques/critique-${featureIndex}.md with pass/fail for each criterion and a numerical score.
      Score format: "Score: X/100".`,
      { label: `eval:${featureIndex}-r${retry}`, schema: {
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

    if (!evalResult) { log(`❌ Evaluation failed`); break; }

    log(`📊 Score: ${evalResult.score}/100 (${evalResult.passed}/${evalResult.total} passed, ${evalResult.failed} failed)`);

    if (evalResult.score >= PASS_THRESHOLD) {
      log(`✅ Sprint "${sprintName}" PASSED!`);
      passed = true;
      break;
    }

    log(`🔄 Score ${evalResult.score} < ${PASS_THRESHOLD}, retrying... (${retry}/${MAX_RETRIES})`);
  }

  if (!passed) {
    log(`⚠️  Sprint "${sprintName}" needs manual review (${MAX_RETRIES} retries exhausted)`);
    if (budget.total && budget.remaining() < 50000) {
      log('💸 Budget running low, stopping.');
      break;
    }
  }
}

log('\n🏁 Workflow complete. Check specs/ and critiques/ for details.');
