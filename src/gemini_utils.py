import os
try:
    import google.generativeai as genai
except ImportError:
    genai = None

import config # For accessing GEMINI_PROMPT_FILENAME and GEMINI_MODEL_NAME

def load_gemini_prompt_template():
    """Loads the base prompt template from a file."""
    try:
        # The content of the prompt file is the text selected by the user.
        # This function reads that content from the file specified in config.
        print(f"Loading Gemini prompt template from: {config.GEMINI_PROMPT_FILENAME}")
        with open(config.GEMINI_PROMPT_FILENAME, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: Gemini prompt file '{config.GEMINI_PROMPT_FILENAME}' not found.")
        return None
    except Exception as e:
        print(f"ERROR: Could not read Gemini prompt file '{config.GEMINI_PROMPT_FILENAME}': {e}")
        return None

def call_gemini_api_sse_generator(api_key_param, figma_json_str, figma_svg_str=None, custom_kotlin_files_content=None, additional_instructions=None):
    """
    Calls the Gemini API using a chat session to first provide context from custom Kotlin files,
    then generates Jetpack Compose code, yielding chunks for SSE.
    The prompt structure is loaded from the template file and dynamically filled.
    """
    print("SSE Generator: Attempting to call Gemini API with chat context...")
    if not genai:
        yield f"data: [ERROR] The 'google-generativeai' library is not installed.\n\n"
        yield f"data: [STREAM_END]\n\n" 
        return

    if not api_key_param:
        yield f"data: [ERROR] Gemini API Key was not provided to the generator.\n\n"
        yield f"data: [STREAM_END]\n\n"
        return
        
    try:
        genai.configure(api_key=api_key_param) 
        print(f"SSE Generator: Configured Gemini API with key. Model: {config.GEMINI_MODEL_NAME}")
        
        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        chat = model.start_chat(history=[]) 

        # --- Context Priming Phase: Send custom Kotlin files ---
        context_prime_prompt_parts = []
        if custom_kotlin_files_content:
            yield "data: [INFO] Preparing custom code context for Gemini...\n\n"
            context_prime_prompt_parts.append(
                "You are an expert Android Jetpack Compose developer. I will provide you with several Kotlin files from my existing project. "
                "Please understand and remember these as context for a code generation task that will follow. "
                "You MUST prioritize using definitions (colors, typography, utilities, etc.) from these files "
                "when I later ask you to generate code. Do not redefine them if suitable ones exist in this provided context.\n\n"
                "Here is the custom code:\n"
            )
            
            for file_info in custom_kotlin_files_content:
                context_prime_prompt_parts.append(f"""
                --- Start of content from '{file_info['filename']}' ---
                ```kotlin
                {file_info['content']}
                ```
                --- End of content from '{file_info['filename']}' ---\n
                """)
            context_prime_prompt_parts.append("\nPlease acknowledge that you have received and will prioritize this custom code context for the subsequent generation task.")
            
            full_context_prime_prompt = "".join(context_prime_prompt_parts)
            print(f"SSE Generator: Sending custom code context to Gemini ({len(custom_kotlin_files_content)} files)...")
            
            context_response = chat.send_message(full_context_prime_prompt)
            ack_message = context_response.text.strip()[:150] 
            print(f"SSE Generator: Gemini acknowledgement for context (snippet): {ack_message}...")
            yield f"data: [INFO] Custom code context sent. Gemini acknowledgement (snippet): {ack_message}...\n\n"
        else:
            yield "data: [INFO] No custom Kotlin files provided for context.\n\n"


        # --- Main Generation Phase ---
        main_generation_prompt_template = load_gemini_prompt_template()
        if not main_generation_prompt_template:
            yield f"data: [ERROR] Could not load main Gemini prompt template from '{config.GEMINI_PROMPT_FILENAME}'.\n\n"
            yield f"data: [STREAM_END]\n\n"
            return

        figma_svg_data_section_str = ""
        if figma_svg_str:
            figma_svg_data_section_str = f"If SVG data is provided, it represents the vector graphics of the node. This is crucial for accurately rendering icons, complex shapes, and graphical elements.\n\nFigma Node SVG Content:\n```svg\n{figma_svg_str}\n```"
        else:
            figma_svg_data_section_str = "If SVG data is provided, it represents the vector graphics of the node. This is crucial for accurately rendering icons, complex shapes, and graphical elements.\n\n(No SVG content was provided for this node)."
        
        custom_kotlin_code_section_str = "Remember to use the custom Kotlin code context (colors, typography, utilities) I've already given you in our conversation."
        
        additional_user_instructions_section_str = ""
        if additional_instructions:
            additional_user_instructions_section_str = f"Any additional instructions provided in this section are specific overrides or clarifications for the current generation task and must be followed with precision.\n\nAdditional User Instructions:\n```text\n{additional_instructions}\n```"
        else:
            additional_user_instructions_section_str = "Any additional instructions provided in this section are specific overrides or clarifications for the current generation task and must be followed with precision.\n\n(No additional user instructions were provided)."

        final_generation_prompt = main_generation_prompt_template.format(
            figma_json_data=figma_json_str,
            figma_svg_data_section=figma_svg_data_section_str,
            custom_kotlin_code_section=custom_kotlin_code_section_str, 
            additional_user_instructions_section=additional_user_instructions_section_str
        )
        
        print(f"SSE Generator: --- Sending Main Generation Prompt to Gemini API ({config.GEMINI_MODEL_NAME}) ---") 
        
        response_stream = chat.send_message(final_generation_prompt, stream=True)
        
        print("SSE Generator: --- Receiving Streamed Response from Gemini API: ---")
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if chunk.text: 
                sse_data = chunk.text.replace('\n', '\\n') 
                yield f"data: {sse_data}\n\n"
                print(chunk.text, end='', flush=True) 

        if chunk_count == 0:
            print("SSE Generator: [No chunks received from stream for generation request.]")
            last_response = chat.history[-1] if chat.history and chat.history[-1].role == 'model' else None
            if last_response and hasattr(last_response, 'prompt_feedback') and last_response.prompt_feedback and last_response.prompt_feedback.block_reason:
                 yield f"data: [ERROR] Gemini API request was blocked. Reason: {last_response.prompt_feedback.block_reason_message or last_response.prompt_feedback.block_reason}\n\n"
            else:
                yield "data: [ERROR] No content received from Gemini stream for the generation request.\n\n"
        
        print("\nSSE Generator: --- End of Streamed Response ---")
        
        last_response = chat.history[-1] if chat.history and chat.history[-1].role == 'model' else None
        if last_response and hasattr(last_response, 'prompt_feedback') and last_response.prompt_feedback and last_response.prompt_feedback.block_reason:
             yield f"data: [ERROR] Gemini API request was blocked. Reason: {last_response.prompt_feedback.block_reason_message or last_response.prompt_feedback.block_reason}\n\n"
        
        yield f"data: [STREAM_END]\n\n"

    except Exception as e:
        exception_type = type(e).__name__
        error_detail_str = str(e)
        
        # Construct a more informative base error message
        error_message = f"Error calling Gemini API ({config.GEMINI_MODEL_NAME}) - Type: {exception_type}: {error_detail_str}"

        # Specific check for token limit errors
        if "token" in error_detail_str.lower() and ("exceeds" in error_detail_str.lower() or "limit" in error_detail_str.lower()):
            error_message = f"TOKEN LIMIT EXCEEDED. Type: {exception_type}: {error_detail_str}. This can happen if the total conversation history (including custom code and Figma data) is too large. Please reduce the amount of custom code in the 'common/' folder or simplify the Figma node."
        
        # Add e.args[0] if it exists and provides different information
        if hasattr(e, 'args') and e.args and str(e.args[0]) != error_detail_str:
            error_message += f" Further Details: {e.args[0]}" # Changed "Details" to "Further Details" for clarity
        
        print(f"SSE Generator: {error_message}") 
        yield f"data: [ERROR] {error_message}\n\n"
        yield f"data: [STREAM_END]\n\n" 
