"""Service for rebuilding prompts based on Karpathy guidelines."""

from loguru import logger
from api.models.anthropic import MessagesRequest, Message
from config.settings import Settings
from providers.base import BaseProvider
from core.anthropic import extract_text_from_content

class PromptRebuilder:
    def __init__(self, settings: Settings, provider_getter: callable):
        self._settings = settings
        self._provider_getter = provider_getter
        self._guidelines = self._load_guidelines()

    def _load_guidelines(self) -> str:
        try:
            with open("karpathy-guidelines.skill", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("Karpathy guidelines file not found.")
            return ""

    def _load_constraints(self) -> str:
        return """
        Prompt Constraints:
        - Maintain technical markers (like command prefixes).
        - Apply Karpathy-style simplicity: prune filler, surface assumptions.
        - Ensure goal-driven execution in every rebuilt prompt.
        """

    def rebuild(self, request_data: MessagesRequest) -> MessagesRequest:
        logger.info("Rebuilding prompt using LLM agent.")
        
        # 1. Prepare system prompt
        guidelines = self._load_guidelines()
        constraints = self._load_constraints()
        new_system = f"{request_data.system or ''}\n\n# Mandatory Behavioral Guidelines\n{guidelines}\n\n# {constraints}\n\nRebuild the following prompt according to these guidelines. Return only the rebuilt prompt text."
        
        # 2. Extract original prompt
        original_prompt = ""
        for msg in request_data.messages:
            if msg.role == "user":
                content = extract_text_from_content(msg.content)
                if content.strip().upper().startswith("REBUILD:"):
                    original_prompt = content.strip()[len("REBUILD:"):].strip()
                    break
        
        if not original_prompt:
            return request_data

        # 3. Call LLM for rebuilding
        provider_id = self._settings.model.split('/')[0]
        provider = self._provider_getter(provider_id)
        
        # Construct rebuild request
        rebuild_request = MessagesRequest(
            model=self._settings.model,
            messages=[Message(role="user", content=f"Rebuild this: {original_prompt}")],
            system=new_system
        )
        
        # Run synchronous stream to get result
        rebuilt_text = ""
        for chunk in provider.stream_response(rebuild_request, input_tokens=0, request_id="rebuild", thinking_enabled=False):
            # The streaming response contains text chunks. 
            # This logic depends on the specific provider stream output.
            # Assuming a simplified string accumulation here for the placeholder:
            rebuilt_text += chunk
        
        # 4. Update the user message with the rebuilt prompt
        for msg in request_data.messages:
            if msg.role == "user":
                msg.content = rebuilt_text
                break
        
        return request_data
