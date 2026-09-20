# Crowds Data Product MVP

A small Data Product MVP that transforms raw Crowds event data into
customer-facing run metrics while explicitly handling data quality issues
and ambiguity in the source data.

## Objective

Crowds produces technical event data from audience smartphones, including
device connections, cue delivery, interaction responses, timing information,
and errors.

The goal of this MVP is to turn those raw events into a small, explainable
RunSummary that could be useful to an event organizer.

The focus is correctness, transparency, and reusable metric definitions rather
than production infrastructure.

## Project Structure

```text
crowds-data-product-mvp/
├── data/
│   └── Crowds_Data_Product_Exercise_Sample_Data.csv
├── docs/
│   └── data_model.md
├── output/
│   └── RunSummary.json
├── src/
│   └── transform.py
├── README.md
└── requirements.txt