# Comprehensive Guide to Suricata 7.0 HTTP Rule Writing: Advanced Detection of POST Requests, Headers, and PCRE

**Key Points:**
*   Suricata 7.0 relies on **sticky buffers** (e.g., `http.method; content:"POST";`) rather than legacy content modifiers, fundamentally altering rule-writing syntax and execution order.
*   The `http.request_header` keyword, refined in the 7.0.x branch, does not utilize a distinct `name:` argument; instead, it relies on concatenating the header name and value using a colon-space (`|3a 20|`) delimiter.
*   By default, the `http.request_body` buffer is **not** URL-decoded. Threat researchers must explicitly apply the `url_decode` transform to reliably evaluate form-urlencoded HTTP POST bodies.
*   While legacy Perl Compatible Regular Expressions (PCRE) modifiers like `/P` (for body) and `/H` (for headers) remain supported, modern rule engineering dictates placing the `pcre` keyword explicitly after the relevant sticky buffer.
*   The transition from HTTP/1.1 to HTTP/2 necessitates the use of header normalization transforms (such as `header_lowercase`) to avoid false negatives in heterogeneous network environments.

**Introduction to HTTP Detection in Suricata 7.0**
The evolution of network intrusion detection systems (NIDS) has required a paradigm shift in how application-layer protocols are parsed and analyzed. Suricata 7.0 introduces significant architectural enhancements, particularly in handling HTTP/2 and standardizing payload inspection through sticky buffers. Building a Python utility to automate and validate Suricata rules necessitates a profound understanding of these syntactic nuances, the behavior of the Multi-Pattern Matcher (MPM), and the idiosyncrasies of HTTP normalization. This report provides an exhaustive analysis of Suricata 7.0.x HTTP rule syntax, focusing on detecting specific HTTP POST requests through advanced content matching and regular expressions.

**Understanding Sticky Buffers and Rule Scoping**
In legacy NIDS engines, analysts appended modifiers to content matches (e.g., `content:"POST"; http_method;`). Suricata 7.0 entirely deprecates this conceptual model in favor of sticky buffers. A sticky buffer acts as a stateful context switch: once declared, all subsequent payload keywords (such as `content`, `pcre`, `bsize`, `depth`) apply exclusively to that buffer until another sticky buffer is invoked. This architectural decision improves rule parsing performance and eliminates ambiguity when multiple fields (URI, headers, body) are inspected simultaneously. 

**The Importance of Transforms in Modern Rule Writing**
Modern HTTP traffic frequently employs encodings—both legitimately and maliciously. Suricata 7.0 elevates the concept of "transforms," allowing the detection engine to mutate a buffer's data in memory before applying match conditions. Recognizing when to use transforms like `url_decode` or `header_lowercase` is critical. Failing to account for URL encoding in a POST request body, for instance, is one of the most common pitfalls in contemporary rule writing, leading directly to high false-negative rates.

---

## 1. Suricata 7.0.x HTTP Rule Keywords: Exact Syntax and Semantics

To programmatically generate and validate Suricata rules via a Python utility, the generator must enforce the strict syntactical rules governing Suricata 7.0.x sticky buffers. The legacy Snort-compatible content modifiers (e.g., `http_method`, `http_uri`, `http_client_body`) are deprecated; utilizing them in modern deployments is highly discouraged [cite: 1, 2]. 

### 1.1 `http.method` (Sticky Buffer)
The `http.method` keyword matches on the HTTP verb utilized in the client's request [cite: 3]. 
*   **Correct Syntax:** In Suricata 7.0, `http.method` is a sticky buffer. Therefore, the buffer must be declared *before* the content match.
*   **Exact Ordering:** `http.method; content:"POST";` is the correct syntax.
*   **Incorrect Ordering:** `content:"POST"; http.method;` mimics the legacy content modifier approach. While Suricata's backward compatibility layer might attempt to parse it, it violates 7.0 standard practices and may trigger warnings or engine parsing errors depending on strictness settings [cite: 1, 2].

### 1.2 `http.uri` vs `http.uri.raw`
Suricata provides two distinct buffers for URI inspection to address the complexities of attacker obfuscation.
*   **`http.uri` (Normalized):** This buffer contains the normalized URI. Normalization includes decoding standard percent-encoded characters, converting uppercase hexadecimal escapes to lowercase, and resolving directory traversals (e.g., `//` becomes `/`, and `/./` is resolved) [cite: 1, 3]. 
*   **`http.uri.raw` (Unnormalized):** This buffer contains the exact, unmodified bytes as they appeared on the wire [cite: 1, 3].
*   **Query Strings and Exact Matching:** Yes, `http.uri` *does* include the query string [cite: 1]. It contains the full Request-URI structure. Furthermore, `http.uri` includes the leading slash [cite: 3]. 
*   **How to Ensure an Exact Path Match (Without Partial Matches):**
    If the goal is to match exactly `/telemetry/v2/report` without matching `/telemetry/v2/report/extra` or `/telemetry/v2/report?param=1`, the Python utility must employ buffer constraints. Since `http.uri` includes the query string, a simple `content:"/telemetry/v2/report";` acts as a substring match [cite: 4]. 
    To enforce an absolute exact match, use the `startswith` and `endswith` modifiers (or `bsize`):
    ```suricata
    http.uri; content:"/telemetry/v2/report"; startswith; endswith;
    ```
    Alternatively, if the path might have a query string but you only want to validate the path portion, PCRE is the safest automated approach:
    ```suricata
    http.uri; pcre:"/^\/telemetry\/v2\/report(?:\?|$)/";
    ```

### 1.3 `http.header` vs `http.header.raw`
*   **Format and Concatenation:** The `http.header` sticky buffer contains all extracted HTTP headers concatenated into a single buffer [cite: 1]. Each header is separated by a Carriage Return Line Feed (`\r\n`). Crucially, Suricata does *not* include the leading CRLF from the response or request, but appends `\r\n\r\n` at the end of the entire buffer [cite: 5, 6].
*   **Syntax for Match:** To match a specific header inside the concatenated `http.header` buffer, the utility must explicitly include the `\r\n` (hex `|0d 0a|`) to avoid false positives (e.g., matching a substring in a different header's value).
    ```suricata
    http.header; content:"|0d 0a|X-TLM-Mode: exfil|0d 0a|"; nocase;
    ```

### 1.4 `http.request_header` with Specific Header Name
The user query asks about a `name` parameter syntax (e.g., `http.request_header, name:"X-TLM-Mode"`). **This assumption is incorrect.** Suricata 7.0 does not implement a `name:` key-value parameter for HTTP headers. 
*   **The Reality in 7.0.x:** Introduced in Suricata 7.0.3, the `http.request_header` (and `http.response_header`) keywords allow inspection of a single header natively, addressing issues where HTTP/2 traffic utilizes pseudo-headers and different casing [cite: 7].
*   **Exact Syntax:** The engine isolates each header individually. The header name and the header value are concatenated in memory separated by a colon and a space (hexadecimal `|3a 20|`) [cite: 8]. 
*   **Correct Usage for Python Utility:**
    ```suricata
    http.request_header; content:"X-TLM-Mode|3a 20|exfil"; nocase;
    ```
    If you only know the header name and want to use PCRE on the value:
    ```suricata
    http.request_header; content:"X-TLM-Mode|3a 20|"; startswith; pcre:"/X-TLM-Mode:\s*exfil/i"; 
    ```
    *Note: Suricata normalizes the separator to `|3a 20|` even if the raw wire traffic only had a colon `|3a|` without a space [cite: 9].*

### 1.5 `http.request_body`
The `http.request_body` keyword is the modern sticky buffer replacement for the legacy `http_client_body` [cite: 2, 3]. It matches against the HTTP payload transmitted in a POST, PUT, or PATCH request.
To match `blob=` followed by base64 and `sig=` followed by 64 hex characters, the utility should first use `content` to anchor the search, followed by `pcre` acting on the same sticky buffer. (Detailed construction is provided in Section 3).

---

## 2. PCRE in Suricata Rules: Syntax for Body Matching

Perl Compatible Regular Expressions (PCRE) provide powerful pattern-matching capabilities, relying on the underlying C-based PCRE/PCRE2 libraries [cite: 10, 11, 12]. While PCRE allows for immense flexibility, it is computationally expensive. Suricata mitigates this via the Multi-Pattern Matcher (MPM), which evaluates fast patterns (fixed strings) before executing PCRE [cite: 13].

### 2.1 PCRE Modifiers vs. Sticky Buffers Contexts
Historically, Snort and older Suricata versions appended single-letter modifiers to the end of a PCRE string to specify the target buffer. 
*   `/P` targeted the HTTP request body (`http_client_body`) [cite: 13, 14].
*   `/H` targeted the HTTP headers [cite: 13, 14].
*   `/U` targeted the normalized URI [cite: 13, 14].

**Status in Suricata 7.0:** While these legacy modifiers are still technically supported by the engine for backward compatibility [cite: 5, 13], they are **strongly deprecated** in modern rule writing. 
**The Correct Syntax:** PCRE should be used as a payload keyword *within a sticky buffer context*. When `pcre` follows a sticky buffer, it inherently operates on that buffer without requiring the trailing `/P` or `/H` modifiers.

### 2.2 Writing PCRE Within a Sticky Buffer Context
When writing a rule, declare the sticky buffer, then declare the `pcre` keyword. 
```suricata
http.request_body; pcre:"/pattern/i";
```
The regex must be enclosed in forward slashes `/.../`. Modifiers like `i` (case-insensitive) or `s` (dotall - dot matches newline) can be appended after the closing slash [cite: 13, 15].

### 2.3 Example PCRE Constructions

**Matching `blob=` followed by at least 80 base64 characters:**
Base64 characters consist of `A-Z`, `a-z`, `0-9`, `+`, `/`, and padding `=`. 
```suricata
http.request_body; content:"blob="; pcre:"/blob=[A-Za-z0-9+\/=]{80,}/";
```
*Note: Because URL encoding often converts `+` to `%2B` and `=` to `%3D`, analyzing the raw `http.request_body` directly with this PCRE will fail if the body is form-urlencoded. (See Section 5 on `url_decode`).*

**Matching `sig=` followed by exactly 64 hex characters (and NOT more):**
To ensure the match is exactly 64 characters and does not match a 65-character string, the regex must utilize boundaries. Since this is typically within an HTTP parameter string, the boundary is either an ampersand (`&`) or the end of the string/buffer (`$`).
```suricata
http.request_body; content:"sig="; pcre:"/sig=[0-9a-fA-F]{64}(?:&|$)/";
```

---

## 3. Combining Multiple Match Conditions in a Single Rule

### 3.1 Logical Execution (Implicit AND)
In Suricata, all rule options (headers, content matches, PCREs) provided in a single signature are **implicitly AND-ed** [cite: 16, 17]. The rule will only trigger an alert if the TCP flow characteristics, the `http.method`, the `http.uri`, the `http.request_header`, and the `http.request_body` conditions all evaluate to true for the specific transaction.

### 3.2 Multiple Match Keywords within the Same Scope
A Python rule generator must be capable of inserting multiple `content` and `pcre` keywords under a single sticky buffer. This is highly recommended and fully supported. Once `http.request_body;` is declared, every subsequent content modifier applies to the HTTP request body until a new sticky buffer is declared [cite: 1, 2].

### 3.3 Constructing Multi-Pattern Body Matches
To search for two separate parameters (`blob=` and `sig=`) in the same POST body, where their order might be unpredictable, use multiple `content` and `pcre` keywords within the same scope.

```suricata
http.request_body; \
content:"blob="; pcre:"/blob=[A-Za-z0-9+\/=]{80,}/"; \
content:"sig="; pcre:"/sig=[0-9a-fA-F]{64}(?:&|$)/";
```
*Engine Execution Logic:* Suricata's MPM will search for the fast patterns (`blob=` and `sig=`). If both exist in the `http.request_body`, it will execute the first PCRE. If that passes, it executes the second PCRE. Relative modifiers (like `distance`) are not used here, meaning `blob=` and `sig=` can appear in any order within the body.

---

## 4. Rule Structure and Syntax

A valid Suricata rule consists of three core components: Action, Header, and Options [cite: 16, 18].

### 4.1 `alert http` vs. `alert tcp`
*   `alert tcp`: Instructs the engine to evaluate the rule against any TCP packet/stream matching the IP and Port criteria [cite: 16, 19].
*   `alert http`: Leverages Suricata's Application Layer Protocol Identification (ALPI). The engine automatically detects HTTP traffic regardless of the port (e.g., HTTP running on port 8080 or 9000) [cite: 19].
*   **Which is correct?** When utilizing HTTP sticky buffers, `alert http` is strongly recommended. It acts as an implicit pre-filter; the rule will only be evaluated if the engine has successfully parsed the stream as HTTP [cite: 16, 19].

### 4.2 The `flow:established,to_server` Keyword
*   `established`: Ensures the TCP 3-way handshake has successfully completed. This prevents attackers from spoofing source IPs to trigger false positive alerts (since they cannot complete the handshake without intercepting the SYN-ACK) [cite: 16, 20].
*   `to_server`: Ensures the engine only applies the rule to packets flowing from the client to the server [cite: 20, 21]. Since we are inspecting an HTTP Request (Method, URI, Request Body), the traffic flows inherently `to_server`.
*   **Requirement:** While not strictly mandatory for the engine to parse the rule, omitting `flow:established,to_server` in TCP/HTTP request rules is considered exceptionally poor practice and is universally mandated in professional rulesets (like Emerging Threats) [cite: 20, 22].

### 4.3 Complete Working Example
Below is the synthesized rule addressing all parameters of the prompt. This rule assumes the payload is URL-encoded, necessitating the `url_decode` transform (explained in depth in Section 5).

```suricata
alert http $EXTERNAL_NET any -> $HOME_NET any ( \
    msg:"MALWARE Detection of Exfiltration POST (X-TLM-Mode)"; \
    flow:established,to_server; \
    \
    http.method; \
    content:"POST"; \
    \
    http.uri; \
    content:"/telemetry/v2/report"; \
    startswith; endswith; \
    \
    http.request_header; \
    content:"X-TLM-Mode|3a 20|exfil"; fast_pattern; nocase; \
    \
    http.request_body; \
    url_decode; \
    content:"blob="; \
    pcre:"/blob=[A-Za-z0-9+\/=]{80,}/"; \
    content:"sig="; \
    pcre:"/sig=[0-9a-fA-F]{64}(?:&|$)/"; \
    \
    classtype:trojan-activity; \
    sid:1000001; \
    rev:1; \
)
```
*(Note: `fast_pattern` is placed on the header content, as `X-TLM-Mode|3a 20|exfil` is highly unique and serves as an excellent trigger for the MPM to quickly discard non-matching traffic [cite: 17].)*

---

## 5. Critical Pitfalls and Edge Cases

Developing a Python utility to write Suricata rules mandates strict programmatic guardrails to prevent common logical errors that lead to false positives (FP) or false negatives (FN).

### 5.1 Ensuring Exact Matches in `http.uri`
As established, `http.uri` includes the query string and the leading slash [cite: 1, 3].
*   `content:"/telemetry/v2/report"; http.uri;` is a **substring match**. It will erroneously alert on `/telemetry/v2/report/extra` and `/api/v1/proxy?url=/telemetry/v2/report`.
*   **Guardrail:** If the Python tool accepts an "exact path" input, it must generate `startswith` and `endswith` around the content. If query strings are permissible but the path must be exact, it must generate an anchored PCRE.

### 5.2 The `http.request_body` and `url_decode` Pitfall (CRITICAL)
This is arguably the most dangerous edge case in Suricata 7.0 HTTP body inspection. 
*   **The Issue:** Unlike the `http.uri` buffer which normalizes hex-encoded characters, **the `http.request_body` buffer is NOT URL-decoded by default** [cite: 23]. 
*   **Impact:** If an HTTP POST uses `Content-Type: application/x-www-form-urlencoded` (the default for web forms and many malware implants), spaces become `+` and base64 padding `=` becomes `%3D`. A PCRE looking for `[A-Za-z0-9+\/=]{80,}` will **fail** because the raw buffer contains `%3D` instead of `=` [cite: 23].
*   **The Solution:** Suricata 7.0 provides the `url_decode` transform. When declared after a sticky buffer, it mutates the buffer in memory, replacing `%HH` with its ASCII equivalent and `+` with spaces [cite: 23, 24, 25].
*   **Rule Generator Logic:** If the Python utility is targeting parameters in a POST request, it **must** inject `url_decode;` immediately after `http.request_body;` before applying `content` or `pcre`. 

### 5.3 TCP Stream Reassembly Requirements
*   **Does Suricata handle reassembled HTTP by default?** Yes. Suricata is a stateful inspection engine. It automatically buffers, reorders, and reassembles TCP streams before passing the data to the HTTP parser [cite: 19, 21]. 
*   **Config Limitations:** The extent of this reassembly is dictated by `suricata.yaml` settings, specifically `stream.reassembly.depth` (default is usually 1MB). If a POST body exceeds this depth, Suricata stops inspecting the body. Additionally, `libhtp` configurations define `request-body-limit`. If malware pads a POST request with 2MB of junk before sending `blob=...`, it may bypass detection unless `stream-event:reassembly_depth_reached` alerts are monitored [cite: 3, 21].

### 5.4 Modifiers: `bsize`, `depth`, `offset`, `distance`, `within`
These relative modifiers are fully valid when combined with sticky buffers, but their scope is strictly isolated to the currently active buffer [cite: 1, 4].
*   `bsize`: Enforces the exact byte size of the buffer. `http.uri; content:"/test"; bsize:5;` [cite: 4].
*   `distance`: Instructs the engine to look for a content match *N* bytes after the end of the previous content match [cite: 4].
*   `within`: Instructs the engine that the match must occur *within N* bytes of the previous match [cite: 4].
*   **Pitfall:** Attempting to use `distance` or `within` to relate a match in `http.uri` to a match in `http.request_body` will cause a parsing error. Relative modifiers cannot cross buffer boundaries [cite: 1]. 

### 5.5 Common Mistakes to Programmatically Prevent
1.  **Missing Semicolons:** Every keyword and argument pair must terminate with a `;`. 
2.  **Legacy Keywords:** Reject inputs utilizing `uricontent`, `http_method`, or trailing PCRE modifiers like `/P` [cite: 1, 5].
3.  **PCRE Delimiters:** PCRE strings must be enclosed in quotes and slashes: `pcre:"/pattern/"`. A common mistake is omitting the slashes: `pcre:"pattern"`.
4.  **Unescaped Semicolons in Content:** If a content match includes a semicolon or quotation mark, it must be escaped or written in hex. `content:"key="value";` is invalid. It must be `content:"key=|22|value|22|";` or `content:"key=\"value\"";` [cite: 16].

---

## 6. Command-Line Execution and PCAP Analysis

For testing the generated rules, the Python utility should interface with Suricata's command-line interface and subsequently parse the output telemetry.

### 6.1 Running Suricata from the Command Line
To run Suricata against a PCAP file using a specific rule file, the exact command and flags are:

```bash
suricata -r file.pcap -S rules.rules -k none -l output_dir
```
*   `-r file.pcap`: Instructs Suricata to read offline from the specified PCAP file [cite: 26].
*   `-S rules.rules`: Loads *only* the specified rule file, excluding default rulesets defined in `suricata.yaml`. This is critical for isolated unit testing [cite: 26].
*   `-l output_dir`: Specifies the directory where logs (`eve.json`, `fast.log`) will be written [cite: 26].
*   `-k none`: (Optional but recommended for PCAP testing). Disables checksum validation. PCAPs generated via `tcpdump` on the host often contain invalid checksums due to TCP Offload Engines (TOE). Without `-k none`, Suricata drops these packets before inspection, resulting in false negatives during testing.

### 6.2 Reading Results from `eve.json`
Suricata's primary output is the Extensible Event Format (`eve.json`). This file contains one JSON object per line.
*   **Format of Alert Entries:** To identify if a rule triggered, parse the JSON file and filter for objects where the key `"event_type"` equals `"alert"` [cite: 27, 28].
*   **Locating the SID:** Within an `"alert"` event, there is a nested `"alert"` object containing the signature metadata [cite: 27, 28, 29]. 
    ```json
    {
      "timestamp": "2023-10-25T12:00:00.000000+0000",
      "flow_id": 1234567890,
      "event_type": "alert",
      "src_ip": "192.168.1.100",
      "src_port": 54321,
      "dest_ip": "10.0.0.5",
      "dest_port": 80,
      "proto": "TCP",
      "app_proto": "http",
      "alert": {
        "action": "allowed",
        "gid": 1,
        "signature_id": 1000001,
        "rev": 1,
        "signature": "MALWARE Detection of Exfiltration POST (X-TLM-Mode)",
        "category": "A Network Trojan was detected",
        "severity": 1
      },
      "http": {
        "hostname": "example.com",
        "url": "/telemetry/v2/report",
        "http_port": 80,
        "http_method": "POST",
        "protocol": "HTTP/1.1",
        "status": 200,
        "length": 15
      }
    }
    ```
*   **Extraction Logic:** In Python, mapping `json_line['alert']['signature_id']` allows the validation engine to assert that the specific `sid` passed the unit test PCAP. The presence of the `pcap_cnt` field (if testing a PCAP) will also identify the exact packet index that triggered the alert [cite: 27, 28].

**Sources:**
1. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFIQz8NyDnbjWgFyf0bzzB7Hc0hvQ4Rlu6CwOEmT4f2UtB6N_4Al60_nO8d01_y2PiWPxhuRJm6P6z7MlNbMsU5gmLYMdQOZreFx_ytm549WfATDf1lqHpd0wFpgtCzKczoN3Jx3MgbpbcT-Zq9zh9KEvJgn4dRLaAq_Q==)
2. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7TK78IM-Wrg2jGCgDILAR48lD0MFugUO196bLtT5Q-sQFB66gKSmPLOWlfqgPNq04PnatTcjzAOISZe6VAvuR4HNbRw8yswoEeXH_KuSshVbJefRjlZ1FFLQyLOyJt3drtSkS7k4BcwGOehhm7UES67fAC7qnxr4OKw==)
3. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEcyl5qR__zuc-NmdKLsiklXql_6HZGHVcTIIllF1eGdPwU3GvsgQojvP64SzPRfblbpKMPWM82uDtEYq5lSBKDI2tUWwXfjgky86_3ecFjx8Qx0in6VNTbWyLDHFqo8Kp_JWcnvKNXaAEEWcgzGyAgvA==)
4. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFRpLSn5WJmjbWytoUf6ZnvJn8Goxbri5V7BigKNbTRc0i85HQjPCzEhJoLVtyfrZCxNf9ydFx2X4lnlc6NvrV9VxJWz5uJpTRMR0Z5KHB-3NIjUqg6LUJYyEkBrzepN3so2LQZnktgdgE8CFwtxV6Up85m8g==)
5. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF__Ea8nLgC-BLNNnThgs7PUc3mFjXWSsKsz9JI7oD_gfsnZIagGv8uf6AWX_6DXwCcxz_Wui5HLnIdEi8NFR_zKt8R6kVeUL1ld-QIWYmzgH3rsZTFpFm05cTv3y_jP0vkCsE2NmlgmjPbx-L00T1HOLMf2gPbE8SR_Q==)
6. [emergingthreats.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4FjwgxdCVlmkI7HBNVD7qcOZ2A593XeVCuxSAxhfCJI5ilqza5Fos-rqBrJe_eKxYDgcoVkyuLJlWdfyArIU7JBuEUgTePoPQlrEi2eh_Tc161JeJYBEpikJgOeupuI3GZFq4dAkjN1nOMcvl5ka1v8AJTcp7gRGBc59pYRCaq0-xjMCsGTiw57ZiPVDcoXlANptjpWftuDQ=)
7. [emergingthreats.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGkWqdCUD92B_4Xm_GSE2g_9YavCpjcnLWSxwcwK3yQqo0xPy8Vl_AvOXJga_Y4WMm83f4X-ZX9NgqZwr_CNGvgmFb2kTaJIi440vHLV20E-cE3vdzmqYu79qHHhOuBx2ZloPtep10iPkit7W2dBLqPSJmuwLHOmu7Osqy3ww==)
8. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZkzVWXuiLWsqogoL8Uc9kmv8KsQZckQnHBJUoYMt8LL8DEpynn1CUtl0oDo2HsrlFi_Cmx81runaHUyohMHtc0QUVTnsg4or7LHQmZbw6A6x_lYUTnw5-TKgNvuyXhH3IUhIYOZZT2Igyd6YVHSqrkhbbopd2EFLX)
9. [openinfosecfoundation.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjkfMXYO4SMOjebBAZ3xV5UFAB_h1UxQ4PTVHfzBtQiSYv84WbZ2xsAbf9ql9_DU7Kg84qTNh_wOcGRokFE-jDSulb5PJ7YzqTPhyBKVF-BUtv-YFDQZWlOTDxZYdL8tX5xBaZufqDgdiNuA==)
10. [pcre.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpgadpWhD-1QpvOlYsLSuRnntuDNrVFFitJiPLIB_44USYcsAJ6yy-ZhDMsGgJf5oMvRBcG2IRWjmzeqDGhR7OyjVqdKsobhKU13k=)
11. [regular-expressions.info](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaFpV7pPfmbeRUIaeAdxKLHMGic6IDEZZhrN9bKThRQEDEL37mwTxulsEiJ2XFWQyYtS1gfdt9cmrnq3Ji5fHbqp1xTPDaY0Z5OwBY5cprpKuZyXawpHrqIDSFsD5OwyBqKJ0W)
12. [wikipedia.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGK8GxxUV0fYmIO_TzYXHl5Oam6w9gV4sp6WDp6Z-82B83JBwksE0M8SsM8gRTzA25vmRnsZlRPoLzHkjwEkcHeER3CVZ1BUW_kNmn3w2S2qRWhe2bWpzjnc_vUUbz7eEH2f_wewMGsW4W7uXjeUqhX2-JgLlPkg==)
13. [openinfosecfoundation.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdfO-zjN8SnkEjaxyYMxfRZpw02VJITpWKu8eiHgnKiUmRIHMgCoYIly18NKbSXuolUw8EyIG4XPzejG6fHKp03daCiwrrZt8P8Bz6mHW0X2UGUivEtVnGtAgVav1im_XKFa2luwmzitms58MvcTg2xB-h3aKEub5Ju_FxdX96E9GO3zPFvCpKON14kpVhZVYEMqXPex_Gcyy6iGYt_wSLJw==)
14. [cisco.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCIBpFoEu-cIhvfW8XB_rPRnRC0Stv3G8awH3UuihkUqHPpYEUntLi5htnB8ql7jKZNGZOXKzo1t0FFTnd_NY0ModoX8InkHfrDMLo_Zkyy2TqZpPZoCkO1ZVAKUtQShBMlBXv2KymiColscdfQCy_05vZZkQcS-yJ5s5bJnUS)
15. [php.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFw4MuUhBJTmtKEBVqBmASMvuVj_ZbN2MrA3F4etOCwjORvMtT9hzls9iWecNAvQxeMuC_sqb8B-bNFIk3t2gEYnV_8f-gu3Kn-aIZ169UVGHlZ52qthFjgFCfE-Z_FYHHjQI0uS2bE5IUrc5VoWji8SQr9vQXM7RI=)
16. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHATL8QKd4h66kQnjg12fVK8v5rb-ckbkYnp1HHNQQE9RhTmJON2dltGbgGB7jKvqSJ-2CJ8KuDh3buruftXIuwF0DieVfxC6rnK2IlUzSTz1ueK1rDwM0MlH_UFakZ_eRUK5j6ESs_cRQ85dR7oYvKuQc=)
17. [b4y.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHq3Z_WVs_QTNQKpef1EILOAJV21DZiw5a4XFktt2K9qtB0bcUltfTAxW6qNxARGrT7BEGEM1NE_5oYBHLW1Qttc2thKkpKcm0GVQ0dt8YjEYiBqDNWDf7SHyLc1jURtw==)
18. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGvwrBzYiT50GcZHgEZn36MBSVYmLIpWC91SxgLoCN6mUXT6Novn2XL1dvdKQQnwTOaJtw3HBr0CPyzBgi6W5jhoo6Xaz0rgSMjSvIPAsnZyd2j3EIjLbFKTgyope-Gc6jHhaGTGbSr4P0=)
19. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE5PKv2rgz8IabmvczJsLWBLx7E-3F7cqJ91QqRyc7Gbo6WXa5JalsnwpSZPJH4cksjtnRyMfMtnSLzq4glNC-iynOXvPlbBGGYMLrgJUvBUfBqGZcBFcS-UPAS_tLHuq9tN97p_KjhspUQpbPP2_3kw_5ioUD3v5mZa5GLkPkNe6kV_Q==)
20. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_Ot8IKY2-C9RDg1fm-XZ1h13r8ake_EMSI09ecWZIkwUIQ8wuz5gIrw4nHhPzwP-eleIk8mFAh0xOfBwBNvWhaBPBIDPxgH71ZBnFiDtuCfGzj67BFKODXD9JU7xWuDdXOH1vpI2qeY9EwIlS)
21. [amazon.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjgi16Bc5MH2C5DHhgGz96JI5-67bfjkaqz31BfIzuyqFWuP2lyMuYlRALj8Us966g6BnDcXBXnc055NtrLK-faD2EBAhmtoqHhUWCI45cse7CgvAEfGMwy6AhyAbbpi4aD64mlIzjiHmwmkmH-DR3y0wvanx2e3-kMCmj2xh4f4ghQYjJR6wEweclrdiqbWhM1Xs=)
22. [emergingthreats.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEK6K0fgfyQgik8iUdeI7mfFWiQIYnuQOswcDw22tRXw1PFXLl80iwAMjmmaZMOAJcFqP_2QPN0NiwaSuXAYW7a17H9J3foN5UAaShDISy_k5QsgQXnAlj_4XCz7V8BU7CCnaEK3E5WSF3euvkYEMOkbsAkBXQdz3eGaE-u-bdEGQOZfGugwJoM)
23. [greynoise.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHn4xUIeNqBfrj6w04m7jS7COM_p97OxJL_YsjwwHsoghtafNnwbSWK8pbCMeMRqi3x75EBdWHofzXm8aCl50KjVAwW4A0P54IhkATIETdP3NePJlBvZeisLpZZUZsLY694YZqw5Q8peqPHY_nAbHrxDYZqFhYcGJGIeDnXIks=)
24. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFscu3ggx-FSbbBlw3idxHeSXDHmrIrzptAMQpqSxKcWO8xvz2FjWSFZBPXbXPxUhIfKtPbgDs-7O9qxhrbXXREnJsbKIg444ijm5rX3KVS62npSk6i6OdD6fxI07BID6WFT0pySgOrLxK3C8WEgA5lALH_NF0uUg==)
25. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7AKSmPS16sLUHqgBns48VpZB3mqAe9PcUenj0Uzspqq5_7X-JKmFOzu_WgIRI3TcEZHK3QQU_t1r6QGmomsMKytyaXiSksm47wuXtYLQPeRuOxCFpQKq1M0J_TJo1uefQhxRR7BQ1PQFc59SPtGLClm58KE1gYg==)
26. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE4TWe7XYfS__70BxXE6mT33unMwQdzAUuk_KHpg-YXoxCYcp0nbmSaXoTUej2RwZUpUxhW9s7fl6ZSkzIZHkzVZxGOObreem7IffCGRAvvwY7rFoHVFEQjiIzLGp6fXaVKvoaW1A_Kpm2A_DqV-EQz_0NOz7hoG9NnAQlbxyJCKrNYKb1Ks7d11B3BzA==)
27. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOOcyI8pAenfIbrZVW95CCpfdfEF35cY0DFn-fHYMM0Zwltoqx7nNiGZLBK2dilOsyVE47eGkWl-5b1s91aqLEKizEeLqR-Y5srEwgpirP6sPGZpGhC0hmNJxRzB8yAvvLI5VJCJ7OvwmfnRW-a05IqkgxEOxLD3c=)
28. [suricata.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMEoMrdHHOAA0VfeSYvwiUneAc24IGTfl-zZaewj-2UVDfvFD4FHvyapHd-wdqc-BubpC9BppeAI3kJdiyjZwbkFRP371sPIPd6HcDb0uh4v1LQWaUHaHrqQTFfoE4oY5RVfRw0s5uEQvejeGWVdiT1YIv1y_opJSHUN1blbbWxKU=)
29. [elastic.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFcBi9RS44udCwLy6-fU_NEvArxou4y9hxi3qLJzKs7vusmc_jJPVEvRDdg8ddgkH80m2dT6fg6Z64_dvZIN3ChjJaTczqG4WxI2N8RInheZVB6vbtRsHkB-VqIxKm8keW3oafurkMvSv8a9Tp9goYs66Jr3RqBs3BbnSSoyVhngvqzYg==)
