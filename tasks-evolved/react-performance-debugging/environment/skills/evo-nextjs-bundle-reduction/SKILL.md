---
name: evo-nextjs-bundle-reduction
description: Identifies and fixes bundle size issues including wildcard/barrel imports, missing dynamic imports for heavy components, unnecessary use client directives, and useEffect-based data fetching.
---

# evo-nextjs-bundle-reduction

Reduces client bundle size by:
1. Converting barrel lodash imports to individual module imports
2. Applying next/dynamic for code splitting heavy components
3. Minimizing 'use client' boundary scope
4. Converting client-side useEffect fetches to server-side patterns

## Key Patterns

### Barrel Lodash Imports → Individual Imports
Anti-pattern:
```typescript
import { groupBy, sortBy, meanBy } from 'lodash';
```

Fix:
```typescript
import groupBy from 'lodash/groupBy';
import sortBy from 'lodash/sortBy';
import meanBy from 'lodash/meanBy';
```

### Dynamic Import for Heavy Components
Anti-pattern: Static inline component using heavy library (mathjs)

Fix: Extract to separate file and use next/dynamic:
```typescript
import dynamic from 'next/dynamic';
const AdvancedAnalysis = dynamic(() => import('@/components/AdvancedAnalysis'), {
  ssr: false,
  loading: () => <div data-testid="advanced-content">Loading...</div>
});
```

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-nextjs-bundle-reduction/scripts')
from utils import fix_barrel_lodash_imports, extract_and_dynamify_component, apply_bundle_fixes

fix_barrel_lodash_imports('/app/src/app/compare/page.tsx')
extract_and_dynamify_component('/app/src/app/compare/page.tsx', 'AdvancedAnalysis')
```
