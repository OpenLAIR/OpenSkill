# Apache Flink 1.20 DataStream API: Implementing Event-Time Session Window Aggregations on Google Cluster Trace Data

**Key Points:**
*   **API Evolution**: Apache Flink 1.20 introduces significant API shifts, strictly deprecating older time abstractions (e.g., `Time.minutes()`) in favor of Java's native `Duration` class, and replacing legacy `SinkFunction` implementations (like `writeAsText`) with the unified `FileSink` API.
*   **Time Semantics**: The Google Cluster Trace 2011 v2 utilizes a microsecond-based timestamp offset from a specific epoch. Implementing event-time processing in Flink requires meticulous conversion to milliseconds and robust watermark strategies to handle out-of-order trace events.
*   **Windowing Mechanics**: Event-time session windows are highly effective for tracking job-submission stages. Flink dynamically groups events separated by less than a specified inactivity gap, seamlessly merging windows when late data arrives within the allowed latency bounds.

**Understanding the Challenge**
Processing large-scale data traces like the Google Cluster Trace requires a robust distributed system. The goal here is to analyze millions of task events to track how jobs are submitted and scheduled over time. By using Apache Flink, we can treat this historical dataset as a continuous "stream" of events. 

**Why Session Windows?**
Unlike fixed windows (e.g., every 5 minutes), session windows group events based on activity. If a job receives a flurry of task submissions, they are grouped into a single "session." If there is a long pause, the session closes. This perfectly models real-world computing workloads where job scheduling is bursty rather than continuous.

**The Role of Watermarks**
Because events in distributed systems (and in historical logs) can be slightly out of order, Flink uses "watermarks" as a way to track the progress of time. A watermark essentially tells the system, "I do not expect any more events older than this timestamp," allowing the system to confidently close windows and compute final results.

---

## 1. Google Cluster Data 2011 v2 Schema Configuration

The Google Cluster Trace 2011 v2 dataset provides an unparalleled view into the resource utilization and scheduling behaviors of a massive Borg-managed compute cell over a 29-day period [cite: 1, 2]. This dataset is distributed as multiple gzipped CSV files. Understanding the exact schema is critical for designing the deserialization logic in Flink.

### 1.1 Table Schemas

The dataset is strictly structured, though it lacks CSV headers [cite: 1]. The columns must be parsed by their index position. 

**Task Events Table (`task_events`)**
The `task_events` table tracks the lifecycle of individual tasks, which are the fundamental units of execution mapped to physical machines [cite: 3, 4]. The columns, in exact order, are:

| Index | Column Name | Data Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | **timestamp** | `Long` | Event time in microseconds. |
| 1 | **missing info** | `Integer` | Indicates if data is missing. |
| 2 | **job ID** | `Long` | Unique identifier for the job. |
| 3 | **task index** | `Integer` | The index of the task within the job. |
| 4 | **machine ID** | `Long` | The ID of the machine executing the task. |
| 5 | **event type** | `Integer` | Integer code representing the lifecycle state. |
| 6 | **user** | `String` | Anonymized user identifier. |
| 7 | **scheduling class** | `Integer` | Latency sensitivity (0-3). |
| 8 | **priority** | `Integer` | Priority of the task. |
| 9 | **CPU request** | `Double` | Normalized CPU cores requested. |
| 10 | **memory request** | `Double` | Normalized RAM requested. |
| 11 | **disk space request** | `Double` | Normalized local disk space requested. |
| 12 | **different-machines constraint** | `Boolean` | Restriction flag for deployment. |

**Job Events Table (`job_events`)**
The `job_events` table tracks the higher-level lifecycle of jobs, which are collections of tasks [cite: 3, 5].

| Index | Column Name | Data Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | **timestamp** | `Long` | Event time in microseconds. |
| 1 | **missing info** | `Integer` | Indicates if data is missing. |
| 2 | **job ID** | `Long` | Unique identifier for the job. |
| 3 | **event type** | `Integer` | Integer code representing the lifecycle state. |
| 4 | **user** | `String` | Anonymized user identifier. |
| 5 | **scheduling class** | `Integer` | Latency sensitivity (0-3). |
| 6 | **job name** | `String` | Hash of the job name. |
| 7 | **logical job name** | `String` | Hash of the logical job name. |

### 1.2 Event Type Integer Codes

Google encodes the state transitions of tasks and jobs using specific integer mappings [cite: 6]. The trace may contain simultaneous submissions and schedules. The codes are:

*   **`0` (SUBMIT)**: The job or task was submitted to the scheduler.
*   **`1` (SCHEDULE)**: The job or task became eligible for scheduling or was dispatched.
*   **`2` (EVICT)**: The task was descheduled due to a higher priority task or overcommitment.
*   **`3` (FAIL)**: The task or job failed.
*   **`4` (FINISH)**: The task or job completed successfully.
*   **`5` (KILL)**: The task or job was cancelled by the user or cluster manager.
*   **`6` (LOST)**: The record of the task was lost, usually due to machine failure.
*   **`7` (UPDATE_PENDING)**: Resource requirements were updated while pending.
*   **`8` (UPDATE_RUNNING)**: Resource requirements were updated while running.

### 1.3 Timestamp Semantics

Timestamps in the Google Cluster Trace are not standard UNIX epochs. Instead, they are recorded as 64-bit integers representing **microseconds** since 600 seconds before the beginning of the trace period (May 1, 2011) [cite: 1, 2]. Furthermore, a timestamp of `0` is a special value representing events that occurred *before* the trace window began (e.g., jobs that were already running when the trace started) [cite: 1]. When processing this data in Flink, these microseconds must be divided by `1000` to convert them into the milliseconds that Flink's internal event-time clock requires [cite: 7].

## 2. Flink 1.20 DataStream API: Reading Gzipped CSV Files

In Flink 1.20, the legacy `StreamExecutionEnvironment.readTextFile()` method is heavily discouraged and internally deprecated for production pipelines because it does not support advanced unified source concepts (like dynamic partition discovery and modern watermark alignment) [cite: 8, 9]. The modern, robust approach is to use the `FileSource` API from the `flink-connector-files` library [cite: 8].

### 2.1 Transparent Gzip Decompression

Both the legacy `readTextFile()` and the modern `FileSource` (using `TextLineInputFormat`) leverage Flink's underlying `FileInputFormat` which transparently handles decompression [cite: 10]. When a file ends with the `.gz` extension, Flink's API automatically delegates the reading to a `GZIPInputStream`, decompressing the data on the fly without requiring explicit user logic [cite: 8, 10].

### 2.2 Implementing FileSource

To utilize the modern `FileSource`, ensure the `flink-connector-files` dependency is included [cite: 11]. The exact code implementation for reading a gzipped CSV is as follows:

```java
import org.apache.flink.connector.file.src.FileSource;
import org.apache.flink.connector.file.src.reader.TextLineInputFormat;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;

// Define the path (can be a directory or a specific .csv.gz file)
Path traceFilePath = new Path("path/to/task_events.csv.gz");

// Build the FileSource
FileSource<String> fileSource = FileSource.forRecordStreamFormat(
        new TextLineInputFormat(), traceFilePath)
    .build();

// Add the source to the environment
DataStream<String> traceLines = env.fromSource(
    fileSource,
    WatermarkStrategy.noWatermarks(), // Watermarks will be assigned post-parsing
    "Google Trace File Source"
);
```

## 3. Flink 1.20 POJO vs. Tuple Requirements

When parsing the string lines into structured data, developers must choose between Flink's built-in `Tuple` classes or custom Plain Old Java Objects (POJOs).

### 3.1 POJO Requirements

To achieve optimal serialization performance, Flink relies on the `PojoSerializer`. If a class fails Flink's POJO validation, it silently falls back to the inefficient `Kryo` serializer, creating a `GenericTypeInfo` which can severely degrade performance and cause state migration issues [cite: 12, 13].

A valid Flink POJO in version 1.20 must meet the following strict criteria:
1.  **Public Class**: The class itself must be public and standalone (no non-static inner classes) [cite: 14].
2.  **No-Argument Constructor**: It must possess a public no-argument constructor [cite: 14, 15].
3.  **Field Accessibility**: All fields must either be `public` (and non-final), or they must be `private` but accessible via public getters and setters that strictly follow the Java Beans naming convention (e.g., `getTimestamp()` and `setTimestamp()`) [cite: 14, 15].
4.  **Serializable Types**: Every field type must be supported by Flink's native serializers (avoid complex generic collections; use primitive wrappers or native arrays where possible) [cite: 12].

**Example POJO Implementation:**
```java
public class TaskEvent {
    public long timestamp;
    public long jobId;
    public int eventType;
    // Public no-arg constructor is mandatory
    public TaskEvent() {}
}
```

### 3.2 Tuple Requirements

Alternatively, Flink provides built-in `Tuple` classes (from `Tuple0` to `Tuple25`) [cite: 14]. Tuples are highly optimized composite types with deterministic field order. Unlike POJOs, you access their fields directly using `f0`, `f1`, `f2`, etc.

**Tuple Import Path:**
`import org.apache.flink.api.java.tuple.Tuple2;`

Tuples are instantiated directly (e.g., `new Tuple2<>(jobId, count)`) and their `.toString()` automatically produces the desired `(value1,value2)` format natively, making them highly convenient for simple output sinks.

## 4. Event Time and Watermarks in Flink 1.20

The Google cluster trace relies entirely on its own historical timestamps. To allow Flink to window this data accurately, we must instruct Flink to use **Event Time** rather than the wall-clock time of the processing machine [cite: 7].

### 4.1 Timestamp Assignment and Microsecond Conversion

Flink's internal watermark and event-time mechanisms operate strictly in **milliseconds**. Because the Google trace uses microseconds, the parsed timestamp must be divided by `1000` inside the `TimestampAssigner` [cite: 1, 7].

### 4.2 WatermarkStrategy API

Flink 1.20 utilizes the unified `WatermarkStrategy` API. Because historical data can be slightly out of order due to file splitting or distributed ingestion, `forBoundedOutOfOrderness` is the standard approach [cite: 7]. 

**Exact API Usage and Import Paths:**
```java
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import java.time.Duration;

WatermarkStrategy<TaskEvent> strategy = WatermarkStrategy
    .<TaskEvent>forBoundedOutOfOrderness(Duration.ofSeconds(10))
    .withTimestampAssigner((event, timestamp) -> {
        // Convert microsecond trace time to milliseconds
        return event.timestamp / 1000L;
    });

DataStream<TaskEvent> eventStream = parsedStream.assignTimestampsAndWatermarks(strategy);
```
*(Note: If the data is guaranteed perfectly ordered by time, `forMonotonousTimestamps()` can be used, but bounded out-of-orderness is safer for distributed trace files).*

## 5. Filtering the DataStream

To identify task submission stages, the stream must be filtered to isolate `SUBMIT` events. According to the trace schema, a `SUBMIT` event is represented by the integer code `0` [cite: 6].

Filtering is achieved using a standard `FilterFunction`:
```java
import org.apache.flink.api.common.functions.FilterFunction;

DataStream<TaskEvent> submitEvents = eventStream.filter(new FilterFunction<TaskEvent>() {
    @Override
    public boolean filter(TaskEvent event) throws Exception {
        return event.eventType == 0; // 0 = SUBMIT
    }
});
```

## 6. Flink 1.20 Session Windows

Session windows are dynamic. Instead of enforcing rigid time boundaries (like Tumbling windows), they group events based on temporal proximity. If a defined gap of inactivity occurs (e.g., no tasks submitted for 10 minutes), the session is closed [cite: 16, 17].

### 6.1 The Transition to `Duration`

A major API shift in Flink 1.20 (originating in late 1.19 and solidified for 2.0 preparation) is the strict deprecation of the `org.apache.flink.streaming.api.windowing.time.Time` class [cite: 18]. The API `EventTimeSessionWindows.withGap(Time.minutes(10))` is deprecated. Developers must now use the standard Java `java.time.Duration` [cite: 18, 19].

**Correct Import Path:**
`import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;`

### 6.2 Aggregation Strategy

To count the number of submissions per session per job, the stream is keyed by `jobId`. Then, the window function is applied.

While you *could* use a `ProcessWindowFunction` to iterate over all elements and count them, this is highly inefficient because Flink must buffer every single `TaskEvent` inside the window state until the window fires [cite: 16]. 

The simplest and most performant approach is to use `.aggregate()` with an `AggregateFunction` coupled with a `ProcessWindowFunction` [cite: 20]. The `AggregateFunction` maintains a rolling integer count (keeping state infinitesimally small), and the `ProcessWindowFunction` is invoked only once at window closure to wrap the final count into a structured output (like a Tuple containing the job ID, session start time, and count) [cite: 20, 21].

**Implementation Example:**
```java
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

// 1. The AggregateFunction: incrementally counts elements
public class CountAggregator implements AggregateFunction<TaskEvent, Long, Long> {
    @Override
    public Long createAccumulator() { return 0L; }
    @Override
    public Long add(TaskEvent value, Long accumulator) { return accumulator + 1L; }
    @Override
    public Long getResult(Long accumulator) { return accumulator; }
    @Override
    public Long merge(Long a, Long b) { return a + b; }
}

// 2. The ProcessWindowFunction: wraps the final count into a Tuple3
public class SessionResultWrapper extends ProcessWindowFunction<Long, Tuple3<Long, Long, Long>, Long, TimeWindow> {
    @Override
    public void process(Long jobId, Context context, Iterable<Long> elements, Collector<Tuple3<Long, Long, Long>> out) {
        Long count = elements.iterator().next();
        out.collect(new Tuple3<>(jobId, context.window().getStart(), count));
    }
}

// 3. Pipeline application
DataStream<Tuple3<Long, Long, Long>> sessionCounts = submitEvents
    .keyBy(event -> event.jobId)
    .window(EventTimeSessionWindows.withGap(Duration.ofMinutes(10)))
    .aggregate(new CountAggregator(), new SessionResultWrapper());
```

## 7. Finding the Maximum Across Multiple Windows Per Key

The previous step outputs a stream of `(jobId, sessionStart, count)`. Since a single job might have multiple sessions over the 29-day trace, we want to find the single session that had the absolute maximum number of task submissions for that specific job.

To achieve this, we execute a secondary `keyBy` on the `jobId` and apply a `reduce` function. The `reduce` function acts as a continuous running maximum: it compares the newly fired session count against the historically maintained highest count for that job, and emits the larger of the two.

```java
DataStream<Tuple3<Long, Long, Long>> maxSessionsPerJob = sessionCounts
    .keyBy(tuple -> tuple.f0) // key by jobId
    .reduce((currentMax, newSession) -> {
        if (newSession.f2 > currentMax.f2) {
            return newSession; // The new session is larger
        }
        return currentMax; // The old maximum remains
    });
```
*Note: Because this stream is unbounded, `reduce` will emit an updated maximum every time a session completes that breaks the previous record. To output strictly one record per job, the stream must be completely bounded, which we address in the pitfalls section.*

## 8. Flink 1.20: Writing Output to a Local File

### 8.1 The Deprecation of `writeAsText()`

In Flink 1.20, `DataStream.writeAsText()` is deprecated and highly discouraged [cite: 22, 23]. It was never a production-ready sink because it lacked proper integration with Flink's checkpointing mechanics (resulting in at-least-once or undefined semantics upon failure) and is slated for removal in Flink 2.0 [cite: 22, 23]. Furthermore, the `SinkFunction` interface itself is officially deprecated in 1.20 in favor of the unified `SinkV2` architecture [cite: 24].

### 8.2 Implementing FileSink

The modern replacement is the `FileSink` from `flink-connector-files` [cite: 22]. By mapping our `Tuple3` to a `Tuple2<Long, Long>` (stripping out the timestamp if only `(jobId, count)` is desired), we can rely on Flink's native string encoding.

To force all output into a single local file instead of multiple part-files spread across task managers, we must explicitly chain `.setParallelism(1)` to the sink [cite: 25].

```java
import org.apache.flink.connector.file.sink.FileSink;
import org.apache.flink.api.common.serialization.SimpleStringEncoder;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.functions.sink.filesystem.rollingpolicies.DefaultRollingPolicy;

// Transform to Tuple2<Long, Long> which natively prints as (value1,value2)
DataStream<Tuple2<Long, Long>> finalOutput = maxSessionsPerJob
    .map(t -> new Tuple2<>(t.f0, t.f2))
    .returns(org.apache.flink.api.common.typeinfo.Types.TUPLE(
        org.apache.flink.api.common.typeinfo.Types.LONG, 
        org.apache.flink.api.common.typeinfo.Types.LONG));

// Build the FileSink
FileSink<Tuple2<Long, Long>> sink = FileSink
    .forRowFormat(new Path("file:///tmp/flink-output"), new SimpleStringEncoder<Tuple2<Long, Long>>("UTF-8"))
    .withRollingPolicy(
        DefaultRollingPolicy.builder()
            .withRolloverInterval(Duration.ofMinutes(15))
            .withInactivityInterval(Duration.ofMinutes(5))
            .withMaxPartSize(1024 * 1024 * 1024L) // 1 GB
            .build())
    .build();

// Attach the sink with Parallelism 1
finalOutput.sinkTo(sink).setParallelism(1);
```

## 9. Common Pitfalls and Architectural Patterns

### 9.1 Bounded vs. Streaming Mode and Final Watermarks
When processing historical data files via `FileSource`, Flink reads in **bounded** (batch) mode by default [cite: 8]. This has a critical interaction with Event Time and watermarks. 
In unbounded streams, a session window only closes when a watermark passes the `window_end + allowed_lateness` threshold. However, in a bounded trace file, once EOF is reached, the source automatically emits a `MAX_WATERMARK`. This terminal watermark forces all open windows (and subsequent stateful operators) to flush and emit their final results before the job terminates. Therefore, developers do not need to worry about the final session windows remaining stranded in state.

### 9.2 The Parallelism 1 Sink Bottleneck
While setting `.setParallelism(1)` on the sink successfully generates a single output file, it forces all upstream data across the cluster to funnel into a single TaskManager. For the 40GB compressed Google Trace, this will cause severe backpressure and network bottlenecking. In a true production environment, it is best practice to let Flink write to multiple part-files (`.setParallelism(default)`) and concatenate them post-execution using an OS command (e.g., `cat part-* > final_output.txt`).

### 9.3 The `AppBase` Pattern
In Flink training and structured engineering environments, the `AppBase` pattern is heavily utilized. An `AppBase` is an abstract class that encapsulates boilerplate setup:
1.  **Environment Initialization**: Centralizes `StreamExecutionEnvironment.getExecutionEnvironment()`.
2.  **Configuration Management**: Reads properties files to supply dynamic variables via methods like `getTaskEventSourcePath()`, `getJobEventSourcePath()`, and `getOutputPath()`.
3.  **Execution Hook**: Provides a protected abstract method `buildTopology(StreamExecutionEnvironment env)` which subclasses implement, and a public `execute()` method that handles the `env.execute("Job Name")` call.

## 10. Comprehensive Working Code Example

Below is the complete, integrated working code fulfilling all user requirements, adhering to Flink 1.20 modern best practices.

```java
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.AggregateFunction;
import org.apache.flink.api.common.functions.FilterFunction;
import org.apache.flink.api.common.functions.MapFunction;
import org.apache.flink.api.common.serialization.SimpleStringEncoder;
import org.apache.flink.api.java.tuple.Tuple2;
import org.apache.flink.api.java.tuple.Tuple3;
import org.apache.flink.connector.file.sink.FileSink;
import org.apache.flink.connector.file.src.FileSource;
import org.apache.flink.connector.file.src.reader.TextLineInputFormat;
import org.apache.flink.core.fs.Path;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.filesystem.rollingpolicies.DefaultRollingPolicy;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.assigners.EventTimeSessionWindows;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.time.Duration;

public class GoogleClusterTraceSessionProcessor {

    // 1. Define the POJO ensuring it meets Flink's strict serialization requirements
    public static class TaskEvent {
        public long timestamp;
        public long jobId;
        public int eventType;
        
        public TaskEvent() {} // Mandatory no-arg constructor
        
        public TaskEvent(long timestamp, long jobId, int eventType) {
            this.timestamp = timestamp;
            this.jobId = jobId;
            this.eventType = eventType;
        }
    }

    public static void main(String[] args) throws Exception {
        // Initialize the environment
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // 2. Read the Gzipped CSV using FileSource
        Path traceFilePath = new Path("data/task_events.csv.gz");
        FileSource<String> fileSource = FileSource.forRecordStreamFormat(new TextLineInputFormat(), traceFilePath).build();

        DataStream<String> rawStream = env.fromSource(fileSource, WatermarkStrategy.noWatermarks(), "CSV Source");

        // 3. Parse CSV to POJO
        DataStream<TaskEvent> parsedStream = rawStream.map(new MapFunction<String, TaskEvent>() {
            @Override
            public TaskEvent map(String line) {
                String[] parts = line.split(",");
                // Protect against empty lines or malformed data
                if (parts.length < 6) return new TaskEvent(-1L, -1L, -1);
                try {
                    long ts = Long.parseLong(parts);
                    long jobId = Long.parseLong(parts[cite: 26]);
                    int evType = Integer.parseInt(parts[cite: 27]);
                    return new TaskEvent(ts, jobId, evType);
                } catch (NumberFormatException e) {
                    return new TaskEvent(-1L, -1L, -1);
                }
            }
        }).filter(event -> event.timestamp != -1L); // Remove parse errors

        // 4. Assign Timestamps and Watermarks (Microseconds to Milliseconds)
        WatermarkStrategy<TaskEvent> watermarkStrategy = WatermarkStrategy
                .<TaskEvent>forBoundedOutOfOrderness(Duration.ofSeconds(10))
                .withTimestampAssigner((event, timestamp) -> event.timestamp / 1000L);

        DataStream<TaskEvent> eventTimeStream = parsedStream.assignTimestampsAndWatermarks(watermarkStrategy);

        // 5. Filter for SUBMIT events (eventType == 0)
        DataStream<TaskEvent> submitStream = eventTimeStream.filter(new FilterFunction<TaskEvent>() {
            @Override
            public boolean filter(TaskEvent event) {
                return event.eventType == 0;
            }
        });

        // 6. Session Window Aggregation
        DataStream<Tuple3<Long, Long, Long>> sessionCounts = submitStream
                .keyBy(event -> event.jobId)
                // Use Duration.ofMinutes, not Time.minutes!
                .window(EventTimeSessionWindows.withGap(Duration.ofMinutes(10)))
                .aggregate(new CountAggregator(), new SessionResultWrapper());

        // 7. Find Maximum Session per Job
        DataStream<Tuple2<Long, Long>> maxSessions = sessionCounts
                .keyBy(tuple -> tuple.f0)
                .reduce((t1, t2) -> t1.f2 > t2.f2 ? t1 : t2)
                // Strip out the timestamp, leaving (jobId, maxCount)
                .map(t -> new Tuple2<>(t.f0, t.f2))
                .returns(org.apache.flink.api.common.typeinfo.Types.TUPLE(
                        org.apache.flink.api.common.typeinfo.Types.LONG, 
                        org.apache.flink.api.common.typeinfo.Types.LONG));

        // 8. Write to Local FileSink (Replacing writeAsText)
        FileSink<Tuple2<Long, Long>> sink = FileSink
                .forRowFormat(new Path("output/max_sessions"), new SimpleStringEncoder<Tuple2<Long, Long>>("UTF-8"))
                .withRollingPolicy(DefaultRollingPolicy.builder()
                        .withRolloverInterval(Duration.ofMinutes(15))
                        .withInactivityInterval(Duration.ofMinutes(5))
                        .withMaxPartSize(1024 * 1024 * 1024L)
                        .build())
                .build();

        maxSessions.sinkTo(sink).setParallelism(1); // Force to a single file

        env.execute("Google Cluster Trace - Session Analysis");
    }

    // --- Helper Classes ---

    public static class CountAggregator implements AggregateFunction<TaskEvent, Long, Long> {
        @Override
        public Long createAccumulator() { return 0L; }
        @Override
        public Long add(TaskEvent value, Long accumulator) { return accumulator + 1L; }
        @Override
        public Long getResult(Long accumulator) { return accumulator; }
        @Override
        public Long merge(Long a, Long b) { return a + b; }
    }

    public static class SessionResultWrapper extends ProcessWindowFunction<Long, Tuple3<Long, Long, Long>, Long, TimeWindow> {
        @Override
        public void process(Long jobId, Context context, Iterable<Long> elements, Collector<Tuple3<Long, Long, Long>> out) {
            out.collect(new Tuple3<>(jobId, context.window().getStart(), elements.iterator().next()));
        }
    }
}
```

**Sources:**
1. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDXYMgmymTcQiYe2A2IQPzApa9rcMJAdAWqm3ulxB49JRdIGKl1770ZXNkPCFoH4gmFeoirQLN1680GIJ1__mWDdXRl7u7e4Rj6SJVu0fjChOy-6_h2EHK_U646Ay9zt8v2w5V-hQukKrqmPR9erVVoKmfz3eM_zip0_SpnNwr71NBMioFlRz6_AIeZ3VeQWBhISc6_PvksyNWMofpJXS3YriQZHpNoOxjIkXAaxMUeZJVOXmCNsnSAUJwz6cduTP96ts5a9oL-ngVQXF3AyuygdY5tbtNwWqyr4eKY1cmOtq2kUdMs17QDUvU2yU5M4F0LfllH8PiqnUuNSSCRj-WqPhFbGQlyg==)
2. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPW_qWoaXLvL2eLvICs7sbHkGe4PhqPSqAyFul_FnlmiutkJdWlZOHJ-5kKJJYQUAYz4mdVK9Gupvd5SJsbZ3ntIyR_13TK3wE3HhwyyjrfVFJGwhJf-2UF0H5RwrZWLKP2oha3d8RxFtTi_P36k43sT5G1lMbwzQ8G8lWaA==)
3. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHy6tQHqqHgrwhYXCVrbWyWdRB_0RQ4A6wFGB2Cd41pT6-lZ_xXeduy_ynProa2r_a_6F3fR0E-DCwgHzKvLJA4pcWKvUXPO2JpYX2H4Ci22Iaodx3JrorDXmHBJigSXEu5ORZxEvGLPHEsBanDRBIcHwiek2BzHGjrV8qPELeUVzYes3_dP0PF-hF3sFJcFjOjjLlBXUhcBi_DuOKNFkkJ2lJg5kXK4mmy6jemzFbOQdNw9hZY9VOIBgn97VMJDQ4y1OR8M7pJqj2OkRQrlW_7OawWdVpB1_hUw-H7Bg==)
4. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHB_Uyr87FUYjt663SZEfp9hMsKNJ2VB1ZE7yekxTeRoQUGmkgFgxKnqdacxltINJps7i4UV5e1ScAQO5UrDc0VJdaTficLoon9xX4UczPZ90FxdqDfwA==)
5. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGFKFam-7jaxgQMoh7KyYwtbbiMpxQgd39jOAi7ad6b6q6svC7v2C7NGcwuoc4IU-g30xA_Y-CdxtlLfFVgSBpYm39xCeTC74nqpZhVH1qLrh0c_8oQWw==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGilg_KEHhagW2oPCfcLbYLfMH138XzpMU-aV9CcjIEDuPSodR399HLzkDzMgnO8oJFwDE8kOK3v-jDHaJcwWONoICV1xEz61CK2UIjfLUcnPUYN05lA_UXm6XyYHTM_uTc4sy1h4Ya5N9y8iPDKvtV6WB4LRiVC04OHZXBAtQjkI5sHF_m9LtPKrI=)
7. [conduktor.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHEPuDanODyiGpbLoq59yetNV6A47NPXL7YI_ODqCFkC7qOe3uHwVG_g24es_uwwy8XFutrYiybiJu_TvgPsLIwe8znaTUP80ivYaVhi5VpJLD326MQB3edX1iNnOtGM4xm3PBjU1fT-UJeUDXK3OmzBX5FZDET)
8. [javadoc.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFl49lbeOxGsTvsu8eJQbLu8IuD3ljhLZRUlbxFEMJyR6eYYrqbJfWQXcQsHDouosFBoRBkF8ouQVYeGPAGZrfAVjKXjGt9zWZhAJvdzgKbRLKZxH4RoWTksw8OV65YtcMde1T1a43RNM2XLcCOz3it-3gqI0DyJyA620csDZqnzE06kjGAaZfRA4GJWOtF8eagBcloXEcTFaNntCXu4_THONvGEA2qp_ickfBMN64=)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHpYk8tzex2jz4uwylrm5ww6fYx1ZXwbMbmdg1GdO1V4EVGxHeNGJ50PHpZ38jpe7o8wyrI2A8NncqiOg1V0cn5RVfGUAEZczvFuq-Q4TfVwfF8aUYxo11WP-aYkGrHGhUw5Wwy3WwTyqZAPbTavt4xD0RqFYbjXzmCkrG6lGIXPxuQGTeifbwy7ExrI6mb9ydgSA==)
10. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH6ZNsNtqIdbIfixSDAUYX38cILrusOhgVOiZSEchD1-5M-xSjj8foUleH5rr2IuV49v894pjUe26Voxj2CMGyYPt65tGhkaSXaKPBuc1yckgpgkukog2DE9r9l-Ry9CBCP64zhlHnrI_UBeVz8NDFFMNGY0kf0RL27tvaU21GN2cOdJbkHsnNr)
11. [amazon.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE0D2ETZaXSNtbdPimPtI3_9mD1kQDmFMYrex9LXvJrsaTprg5aUDySlb5TN8rlMt0IVA4QGbuqGurTvP8UkbAnwtcw6Q2pd4WY1gmM39DAhoO_OxtdHpEc8s4bR73LujB3yNWqkgJNB847_rMHxcSPl9vvxqgYJUidgQPFcS39)
12. [amazon.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFo9V0MCKpZkQNTh2TdIKQ4XEQ63f9omk8z_-xaB3I6x-FQ2PHR6_qWFr37LQuNsNrHSAX0mTcl7iGgHkbcE_nLSuxPKW2O_gug_4hKszUishykkvgS_lPk4HabDHq3ocZeykPv9LAnsMW59nc7NP6VcXuT4FBueLQw3cJULeBu0AX4EMg=)
13. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHICQRXSY-mmj3PNtRF7wrLaeNK-1b2PY8_qTqDqzSMKy9A43Iq-hDELLkdpnxb7waVFEIqoJPmnFTJlbbxiO5WGI2cDZvEzVEZb7VgS_URvAVhf81KrnYMNo47dmRQt3kCGH4wHu42IWMV7peSLtdcax6jXOPOY2FpC3abXqm5UVa6e5_KzB00Q4q-4_v1xyutIw3TwgqOK_535UVefNc4q0mM_Nr64HbPv_3ssE951LE=)
14. [javadoc.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEMUaL-YPNssioOddVf8tDm2wDNk1duzJKLmpUTCd0u_hHRGHnJnNr3H5uRYdiup3_tdZvlrSKKftstIlRBuJ82jMM6YzNlQqktgy96cKU_gq_ghag46JnAYwEskFS3J7ewR0EDfWji7ovBCYSRI_k-WB6OPDOQLc2a3ui_gAybLLDeDBHpbSX2_KRdntodU1_1M0rnHxrDHOlr619GvEJwmCg=)
15. [ibm.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7kUrFYWMS8B7RpUOFuC9weESDGu8LGRtFBXD7hRINzzgL5t551BaknVobTdnE0R_6j8JMKIHx2Ya0oDCLkE8kDaHEPLpDDclRJ_iXgpiVhrQ42FHHuSRAt81dne_SYcpwf_DEvX7-pmnlJ4MBMsjHNhQx_eQRUNo-1f1fpYkUpfmCDfJVq00v9Sf-SnDsRcm-6kcYeNpKzmVZkeVwQ1Cl3DlI1ynO-bp--e-bEx0=)
16. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErDnvZF8vcnfeA0y_oxg4Xl4T-buC29JAH3RYnrFGpi-DS0W8Bo263mFAySVEP-9vGRfzM6ZEJ-XPYO85gYv54Oi66faUIm24BcUKCNvtsBq1OuR2c2TO5O1u4IEz-_EvrN_8fXHclxstm_ZpQghoyUoQMkWerRKYvhgnRmigIYPUTPeK957BR2jz7sSgqVKIZAZLQdBMfYioWQMDzvRg=)
17. [oneuptime.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH1GmoQHs6YSyLPMsviXZFn9OBwnExGFdrBb8RYDH3HBS546Lo_M-HamHHuNht9ZH07tZwxgC_xtjeLRLeqvAQwXMNiLnsE38tLZYg211koPFjmk62TEELNBVg4ZHW0Sd8cnrJK6IJcb-HRqh9RKCx1DqacjiE=)
18. [cloudns.asia](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFV6k3TXqKKSofTZQH1AQq2-dJfw4JVejOd3cajCNnun3XkDntVqyHTlX5kjFNwCcodOu3lMlYDwtULvdUU1h3CTq9bCDJP_kEQU_H1D0-p9LuJyrLGxle8x_QJeEs7kGmbccRIHFubfTUwooW7xE45FhpvtlZ8EVIy5RrSg4yDY1plh92gQzdaNjk=)
19. [cloudns.asia](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGt9ULnwbNvE5_TTG-mTtkq6y0hjzVuuicWXIHpbarDbbRrvC_szxXe3-rrRSvk3Gdc4DLU15pIySj9YkNzPl5YbzwpV6gvnaJ15sO-_S7Dv8_PbmBW2hTrG2ducUfDWV2lZfa07_RlCTxCRWVIsX7IQKTAGrAS4ce40dj_NhE1pKYmxb4t985wmsmQ8mhwPK6QHZmYl35WHiOplQXPWpf-JKCM8OMqyotk0lmlsw==)
20. [conduktor.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQENklZhQdNn_Xrsse8zOqqaGMVa0Aul7xFTvYUEnEljjjWQV5xIsj_1XwFYJ4dBesR7i_gvSBMA_xRL05g3ld2V9QIpqD0zS2VQq_4_LCotfXol9Ufb7Y_eUYt2AxFG6GSuPpZ-RjDj0QAYp6DGf0Jcu9ahUxCDomXOCPj2sqXW701J-NlKH2I9r30TkNASYDs7bFQYOtc=)
21. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_MkUCE2h7UE8qcWiQrl1fGsT68i4zEhyIXDBLzm21kUWSj-dN7ce_hoRqxGXBOeEaTZUvVbGH-RduswUbwbanzDnyKR644huHTTqer4PTcIRiXJoqY24FeCWN9N0bQ-BVLZk58YrbfxZsR7GavWGGjGlrzhuHE_6vRNPoPBEEmtqSGjK602_GwCUUAF4hS4rK7rSO4nsHfjKzC787iPqjHDXzs8dgL_vJsudFItTwhVs=)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErfP5MlSSWWGDjunNRqTmFZLBi8WJIEj2xv9PLqU-WjIFPhGEs5hy6ag2ux2yBz-nLihbN7CpLukB-PvjZ3r37hZTGTsnWUOls7Wwxgb2ab0OuLCXFRVBwoNBSiXj1I5KQ1mAeIlOfhXF-YuZxASzGRN5x2tY06GoDFm5eIAy0fVHVjvDw-0IBg0UPpk-h)
23. [confluent.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFf0Nj0XtrIofc3K0nVsI4rVX3B32X9zxpcOJS7H58GGbhXCtyELpRMH531Sked3faZCpXUwg6W-pXIrDI99Tbig5Gt5lOQn8A55KyafCSE1nI-DSnyysvBmdLQnPlHQ5XGNsbbCznLba3_qkNbC3Ar)
24. [apache.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHqvODsIB1BHWRnIPeiqRcvIXRZEx0TMQMFDiVZBrwEfGMFRA0kDG6s7JKRkhUMY2k0iAkgifPiYtAxSH9WYAgXaPJg7UMAE04T76p-1kxPM22oVYQWv4gjmAErESmc7MBMYusxvFcb7EFfLteJGuksbnFd2ZerZgI6uq9LD9fwMyK_sE9fcA==)
25. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGVdf0n4i2E1MnjeUXtE4TEsT1dpJqQxks-cVhxzFCPLRb3VLKeXvVrWF6TJL1S8PJer8N6OElDW1q5Sq6FnND_u2gD_BDlSuenLQcduSl6wSqwMp_4H3YeQcFWbAr7CYBuaxWj40HZl43I7gU9OlwhVAM9oOCsSWogRTkx-SrdG4aTRDxfi3-jy3oK1QMkbwEEMA==)
26. [core.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0xzg98-BEDURAJs59sRpY1jqrsLOVmn8qVTF6UHOmQ0I6UdzrhP1vphb-yeHEaLtMUouB5ozX4yPFU1TnRA0ZI9plPV16RHF-owBsXqul4rBLNGx3dtoSkb6YedBgCPh-1w==)
27. [tuwien.at](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHW1FWqflT9bhxSUYkqi085Rl3MWCaFfuzpBgYba0HwAQZFy1QueHaDghyFlCB7AeRG3wXxw5BSJ7rg_X6rVFLGFkV-upjzSvegzrripQyjT_h_UY_bDqJfBpVZ1u754pX8uVeQf2ThABjLnZhZhZzmd1hA0o0fJzWb9hW2eAiw8oEapboz3oV7OTOEtyC8pXAAknfirUmZG8crpn6fA4qeubc7Ki6l1ioyasixh379kDjj3AIHKLsvySn0h64L5_LSZEjSVD8Aoqt92Mv5bMTd4eiUX6kJ4OJZ)
