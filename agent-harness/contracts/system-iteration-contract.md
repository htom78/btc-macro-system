# System Iteration Contract

Use this contract whenever an agent modifies the public research system, adds a
new monitoring page, updates an investment-thesis module, or changes deployment
behavior.

## Goal

The system should become more useful, more observable, and easier for the next
agent to continue. A change is not complete merely because a page renders.

## Required Done Criteria

1. **Map updated**
   - New first-class routes are reachable from `home.html`.
   - New public artifacts are included in `tools/build_pages_site.sh`.
   - The relevant README or harness file explains the new source of truth.

2. **Data contract preserved**
   - Public JSON used by pages remains valid.
   - Generated pages can read their local/Pages data paths.
   - Private local data has a public fallback when CI cannot access it.

3. **Research contract preserved**
   - Investment analysis separates facts, estimates, and inferences.
   - Thesis pages keep: cash-flow floor, platform transition, optionality,
     competition vectors, falsification triggers, and monitoring cadence.
   - Market-temperature pages keep: capital-cycle stage, observable variables,
     and what would move the stage colder or hotter.

4. **Judge run**
   - Run `bash agent-harness/scripts/run_harness.sh` for broad changes.
   - For narrow content-only changes, run the smallest validator that proves the
     modified surface.

5. **Evidence reported**
   - Final response should mention changed files, commands run, and any residual
     risk or skipped verification.

## Failure Loop

When a validator fails:

1. Read the exact failure.
2. Fix the source of truth, not just the generated `_site` artifact.
3. Rebuild `_site`.
4. Rerun the failed validator and the link check.
5. If the same blocker repeats three times, stop and report the blocker clearly.
