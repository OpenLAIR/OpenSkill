To verify the performance and correctness of the Next.js e-commerce application, you can implement a surrogate test suite using `pytest` combined with `playwright` for end-to-end verification and `httpx` for API-level validation.

### 1. Independently Computable Reference Values
For e-commerce performance, you can establish invariants based on the expected behavior of the API simulator and the frontend.

*   **Request Memoization Invariant**: If a component tree triggers multiple identical `fetch` requests for product data (e.g., `GET /api/products/123`) within a single render pass, the total number of network requests to the backend must be **exactly 1**.
    *   *Verification*: Use a mock server or proxy to count incoming requests.
    *   *Assertion*: `assert request_count == 1` for a page rendering multiple instances of the same product.
*   **Cache-Control Invariant**: API routes for static product metadata should include `Cache-Control: public, s-maxage=...` or similar headers, while real-time endpoints (cart, inventory) must include `Cache-Control: no-store`.
    *   *Verification*: `httpx.get(url).headers['Cache-Control']`.
    *   *Assertion*: `assert response.headers['Cache-Control'] == 'no-store'` for `/api/cart`.

### 2. Dataset-Level Statistical Invariants
These properties ensure the application remains functional while optimized:

*   **Completeness Check**: The number of products rendered on the homepage must match the number of items returned by the API simulator.
    *   *Constraint*: `len(rendered_product_cards) == len(api_product_list)`.
*   **Monotonicity of Cart**: Adding an item to the cart must result in a cart count that is strictly non-decreasing.
    *   *Constraint*: `cart_count_after >= cart_count_before`.
*   **Rendering Integrity**: The `data-testid="advanced-content"` element must exist and be visible on the Compare page.
    *   *Constraint*: `page.locator('[data-testid="advanced-content"]').is_visible() is True`.

### 3. Cross-Validation Approaches
You can use `httpx` in Python to independently verify API behavior against the `api-simulator` without relying on the Next.js frontend code.

```python
import httpx
import pytest

# Cross-check API response time and caching headers
def test_api_performance_and_headers():
    client = httpx.Client(base_url="http://localhost:3001")
    
    # Verify real-time endpoint
    resp = client.get("/stock/123")
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    
    # Verify latency (e.g., should be under 200ms for simulated local API)
    assert resp.elapsed.total_seconds() < 0.2
```

### 4. Benchmarks and Reference Implementations
Use the following as oracles for your performance tests:

| Metric | Target | Verification Tool |
| :--- | :--- | :--- |
| **LCP (Largest Contentful Paint)** | < 2.5s | Playwright `performance.mark` / Lighthouse CLI |
| **Request Memoization** | 1 request per unique URL | Mock server request counter |
| **Bundle Size** | < 150kB (Initial JS) | `npm run build` output analysis |
| **CLS (Cumulative Layout Shift)** | < 0.1 | Playwright layout shift monitoring |

*   **Reference**: Refer to [Google's Core Web Vitals documentation](https://web.dev/vitals/) for the authoritative thresholds for LCP, FID (or INP), and CLS.
*   **Implementation**: Use `performance.mark()` and `performance.measure()` in your `ProductCard` components as requested, and extract these values in your `pytest` suite using `page.evaluate("window.performance.getEntriesByType('measure')")`.