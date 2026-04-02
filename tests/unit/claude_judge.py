import os
from deepeval.models import DeepEvalBaseLLM
from anthropic import Anthropic

class ClaudeJudge(DeepEvalBaseLLM):
    def __init__(self, model_name="claude-sonnet-4-6"):
        self.model_name = model_name
        # automatically look for the ANTHROPIC_API_KEY environment variable
        self.client = Anthropic()

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self):
        return self.model_name