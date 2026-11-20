# TASK-261120-kot99z: cli-wake-routes-all-runtimes

## Description
a2a CLI: identity ensure finishes with a working wake route on every runtime. Pi and Antigravity get a CLI-generated supervised sidecar with PID and log plus a bind record. bind status shows route and last qualification.

## Scope
After a2a-swarm 532, extend ensure and bind to pi and antigravity without hand-made sidecars.

## Acceptance Criteria
Idle Pi and Antigravity lanes wake from an event and run a2a inbox unaided; bind status proves the route.
