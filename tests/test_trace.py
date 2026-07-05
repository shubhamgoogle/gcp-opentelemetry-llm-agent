import asyncio
from agents.otel_agent.agent import root_agent

async def main():
    print("Running agent directly...")
    try:
        from google.adk.models.message import Message, Content
        msg = Message(role="user", content=Content(parts=[{"text": "Count the vowels in this sentence."}]))
        async for chunk in root_agent.run_async([msg]):
            print(f"Agent response chunk: {chunk}")
    except Exception as e:
        print(f"Agent crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
