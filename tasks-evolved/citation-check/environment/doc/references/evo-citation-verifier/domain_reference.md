# Domain Reference for evo-citation-verifier

**Responsibility**: Network communication with academic APIs, DOI resolution, rate limiting, retry logic, and returning raw API results for each citation

**Key functions to implement**: verify_doi_exists, query_crossref, query_semantic_scholar, query_dblp, get_robust_session, rate_limited_query

---

## 3. Landscape of Free Academic Citation Verification APIs


Once the citation is parsed and cleaned, the module must query external databases to verify the existence of the text. The user's requirement to rely on *free APIs without API keys* imposes significant structural limitations, making the choice of endpoints and HTTP header configurations paramount.

## 5. Practical Implementation of Robust API Querying


When scraping thousands of citations using unauthenticated API endpoints, network failures, timeouts, and rate limits are inevitable. Bypassing these issues requires enterprise-grade resilience using the `requests` library.