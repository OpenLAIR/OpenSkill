---
name: evo-nextjs-api-optimization
description: Identifies and fixes performance anti-patterns in Next.js API routes including artificial delays, N+1 sequential fetch patterns, missing caching headers, and unnecessary data processing.
---

# evo-nextjs-api-optimization

Optimizes Next.js API routes by:
1. Removing artificial delays (setTimeout in production)
2. Parallelizing sequential awaits with Promise.all
3. Adding caching headers (Cache-Control)
4. Optimizing data fetching patterns

## Key Patterns

### Sequential Awaits → Promise.all
Anti-pattern:
```typescript
const user = await fetchUser();
const products = await fetchProducts();
const reviews = await fetchReviews();
```

Fix:
```typescript
const [user, products, reviews] = await Promise.all([
  fetchUser(),
  fetchProducts(),
  fetchReviews(),
]);
```

### Artificial Delays
Remove `await new Promise(resolve => setTimeout(...))` from production routes.

### Cache-Control Headers
Add appropriate Cache-Control headers to API responses.

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-nextjs-api-optimization/scripts')
from utils import find_sequential_awaits, fix_sequential_awaits, find_artificial_delays, apply_api_fixes

# Analyze a file
issues = find_sequential_awaits('/app/src/app/page.tsx')
# Apply fixes
apply_api_fixes('/app/src/app/page.tsx')
```
