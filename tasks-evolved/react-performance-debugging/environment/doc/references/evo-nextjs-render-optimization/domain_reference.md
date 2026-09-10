# Domain Reference for evo-nextjs-render-optimization

**Responsibility**: React rendering performance: add useMemo/useCallback for expensive computations and callback stability, apply React.memo to frequently re-rendered components, split overloaded contexts, fix key prop issues in lists

**Key functions to implement**: detect_unmemoized_computations, detect_inline_object_props, detect_context_overloading, suggest_memo_wrapping, analyze_render_performance

---

## 3. Excessive Re-rendering Prevention in React/Next.js


In an e-commerce context, a cart update must not trigger a re-render of the entire 1,000-item product list. Unnecessary re-renders occur when React detects a change in state or props using Object.is() shallow comparison [cite: 34, 35].

### Reference Equality: The Object/Array/Function Problem

When a parent component renders, any inline object, array, or function defined inside it is recreated with a new memory reference [cite: 36, 37]. Even if a child component is wrapped in `React.memo`, it will re-render because the new reference violates shallow equality [cite: 34].

**Anti-Pattern:**
```tsx
const Parent = () => {
    const [count, setCount] = useState(0);
    // Recreated on every render (count update)
    const config = { theme: 'dark' }; 
    const handleClick = () => console.log('click');

    return (
        <div>
            <button onClick={() => setCount(c => c + 1)}>Increment</button>
            <MemoizedChild config={config} onClick={handleClick} />
        </div>
    );
};
```

**Optimized Pattern:**
```tsx
const Parent = () => {
    const [count, setCount] = useState(0);
    
    // Reference preserved across renders
    const config = useMemo(() => ({ theme: 'dark' }), []); 
    const handleClick = useCallback(() => console.log('click'), []);

    return (
        <div>
            <button onClick={() => setCount(c => c + 1)}>Increment</button>
            <MemoizedChild config={config} onClick={handleClick} />
        </div>
    );
};
```

### React.memo and Custom Comparisons

`React.memo()` is a Higher Order Component that memorizes the render output [cite: 34, 38].

```tsx
// Standard memoization
const ProductCard = React.memo(function ProductCard({ product }) {
    return <div>{product.name}</div>;
});

// Custom comparison signature
const OptimizedCard = React.memo(
    ProductCard, 
    (prevProps, nextProps) => prevProps.product.id === nextProps.product.id
);
```

### Context Splitting for Cart State

React Context triggers a re-render of *all* consumers whenever the `value` prop changes [cite: 36, 39]. If the cart state and the `addToCart` function are in the same context, any component needing only `addToCart` will unnecessarily re-render when the cart quantity updates [cite: 40, 41].

**Solution: Context Splitting [cite: 40]**
```tsx
// 1. Create two contexts
const CartStateContext = createContext<CartState | null>(null);
const CartDispatchContext = createContext<React.Dispatch<Action> | null>(null);

export function CartProvider({ children }) {
    const [state, dispatch] = useReducer(cartReducer, initialState);

    return (
        <CartDispatchContext.Provider value={dispatch}>
            <CartStateContext.Provider value={state}>
                {children}
            </CartStateContext.Provider>
        </CartDispatchContext.Provider>
    );
}
```
Now, a `ProductButton` consuming *only* `CartDispatchContext` will not re-render when `CartStateContext` updates [cite: 40, 41].

## 5. Common Anti-Patterns in Slow Next.js E-commerce Apps


For an automated Python AST tool, identifying these specific syntactical anti-patterns is highly lucrative:

1.  **Artificial Delays:** `await new Promise(resolve => setTimeout(...))` left in production API routes [cite: 49].
2.  **Unoptimized Derived Data:** Re-computing expensive logic on every render instead of caching it.
    *   *Bad:* `const sorted = heavySort(products);`
    *   *Good:* `const sorted = useMemo(() => heavySort(products), [products]);`
3.  **Context Overloading:** Passing entire deep objects when primitives suffice, bypassing memoization shallow comparisons.
4.  **Missing/Index `key` Props:** Using `key={index}` in lists where items can be deleted or reordered forces React to destroy and remount DOM nodes, devastating performance [cite: 50].
5.  **Synchronous Heavy Computation:** Blocking the main thread with massive array filters.
6.  **Deep Cloning Anti-pattern:** Using `JSON.parse(JSON.stringify(obj))` for immutability is extremely slow; AST tools should replace this with `structuredClone(obj)` or spread operators.

## 7. Specific Code Transformation Patterns


When writing AST transformations via Python, the paramount concern is safety—maintaining the integrity of testing attributes (`data-testid`) and telemetry (`performance.mark()`) [cite: 56, 57, 58]. AST rewrites handle this gracefully by matching and carrying over the exact node definitions.