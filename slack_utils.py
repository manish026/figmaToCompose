import os
import requests
from flask import session # For accessing session data like last_node_id
import config # For accessing SLACK_WEBHOOK_URL_ENV_VAR and SLACK_WEBHOOK_URL_SESSION_KEY

def get_slack_webhook_url(): 
    """Retrieves Slack Webhook URL: session (from UI) > environment variable."""
    url = session.get(config.SLACK_WEBHOOK_URL_SESSION_KEY)
    if url: 
        return url
    env_url = os.environ.get(config.SLACK_WEBHOOK_URL_ENV_VAR)
    return env_url

def _clean_generated_code_for_slack(code_text):
    """Helper to remove potential leading/trailing markdown from Gemini's output."""
    if not isinstance(code_text, str): 
        return ""
    cleaned_code = code_text.strip()
    # Remove leading ```kotlin or kotlin
    if cleaned_code.startswith("```kotlin"):
        cleaned_code = cleaned_code[len("```kotlin"):].strip()
    elif cleaned_code.startswith("kotlin"): 
        cleaned_code = cleaned_code[len("kotlin"):].strip()
    
    # Remove trailing ```
    if cleaned_code.endswith("```"):
        cleaned_code = cleaned_code[:-len("```")].strip()
    return cleaned_code

def send_to_slack(message_text, webhook_url):
    """Sends a message to Slack using an Incoming Webhook."""
    if not webhook_url:
        print("Slack Webhook URL not configured. Skipping Slack notification.")
        return False, "Slack Webhook URL not configured."
    
    cleaned_code = _clean_generated_code_for_slack(message_text)

    # Max characters for the code block content itself to keep overall message reasonable
    MAX_CODE_CONTENT_LENGTH_SLACK = 2800 
    
    code_to_send = cleaned_code
    is_code_truncated = False
    
    if len(cleaned_code) > MAX_CODE_CONTENT_LENGTH_SLACK:
        is_code_truncated = True
        ellipsis = "\n...\n...(code truncated for Slack message)\n...\n"
        ellipsis_len = len(ellipsis)
        
        # Ensure there's enough space for a meaningful snippet around the ellipsis
        if MAX_CODE_CONTENT_LENGTH_SLACK > ellipsis_len + 100: # 100 for some start/end context
            half_len = (MAX_CODE_CONTENT_LENGTH_SLACK - ellipsis_len) // 2
            code_to_send = f"{cleaned_code[:half_len]}{ellipsis}{cleaned_code[-half_len:]}"
        else: # Not enough space for fancy truncation, just hard truncate
            hard_truncate_msg = "... (code truncated)"
            code_to_send = cleaned_code[:MAX_CODE_CONTENT_LENGTH_SLACK - len(hard_truncate_msg)] + hard_truncate_msg
    
    node_id_info = session.get('last_node_id', 'N/A')
    generation_info_header = f"Figma to Jetpack Compose Generation Complete!\nNode ID: {node_id_info}"
    if is_code_truncated:
        generation_info_header += "\n(Full code generated, but truncated for this Slack message due to length.)"

    # Construct the final message text for Slack
    # Ensure the code block is correctly formatted
    final_slack_text = f"{generation_info_header}\n```kotlin\n{code_to_send}\n```"

    payload = {"text": final_slack_text}
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status() 
        print("Successfully sent message to Slack.")
        return True, "Message sent to Slack."
    except requests.exceptions.RequestException as e:
        error_msg = f"Error sending message to Slack: {e}"
        print(error_msg)
        return False, error_msg