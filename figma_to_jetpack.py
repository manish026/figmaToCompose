import os
import subprocess
import json
import re
import urllib.parse
import glob # For finding files
import time # For SSE keep-alive if needed, and demo
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, Response, jsonify

# Attempt to import the Gemini library
try:
    import google.generativeai as genai
except ImportError:
    genai = None 

# Initialize Flask App
app = Flask(__name__)
app.secret_key = os.urandom(24) 

# --- Configuration ---
OUTPUT_JSON_FILENAME = "figma_node_data.json"
OUTPUT_IMAGE_FILE_PREFIX = "figma_node_image_"
OUTPUT_IMAGE_FORMAT = "svg" 
FIGMA_TOKEN_ENV_VAR = "FIGMA_ACCESS_TOKEN"
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY" 
DEFAULT_FLASK_PORT = 5006 
FLASK_PORT_ENV_VAR = "FLASK_RUN_PORT"
GEMINI_MODEL_NAME = "gemini-2.5-pro-preview-05-06" 
COMMON_CODE_DIR = "common"


# --- HTML Template with Material Design Lite ---
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="description" content="Figma Node Fetcher and Compose Generator">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
    <title>Figma to Jetpack Compose via Gemini</title>

    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
    <link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.indigo-pink.min.css">
    <style>
        body {
            font-family: 'Roboto', 'Helvetica', 'Arial', sans-serif;
            background-color: #f5f5f5;
            display: flex;
            flex-direction: column; 
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }
        .mdl-card {
            width: 100%;
            max-width: 700px; 
            border-radius: 8px;
            margin-bottom: 20px; 
        }
        .mdl-card__title {
            background-color: #3f51b5; 
            color: white;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }
        .mdl-card__supporting-text {
            padding-bottom: 0;
            width: 100%; 
            box-sizing: border-box;
        }
        .mdl-textfield {
            width: 100%;
        }
        .mdl-button--raised.mdl-button--colored {
            background-color: #3f51b5; 
        }
         .mdl-button--accent { 
            background-color: #009688; 
        }
        .messages {
            margin-top: 20px;
            padding: 10px;
            border-radius: 4px;
            word-break: break-word; 
        }
        .messages.success { background-color: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
        .messages.error   { background-color: #ffebee; color: #c62828; border: 1px solid #ef9a9a; }
        .messages.warning { background-color: #fffde7; color: #f57f17; border: 1px solid #fff59d; }
        .messages.info    { background-color: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; } 
        
        .info-box {
            margin-top: 15px; padding: 10px; background-color: #e3f2fd;
            color: #1565c0; border: 1px solid #90caf9; border-radius: 4px; font-size: 0.9em;
        }
        .info-box p { margin: 5px 0; }
        .info-box code { background-color: #eceff1; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
        .info-box ul { padding-left: 20px; }

        #gemini-stream-container {
            margin-top: 15px;
            padding: 10px;
            background-color: #212121; /* Dark background for log */
            color: #00e676; /* Greenish text for log */
            border: 1px solid #424242;
            border-radius: 4px;
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.85em;
            white-space: pre-wrap; /* Wrap long lines but preserve spaces */
            word-break: break-all; /* Break long words/tokens */
        }
        #gemini-stream-container h4 {
            margin-top: 0;
            color: #90caf9; /* Light blue for heading */
        }

        textarea#final-compose-code { /* Changed ID for clarity */
            width: 100%;
            height: 500px; 
            font-family: monospace;
            font-size: 0.85em;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 10px;
            box-sizing: border-box;
            white-space: pre;
            overflow: auto;
            background-color: #f9f9f9;
            margin-top: 10px; /* Space above final code */
        }
        .compose-section { margin-top: 20px; }
        .file-info { font-size: 0.9em; color: #555; margin-bottom:10px; }
    </style>
</head>
<body>
    <div class="mdl-card mdl-shadow--6dp">
        <div class="mdl-card__title">
            <h2 class="mdl-card__title-text">Figma Node Data Fetcher</h2>
        </div>
        <div class="mdl-card__supporting-text">
            <p>Enter your Figma file URL to fetch node data and its {{ output_image_format.upper() }} image.</p>
            <form action="{{ url_for('fetch_figma_data') }}" method="post">
                <div class="mdl-textfield mdl-js-textfield mdl-textfield--floating-label">
                    <input class="mdl-textfield__input" type="url" id="figma_url" name="figma_url" required>
                    <label class="mdl-textfield__label" for="figma_url">Figma File URL (with node-id)</label>
                </div>
                <div class="mdl-card__actions mdl-card--border">
                    <button type="submit" class="mdl-button mdl-js-button mdl-button--raised mdl-button--colored mdl-js-ripple-effect">
                        Fetch Data & Image
                    </button>
                </div>
            </form>

            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="messages {{ category }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            {% if session.get('json_file_path') %}
            <div class="compose-section">
                <p class="file-info">
                    JSON: {{ session.get('json_file_path') }}
                    {% if session.get('image_file_path') %}<br>{{ output_image_format.upper() }} Image: {{ session.get('image_file_path') }}{% endif %}
                </p>
                
                <button id="generate-compose-btn" class="mdl-button mdl-js-button mdl-button--raised mdl-button--accent mdl-js-ripple-effect" style="margin-top:10px;">
                    Generate Jetpack Compose with Gemini
                </button>
                
                <div id="gemini-stream-container" style="display:none;">
                    <h4>Gemini Generation Log:</h4>
                    <pre id="gemini-stream-log"></pre>
                </div>

            </div>
            {% endif %}
            
            <div class="info-box">
                <p><strong>Important Setup:</strong></p>
                <ul>
                    <li>Ensure <code>curl</code> is installed.</li>
                    <li>Set <code>{{ token_env_var }}</code> environment variable for Figma.</li>
                    <li>Install Python libraries: <code>pip install Flask google-generativeai</code> (add <code>Pillow</code> if using PNG/JPG with vision models).</li>
                    <li>Set <code>{{ gemini_api_key_env_var }}</code> environment variable with your Gemini API Key.</li>
                    <li>Optionally, set <code>{{ flask_port_env_var }}</code> to customize the run port (default: {{ default_flask_port }}).</li>
                    <li>JSON saved to <code>{{ output_json_filename }}</code>.</li>
                    <li>Image saved as <code>{{ output_image_prefix }}NODE-ID.{{ output_image_format }}</code>.</li>
                    <li><strong>For Custom Code:</strong> Create a directory named <code>{{ common_code_dir }}</code> in the same location as this script. Place any relevant Kotlin files (<code>*.kt</code>) inside it.</li>
                </ul>
            </div>
        </div>
    </div>

    {% if session.get('json_file_path') %} <div class="mdl-card mdl-shadow--6dp">
        <div class="mdl-card__title" style="background-color: #009688;"> 
            <h2 class="mdl-card__title-text">Final Generated Jetpack Compose Code</h2>
        </div>
        <div class="mdl-card__supporting-text">
            <p>The complete code generated by Gemini API (<code>{{ gemini_model_name }}</code>) will appear here after streaming finishes. <strong>Always review and test thoroughly.</strong></p>
            <p class="file-info">Based on Figma data for Node ID: {{ session.get('last_node_id', 'N/A') }}</p>
            <textarea id="final-compose-code" readonly class="compose-code" placeholder="Generated code will appear here...">{{ session.get('compose_code_output', '') }}</textarea>
        </div>
    </div>
    {% endif %}


    <script>
        document.addEventListener('DOMContentLoaded', function () {
            const generateBtn = document.getElementById('generate-compose-btn');
            const streamContainer = document.getElementById('gemini-stream-container');
            const streamLog = document.getElementById('gemini-stream-log');
            const finalCodeTextarea = document.getElementById('final-compose-code');

            if (generateBtn && finalCodeTextarea) { 
                generateBtn.addEventListener('click', function () {
                    if (!streamContainer || !streamLog) {
                        console.error('Required DOM elements for streaming log are missing.');
                        alert('Error: UI elements for streaming log are not ready.');
                        return;
                    }

                    streamContainer.style.display = 'block';
                    streamLog.textContent = 'Starting generation... Please wait.\\n';
                    finalCodeTextarea.value = ''; 
                    let accumulatedCode = ''; 

                    generateBtn.disabled = true;
                    generateBtn.textContent = 'Generating...';

                    const eventSource = new EventSource("{{ url_for('stream_compose_generation') }}");

                    eventSource.onmessage = function (event) {
                        if (event.data === "[STREAM_END]") {
                            streamLog.textContent += '\\n\\n--- Generation Complete ---';
                            eventSource.close();
                            finalCodeTextarea.value = accumulatedCode; 
                            generateBtn.disabled = false; 
                            generateBtn.textContent = 'Generate Jetpack Compose with Gemini';

                            fetch("{{ url_for('save_generated_code') }}", {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({ code: accumulatedCode })
                            })
                            .then(response => response.json())
                            .then(data => {
                                console.log('Save response:', data);
                                if(data.status !== 'success') {
                                    alert('Could not save generated code to session: ' + (data.message || 'Unknown error'));
                                }
                            })
                            .catch(error => {
                                console.error('Error saving code to session:', error);
                                alert('Error saving code to session. Check console.');
                            });

                        } else if (event.data.startsWith("[ERROR]")) {
                            let errorMessage = event.data.substring("[ERROR]".length).trim();
                            streamLog.textContent += '\\n\\n--- ERROR --- \\n' + errorMessage;
                            eventSource.close();
                            finalCodeTextarea.value = "Error during generation. See log above.";
                            generateBtn.disabled = false;
                            generateBtn.textContent = 'Generate Jetpack Compose with Gemini';
                        } else {
                            let textChunk = event.data.replace(/\\\\n/g, '\\n'); 
                            streamLog.textContent += textChunk;
                            accumulatedCode += textChunk; 
                            streamContainer.scrollTop = streamContainer.scrollHeight; 
                        }
                    };

                    eventSource.onerror = function (error) {
                        console.error("EventSource failed:", error);
                        streamLog.textContent += '\\n\\n--- Connection Error with Server ---';
                        eventSource.close();
                        finalCodeTextarea.value = "Error connecting to the server for streaming. Check console.";
                        generateBtn.disabled = false;
                        generateBtn.textContent = 'Generate Jetpack Compose with Gemini';
                    };
                });
            }
        });
    </script>
    <script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
</body>
</html>
"""

def parse_figma_url(url):
    patterns = [
        r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)[^?]*\?(?:.*&)?node-id=([^&]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_key = match.group(1)
            node_id_encoded = match.group(2)
            node_id_decoded = urllib.parse.unquote(node_id_encoded)
            return file_key, node_id_decoded
    return None, None

def call_gemini_api_sse_generator(figma_json_str, figma_svg_str=None, custom_kotlin_files_content=None):
    """
    Calls the Gemini API and yields chunks for SSE.
    Does NOT modify session.
    """
    print("SSE Generator: Attempting to call Gemini API...")
    if not genai:
        yield f"data: [ERROR] The 'google-generativeai' library is not installed.\n\n"
        yield f"data: [STREAM_END]\n\n" 
        return

    api_key = os.environ.get(GEMINI_API_KEY_ENV_VAR)
    if not api_key:
        yield f"data: [ERROR] The environment variable {GEMINI_API_KEY_ENV_VAR} is not set.\n\n"
        yield f"data: [STREAM_END]\n\n"
        return

    try:
        genai.configure(api_key=api_key)
        print(f"SSE Generator: Configured Gemini API with key. Model: {GEMINI_MODEL_NAME}")
        
        model = genai.GenerativeModel(GEMINI_MODEL_NAME) 

        prompt = f"""
        You are an expert Android Jetpack Compose developer. Your task is to generate high-quality, production-ready Jetpack Compose (Kotlin) code based on Figma design data.
        The goal is to achieve a UI that is as close to pixel-perfect as possible with the provided Figma data, while ensuring the code is runnable and idiomatic.

        Figma Node JSON:
        ```json
        {figma_json_str}
        ```
        """

        if figma_svg_str:
            prompt += f"""
        Figma Node SVG Content (if applicable, for VECTOR nodes or image fills):
        ```svg
        {figma_svg_str}
        ```
        """
        else:
            prompt += "\nNo SVG content was provided for this node.\n"

        if custom_kotlin_files_content:
            prompt += "\nConsider the following existing custom Kotlin code from the project. You MUST prioritize using these definitions (colors, typography, utilities, etc.) over defining new ones if they serve the purpose:\n"
            for file_info in custom_kotlin_files_content:
                prompt += f"""
                --- Start of content from '{file_info['filename']}' ---
                ```kotlin
                {file_info['content']}
                ```
                --- End of content from '{file_info['filename']}' ---
                """
        else:
            prompt += "\nNo custom Kotlin files were provided or found. Generate standard Jetpack Compose code.\n"
        
        prompt += """
        Key Instructions for Jetpack Compose Code Generation:
        1.  **Accuracy and Pixel Perfection**: Strive for the closest possible visual match to the Figma design described by the JSON and SVG. Pay attention to dimensions, padding, margins, colors, fonts, corner radii, and layout.
        2.  **Use Provided Custom Code**: If custom Kotlin files (for colors, typography, utilities) are provided above, YOU MUST USE THEM. Do not redefine colors or typography styles if suitable ones exist in the provided custom code. Refer to custom utility functions if they can simplify the generated code.
        3.  **Standard Composables**: Use standard Jetpack Compose functions and Modifiers (`Box`, `Column`, `Row`, `Text`, `Image`, `Surface`, `Modifier.padding`, `Modifier.size`, `Modifier.background`, etc.).
        4.  **SVG Handling**: If SVG content is provided for a VECTOR node, generate code to render it. Suggest using a library like Coil-SVG for Compose (`rememberAsyncImagePainter` with an SVG decoder) or, if the SVG is extremely simple, note that it could be converted to an Android VectorDrawable.
        5.  **Interactivity**: If a node seems interactive (e.g., a button), include a placeholder `onClick` lambda (e.g., `onClick = {{ /* TODO: Implement action */ }}`). For input-like elements, suggest `remember {{ mutableStateOf("") }}`.
        6.  **Previews**: ALWAYS include a `@Preview` Composable function for the generated component. Ensure the preview is self-contained or uses easily mockable data.
        7.  **Imports**: Include ALL necessary import statements for Jetpack Compose, Kotlin standard library, and any custom code references.
        8.  **Error-Free Code**: The generated Kotlin code MUST be syntactically correct and runnable.
        9.  **Comments for Complex Translations**: If a direct or complex translation of a Figma property is difficult or potentially error-prone, use a simpler, standard Jetpack Compose equivalent and add a comment in the code noting the original Figma property or the intended behavior. For example: `// Figma 'drop-shadow': ...`.
        10. **Color Mapping**: Map Figma colors (RGBA from JSON) to your provided custom color definitions first. If no suitable custom color exists, use standard Compose `Color(red, green, blue, alpha)` objects.
        11. **Typography Mapping**: Map Figma typography (font family, weight, size, letter spacing, line height) to your provided custom typography definitions (e.g., `TextStyle` objects) first. If not applicable, create new `TextStyle` objects.
        12. **Layout**: Carefully translate Figma's auto-layout properties (layoutMode, itemSpacing, padding, alignment) to Compose `Row`/`Column` arrangements and alignments. For absolute positioning or complex constraints, use `Box` with `Alignment` modifiers or, if necessary, suggest `ConstraintLayout` with a comment.
        13. **Clarity and Readability**: Generate clean, well-formatted, and readable Kotlin code.

        Output ONLY the complete, runnable Kotlin code block. Do not include any explanatory text, greetings, or apologies before or after the code block. Start directly with the package statement or imports.
        """
        
        print(f"SSE Generator: --- Sending Prompt to Gemini API ({GEMINI_MODEL_NAME}) ---") 
        
        response_stream = model.generate_content(prompt, stream=True)
        
        print("SSE Generator: --- Receiving Streamed Response from Gemini API: ---")
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if chunk.text: 
                sse_data = chunk.text.replace('\n', '\\n') 
                yield f"data: {sse_data}\n\n"
                print(chunk.text, end='', flush=True) 
            # else: 
            #     print(f"\n[Stream chunk {chunk_count} had no text content. Parts: {chunk.parts}]", end='', flush=True)

        if chunk_count == 0:
            print("SSE Generator: [No chunks received from stream.]")
            yield "data: [ERROR] No content received from Gemini stream.\n\n"
        
        print("\nSSE Generator: --- End of Streamed Response ---")
        
        if hasattr(response_stream, 'prompt_feedback') and response_stream.prompt_feedback and response_stream.prompt_feedback.block_reason:
             yield f"data: [ERROR] Gemini API request was blocked. Reason: {response_stream.prompt_feedback.block_reason_message or response_stream.prompt_feedback.block_reason}\n\n"
        
        yield f"data: [STREAM_END]\n\n"


    except Exception as e:
        error_message = f"Error calling Gemini API ({GEMINI_MODEL_NAME}): {str(e)}"
        if hasattr(e, 'args') and e.args:
            error_message += f" Details: {e.args[0]}"
        print(f"SSE Generator: {error_message}") 
        yield f"data: [ERROR] {error_message}\n\n"
        yield f"data: [STREAM_END]\n\n" 


@app.route('/', methods=['GET'])
def index():
    """Renders the main page."""
    compose_output = session.get('compose_code_output', '')
    return render_template_string(HTML_TEMPLATE,
                                  output_json_filename=OUTPUT_JSON_FILENAME,
                                  output_image_prefix=OUTPUT_IMAGE_FILE_PREFIX,
                                  output_image_format=OUTPUT_IMAGE_FORMAT, 
                                  token_env_var=FIGMA_TOKEN_ENV_VAR,
                                  gemini_api_key_env_var=GEMINI_API_KEY_ENV_VAR,
                                  flask_port_env_var=FLASK_PORT_ENV_VAR, 
                                  default_flask_port=DEFAULT_FLASK_PORT, 
                                  gemini_model_name=GEMINI_MODEL_NAME,
                                  common_code_dir=COMMON_CODE_DIR, 
                                  compose_code_output=compose_output)


@app.route('/fetch', methods=['POST'])
def fetch_figma_data():
    figma_url = request.form.get('figma_url')
    session.pop('compose_code_output', None) 
    session.pop('json_file_path', None)
    session.pop('image_file_path', None)
    session.pop('last_node_id', None)
    
    if not figma_url:
        flash("Figma URL is required.", "error")
        return redirect(url_for('index'))

    file_key, node_id = parse_figma_url(figma_url)
    session['last_node_id'] = node_id 

    if not file_key or not node_id:
        flash(f"Could not parse File Key or Node ID from URL: {figma_url}", "error")
        return redirect(url_for('index'))

    figma_token = os.environ.get(FIGMA_TOKEN_ENV_VAR)
    if not figma_token:
        flash(f"Error: {FIGMA_TOKEN_ENV_VAR} not set.", "error")
        return redirect(url_for('index'))

    encoded_node_id_for_api = urllib.parse.quote(node_id)
    json_api_url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={encoded_node_id_for_api}"
    curl_json_command = ["curl", "-s", "-H", f"X-Figma-Token: {figma_token}", json_api_url]

    json_saved = False
    output_json_path = os.path.join(os.getcwd(), OUTPUT_JSON_FILENAME)
    try:
        process_json = subprocess.run(curl_json_command, capture_output=True, text=True, check=True)
        loaded_json = json.loads(process_json.stdout)
        with open(output_json_path, 'w') as f:
            json.dump(loaded_json, f, indent=4)
        flash(f"JSON for '{node_id}' saved to '{output_json_path}'.", "success")
        session['json_file_path'] = output_json_path 
        json_saved = True
    except subprocess.CalledProcessError as e:
        error_message = f"Error fetching node JSON for '{node_id}'. Curl Return code: {e.returncode}. "
        try:
            error_details = json.loads(e.stdout.strip()) 
            error_message += f"Figma API: {error_details.get('err') or error_details.get('message', e.stdout.strip())}"
        except (json.JSONDecodeError, AttributeError):
            error_message += f"Stderr: {e.stderr.strip() if e.stderr else ''} Stdout: {e.stdout.strip() if e.stdout else ''}"
        flash(error_message, "error")
        return redirect(url_for('index'))
    except json.JSONDecodeError as e_json:
        flash(f"Error decoding JSON from Figma API for node '{node_id}': {e_json}. Response: {process_json.stdout[:200]}...", "error")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error fetching/saving JSON for '{node_id}': {str(e)}", "error")
        return redirect(url_for('index'))

    if not json_saved:
        return redirect(url_for('index'))

    safe_node_id_for_filename = node_id.replace(":", "-").replace("/", "-").replace("\\", "-")
    image_filename = f"{OUTPUT_IMAGE_FILE_PREFIX}{safe_node_id_for_filename}.{OUTPUT_IMAGE_FORMAT}" 
    image_output_path = os.path.join(os.getcwd(), image_filename)
    image_api_url = f"https://api.figma.com/v1/images/{file_key}?ids={encoded_node_id_for_api}&format={OUTPUT_IMAGE_FORMAT}"
    curl_image_url_command = ["curl", "-s", "-H", f"X-Figma-Token: {figma_token}", image_api_url]
    
    try:
        process_image_url = subprocess.run(curl_image_url_command, capture_output=True, text=True, check=True)
        image_url_response_json = json.loads(process_image_url.stdout)
        actual_image_url = None
        image_dict = image_url_response_json.get("images")

        if isinstance(image_dict, dict) and image_dict:
            if node_id in image_dict: actual_image_url = image_dict[node_id]
            else: 
                node_id_parts = node_id.split('-', 1)
                if len(node_id_parts) == 2:
                    node_id_colon_variant = f"{node_id_parts[0]}:{node_id_parts[1]}"
                    if node_id_colon_variant in image_dict: actual_image_url = image_dict[node_id_colon_variant]
                if actual_image_url is None and ',' not in node_id and len(image_dict) == 1: 
                    actual_image_url = list(image_dict.values())[0]
        
        if actual_image_url:
            curl_download_image_command = ["curl", "-sL", actual_image_url] 
            process_download = subprocess.run(curl_download_image_command, capture_output=True, check=True) 
            with open(image_output_path, 'wb') as img_file: img_file.write(process_download.stdout)
            flash(f"{OUTPUT_IMAGE_FORMAT.upper()} image for '{node_id}' saved to '{image_output_path}'.", "success")
            session['image_file_path'] = image_output_path 
        else:
            err_msg = image_url_response_json.get("err") if isinstance(image_url_response_json, dict) else "Image not found in API response."
            flash(f"Could not find/fetch {OUTPUT_IMAGE_FORMAT.upper()} image URL for '{node_id}'. API msg: {err_msg}. Response: {str(image_url_response_json)[:100]}...", "warning")
    except subprocess.CalledProcessError as e_img_url:
        error_message = f"Error during {OUTPUT_IMAGE_FORMAT.upper()} image API call for node '{node_id}'. Curl Return code: {e_img_url.returncode}. "
        try:
            error_details = json.loads(e_img_url.stdout.strip())
            error_message += f"Figma API: {error_details.get('err') or error_details.get('message', e_img_url.stdout.strip())}"
        except (json.JSONDecodeError, AttributeError): 
             error_message += f"Stderr: {e_img_url.stderr.strip() if e_img_url.stderr else ''} Stdout: {e_img_url.stdout.strip() if e_img_url.stdout else ''}"
        flash(error_message, "error") 
    except Exception as e_img: 
        flash(f"Error fetching/saving {OUTPUT_IMAGE_FORMAT.upper()} image for '{node_id}': {str(e_img)}", "error")

    return redirect(url_for('index'))


@app.route('/stream_compose_generation') 
def stream_compose_generation():
    session.pop('compose_code_output', None) 

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
    if os.path.exists(COMMON_CODE_DIR):
        kotlin_files_pattern = os.path.join(COMMON_CODE_DIR, "*.kt")
        for kt_file_path in glob.glob(kotlin_files_pattern):
            try:
                with open(kt_file_path, 'r', encoding='utf-8') as f_kt:
                    custom_kotlin_files.append({
                        "filename": os.path.basename(kt_file_path),
                        "content": f_kt.read()
                    })
            except Exception as e:
                print(f"Warning: Error reading custom Kotlin file '{kt_file_path}': {e}")
    
    return Response(call_gemini_api_sse_generator(
        figma_json_content_str, 
        figma_svg_content_str,
        custom_kotlin_files_content=custom_kotlin_files
    ), mimetype='text/event-stream')

@app.route('/save_generated_code', methods=['POST'])
def save_generated_code():
    try:
        data = request.get_json()
        code_to_save = data.get('code')
        if code_to_save is not None:
            session['compose_code_output'] = code_to_save
            return jsonify(status="success", message="Code saved to session."), 200
        else:
            return jsonify(status="error", message="No code provided."), 400
    except Exception as e:
        print(f"Error in /save_generated_code: {e}")
        return jsonify(status="error", message=str(e)), 500


if __name__ == '__main__':
    port = int(os.environ.get(FLASK_PORT_ENV_VAR, DEFAULT_FLASK_PORT))

    if not os.path.exists(COMMON_CODE_DIR):
        try:
            os.makedirs(COMMON_CODE_DIR)
            print(f"Created directory '{COMMON_CODE_DIR}' for custom Kotlin files.")
        except OSError as e:
            print(f"Error creating directory '{COMMON_CODE_DIR}': {e}. Please create it manually.")

    if not genai:
        print("Warning: The 'google-generativeai' library is not installed. Generation will fail.")
        print("Please run: pip install Flask google-generativeai")
    
    print(f"Starting Flask app with Gemini model '{GEMINI_MODEL_NAME}'. Open http://127.0.0.1:{port} in your browser.")
    print(f"Ensure '{FIGMA_TOKEN_ENV_VAR}' and '{GEMINI_API_KEY_ENV_VAR}' environment variables are set.")
    print(f"Optionally, set '{FLASK_PORT_ENV_VAR}' to change the port (default: {DEFAULT_FLASK_PORT}).")
    print(f"Place your custom Kotlin files (ending with .kt) in the '{COMMON_CODE_DIR}/' directory.")
    print("Ensure 'curl' is installed and in your system PATH.")
    print("Streaming output from Gemini will appear in this console and in the web UI log.") 
    
    app.run(host='0.0.0.0', port=port, debug=True)
