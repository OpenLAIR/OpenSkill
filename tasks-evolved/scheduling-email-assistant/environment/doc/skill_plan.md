# Skill Creation Plan

**Task**: Read meeting request emails from JSON, check Google Calendar for availability, find earliest compatible time slots, send formatted reply emails via Gmail API, and save sent message IDs to results.json

**Rationale**: The task has three distinct functional domains: (1) parsing natural language email requests to extract scheduling constraints, (2) interacting with Google Calendar API to find available slots, and (3) composing and sending reply emails via Gmail API. However, since the environment has pre-installed Node.js skills for Gmail and Calendar, and the overall orchestration is tightly coupled, a 3-skill decomposition by concern (email parsing, calendar availability, email sending+orchestration) provides clear boundaries while keeping complexity manageable.

**Number of skills**: 3

---

## Skill 1: evo-meeting-request-parser

**Description**: Parses natural language meeting request emails to extract structured scheduling constraints including date ranges, time windows, meeting duration, and sender information.

**Responsibility**: Extract meeting dates/date ranges, time availability windows, meeting duration, and timezone from free-text email bodies. Returns structured data ready for calendar querying.

**Key functions**: `parse_meeting_request`, `extract_dates`, `extract_time_window`, `extract_duration_minutes`, `normalize_to_datetime_ranges`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-meeting-request-parser/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-calendar-availability-finder

**Description**: Queries Google Calendar API to retrieve busy periods and finds the earliest available time slot matching the requested duration within specified date/time constraints.

**Responsibility**: Authenticate with Google Calendar API, query events or freebusy endpoint for given date ranges, compute available gaps using interval merging algorithm, and return the earliest slot that satisfies the meeting duration requirement.

**Key functions**: `authenticate_calendar`, `get_busy_periods`, `find_earliest_available_slot`, `merge_busy_intervals`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-calendar-availability-finder/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 3: evo-gmail-reply-sender

**Description**: Composes and sends formatted meeting reply emails via Gmail API using the specified template, and saves sent message IDs to results.json.

**Responsibility**: Authenticate with Gmail API, construct MIME messages with proper base64url encoding and reply headers, format date/time strings per the exact required format, send emails, collect message IDs, and write results.json output file.

**Key functions**: `authenticate_gmail`, `format_meeting_reply`, `create_and_send_email`, `save_results_json`, `format_date_string`, `format_time_range`

**Depends on**: evo-meeting-request-parser, evo-calendar-availability-finder


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-gmail-reply-sender/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.
