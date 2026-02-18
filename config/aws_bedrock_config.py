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

load_dotenv()

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


class BedrockLLM:

    def __init__(self, client, model_id):
        self.client = client
        self.model_id = model_id

    def invoke(self, prompt: str):

        messages = [
            {"role": "system", "content": "Return ONLY valid JSON. No explanations."},
            {"role": "user", "content": prompt}
        ]

        payload = {
            "messages": messages,
            "max_tokens": 500,
            "temperature": 0.3
        }

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
        # Extract JSON safely
        # -----------------------------
        json_match = re.search(r"\{.*\}", content, re.DOTALL)

        if not json_match:
            raise ValueError(f"No JSON found in model response: {content}")

        clean_json = json_match.group()

        return type("LLMResponse", (), {"content": clean_json})


def get_llm():
    return BedrockLLM(client, MODEL_ID)
