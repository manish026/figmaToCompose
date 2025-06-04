# --- Configuration ---
# Output file names and prefixes
OUTPUT_JSON_FILENAME = "figma_node_data.json"
OUTPUT_IMAGE_FILE_PREFIX = "figma_node_image_"
OUTPUT_IMAGE_FORMAT = "svg" 

# Environment variable names
FIGMA_TOKEN_ENV_VAR = "FIGMA_ACCESS_TOKEN"
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY" 
SLACK_WEBHOOK_URL_ENV_VAR = "SLACK_WEBHOOK_URL" 

# Flask server settings
DEFAULT_FLASK_PORT = 5006 
FLASK_PORT_ENV_VAR = "FLASK_RUN_PORT"

# Gemini API settings
GEMINI_MODEL_NAME = "gemini-2.5-pro-preview-05-06" 

# Directory for custom Kotlin code
COMMON_CODE_DIR = "common"
GEMINI_PROMPT_FILENAME = "src/gemini_prompt.txt"

# Session keys for UI-inputted tokens (used by Flask session)
FIGMA_TOKEN_SESSION_KEY = 'figma_token_ui_session' 
GEMINI_API_KEY_SESSION_KEY = 'gemini_api_key_ui_session' 
SLACK_WEBHOOK_URL_SESSION_KEY = 'slack_webhook_url_ui_session' 

# localStorage keys (used by JavaScript in the HTML template)
FIGMA_TOKEN_LOCALSTORAGE_KEY = 'figma_token_local'
GEMINI_API_KEY_LOCALSTORAGE_KEY = 'gemini_api_key_local'
SLACK_WEBHOOK_URL_LOCALSTORAGE_KEY = 'slack_webhook_url_local' 
