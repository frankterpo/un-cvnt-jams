# un-cvnt-jams — Instagram upload: human-in-the-loop login + forensic logging (Codex master prompt)

You are an autonomous coding agent operating inside the repo. Implement a robust, human-in-the-loop (HITL) workflow for Instagram uploads on an EC2 instance running via SSM, with strong forensic logging and repeatable run artifacts.

## Context
- Current flow: `scripts/test_instagram_upload.py` uses `src/tools/instagram_client.py` + `src/tools/instagram_browser.py` (Selenium + Chrome) to upload reels.
- Fail mode: `InstagramNotLoggedInError: Instagram profile is not logged in`. Debug HTML showed `userId: 0` / empty account keys → logged out.
- We **do not** assume headless automation can solve Instagram checkpoints/captcha; we **optimize for HITL**: a human can jump in, clear blockers, and then automation continues.

## Goals (must deliver)
1. **Per-run artifact directory**
   - Every run writes all artifacts under: `/tmp/ig_runs/<RUN_ID>/`
   - At minimum create:
     - `run.log` (full stdout/stderr stream)
     - `steps.jsonl` (one JSON object per step, includes timestamp + step name + URL + status)
     - `debug_<tag>.html` (HTML snapshots at key checkpoints)
     - `debug_<tag>.png` (screenshots at key checkpoints)
     - `chromedriver.log` (chromedriver logs)
     - `chrome.log` (Chrome logs if possible)
     - `env.json` (sanitized env: headless flag, profile dir, video path basename, run id)

2. **Better structured logging**
   - Always log step boundaries:
     - driver creation
     - navigation to IG
     - cookie consent / modal handling
     - login check result
     - beginning upload flow, each major click/page transition
     - publish/finish confirmation OR final failure
   - When failing, log:
     - `driver.current_url`, page `title`
     - a short classification string: `LOGIN_PAGE`, `CHECKPOINT`, `CHALLENGE`, `CAPTCHA`, `UNKNOWN`, etc.
     - write HTML + screenshot to the artifact dir.

3. **HITL login bootstrap (Option A)**
   - If not logged in, do **not** just fail.
   - If `IG_INTERACTIVE_LOGIN=true` (or CLI `--interactive-login`), launch a dedicated Chrome session that a human can operate via **Chrome DevTools Protocol (CDP) + screencast** over SSM port-forwarding.
   - Print exact operator instructions to the log:
     - how to open a port forward from local machine
     - URL to open locally (`http://127.0.0.1:<localPort>`)
     - where to click "inspect" and how to enable "Show Screencast"
   - Then **wait/poll** until login is detected, for up to `IG_INTERACTIVE_TIMEOUT_SECS` (default 900).
   - Once logged in, proceed with the normal upload flow.

   Notes:
   - Use the **same** `--user-data-dir` profile directory so cookies persist.
   - Avoid leaving the CDP Chrome process running forever; ensure it is terminated on success/timeout.

4. **Operator-friendly run wrapper**
   - Add a script: `scripts/run_instagram_upload_run.sh`
   - Responsibilities:
     - hard reset (kill chrome/chromedriver/old python; remove SingletonLock/Socket/Cookie; fix ownership)
     - create RUN_ID + artifact dir
     - export `IG_RUN_ID` and `IG_DEBUG_DIR`
     - run `scripts/test_instagram_upload.py` with `tee` into `/tmp/ig_runs/<RUN_ID>/run.log`
     - on exit, write a final `summary.json` with rc + runtime + last step
     - optional: zip artifacts into `/tmp/ig_runs/<RUN_ID>.zip`

5. **SSM visibility improvements**
   - Provide an additional script: `scripts/ssm_send_instagram_run.sh` that can be executed locally (mac/linux)
     - Uses `aws ssm send-command` with **CloudWatch output enabled** (use `--cloud-watch-output-config`).
     - Prints the CommandId and a helper command to tail CloudWatch logs OR to fetch invocation output.
   - Ensure shell quoting is robust (no syntax errors due to parentheses/quotes).
   - Avoid leaking secrets in stdout.

## Implementation plan (follow, but adapt as needed)
### A) Config plumbing
- Extend Instagram config object (wherever it lives) to include:
  - `run_id: str`
  - `debug_dir: str`
  - `interactive_login: bool`
  - `interactive_timeout_secs: int`
  - `cdp_port: int` (default 9222, but allow override)
- Plumb from env:
  - `IG_RUN_ID`, `IG_DEBUG_DIR`
  - `IG_INTERACTIVE_LOGIN` (true/false)
  - `IG_INTERACTIVE_TIMEOUT_SECS` (int)
  - `IG_CDP_PORT` (int)

### B) Browser build logging
In `src/tools/instagram_browser.py` (or equivalent):
- Enable chromedriver logging into `debug_dir/chromedriver.log` (Selenium Service log output).
- Enable chrome logging into `debug_dir/chrome.log` (Chrome `--enable-logging` + `--log-file`).
- Ensure all paths are writable by `ec2-user`.
- Log the final resolved chrome args (redact sensitive paths if needed).

### C) Client step artifacts
In `src/tools/instagram_client.py`:
- Add helper:
  - `write_step(step, status, extra={})` → append JSON line to `steps.jsonl`
  - `_dump(tag)` → write html+screenshot to debug_dir with unique tag and timestamp
  - `_classify_page(html, url)` → returns enum/string (LOGIN_PAGE/CHECKPOINT/etc.)
- At each key step call `write_step(...)` and `_dump(...)` on failure.

### D) HITL login helper
Add `src/tools/instagram_hitl.py` (new) OR implement inside client:
- `start_cdp_login_chrome(profile_dir, debug_dir, cdp_port) -> pid`
  - launch `google-chrome --headless=new --remote-debugging-address=127.0.0.1 --remote-debugging-port=<port> --user-data-dir=<profile_dir> https://www.instagram.com/`
  - redirect stdout/stderr to `debug_dir/cdp_chrome.out` / `debug_dir/cdp_chrome.err`
- `wait_for_login(check_fn, timeout_secs)`:
  - poll every 5-10 seconds; re-check login using a lightweight selenium driver OR a simple cookie heuristic.
- `stop_process(pid)` always in finally.

### E) CLI improvements
Update `scripts/test_instagram_upload.py`:
- Accept optional flags:
  - `--debug-dir`
  - `--run-id`
  - `--interactive-login`
  - `--interactive-timeout-secs`
  - `--cdp-port`
- Ensure config resolution logs include these values.

## Acceptance criteria (must satisfy)
- Running `scripts/run_instagram_upload_run.sh` on the EC2 instance produces a populated `/tmp/ig_runs/<RUN_ID>/` with logs and artifacts even on failure.
- If profile is logged out AND `IG_INTERACTIVE_LOGIN=true`, the script does **not** immediately fail; it starts CDP login flow and waits.
- If the operator logs in during the wait, the script continues and reaches the upload step.
- No more opaque “InProgress” only: logs show continuous progress via `run.log` + `steps.jsonl`.
- All new scripts are executable (`chmod +x`), shellcheck-ish clean, and safe quoting.
- Add/update minimal docs in `docs/instagram_hitl.md` (create if missing).

## Tests / validation (run these)
1. Lint / import check:
   - `python -m compileall src scripts`
2. Unit-ish smoke (no IG):
   - run a small function test that creates debug_dir and writes a dump without exception.
3. On EC2 (manual):
   - `scripts/run_instagram_upload_run.sh --video ... --caption ... --profile-dir ... --post-type reel --interactive-login`
   - Verify artifact dir and the CDP instructions printed.

## Deliverables
- Code changes + new scripts + new doc.
- Commit with message: `ig: add HITL login + forensic logging`.
