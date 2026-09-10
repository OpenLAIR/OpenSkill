# Idiomatic Scala 2.13 Patterns for Translating Python Tokenizer Modules

**Key Points**
*   **Architectural Shifts:** Translating Python to Scala 2.13 requires a paradigm shift from dynamic, duck-typed, and often mutable constructs to statically typed, rigorously checked, and immutable algebraic data types.
*   **Type Safety and Enums:** It appears most robust to use `sealed trait` and `case object` hierarchies rather than the native `scala.Enumeration`, as the former guarantees compile-time exhaustiveness checking and avoids type erasure pitfalls. 
*   **Data Representation:** Python `@dataclass` structures seamlessly translate to Scala `case class` definitions, providing immutability, structural equality, and built-in deep-copy mechanisms out-of-the-box.
*   **Error Handling:** The evidence strongly leans toward utilizing monadic constructs like `Try`, `Either`, and `Option` over traditional `try/catch` exception throwing, fostering composable and type-safe error management.
*   **Performance Considerations:** While Scala supports structural typing (analogous to Python's duck typing), research suggests it relies heavily on reflection in Scala 2.13, incurring severe performance penalties that should be avoided in high-throughput components like tokenizers.

**Understanding the Transition**
Moving from Python to Scala 2.13 for a computationally intensive task like a tokenizer requires addressing fundamental differences in how the two languages model state, handle types, and execute loops. Python's dynamic nature allows for rapid prototyping, but Scala's static type system offers rigorous compile-time guarantees that can prevent entire classes of runtime errors. This report synthesizes best practices and idiomatic patterns for executing this transition. 

**Scope and Constraints**
This analysis focuses strictly on the Scala 2.13 standard library. While the broader Scala ecosystem contains powerful libraries for JSON handling, enum generation, and functional programming, adhering to the standard library ensures zero-dependency deployments and aligns with the explicit constraints of the query. 

**Methodological Approach**
The recommendations presented herein are derived from a comparative analysis of Python and Scala idioms. Code examples are provided to bridge the conceptual gap, illustrating not only the syntax but the underlying semantic shifts required to write truly idiomatic Scala code.

## 1. Scala 2.13 Enum/ADT Representation

In Python, enumerations are typically implemented using the `enum.Enum` class. When translating these to Scala 2.13, developers are faced with a choice between the native `scala.Enumeration` class and an Algebraic Data Type (ADT) approach utilizing `sealed trait` and `case object`. 

Research decisively indicates that the `sealed trait` approach is superior and far more idiomatic in Scala 2.13 [cite: 1, 2]. The native `scala.Enumeration` suffers from significant drawbacks: it is prone to type erasure, meaning different enumerations share the same type at runtime [cite: 3, 4], and it lacks compiler-level exhaustiveness checking during pattern matching [cite: 3, 4]. Using a `sealed trait` guarantees that all possible implementations are known at compile-time (as they must be declared in the same file), allowing the compiler to issue warnings if a `match` expression is not exhaustive [cite: 5, 6].

### Working Example: `TokenType`

Below is an idiomatic translation of a Python string-based Enum to a Scala 2.13 ADT.

```scala
// Idiomatic Scala 2.13 Enum using Sealed Trait
sealed trait TokenType {
  def value: String
  override def toString: String = value
}

object TokenType {
  case object StringToken extends TokenType { val value = "string" }
  case object NumericToken extends TokenType { val value = "numeric" }
  case object IdentifierToken extends TokenType { val value = "identifier" }

  // A sequence of all known tokens to facilitate lookup
  val values: Seq[TokenType] = Seq(StringToken, NumericToken, IdentifierToken)

  // Factory method equivalent to Python's TokenType("string")
  def fromString(s: String): Option[TokenType] = values.find(_.value == s)
  
  // Unsafe factory method throwing an exception if not found (less idiomatic, but useful for strict translation)
  def fromStringUnsafe(s: String): TokenType = fromString(s)
    .getOrElse(throw new IllegalArgumentException(s"Unknown TokenType: $s"))
}
```

### Trade-offs and Best Practices
*   **Pros of Sealed Traits**: Compile-time exhaustiveness checking prevents `MatchError` exceptions at runtime [cite: 6, 7]. They allow adding distinct methods, fields, and behavior to individual enumeration members, which `scala.Enumeration` does not easily support [cite: 4].
*   **Cons of Sealed Traits**: Unlike Python's `Enum` or Scala 3's `enum` keyword, Scala 2.13 requires boilerplate code to list all values (e.g., the `val values` sequence) and implement the string lookup manually [cite: 4]. 

## 2. Scala Case Classes vs Python Dataclasses

Python's `@dataclass` decorator automates the generation of boilerplate code for data containers, providing `__init__`, `__repr__`, and `__eq__` methods. The direct equivalent in Scala is the `case class` [cite: 8]. Case classes provide immutability by default, structural equality, and a built-in `copy` method.

### Translating Python Idioms to Scala Case Classes

1.  **Default values:** Python's `field = "default"` maps directly to Scala's `field: String = "default"`.
2.  **Optional fields:** Python's `Optional[X]` translates to Scala's `Option[X]`.
3.  **Mutable fields:** While highly discouraged in Scala, Python's mutable fields translate from Scala `val` (immutable) to `var` (mutable).
4.  **`default_factory`:** Python's `field(default_factory=list)` is handled in Scala simply by assigning a new instance as the default parameter, e.g., `List.empty[X]`.

### Code Example: Dataclass to Case Class

**Python:**
```python
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Token:
    value: str
    token_type: TokenType
    line_num: int = 1
    metadata: Optional[str] = None
    sub_tokens: List['Token'] = field(default_factory=list)
```

**Scala:**
```scala
case class Token(
  value: String,
  tokenType: TokenType,
  lineNum: Int = 1,
  metadata: Option[String] = None,
  subTokens: List[Token] = List.empty[Token] // default_factory equivalent
)

// Usage of the copy method
val originalToken = Token("hello", TokenType.StringToken)
// Modifying a specific field while keeping the rest identical
val modifiedToken = originalToken.copy(lineNum = 2, metadata = Some("keyword"))
```

Because Scala evaluates default arguments each time the function (or constructor) is called, `List.empty[Token]` generates a new, clean immutable list per instance, avoiding Python's infamous mutable default argument trap.

## 3. Scala Traits and Abstract Classes for Python ABC

Python utilizes the `abc` module and `@abstractmethod` decorator to define abstract base classes and interfaces. Scala natively handles this using `trait` or `abstract class`. Traits are generally preferred as they support multiple inheritance (mixin composition), whereas abstract classes are typically reserved for types that require constructor parameters or close integration with Java code.

### Base Trait with Abstract and Concrete Methods

```scala
trait Tokenizer {
  // Abstract method (no implementation)
  def tokenize(input: String): List[Token]

  // Concrete method (has implementation)
  def countTokens(input: String): Int = tokenize(input).size
}
```

### Generic Type Parameters and Variance

Python uses `TypeVar("T_co", covariant=True)` to define covariant generic types. Scala handles variance directly at the declaration site using `+` (covariant) and `-` (contravariant).

```scala
// Covariant generic trait (equivalent to TypeVar("T_co", covariant=True))
trait Producer[+T] {
  def produce(): T
}

// Contravariant generic trait (equivalent to TypeVar("T_contra", contravariant=True))
trait Consumer[-T] {
  def consume(item: T): Unit
}
```

### Type Bounds

Python restricts TypeVars using bound types, such as `TypeVar("NumericT", int, float, Decimal)`. In Scala 2.13, upper bounds (`<:`) are used to constrain type parameters. For numeric bounds, Scala relies on the `Numeric` type class rather than strict inheritance.

```scala
// Upper bound constraint (T must be a subtype of Token)
class TokenProcessor[T <: Token] {
  def process(token: T): String = token.value.toUpperCase
}

// Type class constraint for Numeric types
class MathProcessor[T: Numeric](val value: T) {
  def doubleValue(implicit num: Numeric[T]): T = num.plus(value, value)
}
```

### Structural Typing (Duck Typing)

Python inherently uses structural typing (duck typing) where an object's suitability is determined by the presence of certain methods rather than inheritance. Scala 2.13 supports structural typing via refinement types, but it must be explicitly enabled, and it relies heavily on Java reflection [cite: 9, 10].

```scala
import scala.language.reflectiveCalls // Required for structural typing [cite: 9]

// Duck typing: accepts ANY object that has a `close()` method
def closeResource(resource: { def close(): Unit }): Unit = {
  resource.close()
}
```
*Note on Performance:* The use of structural types in Scala 2.13 carries a severe performance penalty because method invocation is handled dynamically via reflection [cite: 10, 11]. In the context of a high-performance tokenizer, structural typing should be avoided in favor of nominal typing (traits) or type classes [cite: 10].

## 4. Pattern Matching and Type Matching in Scala 2.13

Python 3.10+ introduced `match`/`case` structural pattern matching, which was heavily inspired by functional languages like Scala. Scala's pattern matching is a cornerstone of the language and is deeply integrated with its type system and case classes.

### Translating Pattern Matches

1.  **Type matching** (equivalent to `isinstance()`):
2.  **Sealed trait members**: Exhaustive checking ensures all variants are handled.
3.  **Options**: Matching on `Some` and `None`.
4.  **Tuple deconstruction**: Unpacking structures on the fly.
5.  **Guard conditions**: `if` statements inside cases.

```scala
def analyzeToken(obj: Any): String = obj match {
  // 1. Type Matching (isinstance)
  case s: String => s"It's a raw string of length ${s.length}"
  case i: Int => s"It's an integer: $i"
  
  // 2. Sealed Trait Members & 5. Guard Conditions
  case Token(value, TokenType.NumericToken, _, _, _) if value.startsWith("-") =>
    s"Negative numeric token: $value"
    
  case Token(value, TokenType.StringToken, line, _, _) =>
    s"String token '$value' at line $line"
    
  // 3. Matching Options
  case Token(_, _, _, Some(meta), _) =>
    s"Token with metadata: $meta"
    
  // 4. Tuple Deconstruction
  case (a: Int, b: String) =>
    s"Tuple containing $a and $b"
    
  // Wildcard fallback
  case _ => "Unknown object"
}
```

## 5. Error Handling in Scala 2.13

Python heavily utilizes control flow via exceptions (`try`, `except`, `raise`). Idiomatic Scala eschews exceptions for business logic, preferring monadic constructs that explicitly encode the possibility of failure in the function's return type.

### `Try`, `Success`, `Failure`

`Try` is used to wrap operations that might throw a JVM exception. It allows chaining operations safely without try/catch blocks.

```scala
import scala.util.{Try, Success, Failure}

def parseNumber(s: String): Try[Int] = Try(s.toInt)

parseNumber("123") match {
  case Success(value) => println(s"Parsed: $value")
  case Failure(exception) => println(s"Failed to parse: ${exception.getMessage}")
}
```

### `Either[Left, Right]`

`Either` is more general and is the standard way to handle logical errors. By convention, `Left` contains the error (often a string or a custom domain error class), and `Right` contains the success value.

```scala
sealed trait TokenizerError
case class InvalidCharacter(char: Char, line: Int) extends TokenizerError
case object EmptyInput extends TokenizerError

def tokenizeStrict(input: String): Either[TokenizerError, List[Token]] = {
  if (input.isEmpty) Left(EmptyInput)
  else if (input.contains("$")) Left(InvalidCharacter('$', 1))
  else Right(List(Token(input, TokenType.StringToken)))
}
```

### When to use which?
*   **`Option[T]`**: Use when a value simply might be missing (e.g., retrieving an item from a map), and you do not care about *why* it is missing.
*   **`Try[T]`**: Use when interacting with legacy Java code, I/O operations, or code that is known to throw exceptions.
*   **`Either[E, T]`**: Use for robust domain modeling where the exact cause of the error `E` needs to be communicated back to the caller.

### Translating Python Exceptions
Python's `ValueError` is typically translated to `IllegalArgumentException` in Scala (via Java), and `TypeError` often becomes unnecessary due to Scala's static typing, though `ClassCastException` is the closest JVM equivalent for runtime type failures.

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

### Detailed Rules
*   **Method Names**: Convert `parse_token_list()` to `parseTokenList()`.
*   **Boolean Methods**: Unlike Python (`is_empty()`), Scala avoids prefixes like `get` or `is` for properties. For boolean checks, `isEmpty` or `hasChildren` is preferred [cite: 14]. 
*   **Constants**: Research indicates a slight community split. The official Scala style guide recommends `PascalCase` for constants (e.g., `val Pi = 3.14`) [cite: 12, 15], though `UPPER_SNAKE_CASE` is sometimes tolerated for global configuration variables borrowed from Java or C [cite: 13]. `PascalCase` is the safest, most idiomatic choice.
*   **Companion Objects**: Must exactly match the name of the class or trait they accompany and must reside in the exact same source file [cite: 13].

## 7. Scala 2.13 Collections and Standard Library Equivalents

The Scala 2.13 collections library underwent a massive redesign for simplicity and performance [cite: 16]. Translating Python data structures requires mapping to Scala's immutable collection hierarchy.

### Standard Mappings
*   `collections.abc.Sequence` or `list` $\rightarrow$ `Seq[T]` or `List[T]` (immutable singly-linked list).
*   `collections.abc.Iterable` $\rightarrow$ `Iterable[T]`.
*   `dict` $\rightarrow$ `Map[K, V]`.
*   `set` $\rightarrow$ `Set[T]`.

### Python List Comprehensions to Scala Comprehensions
Python: `[token.value for token in tokens if token.line_num == 1]`
Scala utilizes `for` comprehensions or functional pipelines (`map`/`filter`).

```scala
// Functional pipeline
val values = tokens.filter(_.lineNum == 1).map(_.value)

// For comprehension (direct equivalent)
val values = for {
  token <- tokens
  if token.lineNum == 1
} yield token.value
```

### Python `dict` Equivalents
```scala
// Construction
val metadata: Map[String, String] = Map("encoding" -> "utf-8", "lang" -> "en")

// Accessing (safe vs unsafe)
val encSafe: Option[String] = metadata.get("encoding") // Returns Some("utf-8")
val encUnsafe: String = metadata("encoding")           // Throws Exception if missing

// Updating (returns a NEW map, original is unchanged)
val updatedMetadata = metadata + ("version" -> "1.0")
```

### Python `enumerate()` Equivalent
```scala
val tokens = List("a", "b", "c")
// zipWithIndex creates tuples of (element, index)
for ((token, index) <- tokens.zipWithIndex) {
  println(s"Token $index: $token")
}
```

### Python Generators (`yield`) to Scala
Python generators lazily produce values. In Scala 2.13, the closest equivalent is `LazyList` (which replaces Scala 2.12's `Stream`). To replicate a complex generator, use `LazyList.unfold` [cite: 17, 18].

```scala
// Python:
// def generate_numbers(limit):
//     n = 0
//     while n < limit:
//         yield n
//         n += 1

// Scala:
def generateNumbers(limit: Int): LazyList[Int] = {
  LazyList.unfold(0) { state =>
    if (state < limit) Some((state, state + 1)) // Some((yield_value, next_state))
    else None
  }
}
```

## 8. Scala Generics and Type System for Python Generic[T]

### Translating `class MyClass(Generic[T])`
```scala
class TokenStack[T] {
  private var elements: List[T] = List.empty
  def push(element: T): Unit = elements = element :: elements
  def pop(): T = {
    val head = elements.head
    elements = elements.tail
    head
  }
}
```

### Union Types (`Union[str, int]`)
Scala 2.13 does not natively support Scala 3's Union Types (`A | B`). To replicate `Union[str, int]`, developers must use `Either[String, Int]` or create a custom sealed trait that wraps the possible types.

```scala
// Using Either for a two-type union
def parseMixed(input: String): Either[Int, String] = {
  Try(input.toInt).map(Left(_)).getOrElse(Right(input))
}
```

### Callable Equivalents
Python's `Callable[[int, str], bool]` translates directly to Scala's function type syntax `(Int, String) => Boolean`.

```scala
def processWithCallback(token: Token, callback: Token => Boolean): Unit = {
  if (callback(token)) println("Callback returned true")
}
```

### `@overload` Decorator
Python uses `@overload` for static type checking annotations. Scala handles this natively with standard method overloading.

```scala
class Tokenizer {
  def tokenize(input: String): List[Token] = tokenize(input, strict = false)
  def tokenize(input: String, strict: Boolean): List[Token] = { /* ... */ }
}
```

## 9. Scala Datetime Handling

Scala completely dropped its legacy date implementations and heavily relies on the Java 8 Time API (`java.time.*`), which is robust, thread-safe, and immutable—directly mirroring Python's `datetime` module.

*   `datetime.datetime` $\rightarrow$ `java.time.LocalDateTime`
*   `datetime.date` $\rightarrow$ `java.time.LocalDate`
*   `datetime.timezone` $\rightarrow$ `java.time.ZoneId` or `java.time.ZonedDateTime`

### Parsing and Formatting

Python's `strftime` and `strptime` are replaced by `java.time.format.DateTimeFormatter`.

```scala
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

// Formatting (strftime)
val now = LocalDateTime.now()
val formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")
val dateString = now.format(formatter)

// Parsing (strptime)
val parsedDate = LocalDateTime.parse("2023-10-27 15:30:00", formatter)

// ISO Formatting (native support)
val isoString = now.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
```

## 10. Scala `BigDecimal` for Python's `decimal.Decimal`

When precision is critical (e.g., tokenizing financial data), Python's `decimal.Decimal` translates to `scala.math.BigDecimal`. 

### Construction and Arithmetic
```scala
// Construct from string to prevent floating point inaccuracies
val a = BigDecimal("10.5")
val b = BigDecimal("2.3")

val sum = a + b
val product = a * b
```

### Precision and MathContext
Python sets precision globally via `getcontext().prec`. In Scala, precision is tied to the `java.math.MathContext` object. A crucial bug regarding `MathContext` ignoring arithmetic operators (`+`, `-`) in Scala 2.12 was permanently fixed in Scala 2.13 [cite: 19]. When performing operations, Scala 2.13 correctly passes the context.

```scala
import java.math.MathContext

// Specify a 5-digit precision
val mc = new MathContext(5)
val preciseDec = BigDecimal(new java.math.BigDecimal("1.23456789"), mc) // Will round based on MathContext [cite: 20]
```

## 11. Scala Companion Objects and Factory Patterns

Python relies on `@classmethod` and `@staticmethod` to create alternate constructors or house static utilities. Scala explicitly separates instance members (in the `class`) from static members (in the `object` of the same name). 

### Translating `@classmethod` and Builders

The builder pattern in Python usually relies on mutating a class instance. In idiomatic functional Scala, the builder pattern is implemented using the `copy` method provided by case classes [cite: 21, 22], allowing for method chaining while maintaining strict immutability.

```scala
case class TokenizerConfig(
  caseSensitive: Boolean = true,
  ignoreWhitespace: Boolean = false,
  maxTokens: Int = 1000
) {
  // Method chaining (functional builder pattern) [cite: 23]
  def withCaseSensitivity(sensitive: Boolean): TokenizerConfig = copy(caseSensitive = sensitive)
  def ignoringWhitespace: TokenizerConfig = copy(ignoreWhitespace = true)
  def withMaxTokens(max: Int): TokenizerConfig = copy(maxTokens = max)
}

// Companion object acting as a factory (Python @staticmethod equivalent)
object TokenizerConfig {
  def default(): TokenizerConfig = TokenizerConfig()
  def strict(): TokenizerConfig = TokenizerConfig(caseSensitive = true, ignoreWhitespace = false, maxTokens = 500)
}

// Usage
val config = TokenizerConfig.default()
  .ignoringWhitespace
  .withMaxTokens(2000)
```

## 12. Scala JSON Handling with Standard Library Only

Scala lacks a robust native JSON parser/generator in its standard library (unlike Python's `json` module). Modern Scala relies on libraries like `circe` or `uPickle`. However, strictly utilizing the standard library to generate JSON strings requires leveraging product iteration features introduced in Scala 2.13.

In Scala 2.13, case classes inherit `Product`, which now includes `productElementNames` [cite: 24, 25]. This allows developers to iterate over field names and values dynamically [cite: 8, 26].

```scala
def caseClassToJson(cc: Product): String = {
  val fields = cc.productElementNames.zip(cc.productIterator).map {
    case (name, value: String) => s""""$name": "$value""""
    case (name, value: Number) => s""""$name": $value"""
    case (name, value: Boolean) => s""""$name": $value"""
    case (name, Some(value: String)) => s""""$name": "$value""""
    case (name, None) => s""""$name": null"""
    case (name, obj: Product) => s""""$name": ${caseClassToJson(obj)}""" // Recursive
    case (name, list: Iterable[_]) => // Simple list handling
      val listStr = list.map(v => s""""$v"""").mkString("[", ", ", "]")
      s""""$name": $listStr"""
    case (name, _) => s""""$name": "UNSUPPORTED_TYPE""""
  }
  fields.mkString("{", ", ", "}")
}

val t = Token("value", TokenType.StringToken, 1, None)
println(caseClassToJson(t))
// Output: {"value": "value", "tokenType": "string", "lineNum": 1, "metadata": null, "subTokens": []}
```

## 13. Scala 2.13 Compilation

To compile a single file manually without build tools like `sbt` or `scala-cli`, you use the `scalac` command [cite: 27, 28]. 

```bash
# Compile a single file with warnings as errors and deprecation warnings
scalac -deprecation -Werror Tokenizer.scala
```
This generates `.class` files in the current directory. To run the compiled code:
```bash
scala TokenizerMain
```

### File Organization and Package Declaration
In Scala, unlike Java, directory structure does not strictly have to match the package name, though it is highly recommended.
```scala
package com.mycompany.nlp.tokenizer

import java.time.LocalDateTime
import scala.util.{Try, Success, Failure}

object TokenizerMain {
  def main(args: Array[String]): Unit = {
    println("Tokenizer ready.")
  }
}
```

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
