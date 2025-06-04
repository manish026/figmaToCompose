import os
import glob
import time 
import json # For reading figma json
from flask import Flask, request, render_template, redirect, url_for, flash, session, Response, jsonify

# Import configurations from config.py
import config 
# Import Figma utilities
import figma_utils 
# Import Slack utilities
import slack_utils 
# Import Gemini utilities
import gemini_utils 

# Attempt to import the Gemini library (though it's primarily used in gemini_utils now)
# This is mainly for the 'genai' variable check at startup.
try:
    import google.generativeai as genai 
except ImportError:
    genai = None 

# Initialize Flask App
app = Flask(__name__) 
app.secret_key = os.urandom(24) 

def get_figma_token():
    """Retrieves Figma token: session (from UI) > environment variable."""
    token = session.get(config.FIGMA_TOKEN_SESSION_KEY) 
    if token: 
        return token
    env_token = os.environ.get(config.FIGMA_TOKEN_ENV_VAR)
    return env_token


def get_gemini_api_key_from_session_or_env(): 
    """Retrieves Gemini API key: session (from UI) > environment variable.
       This is for use within a request context.
    """
    key = session.get(config.GEMINI_API_KEY_SESSION_KEY) 
    if key: 
        return key
    env_key = os.environ.get(config.GEMINI_API_KEY_ENV_VAR)
    return env_key

# get_slack_webhook_url is in slack_utils.py
# _clean_generated_code_for_slack is in slack_utils.py
# send_to_slack is in slack_utils.py
# load_gemini_prompt_template is in gemini_utils.py
# call_gemini_api_sse_generator is in gemini_utils.py

@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    compose_output = session.get('compose_code_output', '')
    figma_token_env_set = True if os.environ.get(config.FIGMA_TOKEN_ENV_VAR) else False
    gemini_api_key_env_set = True if os.environ.get(config.GEMINI_API_KEY_ENV_VAR) else False
    slack_webhook_url_env_set = True if os.environ.get(config.SLACK_WEBHOOK_URL_ENV_VAR) else False 

    return render_template("index.html", 
                                  output_json_filename=config.OUTPUT_JSON_FILENAME,
                                  output_image_prefix=config.OUTPUT_IMAGE_FILE_PREFIX,
                                  output_image_format=config.OUTPUT_IMAGE_FORMAT, 
                                  token_env_var=config.FIGMA_TOKEN_ENV_VAR, 
                                  gemini_api_key_env_var=config.GEMINI_API_KEY_ENV_VAR, 
                                  slack_webhook_url_env_var=config.SLACK_WEBHOOK_URL_ENV_VAR, 
                                  figma_token_session_key=config.FIGMA_TOKEN_SESSION_KEY,
                                  gemini_api_key_session_key=config.GEMINI_API_KEY_SESSION_KEY,
                                  slack_webhook_url_session_key=config.SLACK_WEBHOOK_URL_SESSION_KEY, 
                                  figma_token_localStorage_key=config.FIGMA_TOKEN_LOCALSTORAGE_KEY, 
                                  gemini_api_key_localStorage_key=config.GEMINI_API_KEY_LOCALSTORAGE_KEY, 
                                  slack_webhook_url_localStorage_key=config.SLACK_WEBHOOK_URL_LOCALSTORAGE_KEY, 
                                  figma_token_env_set=figma_token_env_set,
                                  gemini_api_key_env_set=gemini_api_key_env_set,
                                  slack_webhook_url_env_set=slack_webhook_url_env_set, 
                                  flask_port_env_var=config.FLASK_PORT_ENV_VAR, 
                                  default_flask_port=config.DEFAULT_FLASK_PORT, 
                                  gemini_model_name=config.GEMINI_MODEL_NAME,
                                  common_code_dir=config.COMMON_CODE_DIR, 
                                  compose_code_output=compose_output)

@app.route('/configure_settings', methods=['POST']) 
def configure_settings():
    figma_token = request.form.get('figma_token_ui_input') 
    gemini_key = request.form.get('gemini_api_key_ui_input')
    slack_url = request.form.get('slack_webhook_url_ui_input') 

    if figma_token: 
        session[config.FIGMA_TOKEN_SESSION_KEY] = figma_token
        flash('Figma token saved to server session.', 'success')
    else: 
        session.pop(config.FIGMA_TOKEN_SESSION_KEY, None) 
        flash('Figma token cleared from server session. Will use environment variable if set.', 'info')
        
    if gemini_key: 
        session[config.GEMINI_API_KEY_SESSION_KEY] = gemini_key
        flash('Gemini API key saved to server session.', 'success')
    else: 
        session.pop(config.GEMINI_API_KEY_SESSION_KEY, None) 
        flash('Gemini API key cleared from server session. Will use environment variable if set.', 'info')

    if slack_url: 
        session[config.SLACK_WEBHOOK_URL_SESSION_KEY] = slack_url
        flash('Slack Webhook URL saved to server session.', 'success')
    else:
        session.pop(config.SLACK_WEBHOOK_URL_SESSION_KEY, None)
        flash('Slack Webhook URL cleared from server session. Will use environment variable if set.', 'info')

    return redirect(url_for('index'))


@app.route('/fetch', methods=['POST'])
def fetch_figma_data():
    session.pop('compose_code_output', None) 
    session.pop('json_file_path', None)
    session.pop('image_file_path', None)
    session.pop('last_node_id', None)
    
    figma_url = request.form.get('figma_url')
    if not figma_url:
        flash("Figma URL is required.", "error")
        return redirect(url_for('index'))

    file_key, node_id = figma_utils.parse_figma_url(figma_url) 
    if not file_key or not node_id: 
        flash(f"Could not parse File Key or Node ID from URL: {figma_url}", "error")
        return redirect(url_for('index'))
    session['last_node_id'] = node_id 

    figma_token = get_figma_token() 
    if not figma_token:
        flash(f"Error: Figma Access Token is not set. Please set it via UI or the {config.FIGMA_TOKEN_ENV_VAR} environment variable.", "error")
        return redirect(url_for('index'))

    json_file_path = figma_utils.fetch_figma_node_data(file_key, node_id, figma_token)
    if json_file_path:
        session['json_file_path'] = json_file_path
    else:
        return redirect(url_for('index')) 

    image_file_path = figma_utils.fetch_figma_node_image(file_key, node_id, figma_token)
    if image_file_path:
        session['image_file_path'] = image_file_path

    return redirect(url_for('index'))


@app.route('/stream_compose_generation') 
def stream_compose_generation():
    session.pop('compose_code_output', None) 

    retrieved_gemini_api_key = get_gemini_api_key_from_session_or_env() 
    if not retrieved_gemini_api_key:
        def error_stream():
            yield f"data: [ERROR] Gemini API Key is not set. Please set it via UI or the {config.GEMINI_API_KEY_ENV_VAR} environment variable.\n\n"
            yield f"data: [STREAM_END]\n\n"
        return Response(error_stream(), mimetype='text/event-stream')

    additional_instructions = request.args.get('additional_instructions', '') 

    json_path = session.get('json_file_path')
    svg_path = session.get('image_file_path') 

    if not json_path or not os.path.exists(json_path):
        def error_stream():
            yield "data: [ERROR] Figma JSON data not found in session. Please fetch data first.\n\n"
            yield "data: [STREAM_END]\n\n"
        return Response(error_stream(), mimetype='text/event-stream')
    
    figma_json_content_str = None
    figma_svg_content_str = None 

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            loaded_json = json.load(f)
            figma_json_content_str = json.dumps(loaded_json, indent=4) 
    except Exception as e:
        def error_stream():
            yield f"data: [ERROR] Error reading JSON file {json_path}: {e}\n\n"
            yield f"data: [STREAM_END]\n\n"
        return Response(error_stream(), mimetype='text/event-stream')


    if svg_path and os.path.exists(svg_path): 
        try:
            with open(svg_path, 'r', encoding='utf-8') as f: 
                figma_svg_content_str = f.read() 
        except Exception as e:
            print(f"Warning: Error reading SVG file {svg_path}: {e}")

    custom_kotlin_files = []
    if os.path.exists(config.COMMON_CODE_DIR):
        kotlin_files_pattern = os.path.join(config.COMMON_CODE_DIR, "*.kt")
        for kt_file_path in glob.glob(kotlin_files_pattern):
            try:
                with open(kt_file_path, 'r', encoding='utf-8') as f_kt:
                    custom_kotlin_files.append({
                        "filename": os.path.basename(kt_file_path),
                        "content": f_kt.read()
                    })
            except Exception as e:
                print(f"Warning: Error reading custom Kotlin file '{kt_file_path}': {e}")
    
    return Response(gemini_utils.call_gemini_api_sse_generator(
        retrieved_gemini_api_key, 
        figma_json_content_str, 
        figma_svg_content_str,
        custom_kotlin_files_content=custom_kotlin_files,
        additional_instructions=additional_instructions 
    ), mimetype='text/event-stream')

@app.route('/save_generated_code_and_notify_slack', methods=['POST']) 
def save_generated_code_and_notify_slack():
    slack_messages_for_client = [] 
    try:
        data = request.get_json()
        code_to_save = data.get('code')
        if code_to_save is not None:
            session['compose_code_output'] = code_to_save
            slack_messages_for_client.append({"category": "success", "message": "Generated code saved to session."})
            
            slack_webhook = slack_utils.get_slack_webhook_url() 
            if slack_webhook:
                success, slack_msg = slack_utils.send_to_slack(code_to_save, slack_webhook) 
                if success:
                    slack_messages_for_client.append({"category": "success", "message": slack_msg})
                else:
                    slack_messages_for_client.append({"category": "error", "message": slack_msg})
            else:
                slack_messages_for_client.append({"category": "warning", "message": "Slack Webhook URL not configured. Skipping Slack notification."})
            
            return jsonify(status="success", message="Code processed.", flash_messages=slack_messages_for_client), 200
        else:
            return jsonify(status="error", message="No code provided.", flash_messages=slack_messages_for_client), 400
    except Exception as e:
        print(f"Error in /save_generated_code_and_notify_slack: {e}")
        slack_messages_for_client.append({"category": "error", "message": str(e)})
        return jsonify(status="error", message=str(e), flash_messages=slack_messages_for_client), 500

@app.route('/resend_to_slack', methods=['POST'])
def resend_to_slack():
    try:
        data = request.get_json()
        code_to_send = data.get('code')
        if not code_to_send:
            return jsonify(status="error", message="No code provided to resend."), 400

        slack_webhook = slack_utils.get_slack_webhook_url() 
        if not slack_webhook:
            return jsonify(status="warning", message="Slack Webhook URL not configured. Cannot resend."), 200 

        success, slack_msg = slack_utils.send_to_slack(code_to_send, slack_webhook) 
        if success:
            return jsonify(status="success", message=f"Code resent to Slack. ({slack_msg})"), 200
        else:
            return jsonify(status="error", message=f"Failed to resend to Slack: {slack_msg}"), 500
    except Exception as e:
        print(f"Error in /resend_to_slack: {e}")
        return jsonify(status="error", message=str(e)), 500


if __name__ == '__main__':
    port = int(os.environ.get(config.FLASK_PORT_ENV_VAR, config.DEFAULT_FLASK_PORT))

    if not os.path.exists(config.COMMON_CODE_DIR):
        try:
            os.makedirs(config.COMMON_CODE_DIR)
            print(f"Created directory '{config.COMMON_CODE_DIR}' for custom Kotlin files.")
        except OSError as e:
            print(f"Error creating directory '{config.COMMON_CODE_DIR}': {e}. Please create it manually.")

    if not genai: 
        print("Warning: The 'google-generativeai' library is not installed. Generation will fail.")
        print("Please run: pip install Flask google-generativeai")
    
    try: 
        import requests
    except ImportError:
        print("Warning: The 'requests' library is not installed. Slack notification will fail.")
        print("Please run: pip install requests")


    print(f"Starting Flask app with Gemini model '{config.GEMINI_MODEL_NAME}'. Open http://127.0.0.1:{port} in your browser.")
    print(f"Set API tokens & Slack Webhook via UI or as environment variables: '{config.FIGMA_TOKEN_ENV_VAR}', '{config.GEMINI_API_KEY_ENV_VAR}', '{config.SLACK_WEBHOOK_URL_ENV_VAR}'.")
    print(f"Optionally, set '{config.FLASK_PORT_ENV_VAR}' to change the port (default: {config.DEFAULT_FLASK_PORT}).")
    print(f"Place your custom Kotlin files (ending with .kt) in the '{config.COMMON_CODE_DIR}/' directory.")
    print("Ensure 'curl' is installed and in your system PATH.")
    print("Streaming output from Gemini will appear in this console and in the web UI log.") 
    
    app.run(host='0.0.0.0', port=port, debug=True)
