"""
LLM API clients for Zhipu GLM and VLLM.
"""
import os
import json
import html
import re
from typing import Dict, Any, Optional, List

from .prompts import (
    QUESTION_ONLY_PROMPT,
    QUESTION_WITH_ANSWER_PROMPT,
    QUESTION_WITH_MULTIPLE_ANSWERS_PROMPT,
    format_answers_text,
    sanitize_theorem_name
)

try:
    from zai import ZhipuAiClient
    ZAI_AVAILABLE = True
except ImportError:
    ZAI_AVAILABLE = False
    print("Warning: zai-sdk not installed. Using fallback HTTP client.")


def parse_json_from_llm_response(content: str) -> Dict[str, Any]:
    """
    Robust JSON parser for LLM responses.

    Handles:
    - Markdown code blocks (```json, ```)
    - JSON object boundaries detection
    - Invalid escape sequences in LaTeX
    - HTML entities
    - Trailing/leading text outside JSON

    Args:
        content: Raw LLM response content

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If JSON cannot be parsed
    """
    # Remove markdown code blocks if present
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    # Try to find the JSON object boundaries
    start_idx = content.find('{')
    if start_idx == -1:
        raise ValueError("No JSON object found in response")

    # Count braces to find matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False
    end_idx = -1

    for i in range(start_idx, len(content)):
        char = content[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

    if end_idx == -1:
        raise ValueError("Could not find complete JSON object")

    json_str = content[start_idx:end_idx]

    # Fix invalid escape sequences in JSON strings
    def fix_json_escapes(s: str) -> str:
        """Fix invalid escape sequences in JSON string values."""
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                next_char = s[i + 1]
                # Valid JSON escapes
                if next_char in '"\\/bfnrt':
                    result.append(s[i:i+2])
                    i += 2
                    continue
                # Unicode escape like \uXXXX
                elif next_char == 'u' and i + 5 < len(s):
                    result.append(s[i:i+6])
                    i += 6
                    continue
                # Invalid escapes - for LaTeX and special chars, double the backslash
                # These commonly appear in mathematical content
                elif next_char in '({[<>=_~.*+|?^-]\\\'':
                    result.append('\\\\' + next_char)
                    i += 2
                    continue
                else:
                    # Other invalid escapes - just remove the backslash
                    result.append(next_char)
                    i += 2
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    json_str = fix_json_escapes(json_str)

    # Decode HTML entities before parsing JSON
    json_str = html.unescape(json_str)

    return json.loads(json_str)


class ZhipuClient:
    """Client for Zhipu AI GLM API using new zai-sdk."""

    def __init__(self, api_key: str = None):
        """
        Initialize Zhipu client.

        Args:
            api_key: Zhipu API key (default from env or settings)
        """
        self.api_key = api_key or os.getenv('ZHIPU_API_KEY')
        if not self.api_key:
            raise ValueError("Zhipu API key is required. Set ZHIPU_API_KEY environment variable.")

        if ZAI_AVAILABLE:
            self.client = ZhipuAiClient(api_key=self.api_key)
        else:
            raise ImportError("zai-sdk is required. Install with: pip install zai-sdk==0.2.0")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "glm-4.7",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request using new zai-sdk.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (glm-4.7, glm-4.6v, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Response JSON (compatible with old format)
        """
        try:
            # Convert messages format for new SDK
            # Handle vision model content format
            formatted_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    # Already formatted for vision
                    formatted_messages.append(msg)
                else:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            # Build request parameters
            request_params = {
                "model": model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Add thinking parameter for glm-4.7 and glm-4.6v
            # Note: For our use cases, we want the actual response, not just reasoning
            # So we won't enable thinking mode by default
            # Users can enable it by passing thinking parameter in kwargs if needed

            # Add any additional parameters
            request_params.update(kwargs)

            # Call new SDK
            response = self.client.chat.completions.create(**request_params)

            # Extract content from response
            # glm-4.7/4.6v may use reasoning_content field when thinking mode is enabled
            message_obj = response.choices[0].message
            content = message_obj.content or ""

            # If content is empty but reasoning_content exists, use that
            if not content and hasattr(message_obj, 'reasoning_content') and message_obj.reasoning_content:
                content = message_obj.reasoning_content

            # Convert response to old format for compatibility
            return {
                "choices": [{
                    "message": {
                        "role": message_obj.role or "assistant",
                        "content": content
                    },
                    "finish_reason": response.choices[0].finish_reason,
                    "index": 0
                }],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                    "completion_tokens": response.usage.completion_tokens if hasattr(response, 'usage') else 0,
                    "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') else 0
                },
                "model": model
            }

        except Exception as e:
            print(f"Zhipu API error: {e}")
            raise

    def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str = "glm-4.6v",
        temperature: float = 0.1
    ) -> str:
        """
        Analyze an image using GLM-4.6V.

        Args:
            image_url: URL or base64 of image
            prompt: Analysis prompt
            model: Model name
            temperature: Sampling temperature

        Returns:
            Analysis result text
        """
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": prompt}
            ]
        }]

        response = self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature
        )

        return response["choices"][0]["message"]["content"]

    def correct_content(
        self,
        question: str,
        answer: str,
        temperature: float = 0.0,
        model: str = "glm-4.7"
    ) -> Dict[str, Any]:
        """
        Validate and correct question/answer pair.

        Args:
            question: Question text
            answer: Answer text
            temperature: Sampling temperature (default 0.0 for deterministic output)
            model: Model to use (default: glm-4.7 for best quality)

        Returns:
            Correction result as dict
        """
        # Use lower temperature to force more deterministic JSON output
        temp = min(temperature, 0.1)

        # Format prompt with question and answer
        user_prompt = QUESTION_WITH_ANSWER_PROMPT.format(
            question=question,
            answer=answer
        )

        messages = [{"role": "user", "content": user_prompt}]

        # Try using JSON mode if supported
        try:
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )
        except Exception:
            # Fallback to regular call if JSON mode not supported
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000
            )

        content = response["choices"][0]["message"]["content"]

        # Try to extract JSON from response
        try:
            result = parse_json_from_llm_response(content)
            # Sanitize theorem_name if present
            if result.get('theorem_name'):
                result['theorem_name'] = sanitize_theorem_name(result['theorem_name'])
            return result
        except (json.JSONDecodeError, ValueError) as e:
            # Return default safe response
            return {
                "is_valid_question": True,
                "is_valid_answer": True,
                "has_errors": False,
                "errors": [],
                "corrected_question": question,
                "corrected_answer": answer,
                "correction_notes": f"JSON parsing failed, assuming valid: {str(e)[:50]}",
                "worth_formalizing": True,
                "formalization_value": "medium"
            }

    def validate_and_select_answer(
        self,
        question: str,
        answers: list,
        temperature: float = 0.0,
        model: str = "glm-4.7"
    ) -> Dict[str, Any]:
        """
        Validate question with multiple answers and produce a single correct, complete, formalized answer.

        Args:
            question: Question text
            answers: List of answer dicts with 'body', 'is_accepted', 'score'
            temperature: Sampling temperature (default 0.0 for deterministic output)
            model: Model to use

        Returns:
            Validation result with corrected question and corrected answer
        """
        # Use lower temperature to force more deterministic JSON output
        temp = min(temperature, 0.1)

        # Format answers for LLM
        answers_text = format_answers_text(answers)

        # Format prompt with question and answers
        user_prompt = QUESTION_WITH_MULTIPLE_ANSWERS_PROMPT.format(
            question=question,
            answers_text=answers_text
        )

        messages = [{"role": "user", "content": user_prompt}]

        # Try using JSON mode if supported
        try:
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )
        except Exception:
            # Fallback to regular call if JSON mode not supported
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000
            )

        content = response["choices"][0]["message"]["content"]

        # Try to extract JSON from response
        try:
            result = parse_json_from_llm_response(content)
            # Sanitize theorem_name if present
            if result.get('theorem_name'):
                result['theorem_name'] = sanitize_theorem_name(result['theorem_name'])
            return result
        except (json.JSONDecodeError, ValueError) as e:
            # Return default safe response - use first answer if available
            return {
                "is_valid_question": True,
                "is_valid_answer": True,
                "has_errors": False,
                "errors": [],
                "corrected_question": question,
                "corrected_answer": answers[0].get('body', '') if answers else "",
                "correction_notes": f"JSON parsing failed, using first answer: {str(e)[:50]}",
                "worth_formalizing": True,
                "formalization_value": "medium"
            }

    def correct_question_only(
        self,
        question: str,
        temperature: float = 0.0,
        model: str = "glm-4.7"
    ) -> Dict[str, Any]:
        """
        Validate and correct a question without an answer.

        Args:
            question: Question text
            temperature: Sampling temperature (default 0.0 for deterministic output)
            model: Model to use

        Returns:
            Correction result as dict
        """
        # Use lower temperature to force more deterministic JSON output
        temp = min(temperature, 0.1)

        # Format prompt with question
        user_prompt = QUESTION_ONLY_PROMPT.format(question=question)

        messages = [{"role": "user", "content": user_prompt}]

        # Try using JSON mode if supported
        try:
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000,
                response_format={"type": "json_object"}
            )
        except Exception:
            # Fallback to regular call if JSON mode not supported
            response = self.chat_completion(
                messages=messages,
                model=model,
                temperature=temp,
                max_tokens=16000
            )

        content = response["choices"][0]["message"]["content"]

        # Try to extract JSON from response
        try:
            result = parse_json_from_llm_response(content)
            # Sanitize theorem_name if present
            if result.get('theorem_name'):
                result['theorem_name'] = sanitize_theorem_name(result['theorem_name'])
            return result
        except (json.JSONDecodeError, ValueError) as e:
            # Return default safe response
            return {
                "is_valid_question": True,
                "has_errors": False,
                "errors": [],
                "corrected_question": question,
                "correction_notes": f"JSON parsing failed, assuming valid: {str(e)[:50]}",
                "worth_formalizing": True,
                "formalization_value": "medium"
            }


class VLLMClient:
    """Client for VLLM OpenAI-compatible API (for Kimina-Autoformalizer-7B)."""

    def __init__(self, base_url: str = None, model_path: str = None):
        """
        Initialize VLLM client.

        Args:
            base_url: VLLM server base URL
            model_path: Model path/name
        """
        self.base_url = base_url or "http://localhost:8000/v1"
        self.model_path = model_path or "/root/Kimina-Autoformalizer-7B"

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.6,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request.

        Args:
            messages: List of message dicts
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            Response JSON
        """
        import requests

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model_path,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            **kwargs
        }

        try:
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"VLLM API HTTP error: {e}")
            raise
        except Exception as e:
            print(f"VLLM API error: {e}")
            raise

    def convert_to_lean(
        self,
        problem_text: str,
        max_tokens: int = 2048,
        temperature: float = 0.6
    ) -> str:
        """
        Convert mathematical problem to Lean 4.

        Args:
            problem_text: Problem description
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Returns:
            Lean 4 code
        """
        system_prompt = "You are an expert in mathematics and Lean 4."
        user_prompt = f"Please autoformalize the following problem in Lean 4 with a header.\n\n{problem_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = self.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return response["choices"][0]["message"]["content"]
