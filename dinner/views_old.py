import json
from typing import Any, Dict, List

import httpx
from django.shortcuts import render
from django.utils.safestring import mark_safe

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"

SYSTEM_PROMPT = """
You are an AI dinner recommendation agent for a website.

You talk to the user about what they want for dinner and then suggest concrete
restaurants or food places near them.

IMPORTANT RESPONSE FORMAT:

Always respond as a single JSON object, and NOTHING ELSE, in this format:

{
  "reply": "<friendly natural language reply to the user>",
  "restaurants": [
    {
      "name": "Name of place",
      "address": "Full address",
      "lat": 43.6532,
      "lng": -79.3832,
      "price": "$$",
      "cuisine": "Japanese or similar short description"
    }
  ]
}

Rules:
- "restaurants" can be an empty list if you have no concrete suggestions.
- lat/lng MUST be numbers so the map can use them.
- Do NOT wrap JSON in markdown ``` fences.
"""


def _safe_json_extract(text: str) -> Dict[str, Any]:
    """
    Try to parse JSON from model output.
    If it fails, fall back to {"reply": text, "restaurants": []}.
    Also handles the case where the model outputs extra text around the JSON.
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            pass

    return {"reply": text, "restaurants": []}


def _call_openai(api_key: str, messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Synchronous call to OpenAI's /v1/chat/completions.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",  # change this if you want another model
        "messages": messages,
        "temperature": 0.7,
    }

    with httpx.Client(timeout=60.0) as client:
        r = client.post(OPENAI_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return _safe_json_extract(content)


def _verify_openai_key(api_key: str) -> tuple[bool, str]:
    """
    Make a lightweight request to /v1/models to verify that the API key works.
    Returns (ok, message).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(OPENAI_MODELS_URL, headers=headers)
            r.raise_for_status()
        return True, "✅ key verified successfully"
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return False, "Unauthorized (401). Please check that your OpenAI API key is correct."
        return False, f"OpenAI error {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        return False, f"Error verifying API key: {e}"


def home(request):
    error = None
    verify_message = None
    key_status = "no_key"

    # 🔹 Conversation + restaurants are kept as JSON in the form, not in the session
    chat: List[Dict[str, str]] = []
    restaurants: List[Dict[str, Any]] = []
    api_key = ""
    chat_json = "[]"  # default for hidden field

    if request.method == "POST":
        action = request.POST.get("action", "send")  # "send" or "verify"
        api_key = request.POST.get("api_key", "").strip()

        # Load previous chat from hidden field
        raw_chat_json = request.POST.get("chat_json", "[]")
        try:
            chat = json.loads(raw_chat_json)
            if not isinstance(chat, list):
                chat = []
        except Exception:
            chat = []

        user_msg = request.POST.get("message", "").strip()

        if not api_key:
            error = "Please paste your OpenAI API key (sk-...)."
        else:
            if action == "verify":
                ok, msg = _verify_openai_key(api_key)
                if ok:
                    verify_message = msg
                    key_status = "stored"
                else:
                    error = msg
                    key_status = "no_key"

            elif action == "send":
                if not user_msg:
                    error = "Please type a message for the AI."
                else:
                    # 🔹 IMPORTANT: include full history so GPT has memory
                    messages: List[Dict[str, str]] = (
                        [{"role": "system", "content": SYSTEM_PROMPT}]
                        + chat
                        + [{"role": "user", "content": user_msg}]
                    )

                    # Append user message to history
                    chat.append({"role": "user", "content": user_msg})

                    try:
                        result = _call_openai(api_key, messages)

                        reply_text = result.get("reply", "")
                        new_restaurants = result.get("restaurants", []) or []

                        # Call succeeded -> key works
                        key_status = "stored"

                        # Append assistant reply to history
                        chat.append({"role": "assistant", "content": reply_text})

                        # Update restaurants for this turn
                        restaurants = new_restaurants

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            error = "Unauthorized (401). Check that your OpenAI API key is correct."
                        else:
                            error = f"OpenAI API error: {e.response.status_code} {e.response.text[:200]}"
                        chat.append({
                            "role": "assistant",
                            "content": "Sorry, I had trouble calling the OpenAI API."
                        })
                        key_status = "no_key"
                    except Exception as e:
                        error = f"Error talking to GPT: {e}"
                        chat.append({
                            "role": "assistant",
                            "content": "Sorry, something went wrong when contacting GPT."
                        })
                        key_status = "no_key"

    # If we didn't explicitly set key_status but we have a key and no error, treat it as stored
    if request.method == "POST" and key_status == "no_key" and api_key and not error:
        key_status = "stored"

    # Prepare JSON strings for hidden field and map
    chat_json = json.dumps(chat)
    restaurants_json = mark_safe(json.dumps(restaurants))

    # Map center: default or first restaurant
    center = {"lat": 43.6532, "lng": -79.3832}  # Toronto default
    if restaurants:
        first = restaurants[0]
        center["lat"] = first.get("lat", center["lat"])
        center["lng"] = first.get("lng", center["lng"])

    context = {
        "chat": chat,
        "restaurants": restaurants,
        "restaurants_json": restaurants_json,
        "chat_json": chat_json,
        "center": center,
        "error": error,
        "verify_message": verify_message,
        "key_status": key_status,
        "api_key": api_key,  # keeps the password field filled (masked)
    }
    return render(request, "dinner/home.html", context)
