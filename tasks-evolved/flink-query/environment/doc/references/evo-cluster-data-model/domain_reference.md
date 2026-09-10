# Domain Reference for evo-cluster-data-model

**Responsibility**: Define the TaskEvent and JobEvent data type classes under clusterdata.datatypes, ensuring they meet Flink POJO serialization requirements (public fields, no-arg constructor). Provide CSV line parsing logic with correct column indices, handling of empty/missing fields, and microsecond timestamp semantics.

**Key functions to implement**: parse_task_event_from_csv, parse_job_event_from_csv, get_event_type_constants

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