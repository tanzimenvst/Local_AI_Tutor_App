import os
import uuid
from datetime import timedelta
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ollama_client import ask_qwen
import database
import voice_client


app = Flask(__name__)
app.secret_key = "super-secret-key-change-in-production"
app.permanent_session_lifetime = timedelta(days=30)


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    user = database.get_user_by_id(session["user_id"])
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    tutors = database.get_assigned_tutors(user["id"])
    
    if len(tutors) == 0:
        return "No tutors assigned to your account. Please contact the administrator."
    elif len(tutors) == 1:
        return redirect(url_for("chat", tutor_id=tutors[0]["id"]))
    else:
        return render_template("select_tutor.html", user=user, tutors=tutors)


@app.route("/chat/<int:tutor_id>", methods=["GET", "POST"])
def chat(tutor_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    user = database.get_user_by_id(session["user_id"])
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    # Verify authorization: is this tutor assigned to this user?
    tutors = database.get_assigned_tutors(user["id"])
    if not any(t["id"] == tutor_id for t in tutors):
        return "Unauthorized: You do not have access to this tutor.", 403

    tutor = database.get_tutor_by_id(tutor_id)
    if not tutor:
        return "Tutor not found.", 404

    prompt = ""
    response = ""

    if request.method == "POST":
        # Check if an audio file was uploaded via the JS frontend
        if "audio" in request.files:
            audio_file = request.files["audio"]
            temp_input = f"temp_input_{uuid.uuid4().hex}.webm"
            audio_file.save(temp_input)
            
            try:
                # 1. Transcribe voice
                prompt = voice_client.transcribe_audio(temp_input)
                if not prompt:
                    return jsonify({"error": "Could not hear anything."}), 400
                
                # 2. Ask AI
                response = ask_qwen(prompt, tutor["system_prompt"], tutor["model"])
                response = response.replace("*", "")
                
                # 3. Generate Voice Response
                audio_dir = os.path.join(app.root_path, "static", "audio")
                os.makedirs(audio_dir, exist_ok=True)
                
                output_filename = f"response_{uuid.uuid4().hex}.wav"
                output_path = os.path.join(audio_dir, output_filename)
                voice_client.generate_tts(response, output_path)
                
                audio_url = url_for("static", filename=f"audio/{output_filename}")
                database.add_message(user["id"], tutor_id, prompt, response, audio_url)
                
                return jsonify({
                    "prompt": prompt,
                    "response": response,
                    "audio_url": audio_url
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            finally:
                if os.path.exists(temp_input):
                    os.remove(temp_input)

        # Normal text fallback (AJAX)
        prompt = request.form.get("prompt", "").strip()
        if prompt:
            response = ask_qwen(prompt, tutor["system_prompt"], tutor["model"])
            response = response.replace("*", "")
            database.add_message(user["id"], tutor_id, prompt, response, None)
            return jsonify({
                "prompt": prompt,
                "response": response
            })
            
        return jsonify({"error": "Empty prompt"}), 400

    # GET Request: Fetch history
    messages = database.get_messages(user["id"], tutor_id)
    return render_template("index.html", tutor=tutor, user=user, messages=messages)


@app.route("/chat/<int:tutor_id>/clear")
def clear_chat(tutor_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    database.clear_messages(session["user_id"], tutor_id)
    return redirect(url_for("chat", tutor_id=tutor_id))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))
        
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember")
        
        user = database.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session.permanent = bool(remember)
            session["user_id"] = user["id"]
            return redirect(url_for("home"))
        else:
            error = "Invalid username or password"
            
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("login"))


@app.route("/admin")
def admin():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
        
    error = request.args.get("error")
    message = request.args.get("message")
    users = database.get_all_users()
    tutors = database.get_all_tutors()
    
    return render_template("admin.html", user=user, users=users, tutors=tutors, error=error, message=message)


@app.route("/admin/create_user", methods=["POST"])
def admin_create_user():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "")
    is_admin = 1 if request.form.get("is_admin") else 0
    
    if database.get_user_by_username(username):
        return redirect(url_for("admin", error="Username already exists"))
        
    database.create_user(username, display_name, generate_password_hash(password), is_admin)
    return redirect(url_for("admin", message="User created successfully"))


@app.route("/admin/create_tutor", methods=["POST"])
def admin_create_tutor():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    name = request.form.get("name", "").strip()
    tutor_type = request.form.get("tutor_type", "").strip()
    model = request.form.get("model", "qwen3:8b").strip()
    system_prompt = request.form.get("system_prompt", "").strip()
    
    database.create_tutor(name, tutor_type, system_prompt, model)
    return redirect(url_for("admin", message="Tutor created successfully"))


@app.route("/admin/assign", methods=["POST"])
def admin_assign():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    user_id = request.form.get("user_id")
    tutor_id = request.form.get("tutor_id")
    
    if database.assign_tutor(user_id, tutor_id):
        return redirect(url_for("admin", message="Tutor assigned successfully"))
    else:
        return redirect(url_for("admin", error="Tutor already assigned to this user"))


if __name__ == "__main__":
    # Host "0.0.0.0" allows the app to be accessible on the local network (LAN)
    app.run(host="0.0.0.0", port=5000, debug=True)
