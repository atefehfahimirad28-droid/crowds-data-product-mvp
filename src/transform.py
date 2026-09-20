import pandas as pd

import json
from pathlib import Path
# ============================================================
# 1. LOAD DATA
# ============================================================

DATA_PATH = "data/Crowds_Data_Product_Exercise_Sample_Data.csv"

df = pd.read_csv(DATA_PATH)

print("Dataset shape:")
print(df.shape)

print("\nColumns:")
print(df.columns.tolist())

print("\nEvent types:")
print(df["event_type"].value_counts())


# ============================================================
# 2. DATA QUALITY CHECKS
# ============================================================

print("\n--- DATA QUALITY CHECKS ---")


# 2.1 Duplicate event IDs
duplicates = df[
    df.duplicated(subset=["event_id"], keep=False)
]

print("\nDuplicate event IDs:")
print(
    duplicates[
        ["event_id", "event_type", "device_id"]
    ]
)


# 2.2 Missing run_id
missing_run_id = df[
    df["run_id"].isna()
]

print("\nRows with missing run_id:")
print(
    missing_run_id[
        ["event_id", "event_type", "device_id"]
    ]
)


# 2.3 Missing device_id for device-related events
device_events = df[
    df["event_type"].isin(
        [
            "device_joined",
            "device_disconnected",
            "device_reconnected",
            "cue_received",
            "interaction_response",
            "error",
        ]
    )
]

missing_device_id = device_events[
    device_events["device_id"].isna()
]

print("\nDevice events with missing device_id:")
print(
    missing_device_id[
        ["event_id", "event_type", "cue_id"]
    ]
)


# 2.4 Invalid negative latency
invalid_latency = df[
    df["latency_ms"] < 0
]

print("\nNegative latency:")
print(
    invalid_latency[
        ["event_id", "device_id", "cue_id", "latency_ms"]
    ]
)


# 2.5 Invalid client timestamps
parsed_client_timestamp = pd.to_datetime(
    df["client_timestamp"],
    format="mixed",
    errors="coerce",
    utc=True,
)

invalid_client_timestamp = df[
    df["client_timestamp"].notna()
    & parsed_client_timestamp.isna()
]

print("\nInvalid client timestamps:")
print(
    invalid_client_timestamp[
        [
            "event_id",
            "event_type",
            "device_id",
            "client_timestamp",
        ]
    ]
)


# 2.6 Possible semantic duplicate cue receipts
cue_receipts = df[
    (df["event_type"] == "cue_received")
    & df["device_id"].notna()
]

semantic_duplicates = cue_receipts[
    cue_receipts.duplicated(
        subset=["run_id", "cue_id", "device_id"],
        keep=False,
    )
]

print("\nPossible semantic duplicate cue receipts:")
print(
    semantic_duplicates[
        [
            "event_id",
            "cue_id",
            "device_id",
            "latency_ms",
            "payload",
        ]
    ]
)


# ============================================================
# 3. BASIC CLEANING
# ============================================================

print("\n--- CLEANING ---")

clean_df = df.copy()

# Remove exact duplicate event IDs.
clean_df = clean_df.drop_duplicates(
    subset=["event_id"],
    keep="first",
)

# A RunSummary should only use records assigned to a run.
clean_df = clean_df[
    clean_df["run_id"].notna()
].copy()

print("Raw rows:", len(df))
print("Rows after basic cleaning:", len(clean_df))


# ============================================================
# 4. METRIC 1: UNIQUE PARTICIPATING DEVICES
# ============================================================

print("\n--- METRIC 1: PARTICIPATING DEVICES ---")

joined_devices = clean_df[
    clean_df["event_type"] == "device_joined"
].copy()

unique_devices = joined_devices[
    "device_id"
].nunique()

print(
    "Unique participating devices:",
    unique_devices,
)

print("Device IDs:")

print(
    sorted(
        joined_devices["device_id"]
        .dropna()
        .unique()
    )
)


# ============================================================
# 5. EXPLORE CUE TARGET POPULATION
# ============================================================

print("\n--- CUE DELIVERY EXPLORATION ---")

device_population = (
    joined_devices[
        ["device_id", "zone"]
    ]
    .drop_duplicates(subset=["device_id"])
)

print("\nDevices by zone:")
print(
    device_population[
        "zone"
    ].value_counts()
)

sent_cues = clean_df[
    clean_df["event_type"] == "cue_sent"
].copy()

print("\nSent cues:")

print(
    sent_cues[
        [
            "cue_id",
            "target_zone",
            "server_timestamp",
            "payload",
        ]
    ].to_string(index=False)
)


# ============================================================
# 6. METRIC 2: CUE DELIVERY RATE
# ============================================================

print("\n--- METRIC 2: CUE DELIVERY RATE ---")

# MVP assumptions:
# CUE-01 -> all 16 joined devices
# CUE-02 -> only the 8 devices in Zone A
# CUE-03 -> all 16 joined devices
# CUE-04 -> 15 devices because D06 explicitly left
#           the event before CUE-04 was sent.
# Build expected recipients dynamically from the event data.

# Parse server timestamps for event ordering.
clean_df["server_timestamp_parsed"] = pd.to_datetime(
    clean_df["server_timestamp"],
    errors="coerce",
    utc=True,
)

# One row per participating device.
device_population = (
    joined_devices[
        ["device_id", "zone"]
    ]
    .dropna(subset=["device_id"])
    .drop_duplicates(subset=["device_id"])
)

# Devices that explicitly left the event.
left_events = clean_df[
    (clean_df["event_type"] == "device_disconnected")
    & clean_df["payload"].fillna("").str.contains(
        "left_event",
        case=False,
    )
][
    ["device_id", "server_timestamp_parsed"]
].copy()

expected_recipients = {}

for _, cue in sent_cues.iterrows():

    cue_id = cue["cue_id"]
    target_zone = cue["target_zone"]
    cue_time = pd.to_datetime(
        cue["server_timestamp"],
        utc=True,
    )

    # Start with the cue's target population.
    if target_zone == "ALL":
        eligible = device_population.copy()
    else:
        eligible = device_population[
            device_population["zone"] == target_zone
        ].copy()

    # Remove devices that explicitly left
    # before this cue was sent.
    devices_already_left = left_events[
        left_events["server_timestamp_parsed"] < cue_time
    ]["device_id"]

    eligible = eligible[
        ~eligible["device_id"].isin(devices_already_left)
    ]

    expected_recipients[cue_id] = len(eligible)

print("\nExpected recipients derived from data:")
print(expected_recipients)


# Use only cue receipts that can be linked to a device.
deliveries = clean_df[
    (clean_df["event_type"] == "cue_received")
    & clean_df["device_id"].notna()
].copy()

# For customer-facing delivery coverage,
# one device should count only once per cue.
deliveries = deliveries.drop_duplicates(
    subset=["cue_id", "device_id"],
    keep="first",
)

delivery_metrics = {}

for cue_id, expected in expected_recipients.items():

    received = deliveries[
        deliveries["cue_id"] == cue_id
    ]["device_id"].nunique()

    delivery_rate = (
        received / expected
    ) * 100

    delivery_metrics[cue_id] = {
        "received": received,
        "expected": expected,
        "delivery_rate_pct": round(
            delivery_rate,
            2,
        ),
    }

    print(
        f"{cue_id}: "
        f"{received}/{expected} "
        f"({delivery_rate:.2f}%)"
    )


# ============================================================
# 7. METRIC 3: DELIVERY LATENCY
# ============================================================

print("\n--- METRIC 3: DELIVERY LATENCY ---")

# Negative latency is impossible for this metric,
# so exclude it from latency calculations.
# High but plausible latency values are kept.

valid_latency = deliveries[
    deliveries["latency_ms"].notna()
    & (deliveries["latency_ms"] >= 0)
].copy()

median_latency = valid_latency[
    "latency_ms"
].median()

print(
    f"Median delivery latency: "
    f"{median_latency:.1f} ms"
)

print("\nMedian latency by cue:")

latency_by_cue = (
    valid_latency
    .groupby("cue_id")["latency_ms"]
    .median()
)

print(latency_by_cue)


# ============================================================
# 8. METRIC 4: INTERACTION RESPONSE RATE
# ============================================================

print("\n--- METRIC 4: INTERACTION RESPONSE RATE ---")

responses = clean_df[
    (clean_df["event_type"] == "interaction_response")
    & clean_df["device_id"].notna()
].copy()

# Count each device only once per cue
responses = responses.drop_duplicates(
    subset=["cue_id", "device_id"],
    keep="first",
)

response_metrics = {}

for cue_id, expected in expected_recipients.items():

    responded = responses[
        responses["cue_id"] == cue_id
    ]["device_id"].nunique()

    response_rate = (
        responded / expected
    ) * 100

    response_metrics[cue_id] = {
        "responded": responded,
        "expected": expected,
        "response_rate_pct": round(
            response_rate,
            2,
        ),
    }

    print(
        f"{cue_id}: "
        f"{responded}/{expected} "
        f"({response_rate:.2f}%)"
    )
    
   # ============================================================
# 9. CREATE RUN SUMMARY JSON
# ============================================================

print("\n--- CREATING RUN SUMMARY ---")

run_id = clean_df["run_id"].dropna().iloc[0]

run_started = clean_df[
    clean_df["event_type"] == "run_started"
]["server_timestamp"].iloc[0]

run_ended = clean_df[
    clean_df["event_type"] == "run_ended"
]["server_timestamp"].iloc[0]

total_delivered = sum(
    metric["received"]
    for metric in delivery_metrics.values()
)

total_expected = sum(
    metric["expected"]
    for metric in delivery_metrics.values()
)

overall_delivery_rate = (
    total_delivered / total_expected
) * 100

total_responses = sum(
    metric["responded"]
    for metric in response_metrics.values()
)

overall_response_rate = (
    total_responses / total_expected
) * 100


run_summary = {
    "run_id": run_id,
    "run_started_at": run_started,
    "run_ended_at": run_ended,

    "metrics": {
        "participating_devices": int(unique_devices),

        "cue_delivery": {
            "delivered": int(total_delivered),
            "expected": int(total_expected),
            "overall_rate_pct": round(
                overall_delivery_rate,
                2,
            ),
            "by_cue": delivery_metrics,
        },

        "delivery_latency": {
            "median_ms": round(
                float(median_latency),
                1,
            ),
            "median_by_cue_ms": {
                cue_id: float(value)
                for cue_id, value
                in latency_by_cue.items()
            },
        },

        "observed_response": {
            "responses": int(total_responses),
            "expected": int(total_expected),
            "overall_rate_pct": round(
                overall_response_rate,
                2,
            ),
            "by_cue": response_metrics,
        },
    },

    "data_quality": {
        "duplicate_event_records": int(
            len(duplicates)
        ),
        "missing_run_id_records": int(
            len(missing_run_id)
        ),
        "missing_device_id_records": int(
            len(missing_device_id)
        ),
        "negative_latency_records": int(
            len(invalid_latency)
        ),
        "invalid_client_timestamp_records": int(
            len(invalid_client_timestamp)
        ),
        "possible_semantic_duplicate_receipts": int(
            len(semantic_duplicates)
        ),
    },

    "assumptions": [
        (
            "device_id represents a unique "
            "participating device."
        ),
        (
            "Cue target_zone defines the "
            "eligible audience."
        ),
        (
            "A device with an explicit left_event "
            "is excluded from later cue populations."
        ),
        (
            "Each device is counted at most once "
            "per cue for delivery coverage."
        ),
        (
            "Negative latency values are excluded "
            "from latency metrics."
        ),
        (
            "Observed response rate assumes cues "
            "are response-capable; this should be "
            "validated with product metadata."
        ),
    ],
}


output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

output_path = output_dir / "RunSummary.json"

with open(
    output_path,
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        run_summary,
        file,
        indent=2,
    )

print(
    f"RunSummary written to: {output_path}"
) 