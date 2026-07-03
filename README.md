# OpenTelemetry & Google ADK GCP Metrics PoC

This repository serves as a Proof of Concept (PoC) demonstrating how to emit custom metrics from a Google Agent Development Kit (ADK) agent to Google Cloud Monitoring using OpenTelemetry.

## Overview

The AI Agent automatically calculates and emits two custom metrics:
1. **`agent.prompt.vowel_count` (Counter):** Calculates the total number of vowels in the user's input prompt (calculated in the `before_agent_callback`).
2. **`agent.response.char_length` (Histogram):** Tracks the character length of the LLM's response output (calculated in the `after_model_callback`).

The agent is exposed via the ADK Web Server UI, allowing interactive testing.

## Prerequisites

1. Python 3.10+
2. Google Cloud SDK (authenticated via Application Default Credentials)
3. A `.env` file or exported environment variable containing your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Setup & Running Locally

1. **Activate your virtual environment:**
   ```bash
   source venv/bin/activate
   ```

2. **Run the ADK Web Application:**
   ```bash
   adk web --port 8001 agents
   ```

3. **Interact with the Agent:**
   Open your browser to `http://localhost:8001`. Send prompts to the agent, and the telemetry data will automatically be flushed to both your terminal (via `ConsoleMetricExporter`) and GCP (via `CloudMonitoringMetricsExporter`) every 60 seconds.

## Querying Metrics in GCP Metrics Explorer

You can query your data in the Google Cloud Metrics Explorer using PromQL format. By default, the OpenTelemetry exporter maps these metrics under the `workload.googleapis.com` domain.

### PromQL Examples

**Vowel Count (Increase over the dynamic interval window, grouped by agent):**
```promql
sum by (agent_name) (
  increase({"__name__"="workload.googleapis.com/agent.prompt.vowel_count", "monitored_resource"="generic_task"}[${__interval}])
)
```

**Response Length (95th Percentile Histogram):**
```promql
histogram_quantile(0.95, sum by (le, agent_name) (
  rate({"__name__"="workload.googleapis.com/agent.response.char_length", "monitored_resource"="generic_task"}[${__interval}])
))
```

**Total Response Lengths (Raw Sum):**
```promql
sum(increase({"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}[${__interval}]))
```
