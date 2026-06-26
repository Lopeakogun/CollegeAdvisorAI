from functools import cached_property

from google.adk.models import Gemini
from google.genai import Client


class GlobalGemini(Gemini):
    # gemini-3 series only served from 'global', not regional AgentEngine endpoints
    @cached_property
    def api_client(self) -> Client:
        return Client(vertexai=True, location="global")
