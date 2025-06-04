import os
import subprocess
import json
import re
import urllib.parse
from flask import flash # For flashing messages back to the main app
import config # Import configurations

def parse_figma_url(url):
    """Parses a Figma URL to extract the file key and node ID (URL-decoded)."""
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

def fetch_figma_node_data(file_key, node_id, figma_token):
    """
    Fetches the Figma node JSON data using the provided file key, node ID, and token.
    Returns the path to the saved JSON file or None if an error occurs.
    """
    encoded_node_id_for_api = urllib.parse.quote(node_id)
    json_api_url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={encoded_node_id_for_api}"
    curl_json_command = ["curl", "-s", "-H", f"X-Figma-Token: {figma_token}", json_api_url]

    output_json_path = os.path.join(os.getcwd(), config.OUTPUT_JSON_FILENAME)
    try:
        process_json = subprocess.run(curl_json_command, capture_output=True, text=True, check=True)
        loaded_json = json.loads(process_json.stdout) # Validate JSON
        with open(output_json_path, 'w') as f:
            json.dump(loaded_json, f, indent=4)
        flash(f"JSON for '{node_id}' saved to '{output_json_path}'.", "success")
        return output_json_path
    except subprocess.CalledProcessError as e:
        error_message = f"Error fetching node JSON for '{node_id}'. Curl Return code: {e.returncode}. "
        try:
            error_details = json.loads(e.stdout.strip()) 
            error_message += f"Figma API: {error_details.get('err') or error_details.get('message', e.stdout.strip())}"
        except (json.JSONDecodeError, AttributeError):
            error_message += f"Stderr: {e.stderr.strip() if e.stderr else ''} Stdout: {e.stdout.strip() if e.stdout else ''}"
        flash(error_message, "error")
    except json.JSONDecodeError as e_json:
        flash(f"Error decoding JSON from Figma API for node '{node_id}': {e_json}. Response: {process_json.stdout[:200]}...", "error")
    except Exception as e:
        flash(f"Error fetching/saving JSON for '{node_id}': {str(e)}", "error")
    return None

def fetch_figma_node_image(file_key, node_id, figma_token):
    """
    Fetches the Figma node image (SVG) using the provided file key, node ID, and token.
    Returns the path to the saved image file or None if an error occurs.
    """
    encoded_node_id_for_api = urllib.parse.quote(node_id)
    safe_node_id_for_filename = node_id.replace(":", "-").replace("/", "-").replace("\\", "-")
    image_filename = f"{config.OUTPUT_IMAGE_FILE_PREFIX}{safe_node_id_for_filename}.{config.OUTPUT_IMAGE_FORMAT}" 
    image_output_path = os.path.join(os.getcwd(), image_filename)
    image_api_url = f"https://api.figma.com/v1/images/{file_key}?ids={encoded_node_id_for_api}&format={config.OUTPUT_IMAGE_FORMAT}"
    curl_image_url_command = ["curl", "-s", "-H", f"X-Figma-Token: {figma_token}", image_api_url]
    
    try:
        process_image_url = subprocess.run(curl_image_url_command, capture_output=True, text=True, check=True)
        image_url_response_json = json.loads(process_image_url.stdout)
        actual_image_url = None
        image_dict = image_url_response_json.get("images")

        if isinstance(image_dict, dict) and image_dict:
            # Try exact match first
            if node_id in image_dict: 
                actual_image_url = image_dict[node_id]
            # Handle cases like '66-509' in request vs '66:509' in response key
            elif '-' in node_id:
                node_id_colon_variant = node_id.replace('-', ':', 1)
                if node_id_colon_variant in image_dict:
                    actual_image_url = image_dict[node_id_colon_variant]
            # Fallback if only one image is returned for a single requested ID
            if actual_image_url is None and ',' not in node_id and len(image_dict) == 1: 
                actual_image_url = list(image_dict.values())[0]
        
        if actual_image_url:
            curl_download_image_command = ["curl", "-sL", actual_image_url] 
            process_download = subprocess.run(curl_download_image_command, capture_output=True, check=True) 
            with open(image_output_path, 'wb') as img_file: # Save as binary
                img_file.write(process_download.stdout)
            flash(f"{config.OUTPUT_IMAGE_FORMAT.upper()} image for '{node_id}' saved to '{image_output_path}'.", "success")
            return image_output_path 
        else:
            err_msg = image_url_response_json.get("err") if isinstance(image_url_response_json, dict) else "Image not found in API response."
            flash(f"Could not find/fetch {config.OUTPUT_IMAGE_FORMAT.upper()} image URL for '{node_id}'. API msg: {err_msg}. Response: {str(image_url_response_json)[:100]}...", "warning")
    except subprocess.CalledProcessError as e_img_url:
        error_message = f"Error during {config.OUTPUT_IMAGE_FORMAT.upper()} image API call for node '{node_id}'. Curl Return code: {e_img_url.returncode}. "
        try:
            error_details = json.loads(e_img_url.stdout.strip())
            error_message += f"Figma API: {error_details.get('err') or error_details.get('message', e_img_url.stdout.strip())}"
        except (json.JSONDecodeError, AttributeError): 
             error_message += f"Stderr: {e_img_url.stderr.strip() if e_img_url.stderr else ''} Stdout: {e_img_url.stdout.strip() if e_img_url.stdout else ''}"
        flash(error_message, "error") 
    except Exception as e_img: 
        flash(f"Error fetching/saving {config.OUTPUT_IMAGE_FORMAT.upper()} image for '{node_id}': {str(e_img)}", "error")
    return None