import json
from typing import Type, TypeVar
from pydantic import BaseModel, ValidationError
from loguru import logger

T = TypeVar('T', bound=BaseModel)

class SchemaValidator:
    """Validates LLM JSON output against Pydantic schemas."""
    
    @staticmethod
    def validate(response_text: str, schema_class: Type[T]) -> T:
        """
        Validates a JSON string against a Pydantic schema.
        
        Args:
            response_text: The raw string response from the LLM.
            schema_class: The Pydantic model class to validate against.
            
        Returns:
            An instance of the schema_class.
            
        Raises:
            ValueError: If JSON is invalid or validation fails.
        """
        # Clean the response text (sometimes LLMs wrap in markdown code blocks)
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()
        
        try:
            # Parse JSON
            parsed_json = json.loads(cleaned_text)
            
            # Validate with Pydantic v2
            validated_data = schema_class.model_validate(parsed_json)
            return validated_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}\nRaw Text: {response_text}")
            raise ValueError(f"Failed to parse JSON: {e}")
        except ValidationError as e:
            logger.error(f"Schema Validation Error: {e}\nParsed JSON: {parsed_json}")
            raise ValueError(f"JSON does not match expected schema: {e}")
