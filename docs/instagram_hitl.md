# Instagram HITL (EC2 + SSM + CDP Screencast)

This repo treats Instagram authentication as human-in-the-loop (HITL). If the
persisted Chrome profile is logged out, automation should not attempt to bypass
checkpoints/captcha/2FA headlessly; instead it should pause and guide an
operator to complete login via DevTools screencast over SSM port-forwarding.

Security:
- Do not paste full HTML dumps into chat.
- Do not print cookies, session tokens, or secret env vars.

## Run artifacts
Each run writes artifacts under:

`/tmp/ig_runs/<RUN_ID>/`

Minimum expected files:
- `run.log` (full stdout/stderr stream from the run)
- `steps.jsonl` (JSON per step with ts/step/status/url)
- `env.json` (sanitized env summary)
- `debug_<tag>_<ts>.html` + `debug_<tag>_<ts>.png` (snapshots)
- `chromedriver.log`
- `chrome.log` (if Chrome supports file logging)

## Recommended EC2 execution
On the instance:

`/home/ec2-user/un-cvnt-jams/scripts/run_instagram_upload_run.sh --video ... --caption ... --profile-dir ... --post-type reel --interactive-login`

This wrapper:
- creates `RUN_ID` + debug dir
- exports `IG_RUN_ID`, `IG_DEBUG_DIR`
- enables interactive login if requested
- tees output to `run.log` and writes `summary.json` on exit

## Interactive login (CDP + screencast)
When interactive login is required, the run prints operator instructions, including:
- an `aws ssm start-session` port-forward command (use your instance id)
- the local URL to open: `http://127.0.0.1:<CDP_PORT>`
- how to enable DevTools “Show Screencast”

After the operator completes login/checkpoint, the run detects the authenticated
session (best-effort heuristic) and resumes the upload flow.

## CloudWatch output (send-command)
For long runs, prefer CloudWatch streaming output via:

`scripts/ssm_send_instagram_run.sh`

It sends a single SSM command with CloudWatch output enabled, prints the
CommandId, and provides helper commands to fetch invocation output or tail
CloudWatch logs.

