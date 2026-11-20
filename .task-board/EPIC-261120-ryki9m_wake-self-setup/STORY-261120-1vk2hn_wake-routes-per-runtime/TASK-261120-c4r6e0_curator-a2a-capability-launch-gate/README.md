# TASK-261120-c4r6e0: curator-a2a-capability-launch-gate

## Description
Curator: the a2a capability in a profile declares the wake route per runtime. The launcher performs ensure and bind, then idle qualification before reporting a lane ready; a deaf lane reports degraded.

## Scope
Curator and curator-run own launch composition and qualification; profile carries identity and route intent.

## Acceptance Criteria
curator run reports ready only after qualification; failure is visible as degraded with the exact route blocker.
