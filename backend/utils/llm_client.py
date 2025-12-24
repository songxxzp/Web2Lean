"""
LLM API clients for Zhipu GLM and VLLM.
"""
import os
import requests
from typing import Dict, Any, Optional, List


class ZhipuClient:
    """Client for Zhipu AI GLM API."""

    def __init__(self, api_key: str = None):
        """
        Initialize Zhipu client.

        Args:
            api_key: Zhipu API key (default from env or settings)
        """
        self.api_key = api_key or os.getenv('ZHIPU_API_KEY')
        if not self.api_key:
            raise ValueError("Zhipu API key is required. Set ZHIPU_API_KEY environment variable.")

        self.base_url = "https://open.bigmodel.cn/api/paas/v4"

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "glm-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (glm-4, glm-4v, etc.)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Response JSON
        """
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }

        # GLM-4V requires special format for images
        if model == "glm-4v" or "vision" in model.lower():
            # Format messages for vision model
            formatted_messages = []
            for msg in messages:
                if isinstance(msg.get("content"), list):
                    # Already formatted for vision
                    formatted_messages.append(msg)
                else:
                    formatted_messages.append({
                        "role": msg["role"],
                        "content": [{"type": "text", "text": msg["content"]}]
                    })
            payload["messages"] = formatted_messages

        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            print(f"Zhipu API HTTP error: {e}")
            print(f"Response: {response.text}")
            raise
        except Exception as e:
            print(f"Zhipu API error: {e}")
            raise

    def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str = "glm-4v",
        temperature: float = 0.1
    ) -> str:
        """
        Analyze an image using GLM-4V.

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
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Validate and correct question/answer pair.

        Args:
            question: Question text
            answer: Answer text
            temperature: Sampling temperature

        Returns:
            Correction result as dict
        """
        prompt = f"""Analyze this mathematical question and answer pair:

--- QUESTION ---
{question}

--- ANSWER ---
{answer}

Tasks:
1. Verify if the question is well-formed and mathematically valid
2. Verify if the answer is correct and addresses the question
3. Check for any obvious errors, typos, or ambiguities
4. Identify if this pair has value for formalization

Respond in JSON format:
{{
  "is_valid_question": true/false,
  "is_valid_answer": true/false,
  "has_errors": true/false,
  "errors": ["list of specific issues found"],
  "corrected_question": "corrected version if needed, else original",
  "corrected_answer": "corrected version if needed, else original",
  "correction_notes": "detailed explanation of corrections made",
  "worth_formalizing": true/false,
  "formalization_value": "high/medium/low"
}}"""

        messages = [{"role": "user", "content": prompt}]
        response = self.chat_completion(
            messages=messages,
            model="glm-4",
            temperature=temperature,
            max_tokens=2000
        )

        import json
        content = response["choices"][0]["message"]["content"]

        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "is_valid_question": True,
                "is_valid_answer": True,
                "has_errors": False,
                "errors": [],
                "corrected_question": question,
                "corrected_answer": answer,
                "correction_notes": "Could not parse LLM response as JSON",
                "worth_formalizing": True,
                "raw_response": content
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
