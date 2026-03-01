# /release-tools — Commit, PR, and Docker release for a tool batch

Run this after implementing a batch of MCP tools and completing manual smoke tests.
Handles the full release pipeline: commit → push → PR → (wait for merge) → docker push.

## Argument

$ARGUMENTS should contain the issue numbers being closed (e.g., `#45 #44 #37 #43 #20 #19 #51`).
If empty, detect them from the branch diff against main.

## Step 1: Pre-flight checks

1. Run `~/.local/bin/uv run pytest` — abort if any test fails.
2. Run `git status` and `git diff --stat main...HEAD` to verify changes look right.
3. Count the new tools by diffing `test_server_startup.py` tool count vs main.
4. Summarize what's about to be released (tool names, issue numbers, test count change).
5. **Ask the user to confirm** before proceeding.

## Step 2: Commit

Stage all changed files (be specific — don't use `git add -A`). Create a single commit following this project's established style:

```
feat: add N P<tier> MCP tools including <notable_tool>

Implements all P<tier> priority tools:

<category>:
- tool_name (#issue) — one-line description
...

<test_count_before> → <test_count_after> tests passing, tool count <old> → <new>.

Closes #N, Closes #N, ...

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Group tools by category (activity-detail, health-biometrics, fitness-performance, workouts-plans).
Get the old test/tool counts from main's `test_server_startup.py`.

## Step 3: Push and create PR

1. Push the feature branch: `git push -u origin <branch-name>`
2. Create a PR with `gh pr create`. Title format: short, under 70 chars. Body format:

```
## Summary
- <bullet per tool group>
- Test count: X → Y, tool count: X → Y

## Test plan
- [x] All N tests pass (`uv run pytest`)
- [ ] Manual smoke test against live Garmin account
- [ ] Docker build and push after merge

Closes #N, Closes #N, ...

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

3. Print the PR URL.

## Step 4: Docker build and push (post-merge)

**Ask the user**: "PR created. Merge it on GitHub, then tell me when ready for the Docker push."

Once confirmed:

1. `git checkout main && git pull origin main`
2. Run the Docker buildx command (MUST use buildx with platform flag — Apple Silicon produces arm64 otherwise, Unraid needs amd64):
   ```
   docker buildx build --platform linux/amd64 --push -t paulmon/garmin-connect-mcp:latest .
   ```
3. Confirm the push succeeded.

## Step 5: Update memory

Update the memory files in `~/.claude/projects/-Users-pmonaghan-src-GarminClaudeSync/memory/`:
- `MEMORY.md`: update test count and tool count
- `enhancement-backlog.md`: mark the issues as closed
- `p2-implementation.md` (or relevant tier file): mark status as RELEASED
