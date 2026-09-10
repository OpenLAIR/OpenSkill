# Domain Reference for evo-cluster-naming

**Responsibility**: Cluster naming via centroid proximity and TF-IDF top n-grams, enforcement of '<5 words' and ' | ' separator formatting, parent-child name overlap avoidance, and sibling distinctness via Jaccard overlap thresholds.

**Key functions to implement**: compute_centroid_name, extract_tfidf_top_terms, format_category_label, check_sibling_overlap, deduplicate_parent_child_names

---

## 4. Category-Name Selection and Text Normalization


Generating a unified category taxonomy requires assigning human-readable labels to the mathematically derived clusters. Because the system lacks an LLM to "summarize" the cluster, we must extract the most representative terms using offline NLP tools.

### 4.1 NLTK 3.8.1 Offline Handling

NLTK 3.8.1 requires specific corporate data (e.g., `punkt`, `stopwords`, `wordnet`) to perform tokenization and lemmatization. In an offline Docker container, `nltk.download()` will fail via timeout. 
**Offline Pattern:** Pre-download the corpora during the image build process and mount them to `/usr/local/share/nltk_data`, or dynamically set `nltk.data.path.append('/path/to/local/nltk_data')` before invocation.

### 4.2 Cluster Naming via Centroid and TF-IDF

To identify the name of a cluster:
1.  **Centroid Nearest Member:** Compute the mathematical centroid (mean vector) of all normalized embeddings in the cluster. Find the original category string whose embedding has the highest cosine similarity to this centroid. This ensures the name is a real string from the dataset.
2.  **TF-IDF Top Terms:** Use `sklearn.feature_extraction.text.TfidfVectorizer` to extract the top 2-3 highest-weighted n-grams (e.g., unigrams and bigrams) across all strings in the cluster. Combine them with a `" | "` separator [cite: 31].

### 4.3 Preventing Name Overlap (Jaccard Similarity)

Sibling clusters must be semantically distinct. If TF-IDF generates `"Men Shoes"` and `"Shoes Men"` for two sibling branches, their word-overlap (Jaccard similarity) will be 1.0. We enforce a constraint: if sibling overlap > 30%, the algorithm falls back to the second highest TF-IDF term or uses the centroid-nearest original Amazon/Google node.

### 4.4 Code Implementation: Representative Naming


```python
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

## 8. Consolidated Skill Pipeline: The `TaxonomyUnifier` Class


The following snippet provides a fully integrated, robust Python class adhering to the pinned library versions, avoiding deprecated features, and optimized for speed.

```python
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import pdist
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
import warnings