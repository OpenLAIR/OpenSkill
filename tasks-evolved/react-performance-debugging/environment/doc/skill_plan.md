# Skill Creation Plan

**Task**: Diagnose and fix performance issues in a slow Next.js e-commerce app focusing on API route optimization, bundle size reduction, and excessive re-rendering

**Rationale**: The task has three distinct performance domains explicitly called out: API routes (backend slowness, artificial delays, sequential fetches), bundle/rendering (excessive client-side code, missing memoization, unnecessary re-renders), and Next.js-specific patterns (useEffect fetching, dynamic imports, client boundaries). These map cleanly to three skills with clear boundaries.

**Number of skills**: 3

---

## Skill 1: evo-nextjs-api-optimization

**Description**: Identifies and fixes performance anti-patterns in Next.js API routes including artificial delays (setTimeout in production), N+1 sequential fetch patterns, missing caching headers, and unnecessary data processing. Use this skill to diagnose slow API responses.

**Responsibility**: API route performance: remove artificial delays, parallelize sequential awaits with Promise.all, add caching (fetch options, Cache-Control headers, in-memory LRU), and optimize data fetching patterns in route handlers

**Key functions**: `find_artificial_delays`, `detect_sequential_awaits`, `suggest_parallel_fetching`, `check_cache_headers`, `analyze_api_routes`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-nextjs-api-optimization/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-nextjs-bundle-reduction

**Description**: Identifies and fixes bundle size issues including wildcard/barrel imports, missing dynamic imports for heavy components, unnecessary 'use client' directives pushing large trees to client, and useEffect-based data fetching that should be server-side. Use this to reduce JavaScript payload and improve load times.

**Responsibility**: Client bundle optimization: tree-shake heavy imports (lodash, icons), apply next/dynamic for code splitting, minimize 'use client' boundary scope, convert client-side useEffect fetches to server-side patterns

**Key functions**: `find_heavy_imports`, `suggest_dynamic_imports`, `detect_unnecessary_client_directives`, `detect_useeffect_fetching`, `analyze_bundle_issues`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-nextjs-bundle-reduction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-nextjs-render-optimization

**Description**: Identifies and fixes excessive React re-rendering issues including missing React.memo, unmemoized objects/functions/computations passed as props, context overloading causing cascading re-renders, and missing/incorrect key props. Use this to fix slow interactions like cart updates and compare page rendering.

**Responsibility**: React rendering performance: add useMemo/useCallback for expensive computations and callback stability, apply React.memo to frequently re-rendered components, split overloaded contexts, fix key prop issues in lists

**Key functions**: `detect_unmemoized_computations`, `detect_inline_object_props`, `detect_context_overloading`, `suggest_memo_wrapping`, `analyze_render_performance`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-nextjs-render-optimization/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
