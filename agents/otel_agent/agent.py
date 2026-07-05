import re
import uuid

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
import logging
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.cloud_logging import CloudLoggingExporter

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
gcp_reader = PeriodicExportingMetricReader(gcp_exporter, export_interval_millis=5000)
console_reader = PeriodicExportingMetricReader(console_exporter, export_interval_millis=5000)

provider = MeterProvider(metric_readers=[gcp_reader, console_reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("google_adk_telemetry_poc")

# =========================================================================
# Phase 1b: Tracing Setup
# =========================================================================
gcp_trace_exporter = CloudTraceSpanExporter(project_id="deepspace-460917")
console_trace_exporter = ConsoleSpanExporter()

# Do NOT create a new TracerProvider as ADK has already set one!
# Overriding it fails silently with a WARNING and drops our exporters.
provider = trace.get_tracer_provider()
if hasattr(provider, "add_span_processor"):
    provider.add_span_processor(BatchSpanProcessor(gcp_trace_exporter))
    provider.add_span_processor(BatchSpanProcessor(console_trace_exporter))
else:
    print("WARNING: Current TracerProvider does not support adding span processors directly.")

tracer = trace.get_tracer("google_adk_telemetry_poc_tracer")

# =========================================================================
# Phase 1c: Logging Setup
# =========================================================================
gcp_log_exporter = CloudLoggingExporter(project_id="deepspace-460917")
log_provider = get_logger_provider()

if hasattr(log_provider, "add_log_record_processor"):
    log_provider.add_log_record_processor(BatchLogRecordProcessor(gcp_log_exporter))
else:
    new_provider = LoggerProvider()
    new_provider.add_log_record_processor(BatchLogRecordProcessor(gcp_log_exporter))
    set_logger_provider(new_provider)
    log_provider = new_provider

# Route Python's standard logging to OpenTelemetry
otel_handler = LoggingHandler(level=logging.INFO, logger_provider=log_provider)
logging.getLogger().addHandler(otel_handler)

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

# We also map invocation IDs to active spans for tracing
active_spans = {}

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
            
            # Start tracing span
            span = tracer.start_span("agent_execution")
            span.set_attribute("agent.name", "demo_otel_agent")
            span.set_attribute("agent.run_id", run_id)
            span.set_attribute("user.prompt", prompt)
            active_spans[callback_context.invocation_id] = span
            
            # Emit "before" metric
            vowel_counter.add(vowels, {"agent_name": "demo_otel_agent", "run_id": run_id})
            logging.info(f"Agent starts execution for run_id {run_id} with prompt containing {vowels} vowels.")
            print("Number of vowels: ", vowels)
            print(f"Started trace with Trace ID: {span.get_span_context().trace_id:032x}")
    return None

async def after_model_cb(callback_context: CallbackContext, response: LlmResponse = None, **kwargs) -> LlmResponse | None:
    """Triggered after the LLM model responds, before returning to user."""
    
    print(f"after_model_cb triggered for invocation: {callback_context.invocation_id}")
    
    # Always pop and end the span to prevent it from hanging forever
    span = active_spans.pop(callback_context.invocation_id, None)
    
    response_length = 0
    if response and getattr(response, "content", None) and getattr(response.content, "parts", None):
        # Depending on the GenAI SDK version, text might be accessed differently
        try:
            response_text = response.content.parts[0].text
        except AttributeError:
            response_text = ""
            
        if response_text:
            response_length = len(response_text)
            
    if span:
        if response_length > 0:
            span.set_attribute("response.length", response_length)
        span.end()
        logging.info(f"Trace ended successfully for trace_id {span.get_span_context().trace_id:032x} with response length {response_length}.")
        print(f"Ended trace with Trace ID: {span.get_span_context().trace_id:032x}. Trace successfully recorded!")
    else:
        logging.warning(f"No active span found for invocation: {callback_context.invocation_id}")
        print(f"WARNING: No active span found for invocation: {callback_context.invocation_id}")
            
    if response_length > 0:
        run_id = run_ids.get(callback_context.invocation_id, str(uuid.uuid4()))
        char_length_histogram.record(response_length, {"agent_name": "demo_otel_agent", "run_id": run_id})
        
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
