def generate_scala_file(output_path):
    code = get_scala_code()
    with open(output_path, 'w') as f:
        f.write(code)
    print(f"Generated {output_path}")

def get_scala_code():
    return '''package tokenizer

import java.time.{LocalDate, LocalDateTime}
import java.time.format.DateTimeFormatter
import scala.util.Try
import io.circe.Json
import io.circe.syntax._
import io.circe.parser._

// ============================================================================
// TokenType ADT (sealed trait instead of Enum)
// ============================================================================

sealed trait TokenType {
  def value: String
  override def toString: String = value
}

object TokenType {
  case object STRING extends TokenType { val value = "string" }
  case object NUMERIC extends TokenType { val value = "numeric" }
  case object TEMPORAL extends TokenType { val value = "temporal" }
  case object STRUCTURED extends TokenType { val value = "structured" }
  case object BINARY extends TokenType { val value = "binary" }
  case object NULL extends TokenType { val value = "null" }

  val values: Seq[TokenType] = Seq(STRING, NUMERIC, TEMPORAL, STRUCTURED, BINARY, NULL)

  def fromString(s: String): Option[TokenType] = values.find(_.value == s)
}

// ============================================================================
// Token case class
// ============================================================================

case class Token(
  value: String,
  tokenType: TokenType,
  metadata: Map[String, Any] = Map.empty
) {
  def withMetadata(entries: (String, Any)*): Token =
    copy(metadata = metadata ++ entries.toMap)
}

// ============================================================================
// Tokenizable trait (Protocol equivalent)
// ============================================================================

trait Tokenizable {
  def toToken: String
}

trait HasLength {
  def length: Int
}

trait TokenProcessor[-T] {
  def process(item: T): Unit
}

// ============================================================================
// MutableTokenBatch
// ============================================================================

class MutableTokenBatch {
  private var _tokens: List[Token] = List.empty
  private var _processed: Boolean = false

  def tokens: List[Token] = _tokens

  def add(token: Token): Unit = {
    if (_processed) throw new RuntimeException("Batch already processed")
    _tokens = _tokens :+ token
  }

  def markProcessed(): Unit = { _processed = true }
}

// ============================================================================
// Generic Container Classes
// ============================================================================

class TokenContainer[+T](items: Seq[T]) {
  private val _items: Vector[T] = items.toVector

  def getAll: Vector[T] = _items

  def size: Int = _items.size

  def mapTokens(func: T => String): List[String] =
    _items.map(func).toList
}

class TokenSink[-T] {
  private var _received: List[Any] = List.empty

  def receive(item: T): Unit = { _received = _received :+ item }

  def drain(): List[Any] = {
    val result = _received
    _received = List.empty
    result
  }
}

class BivariantHandler[T](private var _value: T) {
  def get: T = _value

  def set(value: T): Unit = { _value = value }

  def transform(func: T => T): T = {
    _value = func(_value)
    _value
  }
}

// ============================================================================
// Base Tokenizer trait
// ============================================================================

trait BaseTokenizer[T] {
  def tokenize(value: T): Token

  def tokenizeBatch(values: Iterable[T]): Iterator[Token] =
    values.iterator.map(tokenize)
}

// ============================================================================
// StringTokenizer
// ============================================================================

class StringTokenizer(
  encoding: String = "UTF-8",
  normalizer: String => String = identity
) extends BaseTokenizer[String] {

  def tokenize(value: String): Token = {
    val normalized = normalizer(value)
    Token(normalized, TokenType.STRING)
  }

  def tokenizeBytes(value: Array[Byte]): Token = {
    val strValue = new String(value, encoding)
    val normalized = normalizer(strValue)
    Token(normalized, TokenType.STRING)
  }
}

// ============================================================================
// NumericTokenizer
// ============================================================================

class NumericTokenizer(
  precision: Int = 6,
  formatOptions: Map[String, Any] = Map.empty
) extends BaseTokenizer[Any] {

  def tokenize(value: Any): Token = value match {
    case d: BigDecimal =>
      val strValue = s"%%.${precision}f".format(d.doubleValue)
      Token(strValue, TokenType.NUMERIC, Map("original_type" -> "Decimal"))
    case d: Double =>
      val strValue = s"%%.${precision}f".format(d)
      Token(strValue, TokenType.NUMERIC, Map("original_type" -> "Double"))
    case f: Float =>
      val strValue = s"%%.${precision}f".format(f.toDouble)
      Token(strValue, TokenType.NUMERIC, Map("original_type" -> "Float"))
    case i: Int =>
      Token(i.toString, TokenType.NUMERIC, Map("original_type" -> "Int"))
    case l: Long =>
      Token(l.toString, TokenType.NUMERIC, Map("original_type" -> "Long"))
    case other =>
      Token(other.toString, TokenType.NUMERIC, Map("original_type" -> other.getClass.getSimpleName))
  }
}

// ============================================================================
// TemporalTokenizer
// ============================================================================

class TemporalTokenizer(
  formatStr: Option[String] = None
) extends BaseTokenizer[Any] {

  private val IsoFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd\'T\'HH:mm:ss")
  private val DateFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd")

  def tokenize(value: Any): Token = value match {
    case dt: LocalDateTime =>
      val fmt = formatStr.map(DateTimeFormatter.ofPattern).getOrElse(IsoFormat)
      Token(dt.format(fmt), TokenType.TEMPORAL)
    case d: LocalDate =>
      val fmt = formatStr.map(DateTimeFormatter.ofPattern).getOrElse(DateFormat)
      Token(d.format(fmt), TokenType.TEMPORAL)
    case other =>
      Token(other.toString, TokenType.TEMPORAL)
  }
}

// ============================================================================
// UniversalTokenizer
// ============================================================================

class UniversalTokenizer {
  private val stringTokenizer = new StringTokenizer()
  private val numericTokenizer = new NumericTokenizer()
  private val temporalTokenizer = new TemporalTokenizer()

  def tokenize(value: Any): Token = value match {
    case null => Token("NULL", TokenType.NULL)
    case t: Tokenizable => Token(t.toToken, TokenType.STRUCTURED)
    case s: String => stringTokenizer.tokenize(s)
    case b: Array[Byte] => stringTokenizer.tokenizeBytes(b)
    case _: Int | _: Long | _: Double | _: Float | _: BigDecimal =>
      numericTokenizer.tokenize(value)
    case dt: LocalDateTime => temporalTokenizer.tokenize(dt)
    case d: LocalDate => temporalTokenizer.tokenize(d)
    case other => Token(other.toString, TokenType.STRING, Map("fallback" -> true))
  }

  def tokenizeNull: Token = Token("NULL", TokenType.NULL)
}

// ============================================================================
// TokenRegistry
// ============================================================================

class TokenRegistry[T] {
  private var _registry: Map[String, TokenContainer[T]] = Map.empty
  private var _handlers: List[T => Option[Token]] = List.empty

  def register(key: String, container: TokenContainer[T]): Unit =
    _registry = _registry + (key -> container)

  def addHandler(handler: T => Option[Token]): Unit =
    _handlers = _handlers :+ handler

  def process(key: String): List[Option[Token]] = {
    _registry.get(key) match {
      case None => List.empty
      case Some(container) =>
        container.getAll.map { item =>
          _handlers.iterator
            .map(h => h(item))
            .find(_.isDefined)
            .flatten
        }.toList
    }
  }
}

// ============================================================================
// TokenFunctor and TokenMonad
// ============================================================================

class TokenFunctor[T](protected val _value: T) {
  def map[U](func: T => U): TokenFunctor[U] = new TokenFunctor(func(_value))

  def flatMap[U](func: T => TokenFunctor[U]): TokenFunctor[U] = func(_value)

  def get: T = _value

  def getOrElse(default: T): T = if (_value != null) _value else default
}

class TokenMonad[T](value: T) extends TokenFunctor[T](value) {
  def ap[U](funcWrapped: TokenMonad[T => U]): TokenMonad[U] =
    new TokenMonad(funcWrapped._value(this._value))
}

object TokenMonad {
  def pure[T](value: T): TokenMonad[T] = new TokenMonad(value)
}

// ============================================================================
// JsonTokenizer
// ============================================================================

class JsonTokenizer(pretty: Boolean = false) {

  def tokenize(value: Json): Token = {
    val jsonStr = if (pretty) value.spaces2 else value.noSpaces
    Token(jsonStr, TokenType.STRUCTURED, Map("json" -> true))
  }

  def tokenizePath(value: Json, path: String): Option[Token] = {
    val parts = path.split("\\\.")
    var current: Option[Json] = Some(value)

    for (part <- parts if current.isDefined) {
      current = current.flatMap { json =>
        if (json.isObject) {
          json.hcursor.downField(part).focus
        } else if (json.isArray) {
          Try(part.toInt).toOption.flatMap { idx =>
            json.asArray.flatMap(arr => arr.lift(idx))
          }
        } else None
      }
    }

    current.map(tokenize)
  }
}

// ============================================================================
// WhitespaceTokenizer
// ============================================================================

class WhitespaceTokenizer(
  lowercase: Boolean = false,
  minLength: Int = 0,
  maxLength: Option[Int] = None,
  stripPunctuation: Boolean = false
) {
  private val punctuation: Set[Char] = ".,!?;:\'\\"()[]{}".toSet

  private def processToken(word: String): Option[String] = {
    var w = word
    if (stripPunctuation) w = w.dropWhile(punctuation.contains).reverse.dropWhile(punctuation.contains).reverse
    if (lowercase) w = w.toLowerCase
    if (w.length < minLength) return None
    maxLength.foreach { max =>
      if (w.length > max) w = w.take(max)
    }
    if (w.isEmpty) None else Some(w)
  }

  def tokenize(text: String): List[Token] = {
    text.split("\\\\s+").filter(_.nonEmpty).zipWithIndex.flatMap { case (word, i) =>
      processToken(word).map { processed =>
        Token(processed, TokenType.STRING, Map("position" -> i, "original" -> word))
      }
    }.toList
  }

  def tokenizeToStrings(text: String): List[String] =
    tokenize(text).map(_.value)

  def tokenizeWithPositions(text: String): List[(String, Int, Int)] = {
    var currentPos = 0
    text.split("\\\\s+").filter(_.nonEmpty).flatMap { word =>
      val start = text.indexOf(word, currentPos)
      val end = start + word.length
      currentPos = end
      processToken(word).map(p => (p, start, end))
    }.toList
  }

  def countTokens(text: String): Int = tokenize(text).length
}

// ============================================================================
// TokenizerBuilder
// ============================================================================

case class TokenizerBuilder[T](
  private val normalizers: List[String => String] = List.empty,
  private val validators: List[T => Boolean] = List.empty,
  private val builderMetadata: Map[String, Any] = Map.empty
) {
  def withNormalizer(normalizer: String => String): TokenizerBuilder[T] =
    copy(normalizers = normalizers :+ normalizer)

  def withValidator(validator: T => Boolean): TokenizerBuilder[T] =
    copy(validators = validators :+ validator)

  def withMetadata(entries: (String, Any)*): TokenizerBuilder[T] =
    copy(builderMetadata = builderMetadata ++ entries.toMap)

  def build(): T => Token = { value: T =>
    validators.foreach { validator =>
      if (!validator(value))
        throw new IllegalArgumentException(s"Validation failed for $$value")
    }
    var strValue = value.toString
    normalizers.foreach { normalizer =>
      strValue = normalizer(strValue)
    }
    Token(strValue, TokenType.STRING, builderMetadata)
  }
}
'''

if __name__ == '__main__':
    generate_scala_file('/root/Tokenizer.scala')
