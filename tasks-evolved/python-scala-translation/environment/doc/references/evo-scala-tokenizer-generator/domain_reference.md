# Domain Reference for evo-scala-tokenizer-generator

**Responsibility**: Produce the final compilable Scala 2.13 source file at /root/Tokenizer.scala with correct package structure, all required classes/traits/objects, proper imports, JSON handling via standard library, and method implementations that match Python behavior.

**Key functions to implement**: generate_token_type_adt, generate_token_case_class, generate_base_tokenizer_trait, generate_specialized_tokenizers, generate_tokenizer_builder, generate_top_level_functions, generate_json_serialization, assemble_scala_file

---

## 1. Scala 2.13 Enum/ADT Representation


In Python, enumerations are typically implemented using the `enum.Enum` class. When translating these to Scala 2.13, developers are faced with a choice between the native `scala.Enumeration` class and an Algebraic Data Type (ADT) approach utilizing `sealed trait` and `case object`. 

Research decisively indicates that the `sealed trait` approach is superior and far more idiomatic in Scala 2.13 [cite: 1, 2]. The native `scala.Enumeration` suffers from significant drawbacks: it is prone to type erasure, meaning different enumerations share the same type at runtime [cite: 3, 4], and it lacks compiler-level exhaustiveness checking during pattern matching [cite: 3, 4]. Using a `sealed trait` guarantees that all possible implementations are known at compile-time (as they must be declared in the same file), allowing the compiler to issue warnings if a `match` expression is not exhaustive [cite: 5, 6].

## 2. Scala Case Classes vs Python Dataclasses


Python's `@dataclass` decorator automates the generation of boilerplate code for data containers, providing `__init__`, `__repr__`, and `__eq__` methods. The direct equivalent in Scala is the `case class` [cite: 8]. Case classes provide immutability by default, structural equality, and a built-in `copy` method.

## 3. Scala Traits and Abstract Classes for Python ABC


Python utilizes the `abc` module and `@abstractmethod` decorator to define abstract base classes and interfaces. Scala natively handles this using `trait` or `abstract class`. Traits are generally preferred as they support multiple inheritance (mixin composition), whereas abstract classes are typically reserved for types that require constructor parameters or close integration with Java code.

## 5. Error Handling in Scala 2.13


Python heavily utilizes control flow via exceptions (`try`, `except`, `raise`). Idiomatic Scala eschews exceptions for business logic, preferring monadic constructs that explicitly encode the possibility of failure in the function's return type.

## 11. Scala Companion Objects and Factory Patterns


Python relies on `@classmethod` and `@staticmethod` to create alternate constructors or house static utilities. Scala explicitly separates instance members (in the `class`) from static members (in the `object` of the same name).

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