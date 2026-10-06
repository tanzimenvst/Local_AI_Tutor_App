# AI Tutor Platform 🎓🤖

An intelligent, multi-tutor learning platform powered entirely by local AI via [Ollama](https://ollama.ai/). This application allows administrators to easily create and manage specialized AI tutors, while learners can chat, speak, and learn from them in a beautiful, dynamic interface.

## 🌟 Key Features

*   **Multi-Model Local AI**: Communicates seamlessly with your locally hosted Ollama instances. Dynamically fetches your installed models (e.g., `llama3.1:70b`, `qwen2.5:32b`, `mixtral:8x7b`) so you can assign different models to different tutors.
*   **Dynamic Skill Tracking**: As users chat, the platform secretly runs a background evaluation thread every 10 messages. It analyzes the conversation and adjusts the user's proficiency (0-100%) on specific target capabilities, displaying live progress bars right in the chat sidebar.
*   **AI Tutor Builder Wizard**: An intelligent admin wizard that asks for a learner's profile, goals, and pain points, and then automatically generates the *perfect* system prompt and custom JSON capability configuration for the new AI tutor.
*   **Voice Integration**: Talk to your tutor naturally. Includes built-in speech-to-text transcription and text-to-speech (TTS) generated audio responses.
*   **Admin Dashboard**: Manage users, assign specific tutors to individuals, monitor user counts, dynamically swap models on the fly, and live-edit JSON tutor configurations via an intuitive, recursive UI editor.
*   **Premium Aesthetics**: A stunning, modern, fully responsive dark-mode UI built with vanilla CSS using glassmorphism, dynamic gradients, and fluid micro-animations.

## 🚀 Getting Started

### Prerequisites

1.  **Python 3.8+**
2.  **Ollama**: Must be installed and running locally on port `11434`.
3.  **Local Models**: Pull at least one model in Ollama to get started (e.g., `ollama run qwen3:8b`).

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/ai-tutor.git
    cd ai-tutor
    ```

2.  Create a virtual environment and activate it:
    ```bash
    python -m venv .venv
    
    # On Windows:
    .venv\Scripts\activate
    
    # On Mac/Linux:
    source .venv/bin/activate
    ```

3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Run the application using the provided batch script (Windows) or standard python command:
    ```bash
    start.bat
    # OR manually: python app.py
    ```

5.  The application will automatically initialize the SQLite database and create a default "Local AI Assistant" tutor.
6.  Access the app at `http://127.0.0.1:5000`.

## 🛠️ Usage

### Creating an Admin Account
To access the Admin Panel, you must have an admin account. If you just initialized the database, you can manually update your first created user in the SQLite database to have `is_admin = 1`.

### The Admin Panel (`/admin`)
*   **Users Tab**: Create new learners and assign them to specific specialized tutors.
*   **Tutors Tab**: Use the "Create New Tutor" wizard. The AI will profile the use-case and generate a comprehensive prompt. You can click the ⚙️ gear icon on any tutor to tweak their settings, models, or edit their dynamic tracking configuration.

### The Chat Interface
*   **Desktop**: Access a left sidebar to seamlessly switch between your assigned tutors, and a right sidebar to view your real-time skill evaluations.
*   **Mobile**: Sidebars collapse gracefully into the 3-dots `⋮` dropdown menu to preserve chat space.

## 📁 Architecture

*   **`app.py`**: Main Flask server, routing, background threads, and API endpoints.
*   **`database.py`**: SQLite database initialization, migrations, and CRUD helper methods.
*   **`ollama_client.py`**: Interfacing logic with the local Ollama API for both chat generation and dynamic available model fetching.
*   **`voice_client.py`**: Handles incoming WebM audio transcription and outgoing WAV generation.
*   **`templates/`**: Contains the HTML views (`index.html`, `admin.html`, `login.html`) powered by Jinja2.
*   **`static/`**: Contains the CSS design system and generated TTS audio files.

## 📝 License

This project is open-source and available under the [MIT License](LICENSE).
