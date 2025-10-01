import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from code_review_assistant.sub_agents.review_pipeline.style_checker import style_checker_agent
from code_review_assistant.services import get_session_service
from google.adk.runners import Runner
from google.genai.types import Content, Part


async def test():
    session_service = get_session_service()

    runner = Runner(
        agent=style_checker_agent,
        app_name="test_style_checker",
        session_service=session_service
    )

    # Code with style issues
    test_code = """
def add(a,b):return a+b
class calculator:
 def multiply(self,x,y):
  return x*y
"""

    session = await session_service.create_session(
        app_name="test_style_checker",
        user_id="test_user"
    )

    print("Testing style checker...")

    message = Content(
        role="user",
        parts=[Part(text=f"Check style of this code:\n\n{test_code}")]
    )

    async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
            new_message=message
    ):
        if event.is_final_response():
            print("\n=== Style Checker Response ===")
            print(event.content.parts[0].text)


asyncio.run(test())