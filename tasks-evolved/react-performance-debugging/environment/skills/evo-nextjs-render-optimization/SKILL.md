---
name: evo-nextjs-render-optimization
description: Identifies and fixes excessive React re-rendering issues including missing React.memo, unmemoized callbacks/computations, and context overloading.
---

# evo-nextjs-render-optimization

Optimizes React rendering by:
1. Wrapping frequently re-rendered components in React.memo
2. Adding useMemo for expensive computations
3. Adding useCallback for callback stability
4. Splitting overloaded contexts

## Key Patterns

### React.memo for ProductCard
Anti-pattern:
```typescript
export function ProductCard({ product, onAddToCart, isInCart }: Props) { ... }
```

Fix:
```typescript
import { memo } from 'react';
export const ProductCard = memo(function ProductCard({ product, onAddToCart, isInCart }: Props) { ... });
```

### useMemo for expensive computations
```typescript
const filteredProducts = useMemo(() => 
  products.filter(...).sort(...), 
  [products, filter, sortBy]
);
```

### useCallback for callbacks
```typescript
const handleAddToCart = useCallback((id: string) => {
  setCart(prev => [...prev, id]);
}, []);
```

## Usage

```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-nextjs-render-optimization/scripts')
from utils import wrap_component_in_memo, add_usememo_to_computations, apply_render_fixes

wrap_component_in_memo('/app/src/components/ProductCard.tsx', 'ProductCard')
apply_render_fixes('/app/src/components/ProductList.tsx')
```
