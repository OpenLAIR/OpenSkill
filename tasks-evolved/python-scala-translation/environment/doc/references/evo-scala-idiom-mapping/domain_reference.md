# Domain Reference for evo-scala-idiom-mapping

**Responsibility**: Provide reference mappings and utility functions for converting Python constructs (enums, dataclasses, ABCs, protocols, generics, type variables, overloads, generators, comprehensions, exceptions, naming conventions) to their idiomatic Scala 2.13 equivalents.

**Key functions to implement**: snake_to_camel, map_python_type_to_scala, map_enum_to_sealed_trait, map_dataclass_to_case_class, map_abc_to_trait, map_protocol_to_trait, map_collection_type, map_error_handling_pattern, map_generic_variance

---

## 1. Scala 2.13 Enum/ADT Representation


In Python, enumerations are typically implemented using the `enum.Enum` class. When translating these to Scala 2.13, developers are faced with a choice between the native `scala.Enumeration` class and an Algebraic Data Type (ADT) approach utilizing `sealed trait` and `case object`. 

Research decisively indicates that the `sealed trait` approach is superior and far more idiomatic in Scala 2.13 [cite: 1, 2]. The native `scala.Enumeration` suffers from significant drawbacks: it is prone to type erasure, meaning different enumerations share the same type at runtime [cite: 3, 4], and it lacks compiler-level exhaustiveness checking during pattern matching [cite: 3, 4]. Using a `sealed trait` guarantees that all possible implementations are known at compile-time (as they must be declared in the same file), allowing the compiler to issue warnings if a `match` expression is not exhaustive [cite: 5, 6].

## 2. Scala Case Classes vs Python Dataclasses


Python's `@dataclass` decorator automates the generation of boilerplate code for data containers, providing `__init__`, `__repr__`, and `__eq__` methods. The direct equivalent in Scala is the `case class` [cite: 8]. Case classes provide immutability by default, structural equality, and a built-in `copy` method.

## 3. Scala Traits and Abstract Classes for Python ABC


Python utilizes the `abc` module and `@abstractmethod` decorator to define abstract base classes and interfaces. Scala natively handles this using `trait` or `abstract class`. Traits are generally preferred as they support multiple inheritance (mixin composition), whereas abstract classes are typically reserved for types that require constructor parameters or close integration with Java code.

## 4. Pattern Matching and Type Matching in Scala 2.13


Python 3.10+ introduced `match`/`case` structural pattern matching, which was heavily inspired by functional languages like Scala. Scala's pattern matching is a cornerstone of the language and is deeply integrated with its type system and case classes.

## 5. Error Handling in Scala 2.13


Python heavily utilizes control flow via exceptions (`try`, `except`, `raise`). Idiomatic Scala eschews exceptions for business logic, preferring monadic constructs that explicitly encode the possibility of failure in the function's return type.

## 6. Scala Naming Conventions


Strict adherence to naming conventions is critical for readable Scala code. While Python relies heavily on `snake_case`, Scala adopts Java-style conventions with specific functional tweaks.

| Element | Python Convention | Scala Convention | Example |
| :--- | :--- | :--- | :--- |
| **Classes / Traits** | PascalCase | PascalCase | `class Tokenizer` |
| **Methods / Functions** | snake_case | camelCase | `def parseTokens()` |
| **Variables** | snake_case | camelCase | `val tokenCount` |
| **Packages** | short_snake_case | alllowercase | `package com.tokenizer` |
| **Global Constants** | UPPER_SNAKE_CASE | PascalCase (or UPPER_SNAKE_CASE) | `val MaxRetries` [cite: 12, 13] |
| **Enum Values** | UPPER_SNAKE_CASE | PascalCase | `case object StringToken` |

## 7. Scala 2.13 Collections and Standard Library Equivalents


The Scala 2.13 collections library underwent a massive redesign for simplicity and performance [cite: 16]. Translating Python data structures requires mapping to Scala's immutable collection hierarchy.

## 8. Scala Generics and Type System for Python Generic[T]



## 9. Scala Datetime Handling


Scala completely dropped its legacy date implementations and heavily relies on the Java 8 Time API (`java.time.*`), which is robust, thread-safe, and immutable—directly mirroring Python's `datetime` module.

*   `datetime.datetime` $\rightarrow$ `java.time.LocalDateTime`
*   `datetime.date` $\rightarrow$ `java.time.LocalDate`
*   `datetime.timezone` $\rightarrow$ `java.time.ZoneId` or `java.time.ZonedDateTime`

## 14. Common Pitfalls When Translating Python to Scala 2.13


Transitioning codebases entails avoiding certain "gotchas" rooted in deep semantic differences.

1.  **Mutable vs Immutable Collections:** Python lists and dictionaries are inherently mutable. In Scala, `List` and `Map` are immutable by default [cite: 16]. Re-assigning or modifying requires explicitly importing `scala.collection.mutable.ListBuffer` or utilizing `var` with immutable collections (the latter is preferred).
2.  **`null` vs `None`:** Python heavily utilizes `None` to indicate absence, mapping to Scala's `Option`. In Scala, `null` exists strictly for JVM interoperability and should **never** be used in idiomatic code. 
3.  **Strict Static Typing vs Duck Typing:** Translating highly polymorphic Python functions requires defining robust trait hierarchies. Avoid abusing the `Any` type in Scala to bypass the compiler, as it defeats the purpose of the language.
4.  **Default Mutable Arguments:** A famous Python anti-pattern (`def func(items=[])`) results in all invocations sharing the same list. In Scala, `def func(items: List[Int] = List.empty)` allocates a new list every time, completely eliminating this bug.
5.  **`==` vs `eq`:** In Python, `==` tests structural equality, and `is` tests referential identity (memory address). In Scala, `==` tests structural equality (equivalent to Python's `==`), while `eq` tests referential identity (equivalent to Python's `is`).
6.  **String Interpolation:** Python's f-strings (`f"Hello {name}"`) map directly to Scala's s-strings (`s"Hello $name"` or `s"Hello ${name.toUpperCase}"`).
7.  **Regex:** Python uses `re.compile(r"pattern")`. Scala utilizes native string extensions `"""pattern""".r`. The triple quotes `"""` prevent the need to escape backslashes, providing an elegant regex experience. 

```scala
// Scala Regex Example
val TokenRegex = """([a-zA-Z_]\w*)""".r

"identifier123" match {
  case TokenRegex(id) => println(s"Found identifier: $id")
  case _ => println("No match")
}
```

**Sources:**
1. [allaboutscala.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHenLZNHOY1cWYWXwfJKw3t8cTX9CCYYnBTLvzv4S-11qXdiKdIch3ndSds1ohn7MQBBoD9opoTv9IQ62dJNGwAlm6apvWqhiCmKhnHlw-ah7tJ34spCX8XpS55JQX9ZEb3soUN1rGMdOaleb-LX3kP-S6JbKSkUq7tLYrOoHnlY4LjBPMtscSQhqHEcqF-uOyVOG7LURw2O7yQGH7vd3_N)
2. [kubuszok.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG7ey3gSVYSicoVINYfqG_PFf8Onffnxq8Y-otwvwB1ZhfA3kR-mZoCpvMCzaqjJENVqXx3RLXj6O1vJGhYOAbXSP3SaqoQkWkCvQm08bCDSUNx3D3tRPPoKjpFCHyUh83uzqs61ccDqtU=)
3. [baeldung.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEoYQSo8IEheLrgBRaAtiy4NTdESZFsYU5FiUqkN8otkH4hrFT5Hql7UBjUnKFo1DhF4rJ7Y5JXdRo1NmXV_FMm04UsDuh4thqJFuFKXJEC5i_-ZGsYOuVvGV2zoovBKyxfw_Y=)
4. [pedrorijo.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHst5H_UrL3I6fbtnz28uVhHDgVzJxbKc3BtHCFQyC7GDmYMn9VzI7RbnM2p52wDrcNx4_ctUNis_4lMQrDqqgYvuIN88AjkV88yLPBNB6k1iLkRRUa0VzoO8Ck18=)
5. [geeksforgeeks.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzjUEs0to1oDfzWjdiEUvSLJqE1iTdsK2jvQsFQpcpqpVYngr4wPeDqrrt-LJwPFcpknlzNGPzfbDDzChQ-nvwtDy23ykXGSNiHlPFBaiTh18thJd0P7-hkXmMMSQhacFU2ECOzPmIVEe3NkEd)
6. [underscore.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHri78SPOnAU-W1jc83Tx8RULEqjc6R2ydy45kCFkGRVjpDM85m8rZCnDEYJabmDEsBN4GZkYRucbMlxiEiBGOGmlAaBS3Jw8kyzrwgYPazUEOZQDWOX7Eggw7qwSweOKpX4mzUDozwqG6F3gvSmCQkKAhdjfUKQod-30yi_uQ=)
7. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdqN-Vpm7rL-FKTQjqJr5HnMgv7KJRBLwNjAeMfcTDMXmA-6-l0RlhF5cNWljAh74MSOf3AP3IdLRFaCWPtk7X0CsRGEphDM5IXJ_wdzMZ-vJMLOix5-6LPqLp8eZWNnMQgijhvrg7P00wDnY2Qj00dfDi8qXGjzFYLejlCOhjyy6Htwez-rBXwjjGbY8DNqEU2VhkcA==)
8. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3iBksLqdNJYAt3HX472Q4BqABfdW-0M6XD1TmQ7YeeZYYky2e95H9SM4yOevvMOK1GQEyWOhalvdb1Yf1nur_l___Esq9R8vCL5iKtXUoVT_k3CxAXO2OdepClcI8Lk5-qLQs7jzi)
9. [scala-lang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHpf3C2_e8pxtfYPQxtGrhJ18SrBbMaBLZ_mFWU20ip-ySs-xcsQS5fMyJOxuSDAfU4Lrof_WTxypiN2AYSh37cvSM4iUNVhik55FGhUO54v7pouPDj8w30uhsEhZ3ewFmOPZtHDYdJwturMTi6ImcT)
10. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEClGE486-xDp2wxslZ-IMpUD8zQwanS5Wfn0z8JBwTaPdE0uOJXxl3KPIVl_oLp1UUxqnjILim_6uOW3FgL5pCMssumIRNJ5wcIZEawAMLCYn5owzXb0U8_YqbpVmJxLRI065QzYnhYOXh-irwnWfUwIJOfsbhUnijMIo5yEMY0K-h)
11. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVmYIQcz3-ns8GwMJzlQgNIs8KMeAPbUVA5qnAS6qdePESSrWKSy7mJu_DJU4RysnWYYflrvAHueBqGp28HytLV2nmHFydU_l-Ybm9frQxmQGBWlygAujqZffmJiXsmBDYGq1kVLVw8Nb8TDcOeKmw5Ri4VV8TSaC8KqAaWrM8bL495JVOv3Bgv4oU1x7sN1vAAxVA5cR1ywwSrUUBre-totemnmX8cI4erFe28McA_H8=)
12. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFO1R7qcYtW_9FaZJcLbZMgHKJUr8HLf9qVLqCy4mA2lrp6WI-_UEZXaIpsW_DvT3NGaA9vXZzQ1sP41lT7O1w4xi_UNJl1bJttCd3-Vff2JwX6me2Uu2tWt0Fc1e2hPmWRcgulfSDTljNzCpeaBdp8-5Fqw9w=)
13. [bibble.co.nz](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4RUJh7RKI8XgZQftNgpIt1ZAG6bTp8tM3JOXSbq345YVSzEO7AD-sZgGKFiCXUYiPg5jLX3TjXB1L41ixwfWEEH3TIya2cOpLjswM_BBNdrjCKU0x7Q8e_ooNWu0x5OcBJzDCbjs=)
14. [scala-lang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVCJIktMYcmJ08QoxDZuavpQ3Tav6YnZpb94G2_XbpfuvP52YMCezFRb7pkfBPrLw_c_knPnM8-OzxVEg4MvVh28jpFK763lpPSi6WGZmaA8cWTGXA0HLvGN-ZFmxgczo1w28hBKiJPFQQgcK9y4A=)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGfg7i2-8WHiS5Bpv71FGRqtiwyIErzYLn3hy8xfeXHG_JE-DwmwytOZpNsRRASEIS0DHbt2AYUthIwIT278NisYhqMg3VwctG7aaKD2ufHnT3I6Yj_kMFjcOcj3pmoO_DHkuru0u0RCJukaPC8-EsAi0OJENme864f3rZUk3xhMLlLzb3u-iI=)
16. [dzone.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_QqroKPKBAcNHsc9M-j2wHzLx62YnqWN4lKXAF5Ofhk9Ro31KRlccJiK44UlZ5vF4DliiPVyIlDcZlGlTzkBwEH43JfqmYqsYJTxGHzUVeANKI-B-CXsxB9rURkNBL8uz-BZnDOC6lfnkhE-15T1VtIg=)
17. [scala-lang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHFEig8skgA50-CrZqU3cNhG1smMw4oXA8gxvY4wCaygxzHkP7AvSRAev83e_hAvsuQavtv06lMwhqYDGnTgMlmOHJ1RkhIsO669bOpzQXe6lViYCnMhShW4vxHIE4mqgYJ54nTMZ1sUASYKTcra3BPiya7gRLQo3FQId2fO3B1WSqy)
18. [fpilluminated.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpB3SeT-WK7ub0YLDB10KEbb3D4WWHGOtdG1H6VcIY9yzVlWUwETmfNePWPy6ZneDdveSrpENK5E9dcDrwTWp24P-wiNp5NlEErcCa-0I0HIQTh2HQhHSBCSBrfgTZxto2gb-k1R1wLGg2VdAPo_uMlF25uMSc32W8RiAVY5N_2oJDcsdOLnJDFPLZ6g3y8x0tBpB0CTUvTgb-xFphb_YRLQIWkrQNTzLpfpexkC68SGDF4pLnxPZSSyn3IFGPdXrEH1EvfeNKh1to5M_w)
19. [kevinlee.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_ZpWiG0mldxaGGij2AQ-SxfZwHjO_-WY1lhVlcppMkGThDvJJZkglnEjPqVXJjg_MR4RBP8am_35lgHJS9EqXyNkBtPDfWxSgSPCaBANe5HbOoSz-gedd9ASDGgkoknXBCOr1ipT6D7sbR--RdaF88LOGsQOFPP8MAW9z3EsV2TTnWsh-OyJ9Qr6uWewr)
20. [scala-lang.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHRfLoSC6oO2M7PMdiddMQLIu7gZfI5CaFBziIJZULrSXquLHWDJLLSwWUcCzO05auAosD8EjuhuyLZdsBvQPoNCBv088E8h2fTDC445q4nfhNH4N3cM5vyVNMnPFFirWeinyx1fMJmwJ-tzxzdOMGdBZc0Mw9U)
21. [baeldung.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEHLVfk_x8w9QeOE1id6_MxvR0P_MlMz0baoQ3uDGOqrtrsuS44O-WGI7WnnV5bFbz5gGG8EIenKIbzCqyqNjkRsb06HkigAwF94HXr778_b3M9R8CpO8zjEMAXnjPs5ZfXWCjO)
22. [pilkauskas.lt](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_fiLzh9f-1o9sthA6kF6EPLHy9pGXzDv5CFmFq8iP8DJrIwmAuJYaB_MOiRl9YQy7f7-7_dgWS5Ij5kWByY9k7UC0pduzMGL6jtNgCbgdhDAOMEAjga-88V8Fr0d6b6hNXiEQ0Vy2tVkOXKrnZ0QTz2mV9_jL3Gq858xhEDQcjQ==)
23. [donderom.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHS_X879J93VPHW3XxCAGz4fu_uyqCQFlXdt_Xyu7rZ9ILR-y3wLaWRyKhvluc8_-LOp0zdGI8khcl7EJ0zECKrjCXtiePiUhNWprXy8E3gSYULWTHSaag2FuQ9HGyHLczw2fjWgJHelEvnaYI=)
24. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFkQABN1nZBHwZ5VBh1TjrVyM1hHRGjyfPb2Qz2QElH0KGSGZYSoTixcZ3xftt3PBXz1lGZxyMFCuvYdGC9GmvvJgAP2abFKdmvV_nVd-N2SbazBQSKViWGtvA05PG_sNleUWG0gtRGD1A3aUXGPFNbFKgAx17Uth5JS9f_aiL-oCTz2nDw1jM=)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE5G_wHr9ys4C3rQ2-EDIosnbq5eOGxRbHOAtg7YinXWu6piSEN5Jq_rlbuK7NmqNc9XqJlwxB9I6IgICiywPM6K2jnlhB703SfLscKAerRUW6i5Y5F-sgnG6kUBLjNzVf2aCkUqOjr64x17Z0nGh2WyXBJIZihPMZOu_FfODL9jRgPD5cS3QFtkulvQxGP7yfdIUjQe2Xxvs-mi3CawaLbu8bwU5WU6KchnYI=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGYtpgNAjb38pLmh1D5JsqH23CjNc6t9ANngWxFcDBTP0kmHis8fRF8Y49kf5UPZcKJ_hEx0PcopJSfyu4072lAuhbUFpUvLzaTspT7GL1iBPRyAXNG-d7KufKhLYz6506DZnBHiNjQKWnykOeRC5f6wRCXRlo9LuM4UMzRy6I2oua9nHdb8gEIL1Wn9pZBj-4MOd_--c75eWpJuiSDIioOE4g=)
27. [code.tools](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGPZfhJ-i77KgRzYcygJXtP-dkQPLOPZNO_BEFweP8_0Mkngl-2-cZKG8Q2Vher6ENjiPFOKznBSXVF95md_6pQomnsbkqoWAipOcNUcZlVtuAX-cfR5A==)
28. [virtuslab.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGw9tUQOdLuhpt__JoqPrM9SuFq77KizFYmrvwbJQEkZKfiJaRxIby7HRvt-z5DvqbVvdq_nUL28bHC7oLduX4Dq54OwvGH8FDVh0UnlXgD5xOx9Hh8jJulsaGVsd3AdYqmZhQkirePUeYgKTI=)