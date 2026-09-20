# Data Model

## Goal

The goal of this model is to transform raw Crowds event data into a small,
reusable structure that can support customer-facing run metrics.

The model intentionally stays simple for the MVP.

---

## 1. Raw Events

The original event-level data is kept as the source of truth.

Important fields:

- event_id
- run_id
- event_type
- server_timestamp
- client_timestamp
- session_id
- device_id
- zone
- cue_id
- target_zone
- latency_ms
- software_version
- payload

Raw data is not assumed to be clean. Data quality checks are applied before
using fields in customer-facing metrics.

---

## 2. Runs

One record per event run.

| Field | Description |
|---|---|
| run_id | Unique run identifier |
| started_at | Run start timestamp |
| ended_at | Run end timestamp |
| status | Run completion status |

Relationship:

One run can contain many devices and many cues.

---

## 3. Run Devices

One record per device participating in a run.

| Field | Description |
|---|---|
| run_id | Run identifier |
| device_id | Device identifier |
| zone | Device zone |
| software_version | Client software version |
| first_joined_at | First observed join time |
| left_at | Time the device explicitly left, if available |

`device_id` is used as the participant identity.

A reconnect with a new `session_id` does not create a new participating device.

---

## 4. Cues

One record per cue sent during a run.

| Field | Description |
|---|---|
| run_id | Run identifier |
| cue_id | Cue identifier |
| sent_at | Server timestamp when the cue was sent |
| target_zone | Intended target population |
| cue_name | Cue name when available in payload |

The target zone is used to determine the expected recipient population.

---

## 5. Cue Device Facts

One logical record per cue and device.

| Field | Description |
|---|---|
| run_id | Run identifier |
| cue_id | Cue identifier |
| device_id | Device identifier |
| received | Whether delivery was observed |
| received_at | Receipt timestamp |
| latency_ms | Valid observed delivery latency |
| responded | Whether an interaction response was observed |
| response_at | Response timestamp |
| quality_flags | Relevant data quality warnings |

This table represents the relationship between a cue and an eligible device.

It can support metrics such as:

- cue delivery rate
- delivery latency
- observed response rate

---

## Relationships

Run
├── Run Devices
├── Cues
└── Cue Device Facts

A run has many devices.

A run has many cues.

A cue can target many devices.

A device can receive and respond to many cues.

---

## Data Quality Rules

The MVP applies the following rules:

1. Duplicate `event_id` records are counted only once.
2. Records without a `run_id` are excluded from the RunSummary.
3. A cue receipt without a `device_id` cannot be attributed to a device-level delivery.
4. A device is counted at most once per cue for delivery coverage.
5. Negative latency is excluded from latency calculations.
6. High but plausible latency values are retained.
7. Invalid client timestamps do not automatically invalidate the entire event.
8. Explicit `left_event` records remove a device from later cue target populations.

---

## Important Assumptions

- `device_id` represents a unique participating device.
- `server_timestamp` is used for event ordering in the MVP.
- `target_zone = ALL` targets all eligible participating devices.
- A specific target zone only targets devices assigned to that zone.
- An explicit `left_event` means the device is no longer eligible for later cues.
- Observed response rate should not automatically be interpreted as engagement rate because the source data does not specify whether every cue expects a response.

These assumptions should be validated with the Crowds product and engineering teams before production use.
