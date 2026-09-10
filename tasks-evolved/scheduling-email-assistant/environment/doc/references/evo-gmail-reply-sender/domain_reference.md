# Domain Reference for evo-gmail-reply-sender

**Responsibility**: Authenticate with Gmail API, construct MIME messages with proper base64url encoding and reply headers, format date/time strings per the exact required format, send emails, collect message IDs, and write results.json output file.

**Key functions to implement**: authenticate_gmail, format_meeting_reply, create_and_send_email, save_results_json, format_date_string, format_time_range

---

## 1. Google Workspace Authentication and Credential Management


The foundation of both the Google Calendar and Gmail API integration lies in secure, persistent authentication utilizing OAuth 2.0. In the contemporary Python ecosystem, this is handled via the `google-auth` library family, specifically migrating away from deprecated HTTP libraries to modern standards.

## 3. Gmail API: Constructing and Sending Reply Emails


Sending messages via the Gmail API involves constructing a standard MIME message, performing specific string encodings, and carefully managing Thread IDs to ensure email client continuity.

## 4. Date and Time Formatting in Python


Date formatting is highly critical for string-matching, Natural Language Processing (NLP), and correct API interactions.

## 5. JSON I/O Pattern


Integrating the utility into a broader automation architecture (like an agentic framework) typically requires strict file I/O operations.

**Pattern Specification:**
When reading `test_input.json` for operations and writing to `results.json`, it is confirmed that the API responds with `id` representing the message identifier [cite: 1, 27]. However, the external architecture expects `messageId` per the query parameter specifications. The adapter logic translates this.

```python
import json

def process_email_tasks(input_file='test_input.json', output_file='results.json'):
    with open(input_file, 'r') as f:
        tasks = json.load(f)
        
    results = {"sent_results": []}
    
    for task in tasks.get("emails_to_send", []):
        payload = create_raw_message(task['to'], task['sender'], task['subject'], task['body'])
        # service is assumed to be instantiated previously
        msg_id, thread_id = send_email(gmail_service, payload)
        
        # Writing 'messageId' to match schema expectations, extracted from response['id']
        results["sent_results"].append({
            "messageId": msg_id, # Confirmed: response['id'] Maps to messageId concept [cite: 1]
            "threadId": thread_id,
            "status": "Success" if msg_id else "Failed"
        })
        
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)
```

---

## 6. Node.js Gmail and Calendar Skills as Alternatives


For environments where Node.js skills are pre-installed (e.g., `/root/.claude/skills/gmail-skill/`), these wrappers utilize the `googleapis` npm package [cite: 34, 35]. The underlying OAuth logic operates identically over REST, though the syntax leverages JavaScript asynchronous promises.

## 7. Synthesis of Common Pitfalls


Through meticulous analysis of the Google API ecosystems, several severe failure modes emerge:

1.  **The Base64 Encoding Trap**: Developers routinely implement `base64.b64encode()` or attempt to directly attach a MIME object via `.as_string()`. The Gmail REST API strictly mandates `base64.urlsafe_b64encode().decode()` [cite: 2, 25]. The presence of standard Base64 characters (`+` and `/`) causes instant HTTP 400 rejection due to URL sanitization issues.
2.  **The 'Z' Suffix Omission**: Timezone nativity in Python (`datetime.now()`) does not inherently include an RFC3339-compliant string. Calling `.isoformat()` on a naive datetime omits the UTC 'Z' suffix or '+00:00' offset, leading the Calendar API to reject the `timeMin` parameter entirely [cite: 19, 20]. Always utilize `timezone.utc` aware objects before calling `.isoformat()`.
3.  **Cross-Threading Failure**: Attempting to attach an email to a thread strictly by reusing the `threadId` is often insufficient for third-party email clients (like Outlook or Apple Mail), which index threads via `Message-ID` histories. Extracting the preceding `Message-ID` from the `payload.headers` array of the original message and applying it to the outgoing email's `In-Reply-To` field is a critical step for robust user experience [cite: 26].
4.  **Credential Constructors**: Passing a string filename to `Credentials()` directly will fail. The constructor accepts instantiated values (token strings), whereas `from_authorized_user_file()` acts as the parser logic bridging file I/O to instantiation [cite: 3, 4].

**Sources:**
1. [directedignorance.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGC1FcUo5SjRw0gIYSooww0Pqfs1fj6Eyx1F6FmTwwJkPXSPt1x8GXiI0P_ZHduu881kmjzdEZPWcyfIMaNAtvUGe_mSNq6kTj6k345HR5jczOU_YTphyQcsTeelJaNDgs2fnEufjhKZJijjz8e)
2. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEYOCOU2o5_-jigeY16L_YQ5oMNSdM0HV79c9QEd94aobdAmGVFPkwvLeOUiXGZf0u1thuwoNx-rf_fFyxRP-5CdZaKMrkNwzYq-2MiqCM_nzoh_2w_pNuGd2lz3gD3_vct1_AnqcTvBDmUYzl6krRlf5gqUMpbw8bh8UgwWb0szniBHTSLna-RwI3eug==)
3. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHkyiRp7I64uGQrU9zpJEdPD862wxYYB_Z4KdeW0cK_XBGZvaYUjNb75bkDXx-orInqJ4SMJNwLSyxs5zWt_W62R4EAdO17QTgk3one8jLgatfmtT0I_MyN3JGn5eWdJb7SJ7g4exQl4S2JiX_o3tIDkVI=)
4. [googleapis.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGglWbytUmlhOlpelfSI1bVIktdKciWOXi5Joy2OW33zpXQzpyVqQio0qZQAIE_ulpXLZ2nszaLRiauvOccyOjiIL11hjvoDXapk0-qLcDOibA48MEAOa0kuj7rplICw3bX72KObJoCfZbB0_w2s6yL8K2YFD9Ncb4z8InqQ_3pZLCSSs3WJjeKzsSQe8Q=)
5. [nema.gov.mn](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_0maMFGsNK4bLNI_mX6Vt8rNZwSX1SUEmWUwwT47fmI9r0tephFmMDyTWWBm3tt0bn3RbLEfFPQiHHzlYIjcd2x5Iqg-w0HMHrwQxkS_7vtMdmm18qQyEjrwrqFY0Dl6f4mlfQbvDXa_C9tsa-PLOmws5ZB4GR7DOyINVimCWcunJtP0C0T8EN_8cyBGTt9_swLxk0rQKNw==)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG2uatiyiwW0SV7dMARjmFXkArj4e9WbbisE9PXc31SYsMExX-f2jJ8eGKwPvlFQ3i-jVWCNHkLIAtxIaAhEgA9JGHoyosRrDR40qnsvjji2xPopG9CAtjdGD9HUzsvsSxQzv7d-W3a1YUDB6gacmz4HiBlYUxmWpG4Mt7IY_vHgtuesfAOM22i2Z3SwZt-QPDKSlptOrp_0yhLm9Hm3IuWOzZ2HPzeGkn5)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHI-R2Yh5hc6khSxP9mheJeeUGc7feziJtRlmPg67WFz_VW9f5Z33nTzuT8qy0qBP25eMM-GVX36oDZP1p_enZ7bJHpVc0RpP1aWocmzNK_SIDy_o2iK670UfeeWEmae2qksCBQ25K-wSUZAV0Hxw56PQkpZ29PZhFOQAuCKceguk8rCUNGAc7mWSyJWeatgMoVRBX8)
8. [merge.dev](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEA-KoqRmUkhDYYNUGmtaYXhqoFj30Yh7jVZuxlHXy7MgDc43ZxlDNJ0uUIvtv7iaBWGIUCY3_GcjVuRHKVXErvrwtM7RtCSoheJJhZXSbNUjeuZWAqP_T3DxrLieLZkXbqjCc9DE4d)
9. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGV1VCGuUDxjVtwpIe3xz3cr4spw7bMB--1T4JI0VGC0MAXIL4BfAax4zJpJLoA1gAsqWCNC5Txn5jepaGDUaVqsGgXnrrknO_lcTfg5VB4Bia7mB8fXrRv1F_1tOcdO1Wu_slw4CqHPPOgY8oDN85oQO3T8iapfczMVi4Bjf7ggXXGZUMz2l6M6k67Oq3ToEqMaCepa4FbRKKHbZ0=)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE7HyqiSdWmGijt_rz--8Rdd_Cy4Ag1U4gt7NIfsLU_h_GBSYmbSSq6SWvRYwkgKz_-dKbS5v22mibyLMfV5GCYJzI9dvFOrsGfrATjy7-tnSTe4RWwozk8J4OgimwWOtenjGmo2BW3007M10PyJVXfKv3cGoIkPjrXlFCbsdOdX9xnvDjDh7t3asmCHpsVRVVb)
11. [latenode.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFSiIJ_m-S7ikr5rtAyHacJ3E1Itd8hUi35Q8UV97ZRzRRMoFO6o3HUA4giu1liQrA0GpyujjffzSz-X5ollzD8twHeNQNfsOm3H3152Ge3Lkr833fgyGmD6KeEWK8y-I0QTD2xxxgQ1y2YzsyDldFU6BHtm1rxObm8muu1-9zWVwipsq_jq1OmcqkQDgQBgcenvb5_4Eci7td__S0nkLk6w0tQDEsdC920r8eTIBhygL8Lg3nXGsLVuzsar8S7DEtrEA==)
12. [scalekit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFn-9jSfm-5_gdaNqUrmNIFrsE4VibdMErWUQUVKFTuj4QgfiQKLzvaycYye9hG5407U8hvTnouoC_4v9qHUBYSj8Q_HzvKoklxVyZGGuwQQiQpPpZhwv0fiwmbPxhBOagReusGSsQL9U=)
13. [tonyaldon.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHufFS5n3JVXl2humAXCkQ7NcMbuIXnJ-5R5ekqskmuibvq4KDvyBiu6TopGmeSmCG392Wl2B5Yop313MbQEUN4rxMZoV52sU5SdtBXh46KGPWAH4QqDsjm5a6muhiUwxO-zpaQgXImRbbYqAF4WVnUoP_8C9J_J7ysXs89-KiwjhlOiBtq1dBmzA2KZ5aqpo26Oi_wc0dWyaqFzt8EZ9EzlH6DwUJdG3i_qjUDtGShGDuc9Z-MOt6EAtr0)
14. [qxf2.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6JwAXVHsfTbDMOpSz9cup7wAzIBOPjGGoPRURLBevY_rOF0Bq8wv3pcA9ab58hhsYl8IP80RHRZpBuPahtHdFoFL5rqhZgHSAwvO_wIll14abM7q5zkd4AH11IMcgugOdxw==)
15. [nishantwrp.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdY0Bt-s9C2jwPmXEOh1b_wyEJu-Urcta6UlUPZoQyLVJFuc4PX5_vNjb-FDV80Ea5kamO_m-ZxkKzSYocfF-3UBSMf5hbPgLK8gLhSErksGU36uIz-nSngxstArQhSruzK1R7w4ebJmAhH4Aso1LYa3k=)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH-KiDZjVMXuHpndxfh5H2_rFJD5Ijr28_1XAPVKAdAUd9SZYm2VPA0LjsFKhG_XvIuydNvwlTOQwFlEC6yLygFkFcy71RcTK-xEqqY5ncqiEJlN5K69hTUQsgH9ke63F2KEuQxOHm2iY1wOs8uox85mlaQyhh4kRj19ExftQS11aVv9dmcyEs25HkItt8Kx7TCIZnDcCK_ZoVIIcLrKHbNtYAnN6tp)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4DXYiP-Fp9vHGC52IllaFANB6QpxnLv5D6lSAI0YoySFA2hDjcxDzi6GQd6mtJjomz2zgb-FShhdhnF9huG2QzRxdALjIhMU-mGCdH14vaRRZHhUTDkbMVImFNQ6bdNZQXm-lBV42uuy5bltK4NiqM3RqoBRMn6MJ0gGqCxEAfg-YQCJr7_N8K_7arAz5ZTgMdxQV)
18. [nem.ec](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOG1z5wufFcIahUI-2ZK_1ZJ0iUbnFl5nrsxgN0N61i_9P9gerbMTLb8RYFegn0U7nzqsaZ0mf8zHi8WnXg6K1HwQseBsp58idXLKtHIU0QKf0FXk36_onJ5uJ_LS0ydFFB9BuLX-LbKavvTPEsw==)
19. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUkTHCRWObN2qdvOYFlfv0dXHtc2Yib1ZzuSXrIfAuw8ndLaCiKlrKGwDbB2ZV2gFCfDc787iAzGtoXzTjQG2DGTYzqZ0QAUJuLRz0F3azzfoQ8NCiMQSnCBSS3M_W2OrsFl__tl_j5YHHw2pXfmLSDpkWVFMGTmGnkeK82WSrHN9bUEiEi355hBgKUBC1sHpoBa2kVQbDZVD4V1GN1OtOBnMJLMaW)
20. [neura.market](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGtzir-9oCuIVDSUw3z_Q-uXBhfE6gn4dHknrEVRtTyaTeM5tlf8k-HM9fJs6Adpsms2ho432K-FeBgAWXxVehOPVe58v0zqNnaYXvFwsqUdV3tVOB10gmeIcMxTkM5ibfvr69OAGxCTWiuqVemyVErjdPzUFg=)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNRc4jGQz3n0RMKQVY3OCbdZSRHdxhRK7Y-rjmA3U82JJeYg-uwJQiOsix6A2apZSdY1zzfIWOzMsapEilMmdG04wTyd7PZp4C3DaPMDHcjVeiuIkeZF8ws9CtBKuyKvFm7TAQQ4FOjk6apLXUqhOCmQnGhq6_pI0qVtl_nlWrpF9SDePW0LT1A7towubbkUeie-vWl0AZwZllaDYJC2rAwju9-g==)
22. [qiita.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFdJi0QRnZ-vTHDLbzOVrLs4iMHDiJsGK3N-y4sscdjPBlHmfQvw1und5b6WBb-GZm2M0gASQ7IswjVOm4JgF2t5YxrQ-RR3FK6Vcme4Z4AgoUa2VwAfsT8IJHOWKq79CAVf6SH8rhwQx245g==)
23. [blowup-bbs.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE99Uw7Q-EPs7Fr6OhCjbFYu-O2Yx-egSbuoW1BSg8it3q68BF_Wya3QtkHqbyPjAc9tYEeAX-WZKyMwIHjHafjHKMMSHiKnLvYipXQXTd9NiEa2eYtPAE7Wymj3qeThIxqyoGkS4Kw42_V0_zEVBJdhDg=)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENfbfm25xllMOIhHUCv36shpKX-4oH6am2eJruYg9Eu4Ubrq2FsT2z29rc9kVzmll4oXKLPnauE4InLJeW7rehn7LIinap6IiU8k6AYMHg2KnmQn4svD4gsvd1bHN1W2R_CoO_9wuCg6zqSjBQSwYzrOw8XVrYaMjLXsj56V685gSxQNvhBn3OkCfDM18sROpR)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHm57_8nXAeWSP7rDejy1WIfNr2tuXYmtRqAedSYr41R-dd8f_qNqHkpWZHBwVyZUwnD_bRyymNnk1f96m5KqW0lr8br43-mSygFgczeiTfQLs6Acz3T2s_XVjhqZoofZI5YwuVhHe1Y8fuDVWheEaE3-sDY14CaJAgJdara46DaGnfRHzPnKcehaSho-zH8TGHDrVRNZ15MijLFzPTtu9zyBtUQbvGyTgIcmRa)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6AgvKMRqNwbm5tXwcbIUm0RtRnZ8Qa87f1G3-yH--KE4rbfZQivIH2ouw5bLxqO_06ZSvQ8Bv4lBf6F5O2wMQEDjUbNWC2uwEiseuaSEFug4EDiRcTnMkzSxz3EBQq9g4zOrBvAJRxXRIjyaWMvoedM79FvKYVQgftm0ZtCdz5KLTvvm7kaQ=)
27. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFXJob4OnpX35XIpD1XKsyC5cGHnF_EuTeU_x_zaZrqgYSwd8pvr7Ad7u3EUB6vz24KxHoQYi2JeQvU1TUUs0YMePrMNrp4gMDdjzJGKb2zzsh_KgS2VvMcwt8NZT4PwldPOO-iS7Iu5eikEyiHNyejLlCiu2o6wYhMVaT7NjACjUdP9i1ahNp-2AIKhAAxk9YgXSmAjaevqNzXAA==)
28. [mimo.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVAAsZGgjhwSQ5fPZJnsQqXb-8flOm11fI7VFCDyJ91dW26dL3bHxeHjAP8k1-kU6o4aNkUAH58c20cmpyXUPnaHZ1X25C-mD4IAxXjvneBqUf8zQB5Q4rJNYuXuqL)
29. [programiz.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHGL62LJNFLu7YroUO5tjuv5ZQGf_MM7s-rPMbrwBGRO4FRYJyvTFoeG301Bkhmg_w5KviKaOYSSqsZSGh447NsF2vEP-OHdMQJ0-h0gakGnoKQIyzuv0kwVswOHR5IeKNcTOvTtBYT1NZDFg4dEnAC2Gr3)
30. [w3resource.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEEo1KMThd2r9xnsktjelTNtxsiAnvUataJl86h98T1UEHoYm28ucoEoE2TblbhE2U4mFd8P9O8fHLZaNUKeKx62aeanhGjKcus9hs4EUFreMzjPuPLXvLGEzAGvl6dKQhMq4OMLUDwbUc)
31. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqATvxas2l8U_E3_Seq__Sx2F_rVtpIeX4F1zfP3223_nzsyLa7h-wtUQc7ib4e1pVVaZbJfjkIkEE3Dokn0Dymee9NG4G2bRpZut7el7aLw_vmTWF2yD0QJ4GYZAuPtjX68iaqcK6vCXfRqjWzXFu-DI4kYABziiOzpIxMvCzQM1O3miRUX2Y4g==)
32. [foursquare.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHc5sTREanX7V7wxk_gmHjpO3T5MyETb2XfktMIOQBf-2KDgks9oSCT0C0O6TJDl5e4IppjOJ1HqYSMLUDkTxrI5hw9MDzPspl2eGpUijkBUXegbxlBiyUxqOGf1R3QWBn4hxZsqSdj2auB-SMCDjw9UK8YHULCv0-5xe74kek=)
33. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_7Ma2w3PmPRxU82y6VaJSIH2Z6bqk3bZz6M35NQPaXiTnUzxBfzBBPS7f4IPk_WtnJQtutQrZ2BtKbLmvFIj8Ubvf-RFMsl_FOE8H9BLpi4sSt5SJLy0m5yzj8B3na9J050jEKZUgrovf2WLBwR6co9LSongnWWjnGnQNyEfMQSOb_OHgi0W5_q_85Mb9ODGUZQ==)
34. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGBeIsDnnP9B7R37n37rBx7AIMVJZam9oSQmLVOcQfZWZwPIvJm6WS1LAUZS0SH_Qpdx7iSmUoyyt0W9LM2PDCei42hfJxXZ2bbOCo6eK79r5LgG8fU_HKE7UoZPDh7snZ-KFFOCbcLXr14N2PrwYyh6X1Y7qhw9aWcgdQ=)
35. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWTFEd0PmIXJMEBadvEGzswy-aw5GC4qUhTnKIvZMUXlfhoD4FHV5mvblOT6rTs6lN9KZ6KY4TiKNRY2YBySRPQwtnjfQ-cVOzCpHqfQnVoWcZYRefXaExMjLMXT-xwuC1UL-Q7EiaePANXOiRR9LgfhQgC3oQRneMVsR-FmTdPPERhMRw1xXhNjD2ayEYeo23E09bdPw1SM-RTnpW3dfEdlXHoljoKCE9yQWjtHR0y-g=)
36. [michaelheap.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG01ouw9U-FNx4sIfvKPmiQCS25JVUqymzEaG0fdFIpaEM6GvnU2qLz0Dj6doqOBzN-EJFkyjGsA6Ew-5l9P--xV7cA67ahyW09x2EoEuBX-Ogn1yO4KFui_5s28dqmccnYT182IXYSf05DxkztAnDQudo4G6GfwqfhMGPoMQ==)