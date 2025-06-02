# Figma to Compose (Using GenAI)🚀 

This project uses Generative AI to convert Figma designs into Jetpack Compose UI code.

---

## 🤔 What it does

`figmaToCompose` leverages Generative AI to translate your Figma designs directly into Jetpack Compose UI code. It accesses your Figma files via the Figma API to understand the design structure, properties, and elements. This information is then processed by a Generative AI model (specifically, Gemini 2.5 Pro is preferred) to generate the corresponding Kotlin code for building your Android UI with Jetpack Compose. The goal is to streamline the handoff from design to development and accelerate the UI implementation process.

---

## ✨ Features

* Automatic layout generation from Figma nodes
* Mapping of common Figma components to Jetpack Compose composables
* Web-based UI for easy interaction and API key input (runs on port 5000)
* Support for various Figma element types

---

## Prerequisites 🔑

Before you begin, ensure you have the following ready to be entered into the application's web UI:

* **Figma API Key**: You'll need an API key from Figma to allow the application to access your design files. You can generate one from your Figma account settings.
    * [How to get a Figma API Key](https://help.figma.com/hc/en-us/articles/8085703771159-Manage-Personal-Access-Tokens)
* **Gemini API Key**: A Google AI Studio API key for the Gemini model is required. The **Gemini 2.5 Pro** model is preferred for best results.
    * [Get a Gemini API Key](https://aistudio.google.com/app/apikey)

---

## 🚀 Getting Started

You can run `figmaToCompose` either directly using Python 3 or with Docker. In both methods, the application will start a web server on port `5000`, and you will interact with it through your web browser where you'll be prompted to enter your API keys.

### 1. Using Python 3 🐍

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/manish026/figmaToCompose.git](https://github.com/manish026/figmaToCompose.git)
    cd figmaToCompose
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    *(Ensure you have a `requirements.txt` file in your repository)*
    ```bash
    pip3 install -r requirements.txt
    ```
    *To create `requirements.txt` if you don't have one, after installing dependencies manually in your activated venv, run: `pip freeze > requirements.txt`*

4.  **Run the application:**
    *(Provide the command to run your main Python script that starts the web server. Ensure it's configured to run on port 5000.)*
    ```bash
    python3 figma_to_jetpack.py
    ```
    After running the script, open your web browser and navigate to `http://127.0.0.1:5000` or `http://localhost:5000`. You will be prompted to enter your Figma and Gemini API keys in the web UI.

5.  **Deactivate the virtual environment (when done):**
    ```bash
    deactivate
    ```

### 2. Using Docker 🐳

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/manish026/figmaToCompose.git](https://github.com/manish026/figmaToCompose.git)
    cd figmaToCompose
    ```

2.  **Build the Docker image:**
    *(You'll need to add a `Dockerfile` to your repo. Ensure your Dockerfile EXPOSEs port 5000 and your application inside the container runs on port 5000. Example command below)*
    ```bash
    docker build -t figmatocompose .
    ```

3.  **Run the Docker container:**
    *(This maps port 5000 of the container to port 5000 on your host machine.)*
    ```bash
    docker run -p 5000:5000 figmatocompose
    ```
    After running the container, open your web browser and navigate to `http://localhost:5000`. You will be prompted to enter your Figma and Gemini API keys in the web UI.

---

## 🛠️ How to Use


https://github.com/user-attachments/assets/ea32f649-ca19-4824-b468-ff21c4f05e5b



A detailed video tutorial on how to use `figmaToCompose` will be added soon! Stay tuned. 🎥

---

## 🤝 Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and use a feature branch. Pull requests are warmly welcome.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 🙏 Acknowledgements

* [Figma API](https://www.figma.com/developers/)
* [Google Gemini](https://deepmind.google/technologies/gemini/)

---

## 📧 Contact

Manish Malviya - [@ManishMalv39377_](https://x.com/ManishMalv39377) *(Replace with your actual Twitter/X handle or preferred contact)*

Project Link: [https://github.com/manish026/figmaToCompose](https://github.com/manish026/figmaToCompose)
