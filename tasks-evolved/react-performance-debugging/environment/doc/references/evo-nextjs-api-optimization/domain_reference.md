# Domain Reference for evo-nextjs-api-optimization

**Responsibility**: API route performance: remove artificial delays, parallelize sequential awaits with Promise.all, add caching (fetch options, Cache-Control headers, in-memory LRU), and optimize data fetching patterns in route handlers

**Key functions to implement**: find_artificial_delays, detect_sequential_awaits, suggest_parallel_fetching, check_cache_headers, analyze_api_routes

---

## 1. Next.js API Route Optimization Patterns


API routes in Next.js act as the crucial middle layer between the frontend and backend databases or external microservices. In e-commerce, where product catalogs and pricing logic are heavily queried, optimizing these routes is paramount.

### API Response Caching Configurations

In Next.js, caching semantics have evolved significantly between the Pages Router and the App Router. The App Router extends the native Web `fetch` API to provide granular, request-level caching control [cite: 9, 10]. 

*   **`cache: 'force-cache'`**: This instructs Next.js to serve the response from the Data Cache indefinitely unless manually invalidated. It is ideal for static product descriptions.
*   **`cache: 'no-store'`**: This bypasses the cache entirely, fetching fresh data from the origin on every request. Next.js 15 defaults to this behavior to prevent accidental stale data [cite: 11]. It is mandatory for real-time pricing and cart endpoints.
*   **`next: { revalidate: N }`**: This implements time-based Incremental Static Regeneration (ISR). The data is cached but automatically marked as stale after `N` seconds [cite: 10, 12].

```typescript
// App Router: Caching Fetch Examples
// 1. Indefinite Caching (Product Metadata)
const metaRes = await fetch('https://api.store.com/meta', { 
    cache: 'force-cache' 
});

// 2. Real-time Fetching (Inventory/Pricing)
const stockRes = await fetch('https://api.store.com/stock/123', { 
    cache: 'no-store' 
});

// 3. Time-based Revalidation (Category Listings)
const categoryRes = await fetch('https://api.store.com/categories', { 
    next: { revalidate: 3600 } // Revalidate every hour
});
```

### Request Deduplication

Next.js automatically deduplicates `fetch` requests that share the same URL and options during a single server render pass [cite: 13, 14]. This Request Memoization ensures that if a layout, a page, and a nested component all `fetch` the current user profile, only one network request is executed [cite: 13, 15]. 

*Note for Python AST utility:* The AST analyzer should detect patterns where developers manually implement `Promise` caching or prop-drilling solely to avoid duplicate fetches, and safely refactor them to rely on native Next.js `fetch` deduplication.

### In-Memory Caching (LRU Cache)

For endpoints that rely on database drivers (e.g., Prisma, raw SQL) rather than `fetch`, native Next.js `fetch` caching does not apply. In such scenarios, implementing a Least Recently Used (LRU) cache using libraries like `lru-cache` prevents memory leaks while reducing database hits [cite: 16, 17].

```typescript
// pages/api/products/[id].ts OR app/api/products/[id]/route.ts
import { LRUCache } from 'lru-cache';
import { NextResponse } from 'next/server';
import { db } from '@/lib/db';

// Initialize LRU cache outside the request handler to persist across invocations
// Note: In serverless environments (Vercel), this cache persists only while the lambda is warm.
const productCache = new LRUCache<string, any>({
  max: 500, // Maximum items
  ttl: 1000 * 60 * 5, // 5 minutes
});

export async function GET(req: Request, { params }: { params: { id: string } }) {
  const { id } = params;
  
  if (productCache.has(id)) {
    return NextResponse.json(productCache.get(id), {
        headers: { 'X-Cache': 'HIT' }
    });
  }

  const product = await db.query(`SELECT * FROM products WHERE id = ?`, [id]);
  
  if (product) {
    productCache.set(id, product);
  }

  return NextResponse.json(product);
}
```

### Detecting and Fixing N+1 Query Patterns

The N+1 query problem occurs when code executes one query to fetch N items, and then executes N additional queries to fetch related data (e.g., fetching 10 products, then running 10 separate queries for their reviews) [cite: 18, 19]. In Next.js, this often manifests as sequential `await` calls inside `.map()` loops.

**Anti-Pattern (Sequential execution \(O(N)\) time complexity):**
```typescript
const products = await getProducts();
const enrichedProducts = [];
for (const product of products) {
    // Blocks execution on every iteration
    const reviews = await getReviews(product.id); 
    enrichedProducts.push({ ...product, reviews });
}
```

**Optimized Pattern (Parallel execution via `Promise.all`):**
```typescript
const products = await getProducts();
// All review fetches fire simultaneously
const enrichedProducts = await Promise.all(
    products.map(async (product) => {
        const reviews = await getReviews(product.id);
        return { ...product, reviews };
    })
);
```
*AST Detection Strategy:* Look for `ForOfStatement` or `.map()` containing an `AwaitExpression` [cite: 5]. If the awaited function does not depend on the previous iteration's result, transform it into a `Promise.all()` wrapper [cite: 20, 21, 22].

### Cache-Control Headers

For custom API responses, correctly configuring HTTP `Cache-Control` headers directs Content Delivery Networks (CDNs) and browsers on how to cache the payload [cite: 7, 23].

```typescript
export async function GET() {
    const data = await getSlowData();
    
    // s-maxage: CDN cache duration (2 minutes)
    // stale-while-revalidate: Serve stale for 4 mins while fetching fresh in background
    return NextResponse.json(data, {
        headers: {
            'Cache-Control': 'public, s-maxage=120, stale-while-revalidate=240',
        },
    });
}
```