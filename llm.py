# llm.py
import os
import json
import re
import time
from typing import Dict

from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=API_KEY)

MODEL_NAME = "gemini-2.5-flash-lite"
MODEL = genai.GenerativeModel(MODEL_NAME)

SYSTEM = (
    "You summarise Steam game reviews.\n"
    "Return EXACTLY this JSON wrapped in triple backticks:\n"
    "```json\n"
    '{"sentiment":"pos|neg|mixed","tldr":"10-word fluent sentence"}'
    "\n```"
    "\nRules:"
    "\n- tldr must be a natural sentence of exactly 10 words."
    "\n- Count words (tokens separated by spaces), not characters."
    "\n- sentiment must be one of: pos, neg, mixed (lowercase)."
    "\n- Do not include any commentary outside the JSON fences."
)


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S | re.I)
_WS_RE = re.compile(r"\s+")


def _strip_code_fence(s: str) -> str:
    """Prefer JSON inside fenced block; otherwise, grab the first {...}."""
    s = s or ""
    m = _CODE_FENCE_RE.search(s)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\{.*\}", s, re.S)
    return m2.group(0).strip() if m2 else s.strip()


def _normalize_sentiment(s: str) -> str:
    s = (s or "").strip().lower()
    if s in {"pos", "positive", "👍", "good"}:
        return "pos"
    if s in {"neg", "negative", "👎", "bad"}:
        return "neg"
    return "mixed"


def _count_words(text: str) -> int:
    return len([w for w in _WS_RE.sub(" ", (text or "").strip()).split(" ") if w])


def _ask_gemini(review_text: str, extra_instruction: str = "") -> Dict:
    """Call Gemini with the system prompt + review + optional extra instruction."""
    prompt = SYSTEM
    if extra_instruction:
        prompt += f"\n\n{extra_instruction}"
    prompt += f"\n\nReview:\n{review_text}"

    resp = MODEL.generate_content(
        prompt,
        generation_config={
            "temperature": 0.0,
            "top_p": 0.0,
            "top_k": 1,
            "max_output_tokens": 256,
        },
    )
    raw = _strip_code_fence((resp.text or "").strip())
    return json.loads(raw)



def summarise(
    review_text: str,
    retries: int = 2,
    backoff: float = 0.8,
    accept_min: int = 8,
    accept_max: int = 12,
    extreme_min: int = 6,
    extreme_max: int = 16,
) -> Dict:
    """
    Summarise a review to: {"sentiment": "pos|neg|mixed", "tldr": "<sentence>"}.

    Strategy:
    - No trimming or padding for fluency.
    - Accept if word count is in [accept_min, accept_max] (default 8–12).
    - If word count is far off (< extreme_min or > extreme_max), re-ask Gemini once
      with an explicit instruction to aim for ~10 words.
    - Otherwise (slightly outside the range), keep the original.
    - Normalize sentiment. Light retry/backoff for API/parsing errors.
    """
    last_err = None

    for attempt in range(retries + 1):
        try:
            data = _ask_gemini(review_text)
            tldr = str(data.get("tldr", "")).strip()
            sentiment = _normalize_sentiment(data.get("sentiment"))
            wc = _count_words(tldr)

            if wc < extreme_min or wc > extreme_max:
                try:
                    data2 = _ask_gemini(
                        review_text,
                        extra_instruction=(
                            "Rewrite the TL;DR as a fluent sentence of about 10 words "
                            f"(acceptable range {accept_min}–{accept_max}). "
                            "Only return the JSON."
                        ),
                    )
                    tldr2 = str(data2.get("tldr", "")).strip()
                    wc2 = _count_words(tldr2)
                    if abs(wc2 - 10) < abs(wc - 10):
                        tldr, wc = tldr2, wc2
                except Exception:
                    pass

            return {"sentiment": sentiment, "tldr": tldr}

        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
            else:
                raise

    raise last_err