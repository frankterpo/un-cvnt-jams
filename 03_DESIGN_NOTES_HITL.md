# Design notes — why HITL + DevTools screencast is the lightweight solution

## Why we do not “just log in headless”
Instagram aggressively defends authentication:
- checkpoints, challenges, 2FA
- bot heuristics
- cookie consent overlays
- intermittent blocks that require human confirmation

Any attempt to solve this purely via automation is brittle. The durable approach is:
- keep automation for the deterministic parts (upload UI flow)
- insert **human-in-the-loop** only when the site demands it

## Why CDP + Screencast over SSM
Compared to VNC/noVNC/X11:
- no extra server stack
- no exposed public ports
- uses SSM port-forwarding (works behind private subnets)
- fast to launch and tear down
- enough UX for login and checkpoints

## Recommended operational pattern
1) Automation starts headless with the persisted Chrome profile dir.
2) If not logged in:
   - launch CDP chrome (still headless) bound to 127.0.0.1
   - instruct operator to port-forward and open screencast
   - wait until login detected
   - terminate CDP chrome
3) Resume upload flow.

## Forensics-first
Every run must leave behind:
- `run.log` + `steps.jsonl`
- HTML + screenshot dumps at the exact moment of failure
- chromedriver + chrome logs

This means “no more InProgress guessing”: you always have artifacts.
