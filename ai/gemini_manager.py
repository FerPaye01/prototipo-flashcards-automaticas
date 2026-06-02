import os
from typing import List, Optional, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from models import FlashcardBase
from config_sets_manager import DEFAULT_PROMPTS

class FlashcardList(BaseModel):
    cards: List[FlashcardBase]

class GeminiManager:
    def __init__(self, api_key: str, model_name: str = "gemini-pro"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2
        )
        self.parser = PydanticOutputParser(pydantic_object=FlashcardList)

    async def generate_cards(self, text_content: str, card_type: str, custom_prompt: Optional[str] = None) -> List[FlashcardBase]:
        """
        Genera flashcards usando LangChain y Gemini Pro.
        """
        base_prompt = custom_prompt or DEFAULT_PROMPTS.get(card_type, "")
        if not base_prompt:
            raise ValueError(f"No prompt found for card type: {card_type}")

        # Injecting output formatting instructions
        format_instructions = self.parser.get_format_instructions()
        
        template = """
        {base_prompt}
        
        INPUT TEXT:
        {text_content}
        
        {format_instructions}
        """
        
        prompt = PromptTemplate(
            template=template,
            input_variables=["text_content", "base_prompt"],
            partial_variables={"format_instructions": format_instructions}
        )
        
        chain = prompt | self.llm | self.parser
        
        try:
            result = await chain.ainvoke({"text_content": text_content, "base_prompt": base_prompt})
            return result.cards
        except Exception as e:
            print(f"❌ Error in LangChain generation: {e}")
            return []

# Placeholder for Presidio integration
class PrivacyManager:
    def __init__(self):
        # In a real scenario, we would init Presidio analyzer and anonymizer here
        self.enabled = os.getenv("ENABLE_PRESIDIO", "false").lower() == "true"

    def anonymize(self, text: str) -> str:
        if not self.enabled:
            return text
        # TODO: Implement Presidio logic
        return text
