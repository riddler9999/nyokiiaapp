# CLAUDE.md

## Project: SMC Sniper Agent

Crypto futures analysis + auto-execution agent running in n8n Code nodes (JavaScript).

## Architecture

Read `smc-sniper-agent-spec.md` for the full architecture spec before writing any code.

## Rules

- Language: JavaScript (for n8n Code node compatibility)
- All modules must be pure functions: input data object → output scored object
- Never use external npm packages that aren't available in n8n Code nodes
- Use `$helpers.httpRequest` for API calls inside n8n, but write modules as standalone testable functions
- Every module returns `null` on error, never throws
- All thresholds come from `CONFIG` object, never hardcoded
- Follow the exact output schemas defined in the spec
- Write unit tests for each module using simple assert patterns

## File Structure

```
/modules/       - One file per module (dataLayer.js, structure.js, etc.)
/utils/         - Shared helpers (indicators.js, swingDetector.js, binanceApi.js)
/tests/         - Test files mirroring module structure
/config.js      - All tunable parameters
/main.js        - Orchestrator
```
