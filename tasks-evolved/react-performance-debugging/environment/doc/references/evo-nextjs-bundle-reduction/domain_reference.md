# Domain Reference for evo-nextjs-bundle-reduction

**Responsibility**: Client bundle optimization: tree-shake heavy imports (lodash, icons), apply next/dynamic for code splitting, minimize 'use client' boundary scope, convert client-side useEffect fetches to server-side patterns

**Key functions to implement**: find_heavy_imports, suggest_dynamic_imports, detect_unnecessary_client_directives, detect_useeffect_fetching, analyze_bundle_issues

---

## 2. Bundle Size Reduction in Next.js


Large JavaScript bundles block the main thread, severely degrading the Time to Interactive (TTI) metric. E-commerce platforms are particularly susceptible due to heavy UI libraries, carousels, and tracking scripts [cite: 1].

### Tree-Shaking Heavy Imports

Tree-shaking is a dead-code elimination process. If a developer imports a massive utility library incorrectly, the bundler cannot shake off the unused parts, bloating the client bundle [cite: 24, 25].

| Library | Anti-Pattern (Bloats Bundle) | Optimized Pattern (Tree-shaken) |
| :--- | :--- | :--- |
| **Lodash** | `import _ from 'lodash'` | `import debounce from 'lodash/debounce'` |
| **Icons** | `import { Arrow } from 'lucide-react'` | `import Arrow from 'lucide-react/dist/esm/icons/arrow'` |
| **Dates** | `import moment from 'moment'` | `import { format } from 'date-fns'` |

### Exact Syntax for `next/dynamic`

Next.js allows component-level code splitting using `next/dynamic` [cite: 26, 27, 28]. This defers loading non-critical JavaScript until the component is rendered. It is highly effective for "below-the-fold" components, heavy charts, or interactive modals.

```typescript
import dynamic from 'next/dynamic';

// 1. Basic Dynamic Import
const DynamicModal = dynamic(() => import('@/components/CartModal'));

// 2. Disabling Server-Side Rendering (SSR) for browser-only APIs
const DynamicChart = dynamic(() => import('@/components/HeavyChart'), { 
    ssr: false, 
    loading: () => <p data-testid="chart-loading">Loading chart...</p> 
});
```
*Note:* In the App Router, `ssr: false` requires the component importing the dynamic module to be marked with `'use client'` [cite: 29].

### Using `@next/bundle-analyzer`

To systematically identify large dependencies, the `@next/bundle-analyzer` plugin must be configured.

**`next.config.js` Configuration [cite: 30, 31, 32, 33]:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // your existing config
};

const withBundleAnalyzer = require('@next/bundle-analyzer')({
  enabled: process.env.ANALYZE === 'true',
});

module.exports = withBundleAnalyzer(nextConfig);
```
Executing `ANALYZE=true npm run build` generates interactive treemap HTML files in the `.next/analyze/` directory, revealing exactly which modules consume the most bytes [cite: 29, 33].

## 4. Next.js Specific Performance Patterns



### Minimizing the Client Boundary (`'use client'`)

In the App Router, Server Components are the default. The `'use client'` directive pushes the component and all its imported children into the client JS bundle [cite: 2, 3, 47, 48]. A common anti-pattern is placing `'use client'` at the very top of the routing tree (e.g., in `layout.tsx`). The fix is to extract interactive elements (like buttons or toggles) into small, isolated "leaf" components, passing server-rendered content to them as `children`.