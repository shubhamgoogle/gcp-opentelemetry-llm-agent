import re
import uuid

# OpenTelemetry imports
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter

# Google ADK imports
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# =========================================================================
# Phase 1: OpenTelemetry Setup
# =========================================================================
# This runs once when the module is imported by the ADK Web Server
gcp_exporter = CloudMonitoringMetricsExporter()
console_exporter = ConsoleMetricExporter()

# We can attach multiple readers to the MeterProvider
gcp_reader = PeriodicExportingMetricReader(gcp_exporter, export_interval_millis=60000)
console_reader = PeriodicExportingMetricReader(console_exporter, export_interval_millis=60000)

provider = MeterProvider(metric_readers=[gcp_reader, console_reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("google_adk_telemetry_poc")

vowel_counter = meter.create_counter(
    name="agent.prompt.vowel_count",
    description="Tracks the total number of vowels in the user's input.",
    unit="{vowels}"
)

char_length_histogram = meter.create_histogram(
    name="agent.response.char_length",
    description="Tracks the character length of the model's output.",
    unit="By"
)

def count_vowels(text: str) -> int:
    return len(re.findall(r'[aeiouAEIOU]', text, flags=re.IGNORECASE))

# We use this to map invocation IDs to our run_id
# so the after_model callback can use the same run_id as before_agent
run_ids = {}

# =========================================================================
# Phase 2: Callbacks
# =========================================================================
async def before_agent_cb(callback_context: CallbackContext, **kwargs) -> types.Content | None:
    """Triggered before the agent starts processing the user request."""
    user_content = callback_context.user_content
    if user_content and getattr(user_content, "parts", None):
        # Safely extract the prompt
        prompt = getattr(user_content.parts[0], "text", "")
        if prompt:
            vowels = count_vowels(prompt)
            run_id = str(uuid.uuid4())
            run_ids[callback_context.invocation_id] = run_id
            
            # Emit "before" metric
            vowel_counter.add(vowels, {"agent_name": "basic_otel_agent", "run_id": run_id})
            print("Number of vowels: ", vowels)
    return None

async def after_model_cb(callback_context: CallbackContext, response: LlmResponse = None, **kwargs) -> LlmResponse | None:
    """Triggered after the LLM model responds, before returning to user."""
    if response and getattr(response, "content", None) and getattr(response.content, "parts", None):
        response_text = getattr(response.content.parts[0], "text", "")
        if response_text:
            response_length = len(response_text)
            
            # Retrieve run_id to link metrics, default to a new one if not found
            run_id = run_ids.get(callback_context.invocation_id, str(uuid.uuid4()))
            
            # Emit "after" metric
            char_length_histogram.record(response_length, {"agent_name": "basic_otel_agent", "run_id": run_id})
            print("Response length: ", response_length)
    return response

# =========================================================================
# Phase 3: Agent Configuration
# =========================================================================
root_agent = Agent(
    model='gemini-3.5-flash',
    name='basic_otel_agent',
    description='A basic ADK agent for demonstrating custom OTel metrics in a Web App.',
    before_agent_callback=[before_agent_cb],
    after_model_callback=[after_model_cb]
)
