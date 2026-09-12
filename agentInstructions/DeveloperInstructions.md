# Developer Instructions

## 1. Before Starting
- Inspect the environment first: list files, read existing code, identify the stack.
- Anchor file paths to the script: `BASE_DIR = os.path.dirname(os.path.abspath(__file__))`
- Never modify files outside the allowed scope.
- Before starting any server, kill the port occupant:
  `lsof -t -i:<PORT> | xargs -r kill -9`

## 2. File Operations
- `Read` before `Edit`. Never `Create` on an existing file.
- Verify important files after writing.

## 3. Shell Rules
- Servers MUST run in background:
  `nohup <cmd> > /tmp/<name>.log 2>&1 &` then `sleep 2` then read log.
- Never run a blocking server in the foreground.
- Never retry the same failing command more than twice.

## 4. Verification Protocol (Mandatory)
1. Rewrite task as numbered testable requirements.
2. For each: run a concrete test, paste RAW output.
3. Status per requirement: VERIFIED / UNVERIFIED / FAILED.
4. Never write "all tests passed" without pasted evidence.
5. Cancelled/timeout/errored tool calls are NOT passes.

## 5. Common Pitfalls
- No template syntax (`{{ }}`) in static assets.
- Flask endpoint = function name, not URL path.
- Every template variable must be passed to render_template.
- dict has `.items()`, not `.items.items`.
- `unique('field')` on list of dicts raises TypeError.
- Session keys are strings.
- Disable dev-server reloader under an agent (Flask: `debug=False`).

## 6. Error Recovery
Read error → find cause → smallest fix → re-run exact command. Report honestly if unresolved.

## 7. Final Report
For each requirement: status + command + raw output. List limitations. Give run instructions.

## 8. Never Do
- Claim success without pasted evidence.
- Call a cancelled test a pass.
- Modify files outside scope.
- Leave a foreground server.
- Put template syntax in static files.

## 9. Tone
Concise, factual. An honest incomplete report beats a confident wrong one.
