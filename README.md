# GCP OpenTelemetry LLM Agent

This repository serves as a Proof of Concept (PoC) demonstrating how to emit custom metrics, distributed traces, and application logs from a Google Agent Development Kit (ADK) agent to Google Cloud (Stackdriver) using OpenTelemetry.

## Overview

The AI Agent automatically calculates and emits the following telemetry:

### 1. Metrics (Cloud Monitoring)
1. **`agent.prompt.vowel_count` (Counter):** Calculates the total number of vowels in the user's input prompt (calculated in the `before_agent_callback`).
2. **`agent.response.char_length` (Histogram):** Tracks the character length of the LLM's response output (calculated in the `after_model_callback`).

### 2. Traces (Cloud Trace)
- **`agent_execution` (Span):** Wraps the entire invocation of the agent. The span records the run ID, the user's prompt text, and the final response length as span attributes. It integrates safely with ADK's native `TracerProvider`.

### 3. Logs (Cloud Logging)
- Natively connects Python's standard `logging.info()` to OpenTelemetry.
- Logs include trace context (Trace ID/Span ID) so they can be perfectly correlated with Traces in GCP Logs Explorer.

## Prerequisites

1. Python 3.10+
2. Google Cloud SDK (authenticated via Application Default Credentials)
3. A properly formatted `.env` file containing your Gemini API key (without quotes):
   ```
   GEMINI_API_KEY=your_api_key_here
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
   Open your browser to `http://localhost:8001`. Send prompts to the agent, and the telemetry data will automatically be flushed to both your terminal (via Console Exporters) and GCP in the background using `BatchSpanProcessor` and `BatchLogRecordProcessor`.

## Querying Metrics in GCP Metrics Explorer

You can query your data in the Google Cloud Metrics Explorer using PromQL format. By default, the OpenTelemetry exporter maps these metrics under the `workload.googleapis.com` domain.

### PromQL Examples

**Absolute number of vowels in a given window:**
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

**Average Response Length:**
```promql
sum(rate({"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}[${__interval}]))
/
sum(rate({"__name__"="workload.googleapis.com/agent.response.char_length_count", "monitored_resource"="generic_task"}[${__interval}]))
```

**The Raw, Cumulative Total of All Characters:**
```promql
{"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}
```

**Total Characters Generated in the given window:**
```promql
sum(increase({"__name__"="workload.googleapis.com/agent.response.char_length_sum", "monitored_resource"="generic_task"}[${__interval}]))

```
