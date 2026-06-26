import asyncio
import sys
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from Agents.agent import root_agent

APP_NAME = "college_admissions"
USER_ID = "user"
SESSION_ID = f"{APP_NAME}_{USER_ID}"
DB_URL = "sqlite+aiosqlite:///college_admissions.db"


async def run():
    session_service = DatabaseSessionService(db_url=DB_URL)

    # Reuse existing session so profile and school list persist across runs
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
        )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print("College Admissions Coach  (type 'quit' to exit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if not user_input:
            continue

        message = types.Content(role="user", parts=[types.Part(text=user_input)])

        try:
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=message,
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if part.text:
                            print(f"\nAgent: {part.text}\n")
        except Exception as e:
            print(f"\nError: {e}\n", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run())
