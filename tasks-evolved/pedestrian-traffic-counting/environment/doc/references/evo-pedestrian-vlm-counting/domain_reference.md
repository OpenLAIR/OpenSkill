# Domain Reference for evo-pedestrian-vlm-counting

**Responsibility**: VLM API integration (OpenAI and Gemini), prompt engineering for unique pedestrian re-identification, response parsing with integer coercion, and Excel output generation with correct sheet/column structure

**Key functions to implement**: count_pedestrians_openai, count_pedestrians_gemini, parse_count_from_response, write_results_to_excel, run_pedestrian_counting_pipeline

---

## 4. Utilizing the OpenAI Vision API (openai 2.15.0)


OpenAI's GPT-4o and GPT-4-vision models possess state-of-the-art visual reasoning capabilities. With the `openai` Python SDK version 2.15.0, these capabilities are exposed through the standard Chat Completions endpoint, treating images as native contextual input alongside text [cite: 10].

## 5. Utilizing the Google Gemini API (google-genai 1.59.0)


Google's Generative AI ecosystem provides a powerful alternative for multi-modal analysis, particularly with models boasting massive context windows (up to 2 million tokens for Gemini 1.5 Pro). However, interacting with this API via Python requires navigating a recent, major paradigm shift in Google's developer tooling.

## 6. Advanced Unique Pedestrian Counting Strategy


Applying Vision LLMs to the task of video pedestrian counting is not a trivial substitution for traditional MOT (Multi-Object Tracking) systems. While VLMs excel at zero-shot object recognition, research indicates they exhibit notable weaknesses in spatial tracking, object permanence across disparate viewpoints, and basic counting when numbers scale beyond small groups [cite: 20, 21].

## 7. Persisting Results with OpenPyXL 3.1.5 and Pandas 2.3.3


Once the LLM has successfully inferred the unique pedestrian count, the resulting data must be aggregated and serialized into a standard reporting format, typically Microsoft Excel. In Python, this is facilitated by the `pandas` data manipulation library, utilizing `openpyxl` as its underlying serialization engine.

## 8. Critical Pitfalls and System Robustness


Building a composite pipeline linking video rendering, network APIs, and data serialization introduces multiple vectors for failure. Below is an exhaustive detailing of critical pitfalls that must be mitigated.