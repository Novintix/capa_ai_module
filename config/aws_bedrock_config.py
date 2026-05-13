"""
config.py

Initializes AWS Bedrock client using environment variables.
Provides a reusable Bedrock invocation function.
"""

import os
import json
import re
import boto3
from dotenv import load_dotenv
from agent_ops import init_agentops, llm_span

load_dotenv()
init_agentops(default_tags=["capa_ai_module", "bedrock"])

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
MODEL_ID = os.getenv("MODEL_ID")

client = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)


def _messages_to_text(messages: list) -> str:
    parts = []
    for message in messages or []:
        role = str(message.get("role", ""))
        content = str(message.get("content", ""))
        parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _estimate_tokens(text: str) -> int:
    text = text or ""
    if not text.strip():
        return 0
    return max(1, len(text.split()))


def _extract_usage(result: dict, prompt_text: str, response_text: str) -> dict:
    usage: dict = {}
    raw_usage = None
    if isinstance(result, dict):
        raw_usage = result.get("usage")
        if not raw_usage:
            raw_usage = result.get("metadata", {}).get("usage")

    if isinstance(raw_usage, dict):
        usage["prompt_tokens"] = (
            raw_usage.get("prompt_tokens")
            or raw_usage.get("input_tokens")
            or raw_usage.get("inputTokenCount")
        )
        usage["completion_tokens"] = (
            raw_usage.get("completion_tokens")
            or raw_usage.get("output_tokens")
            or raw_usage.get("outputTokenCount")
        )
        usage["total_tokens"] = raw_usage.get("total_tokens")

    if usage.get("prompt_tokens") is None:
        usage["prompt_tokens"] = _estimate_tokens(prompt_text)
        usage["prompt_tokens_estimated"] = True

    if usage.get("completion_tokens") is None:
        usage["completion_tokens"] = _estimate_tokens(response_text)
        usage["completion_tokens_estimated"] = True

    if usage.get("total_tokens") is None:
        usage["total_tokens"] = (
            int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
        )
        if usage.get("prompt_tokens_estimated") or usage.get("completion_tokens_estimated"):
            usage["total_tokens_estimated"] = True

    return usage


class BedrockLLM:

    def __init__(self, client, model_id):
        self.client = client
        self.model_id = model_id

    def invoke(self, prompt):
        if isinstance(prompt, list):
            # Message list from get_unified_cause_messages (SystemMessage + HumanMessage)
            messages = []
            for msg in prompt:
                if hasattr(msg, "type"):
                    role = "assistant" if msg.type == "ai" else ("system" if msg.type == "system" else "user")
                    messages.append({"role": role, "content": msg.content})
                elif isinstance(msg, dict):
                    messages.append(msg)
        else:
            # Legacy string prompt — wrap with generic system message
            messages = [
                {"role": "system", "content": "Return ONLY valid JSON. No explanations."},
                {"role": "user", "content": prompt}
            ]

        payload = {
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.0,
            "top_p": 0.001,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }

        return self._single_invoke(payload)

    def _single_invoke(self, payload):
        """Single model invocation"""
        prompt_text = _messages_to_text(payload.get("messages"))
        span_attributes = {
            "agentops.span.kind": "LLM",
            "gen_ai.system": "aws_bedrock",
            "gen_ai.request.model": self.model_id,
            "gen_ai.request.max_tokens": payload.get("max_tokens"),
            "gen_ai.request.temperature": payload.get("temperature"),
            "gen_ai.request.top_p": payload.get("top_p"),
            "gen_ai.request.frequency_penalty": payload.get("frequency_penalty"),
            "gen_ai.request.presence_penalty": payload.get("presence_penalty"),
            "capa_ai.prompt.length": len(prompt_text),
        }

        with llm_span("bedrock.invoke", span_attributes) as span:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(payload)
            )

            raw_body = response["body"].read()

            if not raw_body:
                raise ValueError("Empty response body from Bedrock")

            try:
                result = json.loads(raw_body)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid JSON returned from Bedrock: {raw_body}")

            # -----------------------------
            # Handle OpenAI OSS format
            # -----------------------------
            if "output" in result:
                content_list = result["output"]["message"]["content"]

                if isinstance(content_list, list) and len(content_list) > 0:
                    content = content_list[0].get("text", "")
                else:
                    raise ValueError(f"Unexpected output format: {result}")

            # -----------------------------
            # Handle OpenAI-like format
            # -----------------------------
            elif "choices" in result:
                content = result["choices"][0]["message"]["content"]

            else:
                raise ValueError(f"Unknown Bedrock response format: {result}")

            # -----------------------------
            # Strip <reasoning> tags if present (model thinking block)
            # -----------------------------
            original_content = content
            content = re.sub(r"<reasoning>.*?</reasoning>", "", content, flags=re.DOTALL).strip()

            # -----------------------------
            # Extract JSON safely — fallback to original if strip removed everything
            # -----------------------------
            json_match = re.search(r"\{.*\}", content, re.DOTALL)

            if not json_match:
                # Fallback: search original content (handles JSON inside reasoning block)
                json_match = re.search(r"\{.*\}", original_content, re.DOTALL)

            if not json_match:
                # For simple numeric responses (like our ranking prompts), return the cleaned content
                # Also check for numeric values in the original content if cleaning removed everything
                content_to_check = content if content.strip() else original_content

                # Extract numeric value from text
                numeric_match = re.search(r"\b([0-9]*\.?[0-9]+)\b", content_to_check)
                if numeric_match:
                    numeric_value = numeric_match.group(1)
                    return type("LLMResponse", (), {
                        "content": numeric_value,
                        "raw_content": original_content
                    })()
                raise ValueError(f"No JSON or numeric value found in model response: {original_content}")

            clean_json = json_match.group()

            usage = _extract_usage(result, prompt_text, original_content)

            if span is not None:
                span.set_attribute("gen_ai.usage.prompt_tokens", int(usage.get("prompt_tokens") or 0))
                span.set_attribute("gen_ai.usage.completion_tokens", int(usage.get("completion_tokens") or 0))
                span.set_attribute("gen_ai.usage.total_tokens", int(usage.get("total_tokens") or 0))
                if usage.get("prompt_tokens_estimated"):
                    span.set_attribute("capa_ai.usage.prompt_tokens_estimated", True)
                if usage.get("completion_tokens_estimated"):
                    span.set_attribute("capa_ai.usage.completion_tokens_estimated", True)
                if usage.get("total_tokens_estimated"):
                    span.set_attribute("capa_ai.usage.total_tokens_estimated", True)
                span.set_attribute("capa_ai.response.length", len(original_content or ""))

            return type("LLMResponse", (), {
                "content": clean_json,
                "raw_content": original_content,
                "usage": usage,
            })()


def get_llm():
    return BedrockLLM(client, MODEL_ID)
