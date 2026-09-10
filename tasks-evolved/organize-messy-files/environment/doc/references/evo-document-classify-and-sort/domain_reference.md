# Domain Reference for evo-document-classify-and-sort

**Responsibility**: Document classification based on text content, folder creation, and file movement. No text extraction logic.

**Key functions to implement**: classify_document, create_category_folders, sort_files_into_folders, get_category_keywords

---

## 5. Keyword-Based Document Classification


Once text is extracted, the next stage is classification into predefined categories: LLM/AI, Quantum Computing, Astrophysics, Biology, and Music History.

### 5.1 Classification Scope: First Page vs. Full Text

For scientific papers, using the **first page (title + abstract)** is overwhelmingly the best practice. 
*   **Signal-to-Noise Ratio:** The abstract densely packs domain-specific keywords. Parsing the full text introduces immense noise—for example, an Astrophysics paper might use algorithms drawn from AI, causing full-text keyword searches to misclassify the document based on the methods section rather than the core topic.
*   **Performance:** Processing 1,000 words (abstract) is computationally trivial compared to processing 15,000 words (full text).

### 5.2 Discriminating Keywords per Domain

To construct a robust keyword matcher without Machine Learning models, establishing a dictionary of highly discriminating, mutually exclusive keywords is essential:

*   **LLM/AI:** `["large language model", "transformer", "neural network", "deep learning", "machine learning", "nlp", "attention mechanism"]`
*   **Quantum Computing:** `["trapped ion", "qubit", "quantum entanglement", "quantum state", "superposition", "quantum error correction", "qiskit"]`
*   **Astrophysics:** `["black hole", "event horizon", "gravitational wave", "galaxy", "neutron star", "dark matter", "accretion disk"]`
*   **Biology:** `["dna", "genome", "crispr", "protein folding", "rna", "nucleotide", "amino acid", "gene expression"]`
*   **Music History:** `["baroque", "sonata", "mozart", "polyphony", "concerto", "ethnomusicology", "renaissance music"]`

### 5.3 Implementation: Term Frequency-Inverse Document Frequency (TF-IDF)

While simple keyword frequency matching works (counting the occurrence of words), it treats all words equally. A lightweight TF-IDF algorithm assigns higher mathematical weight to rare, domain-specific words and diminishes the weight of common cross-domain words.

Below is an implementation of a TF-IDF scorer utilizing purely the Python standard library (`math`, `collections`):

```python
import math
import re
from collections import Counter, defaultdict

class DocumentClassifier:
    def __init__(self):
        # Category Definitions with initial seed keywords
        self.categories = {
            "AI": ["llm", "transformer", "neural network", "deep learning", "machine learning"],
            "Quantum": ["trapped ion", "qubit", "quantum", "superposition", "entanglement"],
            "Astrophysics": ["black hole", "astrophysics", "gravitational wave", "galaxy"],
            "Biology": ["dna", "genome", "crispr", "protein", "rna", "biology"],
            "Music_History": ["music", "baroque", "sonata", "mozart", "polyphony", "concerto"]
        }
        
        # Build the vocabulary set
        self.vocab = set(word for keywords in self.categories.values() for word in keywords)
        
        # Inverse Document Frequency (Simulated heuristic for offline processing)
        # In a real TF-IDF, IDF is calculated across the entire corpus. 
        # Here, we hardcode IDF weights to strongly favor highly specific terms.
        self.idf = {
            "llm": 4.5, "transformer": 3.0, "neural network": 3.5,
            "trapped ion": 5.0, "qubit": 4.5, "quantum": 2.5,
            "black hole": 4.0, "astrophysics": 4.5, "gravitational wave": 4.5,
            "dna": 3.0, "genome": 4.0, "crispr": 4.5,
            "baroque": 4.5, "polyphony": 5.0, "sonata": 4.0,
            # Assign a baseline score to other terms
        }
        for word in self.vocab:
            if word not in self.idf:
                self.idf[word] = 2.0 

    def preprocess(self, text: str) -> list:
        # Convert to lowercase and extract words/phrases
        text = text.lower()
        # For simplicity in this demo, we check exact phrase matches by keeping the text as a single string 
        # for phrase counting, and tokenizing for single words.
        return text

    def classify(self, text: str) -> str:
        if not text.strip():
            return "Unclassified"
            
        processed_text = self.preprocess(text)
        scores = defaultdict(float)
        
        for category, keywords in self.categories.items():
            for kw in keywords:
                # Term Frequency (TF): Count occurrences of the keyword/phrase
                tf = processed_text.count(kw)
                if tf > 0:
                    # Score = TF * IDF
                    weight = tf * self.idf[kw]
                    scores[category] += weight
                    
        if not scores:
            return "Unclassified"
            
        # Handle edge cases where multiple topics overlap (e.g., Quantum Machine Learning)
        # Select the category with the highest aggregated TF-IDF score
        best_category = max(scores, key=scores.get)
        return best_category
```

## 6. Robust File Operations and Folder Management


Once a document is successfully classified, it must be physically routed to its corresponding directory.

### 6.1 Creating Destination Folders

The `os.makedirs()` function is the optimal tool for creating directory trees. Using the parameter `exist_ok=True` ensures that no `FileExistsError` is thrown if the directory was created in a previous script run [cite: 29].

```python
import os

def create_folders(base_dir: str, categories: list):
    for category in categories:
        folder_path = os.path.join(base_dir, category)
        os.makedirs(folder_path, exist_ok=True)
```

## 7. Integrated Pipeline Architecture


To combine the methodologies outlined in this report, the following logic models an integrated pipeline:

1.  **File Ingestion:** Iterate over all files in an incoming directory. Identify the file extension using `os.path.splitext()`.
2.  **Text Extraction Stage:** 
    *   If `.pdf`, use PyPDF2 for speed. If extracted text length < 50, use the `pdftotext` subprocess.
    *   If `.docx`, use native `zipfile` extraction.
    *   If `.pptx`, use native `zipfile` extraction.
3.  **Classification Stage:** Pass the extracted string to the `DocumentClassifier.classify()` method.
4.  **Routing Stage:** Sanitize the filename, check for collisions, and execute `shutil.move()` to place the file in the designated topic folder.

This structure forms a cohesive, fault-tolerant Python utility module capable of operating purely on standard libraries where necessary, while capitalizing on efficient C++ binaries (`poppler-utils`) and optimized Python packages (`PyPDF2`) to parse massive document datasets for classification and sorting.

**Sources:**
1. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEeTqa9Kg8RCx1XhmyENiwrwJ8w8miTlLXAunIx4500yzBFr3dnM5QVkm66KwKptjxeJMXFOxRyrAFU7gcZxdoyp3WV7Z6Q7i4zxgqh7qHIkVGNWI6pKkSRDtlljpuVI3i5m-ndAOqjKrBkOwddBcgGg==)
2. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7QE2rPk9HQv1AMQMywUXOYTZoh2ORmIPIlDQuHs5Q6fE1Wv-FLI9pEP6o6dGfdVXpaRV0ubWAxEM4b3sQ-S3VDTnBwVfvFMjZFSvUfb_ykHSpLhfXdlRySweOXNH9CEBcJm6F0o1eFcKXK40Mdw==)
3. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG97Gaq9JbLWIKLZp8hrRBPB1q7WZ2tOKG40OTm6ZGMFUa3CsOH4HUU-J7xqSjnVlAxtYGJEUXdgr0R5_vW9jomM4s5nEjSEBgbei7i5QHLcnQbNfwGww==)
4. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQol6_zsOUzkS2mLapuIOYJYvbbCdjiz8WAe2vF7W13n5JPA-yfODM4-7g7vdd581PUlygbRf-TjiReaM5gIt5_L_rV6Qr2SgJtTqdG17jujtfAXckE3HHmZD3TEAtbxBt8EiPeQ==)
5. [snyk.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG-84-VS2lfpv-6eXGD_e90lD--IKOPe_Cy47UM7nrCRJyRg94RzYhVkCZudxBUOO8sQ0m5RiAynG1wwqncNJv7O5nqbWufnaqK6ErKlfdTzeyu9WMrlSTeNyShBpmrtPIGP31J8K16)
6. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC_yStKVPsao-qqSDLMbJHKpaRcAVGEJdwyb75v4th8xzLn6-Mz2Po-IlvkEqytfCx6V1xhkmdE3l4n0z8EiGSLiHjaP6Ip5KL5lZrb26agcmnJdr_Ct_fBAQ=)
7. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSRoJosmhYfpr_ra_Uq85gfIFLKxfcVcFf8GNh9VkVD0-kka2RM1bkzUzCXxvV_7W5CAT8czrRDBlMzIF3ss966_TL6NBUbMXmmuXGToW3Tx27DdGcRVbhetxAwr6ioa2XfOrs8w==)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHdJjXfqXK7hdeAvyD5lIlnCmPPLS1jNC7pxYhBn1tvXpUV_w9svoua79vl5Bn_DaBhJl3Tog4no9Ru2LvW-bZeS3NYWTJOM2lUjXbqzps5glBOxP7Rq1bRsDg7NsXz0YUgUeb1Mw==)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcNGgbmFeTRDNDOop8CszTGAd9OaGE2oJ3W5Y-q8F_7hx2gLbXn2rquw6-GvEj78WAsVjeaVf2C2Bk9zRhAZyMe78KUZXfh5kGyBjnMU0RHOr2eLHPepP8HiklZbktv5nrnLz_wI8vwmHoOQ==)
10. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE03qkKc-KODVgiKjRAbH9TFeiuBRU7VBrewl-FlxYUcMiOuNLoqsHMwZw59XqchpSaAFUOKtvVpuaOTGZhDiIGISgX0UXA313dVUUsPG8pXzNTKyQPu8_eYpHXzT5Q6a9aQcjA0_9HQD08LV7cWki0H4NJbEU_DcDItTKeaCAOehNy7gHNcK-5hnfOxy4t7b4g7kGx8hKkKqa9sLo=)
11. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG5PZL1gORlsFLqMtcMWHq6lBbw3N8USlqfnadnB829oWGZAUQLObYaIdbERjmsGc0uoxNGnmpozqQQIzJYAPySF1vVms0L8k3bx1pXp9c3Cgg8DCvmV1l-Ta_jMSsFjlz0jPxca5el8lbGfv5qV9PK9j-Vr5jSkyg_w5P2fRkpWultODrJLs7oWjAWt1APChwsHGQXxpfG8iLjEVb_ANYg)
12. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCu1gRH0XCXQ4448cNd2787ZvGk1LHqGGJmTBn_QzsLSq99anjYNcTRBMjXHQVRs8OTalb6sbkKDoIeo7Uovn1Br5qr9gbIKv-X8XXXsG4aoO-A15wIpFP2lTjuj5cee04JmHB6J0pvOow2ZfngdH93tWPWuuQlhB-JGYg9gw3x2AWcM1qnwU8p17ivXDd2PLGlYzeFMKMaoRU)
13. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6VnBV5nADfLYNSFEbcfXuN2L1vX9URrhJBHLE-0inVApNLApTz2pTzMuHZxBw4IlbAf21dwTMJZnQ_iAQBzaKCr7B8OYZiOssz6-EUjTYYOdRhghpXotXehwFxy7evwMfWqIEcK5OnDOQheWZ_efeGBBMfnRMl8el)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhnsNC0vaXVqxHjPsgQfn3i-Hdb0LddWr8XRS3ymHaakthMtk3JeFsoXQbAxNrahcpG5ZyASIAqTxog7EjA5Xdpyj6uldWqHvByBXavTpaRc73LOBonTGf24lTY_EK2bYVNnsha4tgsosKNDeZP3US5wUi7sb4pA_XhYm7AZ1yo_pSA5pbuITGI5vR_dTu)
15. [quora.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXjfP88Lik768VY5QtfGGkK4S6TrgmAuz0WpEegYTGLteKsbnvMZ_XpDO_hnQXZWQqgVDviq7ufPmFHQQFxWV6v9ZxPFVTBELZ4IFd7XI_PYdyxGTf3MAIR3BDuMNG65trIqvMzZqst45VrLT61Vza921l)
16. [otranslator.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF237Md5Dg2BM4YvZeZ76PcxmqZlSaJWiuTKJPysUrz8ySS9rDTyF0Rq4UVWq0a4S1GBE8J_Px-sna1jAYL-OAMujK2uAikFb2UrYYoSe9TGTuGjrnyU4rqwGwZLDd6rZWnRHFxLAubA3ruzh9nnU4POIfupHAet97HouOJkyHOxwYJXA==)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFppMCc5pmX523EWypQTy81ZVFb-e1Rq7neBctmwZr7tGHRrom7AY93e6-zzc4NhECF6pogxlLy9WvdnlO_D0yp6Rkv3pSvxDEdObnobLXoS4lm-gbhC10BZT5Cr1X7HJqgJqRjfDpO7jFgqr9nEmY7NcmIXisIn_oF7LeI97dYCZJwGSoJymaEB_BJLvqy38JHxMFjXG7xuFGYl4FKerXEQyB-JIZLhT-lWOcFxdHL)
18. [superuser.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9H-LSeq2LNgEEN_jbbrd0adwBRz88ouKgdDlVquBPALGF8QUPm1_VT3F0v4slsz0fRJDMFpa5wB41K7ACdleMKZ6qnTQJ01Ud8wzNQm7MNQxbsL6MvdeTedOIq-OkdR90faf4ppdcV_VBldoI0WVF91MNFw==)
19. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFE6coJRbWHl5rE25euU5RwbY5YpMESYYeEqDpL95ACjCUayiJxHBodjBEMNErsfHy6CRguYVe0ct3WMOunXa24_km1294ytiudWxXu_XJIZK5bNvckEiUjBd-viZjnasGp171L3sYCivGE9zrs79b2PLc3YVIE5Q==)
20. [xbwbc.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHt9_xYWst-9y4b8ZYmdcMO7L312z4wzl1x1epky8Ezy6w6aU_LSy5saOJ6Fc7tEUoqP3olFl4WfYE2UqcI89ubakXLvkiAz8HjEVFDXwKC94NbGInQl0MCUwuxkX8DeWfGz6ld7JM=)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFcOhTXfFcY8Xg0altDsJc63_c008-9wqe9e_1UPSlgDsAVDULWj2qxxrkBTaCMkeB-GpMRbodr7PXDdmNr6FHbMC3mFexpmvqyRed6wqFTPQoi2_8W8HFXRjbyH-dYFREiFO5QeoTnXYLsRMcmgi64x5q3SpKHhedQemt4Hi2ITlNVSoLdtXDjKVlgeYiUt40O4uZ8TrHUGkUAPHyuQldwUqOGcrAQAIE_Q==)
22. [linuxcommandlibrary.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgeI5j_811qa8hpf_VpHqcIYeziPO5YwTOdcBrKsJ9P_sRjhG3SJ3SONA4DKdptGOX445PBp2TGnuU8xF4yqeY4vku034kbGDWkh3EoQUp2yf5XDsq5TVys6Fj7VmqOwuX5EI=)
23. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUc55PDNQFH48LJZByOTp1ThqaMrNFqp0-53JPrMU10wF-6hKPT1cpITuP8_6WXJhqUIk3wG-mvYJwWFczMKv9_bLlXyxzRz2wzG4_xB2W23odKr10p8aWkpi3_1H0XUy8KBsBNGbFJLymBds0CmOF)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9F-e5X63Qqz8G9jzLnhCh_fuDUMMWFqHL2zNmOyIGDPI1fTRWnaRDvF8A_AuwGfkksexturW4h0ohf4vUqtlbQiiznavshHxQlyV35BK2ZqMDYFLIiB_tyrlLg13R-GeltoUXc_Zi_Hxy6pbAN8n7tz-wXSwmjSL0qcFZoCtUfDoJPb11E4jHkX4zI6M=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHAPV61jkgHyY27IXdMcmZ-Ny8AwE39VrSKahEkPol676xbOVyXKItDcm8u1ca1tcyLkX3ll4vf7KzTlmR_nnr2O4rqYywE1wxIEVRc5IcYFZzzdGBg24Xb79f70-zCO_zfT7nXIADBrLXzXfPs-rrybm7Gjz5-x0xYkRhxYymqDwO0HZ0GwdBWiBvHkzyGxXAAxUFnd5YMV2PFLbbTpzQzkO5a0q7iJdxQn6r7T0mLnRwf)
26. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7o8f74GYPQrktJaS3FiummWPx5ojFx_ui_3izB9UEubV3ItgaWzN7XdlpvyFWYY7_GLgmQPjQ47cs8_SBTrC96t1_LdBA9BDJHj2CYvsZ79HSTCCDb6-FEpqV9M9PLCi1QShnNvghhLKKCnpXQOOudC9Bu1BsnJg5wttre1jXTA_5_JkgPx-LCXVRNnRJaMBYnSORli5Hssnmvg==)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3PlidRyrfLs4Wjn8R-DMxmvj7-_79rULrTmMpDrzAgLZcnM_7GeyJNq3CWRh4zGwimh9PSc3TaTyOrPSzLbPCBO9a2Wcz6c_R8NSMTSC7GkL5YR5Ocmex3rPt3nlGcBmM8Wl8PxotQxFq3vB_HK-URSTNU81BtwTaV7T9ni_DvuF0vjR0zvbSVg5HEK_y)
28. [torrocus.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEy394r4aIrJFNQC1T23fws_c9AE5UKijkzUGnIYGZzc_OWTo17_xyY14LCfgeHULf--Kg2h23KPwlObJInp36m6dz4VWy-LBbore2Ym-OkCYWUZqk0iSciRZW9I1hHpcDncHxRQOSXEbkF0Rf65WvKFuI=)
29. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG9zoS-O1jCtIf0ZKXZnPyQ1sWEgaTyxMbOXHJ0tFSi3BfoidCLNavxsdfzY3TGLkGfxXmrzgqt3cHqsupdWdFzab8Z2xl1yg78a8jPupL3crqJHeJUyLll86fP6tmd5f6hNcPpMKsVOhduEeAEAMr42oNr)
30. [giedrius.blog](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7ffJCmqsx0k-duyPFeop-TrZO00PFVx1mUmDYrJbbmBVkoPF0vWrJjF59FXXD8RFIwlJDPqq5sJG66WZjqq0vgdWsNKUINtGlX7n5an-xKhDIaIib2qYhID8wef_VVXotYz58EikFzxYc2LDIy4hA3rHuSNipt_5xFs3Mwl28Y5AzB-aC3cumEtp0JhTFYS33kBeAe_WTav5OkwLI)
31. [alexwlchan.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEuV8qwxa84Gr0BwXjikoMh66yfsH2SYw_4gkJ0zhSseMxmHaAxIJP1XuB_skq9l-ccPz2ngrMchtwkc17NZTk8QXJGvlW8F7Vl1B3plBksV_Ok_5bhlr5B7-mdUXoEMf5CplHY-kh-LpqsWjaXPR0LYmAceOPmjwkJA==)