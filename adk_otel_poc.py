import asyncio
import re
import uuid

# OpenTelemetry imports
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.cloud_monitoring import CloudMonitoringMetricsExporter

# Google ADK imports
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

def count_vowels(text: str) -> int:
    """Calculates the number of vowels in a given string."""
    return len(re.findall(r'[aeiouAEIOU]', text, flags=re.IGNORECASE))

async def main():
    # =========================================================================
    # Phase 1: OpenTelemetry Setup
    # =========================================================================
    print("Initializing OpenTelemetry and Google Cloud Monitoring exporter...")
    
    # 1. Initialize the Google Cloud Monitoring Metrics Exporter.
    # Note: This relies on Google Application Default Credentials (ADC) being set.
    gcp_exporter = CloudMonitoringMetricsExporter()
    
    # 2. Set up a PeriodicExportingMetricReader with the GCP exporter.
    metric_reader = PeriodicExportingMetricReader(gcp_exporter)
    
    # 3. Create and set the global MeterProvider.
    provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(provider)
    
    # 4. Get a meter instance for this application to create specific metrics.
    meter = metrics.get_meter("google_adk_telemetry_poc")
    
    # 5. Define Custom Metrics
    vowel_counter = meter.create_counter(
        name="agent.prompt.vowel_count",
        description="Tracks the total number of vowels in the user's input.",
        unit="{vowels}"
    )
    
    char_length_histogram = meter.create_histogram(
        name="agent.response.char_length",
        description="Tracks the character length of the model's output.",
        unit="By" # Bytes/chars
    )

    # We use a unique run_id to avoid Cloud Monitoring's 5-second rate limit
    # on writing to the exact same time series in rapid succession during testing.
    run_id = str(uuid.uuid4())

    # =========================================================================
    # Phase 2: Agent Configuration
    # =========================================================================
    print("Initializing ADK Agent...")
    
    # Initialize a minimal Google ADK Agent.
    agent = Agent(
        model='gemini-3.5-flash',
        name='basic_otel_agent',
        description='A basic agent for demonstrating custom OpenTelemetry metrics.'
    )
    
    # In the new ADK structure, we use a Runner to orchestrate the agent execution
    runner = InMemoryRunner(agent=agent)
    
    # Create an in-memory session for the user
    user_id = "demo_user"
    session = await runner.session_service.create_session(
        user_id=user_id, 
        app_name=runner.app_name
    )

    # =========================================================================
    # Phase 3: Core Logic (The Agent Flow)
    # =========================================================================
    prompt = "Why is the sky blue?"
    print(f"\nUser Prompt: {prompt}")
    
    # Calculate the vowel count (Before metric)
    vowels = count_vowels(prompt)
    print(f"Calculated Vowel Count: {vowels}")
    
    # Record the vowel count to the OTel counter
    vowel_counter.add(vowels, {"agent_name": agent.name, "run_id": run_id})
    
    print("Calling the LLM Agent...")
    response_text = ""
    try:
        # We package the prompt into a genai types.Content object
        new_message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        
        # Execute the agent asynchronously using the Runner
        events = runner.run_async(
            session_id=session.id, 
            user_id=user_id, 
            new_message=new_message
        )
        
        # Stream and accumulate the response from the generator
        async for event in events:
            if getattr(event, 'type', None) == 'model_response':
                 if hasattr(event, 'content'):
                      for part in getattr(event.content, 'parts', []):
                           if getattr(part, 'text', None):
                               response_text += part.text
                               
        if not response_text:
            response_text = "(Received empty response. Check your API key or ADC credentials.)"
            
    except Exception as e:
        print(f"Error calling agent: {e}")
        response_text = "Error occurred."
        
    print(f"\nModel Response:\n{response_text}\n")
    
    # Calculate the character length of the response (After metric)
    response_length = len(response_text)
    print(f"Calculated Response Length: {response_length}")
    
    # Record the response character length to the OTel histogram
    char_length_histogram.record(response_length, {"agent_name": agent.name, "run_id": run_id})

    # =========================================================================
    # Phase 4: Graceful Shutdown
    # =========================================================================
    print("\nFlushing OpenTelemetry metrics...")
    # Force flush the metrics to ensure they are sent to Google Cloud before the script exits.
    provider.force_flush()
    print("Metrics flushed. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
