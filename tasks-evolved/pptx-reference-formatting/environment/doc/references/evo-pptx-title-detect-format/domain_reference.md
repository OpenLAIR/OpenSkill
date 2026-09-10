# Domain Reference for evo-pptx-title-detect-format

**Responsibility**: Dangling title identification via XML heuristics (non-placeholder check, text content analysis), run-level typography manipulation in raw OOXML, text width estimation for box resizing, and spatial repositioning (bottom-center) using EMU coordinates.

**Key functions to implement**: detect_dangling_titles, apply_font_formatting_to_shape, estimate_text_width_emu, resize_textbox_for_single_line, position_bottom_center, extract_title_text

---

## 1. Reading and Iterating Slides and Shapes in `python-pptx`


The structural hierarchy of a presentation in `python-pptx` follows the sequence: `Presentation` \(\rightarrow\) `Slide` \(\rightarrow\) `Shape` \(\rightarrow\) `TextFrame` \(\rightarrow\) `Paragraph` \(\rightarrow\) `Run`. To perform comprehensive data extraction or manipulation, one must effectively traverse this hierarchy while categorizing the encountered geometric and textual elements.

## 2. Typography and Font Formatting in `python-pptx`


In OOXML, text formatting is strictly applied at the `Run` level (`<a:r>`), which exists inside a `Paragraph` (`<a:p>`). While some paragraph-level defaults exist (`<a:defRPr>`), `python-pptx` requires the developer to iterate over runs to explicitly assign character properties.

## 3. Text Box Sizing, Positioning, and Spatial Mathematics


All coordinates and dimensions in OOXML are stored in English Metric Units (EMU). The EMU is an integer unit designed specifically for cross-platform graphic fidelity, defined such that 1 Inch = 914,400 EMU, and 1 Centimeter = 360,000 EMU [cite: 5, 6]. This prevents floating-point precision errors during serialization.

### Heuristics for Title Detection at the Raw XML Level

Identifying academic paper titles strictly through XML elements, without the `python-pptx` abstraction, relies on traversing the `<p:sp>` (Shape) node:
1.  **Non-Placeholder Check**: The shape properties node `<p:nvPr>` must **not** contain a `<p:ph>` tag. If `<p:ph>` exists, it relies on template inheritance rather than being an orphaned copy-paste object.
2.  **Y-Axis Extents**: Check the `<a:off y="X">` element. If `X` is minimal (e.g., `< 2000000` EMU), the text box is pinned to the header boundary.
3.  **Typographic Density**: Check `<a:rPr sz="X">`. If `sz="2400"` or greater, the text is at least 24pt (XML font sizes are 100x the point value). A high font size tied to moderate string length (`<a:t>`) strongly correlates with a document title.
4.  **Bullet Abstinence**: Academic titles lack bullets. Ensure that `<a:buNone>` is present in the `<a:pPr>` properties, indicating the text is not part of a standardized content list.

By utilizing these heuristics inside an `lxml` pipeline, you completely circumvent the Docker dependency lock-out, granting full read-write architecture manipulation over PowerPoint documents.

**Sources:**
1. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFm2bjJgysNJjVzQFq9UXXckLyNDoCK_c4ILit8oP9mkxq2IkqnAYmZE5JeVRgwsvyPtu5wAHTzTkska3PBdpZsuLgYCNHhG2NcynBRE8Oc2O3trUeXuSFS5uEyCqZNWMgJyvU-e3pCNlEN3e9deDVUb2G3IJrDDQch60GnyVCzyKNkPeDdknheG0mLasVr9MevxW20r-YFkjX9L_5OLv22qPSj)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUej6dTh_Ng9PJCw6mXJmaGfTNWrSXmP_EGulgsANU449kAdAFY2Zz4ZB1Cl7DfxsSzpQ43B70_dwPOmK-v_lv-LAWtL4eEgrJC6pQXoBzvTrScf9bksrk9ii5q6_ZgpCBjNPncm3uJDkdQR0VYKzSHkJa8xXQLI16Df1k868IjQnx6uGwe-lSdD-hwe9PlPTm)
3. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHMtEYnLaa6g6XWaDGJktJGqGLn6X_5IH2yM2ng3WGeAg5yEexRusYQGVYBXY1U9h9qaJ61TuSL1t8AjJYshQeoWA2dZq7nLx__ADqR-A0uKukEQhdLQcI6PUmFfK5JU6CPoekee8FNrjVGHr7oLNC_cJn3lg==)
4. [pypistats.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL-poVtpoEgwzF3A2aWGYdNEq5uJggAf_Rpw262lUCBjIjD-CogBt4dtAioHFaqDNrItNEZxcWsotoDvrfyFmQhmADJYYT3WiToWoBDNDtlmtuR9wFXkyygF4Xln8-3lA=)
5. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSeeM23z3k8pFd5hsjIxHTzeDjkj8fp3NQrBDTKj6rX1rqh8g2f-DcETJiXRe2vriEuhtKDvAYcICu4l2ghLHIydiaBoCVcbS8Mu0JsHy0PIjJL0XlPoe5J_4aDwElMaY3XPcXcLz5cCNYYJZOjFg4LFXbpwC_Uw==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTUFwZscKjtRXSJZczNc0iVwvJXn5djqTBDZI-djSDVxHPSiVjs46fpfMHCpaZtipbgYOWKem7W54xNBLrwVS2XloQY1QIVS-JW1XcI_8tWpjQr96tsCB25WWL1S-Ka5y1_3XLZq0MqZzQONr1l6rBuwEEZ7UOVGpxreQBM6FuiA==)
7. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQM2qlYTzegOKOecUkAMC0CB3oDnInY7M0yihrWQgJ4PaivCt3zVX4LpzpPHuDJwvVCb_v4Y4WcKVqBxAc2bS0SxaFRehpRR9hIemgkoy5LFu9Zp8kI0zwoeWAb1HuP-Fk-SzmElX3dwI373Z5UgawCBo8HC1QaylrYuXFfnNggtIgp8_d)
8. [gitconnected.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4K_KanulmvlFY5frKJhfLU6bRl_E3pMXH-ORHVLKm3Jz_wSRMLgIeq7unZ3P0L-X5Rl5X1vWp3iEwqFe0uN6aNfCHLRpeH5E1p6rsIU6vyuPI3JaVTA_igDHS5XTqN1-9dMZK1Oi2sNOMndY8jYaN80-Y5liNLU_83e3l4X3xRrSrjVwY8t4_0FmD-DMd3lQXYykBtQ==)
9. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlYDicqvo5DkeESumdArF7QXjKzSXuGTDJmVPEQR_Lhrzs47eSRtjG9AhRhwFgzg8mo4pZ9US496Rt9BhtZ-IUzlkxW0qdGKJozUbw_ycHUasuYyAuVN8OmQV1FxXGXOChdtLsgrBfeEFpq9VF4qfkM5qWxqonhTvMnJ71JlU2)
10. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOpQjbHgT5DpR3ii_Lhkuu6RO2Fe7hVQmaj9vh4baNoCBZILq6jmQrmv2bM1gpSidVVKP-u6SbkDlMYt47VKpk016Pof7DXfMVv14-FqcS2yPwJgmyd6cViqgX2-_QJzqX)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGiaE8IHjKjOV4EPUEtI5Og4kr4vt4V-SKmLGE-a2MlgeJ416EuVjELQzHSFLoaKkCxkcQvhUn8Gaqkxu63CZydKLjj8EXQTNGJ6o2e-hB1R9ehWcXBWGIGIlyAK_wEYHtAHAv0jy9pDIjAqkQOwhjz6dVyqa2J6NvsFJg3HQ==)
12. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_sc8valN84UQwi5LzkodP37PypeS9SK3XV4iGZ6XSHeuE_Y-7Qyv__rBImW37gMZEsWuYYtIqfh1RNFrKxfD4VCKTzL4KmP9glkZGAoxKa6TAl8HwNC6CKvQcWRil-DfccMtC3g8Vo4NGt9SjAJMpB8W_bkX9gGuIHv6_cQZDOL0h6ZLh)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHWRtnm4kxrThOoWeVpkoa7i1DTLZwkM0C2Rd6kzCIcbxkeNMU_vPd5Em_yNvahBYQhBmABD9QHTqZFKMgiWXnriHh5NTbXBDb8shLmnoVCzTz7GKS5TH3fTQW8ej-QyVUJZG3KxpmRDYzJ3xFo0Nc4qjGs1DDMwZHxyYMfq5ZZ0dmKgg==)
14. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjV8MD1npdK2adE4VY7_Aps5rDbavuN812rN04NKKFjt7k7qPSZpn4mT0OKnxh9h7LkN0RlY7hud6h4KHoqM20srT1DVHc2eWtWjlZtCoNPG8XK2pH4bPg9qj0rel5c2zB5VO9bOHy8DFP_GJ1lDSpT3enZ3nTajAbKgs9ryI=)
15. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGweRq6RIG9vOmmQeDCVi1uXNUfn1tkXH0qD84WE78oZpZ8qVCjVtbH5VQdeUXcIMxTVAj0DMKPCnJqmCjXs4hYjVB4rmJ5jNoBCokI4uOhXbR71Wx8hkg3A__ANVdINz6DlB8YR103fcis3XCJ3HJZcxTACHcQvWLNHPMP)
16. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFC8aRE1Sx11Y3DdYGnHOU9srLCVs4qgYkNpiiIbtLH352PgoxCMGPf6_ammGL62sm0lhbywwh_efFG7fdeyBJVbih4nHpr0nEgQZtbM7u0Zy2VII46jYCiWLrJ4VdTayOLZU_XcmDnF14=)
17. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKhaOxQbk84VPJDG0uc_jtQZrC-ajpO9i4hwFPHEI251WFIrCemV62g61yhJuH_z1xrGCXfCdhs74M7xHgmRNiHhsZEohE7Y3iQzAFXPoZzL_7GBC0Npsj9zI89u1KQsbgA--FLBuxcvxeQ0eW52fH7KhaWGpEw4c3xZKuoz0bMdtn_Q==)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXMLGzWaqPSF2DdB1tX4XSzIZZzFLyBMH6Dp8Vo5RE_qp3ZZE21ByEMPLH1oCdjhR7KW--tPnP4tQBlueRpIsi_FANLHJniqMq57zJImw9Ufi2WlxJwrz55yfxIswU6LwQixu5SO8JCPVFoVmQUFHIhCRdfN1VOVQ9HpLRHZK6DZ7TAF0=)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtr6oE1YaKsu5qNio_0LBFHTsZP2LenGXFTE3uBQi8YZM8VQcMWAWrtevQxXDLo2ffd3dqlLnuu49KUbofAkNny3docJzl1OBqyxS6Ub1--82I-hQJVd9cRMi4ZWHZ9Grm5FXi6wiKu-wo4YtqURjsPKbOS8I6fXJeYXfXqlW0)
20. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFiKLbnuN1HDSGshZ8aNVLe1OlWtHi7W9dvD5Y1y4iFoBJPmE3TYfdHvkWFcmP_GeOg40WtnFxdkWCGnlukwibGjh0Rlgaie1MO5ibQUXMXyZo9e9ko1vGlf17U2MjKEgpsVk6nBsd2_1vRwir37HEdFPgiuQ==)
21. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF_W4JeOCwXeO30DQhmjV8rxO6F0V88X9nH-MNrBGEa-WAMzf6lXGlLqKXPoFTJ4Ap47IZfit7GurIFqriWjXch1KegSE-hjJEUE5rczLrNmm0QBqiyJ9nxRwd_r8FxNNsEp_ss6LYi11HX5m2sR-mWy6ZSa6-F4UMplX_2VyF4ktomftFCN0kfBkuX6DtpNP1J2bLxd-xhlpHZnfwRP4bpMuWCn--Ho9BGKzRM5J_m1KU5og==)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAQt10NEzEHq8pgjQeh4BeFJxxgQ9LkG_8pX1sz0BOaqtwrRX-rxkaxshF2OWBPHQBuNRq-BWhoKaIEavBEeQlgf7au0m5L9HQN8oJtQy7phf4BYigVkfNM6lC4YF77Pq_6au49mRmiNu5bs_AvgKKbeQBwjAdMY80jDjhk4eduoIB2IWxyofVV7BclnBEXJnFlPhjTp32kjko)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE28Z-HvMhKYttVHcNlbPREqAtvppiA0fXVf5JFbuoHMB9kyXLOQiQpCXO0ljWOzrSEaoytM4_Ho9utPAp0f-x94yd4uksUx1wXoSmbZ57c6u9IIROOSU0oVFs2jLN2Wkj7JxBZRYbvLySgtEpJlg==)
24. [piwheels.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNUk68WjQC1la-fvtpbMy0-igpsqAw6r74gyA11XH47_jjHvaezHF3nrK5xfWszkCwX-sFVXfI2umZvawHW3amVOW8By5s4p6d6uid32YD2Y8Rv0KerWoIrAVxM46LRTAxpjw=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnXuCSjfa7y4w2ZHV7mHwdc4ono_wzwZ4IjTJVQG3Rz_80SDvJr9xjRoJhJz-BOWm-XS8CwTYqoBZp23QFu_jJZD31yY5ltidGSyqbP8Z9sZNgsgEy9H0EdlcLvucq6R4qKDAGxkfjF0VyXzl7-Y0BMvbqPA7fhLygvJwhj5rlF40GSaAxJnblip4_-3TQRN1SkV2pVThxmSpNY26J1qo9lg==)