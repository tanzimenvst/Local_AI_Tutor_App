import os
import uuid
from datetime import timedelta
import threading
import json
from flask import Flask, request, render_template, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from ollama_client import ask_qwen, ask_ollama_raw
import database
import voice_client

def background_evaluate_skills(user_id, tutor_id, tutor_model):
    msgs = database.get_messages(user_id, tutor_id)[-10:]
    if not msgs: return
    history = "\n".join([f"User: {m['prompt']}\nTutor: {m['response']}" for m in msgs])
    
    eval_record = database.get_user_evaluation(user_id, tutor_id)
    current_data = eval_record["evaluation_data"]
    
    tutor = database.get_tutor_by_id(tutor_id)
    if not current_data:
        config = {}
        if tutor["configuration"]:
            try:
                config = json.loads(tutor["configuration"])
            except: pass
            
        current_data = {}
        target = config.get("learner_profile", {}).get("target_capabilities", [])
        for cat in target:
            cat_name = cat.get("category", "Uncategorized")
            current_data[cat_name] = {}
            for item in cat.get("items", []):
                current_data[cat_name][item] = 0
                
    if not current_data:
        return # No skills to evaluate
        
    prompt = f"""You are an expert AI evaluator. Review the following conversation.
Assess the user's proficiency in the following skills (currently scored 0-100).
Current Skills: {json.dumps(current_data, indent=2)}

Conversation:
{history}

If the user demonstrates knowledge or improvement, slightly increase the relevant score. If they show misunderstanding, slightly decrease it.
Return ONLY a valid JSON object matching the exact structure of Current Skills, with the updated 0-100 integer scores. Do NOT wrap in markdown.
"""
    try:
        response = ask_ollama_raw(prompt, expect_json=True, model=tutor_model)
        new_data = json.loads(response)
        database.update_user_evaluation_data(user_id, tutor_id, new_data)
    except Exception as e:
        print("Background evaluation failed:", e)


app = Flask(__name__)
app.secret_key = "super-secret-key-change-in-production"
app.permanent_session_lifetime = timedelta(days=30)


@app.before_request
def check_blocked_user():
    if "user_id" in session:
        if request.endpoint not in ["login", "logout", "static"]:
            user = database.get_user_by_id(session["user_id"])
            if user and user["is_blocked"]:
                session.pop("user_id", None)
                return redirect(url_for("login", error="Your account has been blocked by an administrator."))


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
        
    user = database.get_user_by_id(session["user_id"])
    if not user:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    tutors = database.get_assigned_tutors(user["id"])
    tutors = [t for t in tutors if not t["is_blocked"]]
    
    if len(tutors) == 0:
        return "No tutors assigned to your account, or all assigned tutors are currently blocked. Please contact the administrator."
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
    tutors = [t for t in tutors if not t["is_blocked"]]
    
    if not any(t["id"] == tutor_id for t in tutors):
        return "Unauthorized: You do not have access to this tutor, or the tutor is currently blocked.", 403

    tutor = database.get_tutor_by_id(tutor_id)
    if not tutor or tutor["is_blocked"]:
        return "Tutor not found or is currently blocked.", 404

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
                
                database.increment_evaluation_message_count(user["id"], tutor_id)
                eval_record = database.get_user_evaluation(user["id"], tutor_id)
                if eval_record["message_count"] > 0 and eval_record["message_count"] % 10 == 0:
                    threading.Thread(target=background_evaluate_skills, args=(user["id"], tutor_id, tutor["model"])).start()
                
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
            
            database.increment_evaluation_message_count(user["id"], tutor_id)
            eval_record = database.get_user_evaluation(user["id"], tutor_id)
            if eval_record["message_count"] > 0 and eval_record["message_count"] % 10 == 0:
                threading.Thread(target=background_evaluate_skills, args=(user["id"], tutor_id, tutor["model"])).start()
            
            return jsonify({
                "prompt": prompt,
                "response": response
            })
            
        return jsonify({"error": "Empty prompt"}), 400

    # GET Request: Fetch history
    messages = database.get_messages(user["id"], tutor_id)
    eval_record = database.get_user_evaluation(user["id"], tutor_id)
    eval_data = eval_record["evaluation_data"]
    
    if not eval_data:
        config = {}
        if tutor["configuration"]:
            try:
                config = json.loads(tutor["configuration"])
            except: pass
        eval_data = {}
        target = config.get("learner_profile", {}).get("target_capabilities", [])
        for cat in target:
            cat_name = cat.get("category", "Uncategorized")
            eval_data[cat_name] = {}
            for item in cat.get("items", []):
                eval_data[cat_name][item] = 0
                
    return render_template("index.html", tutor=tutor, user=user, messages=messages, tutors=tutors, eval_data=eval_data)


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
        
    error = request.args.get("error")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember")
        
        user = database.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            if user["is_blocked"]:
                error = "This account has been blocked by an administrator."
            else:
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
    raw_users = database.get_all_users()
    # Augment users with their personal assigned tutors
    users = []
    for u in raw_users:
        u_dict = dict(u)
        all_assigned = database.get_assigned_tutors(u['id'])
        u_dict['assigned_tutors'] = [t for t in all_assigned if t['is_general'] == 0]
        users.append(u_dict)
        
    tutors = []
    existing_learners = set()
    raw_tutors = database.get_all_tutors()
    for t in raw_tutors:
        t_dict = dict(t)
        
        # Extract learner for autocomplete
        if t_dict.get("configuration"):
            try:
                import json
                conf = json.loads(t_dict["configuration"])
                if conf.get("learner_profile", {}).get("who"):
                    existing_learners.add(conf["learner_profile"]["who"])
            except:
                pass
                
        if t_dict["is_general"] == 1:
            t_dict["user_count"] = "All"
        else:
            # count how many users have this tutor assigned
            t_dict["user_count"] = sum(1 for u in users if any(at["id"] == t_dict["id"] for at in u["assigned_tutors"]))
        tutors.append(t_dict)
    import ollama_client
    available_models = ollama_client.get_available_models()
    
    return render_template("admin.html", user=user, users=users, tutors=tutors, existing_learners=list(existing_learners), error=error, message=message, available_models=available_models)


@app.route("/admin/create_user", methods=["POST"])
def admin_create_user():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    password = request.form.get("password", "")
    
    if database.get_user_by_username(username):
        return redirect(url_for("admin", error="Username already exists"))
        
    database.create_user(username, display_name, generate_password_hash(password), 0)
    return redirect(url_for("admin", message="User created successfully"))


@app.route("/admin/create_tutor", methods=["POST"])
def admin_create_tutor():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    name = request.form.get("name", "").strip()
    model = request.form.get("model", "qwen3:8b").strip()
    system_prompt = request.form.get("system_prompt", "").strip()
    configuration = request.form.get("configuration", "").strip() or None
    
    database.create_tutor(name, system_prompt, model, configuration)
    return redirect(url_for("admin", tab="tutors", message="Tutor created successfully"))


@app.route("/admin/api/wizard_step_1", methods=["POST"])
def admin_wizard_step_1():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 403
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    who = data.get("who", "")
    why = data.get("why", "")
    objective = data.get("objective", "")

    prompt = f"""You are an expert AI architect designing a persona for a custom AI tutor.
User Profile: {who}
Goal: {why}
Objective: {objective}

Identify exactly what missing categories of information would be useful to properly configure this tutor (e.g. technical skills, experience level). 
Do NOT ask for Name, Goal, Objective, Teaching Style, Difficulty, or Scope. Focus on dynamic domain-specific attributes.
Output ONLY valid JSON matching this exact schema (do not wrap in markdown):
{{
    "dynamic_categories": [
        {{
            "category_name": "Technical Skills",
            "type": "multi-select",
            "options": ["Python", "QGIS", "ArcGIS"]
        }}
    ]
}}"""
    from ollama_client import ask_ollama_raw
    response = ask_ollama_raw(prompt, expect_json=True)
    import json
    try:
        return jsonify(json.loads(response))
    except Exception as e:
        print("JSON parse error from ollama:", e, response)
        return jsonify({"error": "Failed to generate categories. Please try again."}), 500


@app.route("/admin/api/wizard_step_2", methods=["POST"])
def admin_wizard_step_2():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 403
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    config = data.get("configuration", {})

    import json
    config_str = json.dumps(config, indent=2)

    prompt = f"""You are an expert AI architect. Write a complete System Prompt for a tutor based on this verified configuration:

{config_str}

The system prompt should define the persona, boundaries, tone, and specific instructions clearly. 
Tell the AI how to act. Incorporate current vs target capabilities and scope. Do not use asterisks or emojis in the prompt.
Output ONLY valid JSON matching this schema (do not wrap in markdown):
{{
    "system_prompt": "You are an expert...",
    "suggested_name": "A human readable title with spaces, e.g. Frontend Architecture Tutor"
}}"""
    from ollama_client import ask_ollama_raw
    response = ask_ollama_raw(prompt, expect_json=True)
    try:
        return jsonify(json.loads(response))
    except Exception as e:
        print("JSON parse error from ollama:", e, response)
        return jsonify({"error": "Failed to generate system prompt. Please try again."}), 500


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


@app.route("/admin/update_user_role", methods=["POST"])
def admin_update_user_role():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    target_user_id = request.form.get("user_id")
    is_admin = 1 if request.form.get("is_admin") == "1" else 0
    
    # Prevent removing own admin rights
    if str(target_user_id) == str(user["id"]) and is_admin == 0:
        return redirect(url_for("admin", error="You cannot remove your own admin rights."))
        
    database.update_user_role(target_user_id, is_admin)
    return redirect(url_for("admin", message="User role updated successfully."))


@app.route("/admin/update_user_tutors", methods=["POST"])
def admin_update_user_tutors():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    target_user_id = request.form.get("user_id")
    # request.form.getlist handles multiple checkboxes with the same name="tutor_ids"
    tutor_ids = request.form.getlist("tutor_ids")
    
    database.update_user_assignments(target_user_id, tutor_ids)
    return redirect(url_for("admin", message="User tutors updated successfully."))


@app.route("/admin/toggle_block_user/<int:target_user_id>", methods=["POST"])
def admin_toggle_block_user(target_user_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    if str(target_user_id) == str(user["id"]):
        return redirect(url_for("admin", error="You cannot block yourself."))
        
    database.toggle_block_user(target_user_id)
    return redirect(url_for("admin", message="User block status updated."))


@app.route("/admin/delete_user/<int:target_user_id>", methods=["POST"])
def admin_delete_user(target_user_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    if str(target_user_id) == str(user["id"]):
        return redirect(url_for("admin", error="You cannot delete your own account."))
        
    database.delete_user(target_user_id)
    return redirect(url_for("admin", message="User account successfully deleted."))


@app.route("/admin/edit_user/<int:target_user_id>", methods=["POST"])
def admin_edit_user(target_user_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    username = request.form.get("username", "").strip()
    display_name = request.form.get("display_name", "").strip()
    new_password = request.form.get("new_password", "").strip()
    
    if not username or not display_name:
        return redirect(url_for("admin", error="Username and Display Name cannot be empty."))
        
    pw_hash = generate_password_hash(new_password) if new_password else None
    
    success = database.update_user_details(target_user_id, username, display_name, pw_hash)
    if not success:
        return redirect(url_for("admin", error="Username already exists."))
        
    return redirect(url_for("admin", message="User details updated successfully."))


@app.route("/admin/edit_tutor/<int:target_tutor_id>", methods=["POST"])
def admin_edit_tutor(target_tutor_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    name = request.form.get("name", "").strip()
    system_prompt = request.form.get("system_prompt", "").strip()
    configuration = request.form.get("configuration", "").strip()
    
    if not name or not system_prompt:
        return redirect(url_for("admin", tab="tutors", error="Tutor Name and System Prompt cannot be empty."))
        
    database.update_tutor_details(target_tutor_id, name, system_prompt, configuration=configuration if configuration else None)
    return redirect(url_for("admin", tab="tutors", message="Tutor details updated successfully."))


@app.route("/admin/update_tutor_model", methods=["POST"])
def admin_update_tutor_model():
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    tutor_id = request.form.get("tutor_id")
    model = request.form.get("model")
    
    if tutor_id and model:
        database.update_tutor_model(tutor_id, model)
        return redirect(url_for("admin", tab="tutors", message="Tutor model updated successfully."))
    return redirect(url_for("admin", tab="tutors", error="Invalid model update request."))


@app.route("/admin/toggle_block_tutor/<int:target_tutor_id>", methods=["POST"])
def admin_toggle_block_tutor(target_tutor_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    database.toggle_block_tutor(target_tutor_id)
    return redirect(url_for("admin", tab="tutors", message="Tutor block status updated."))


@app.route("/admin/delete_tutor/<int:target_tutor_id>", methods=["POST"])
def admin_delete_tutor(target_tutor_id):
    if "user_id" not in session: return redirect(url_for("login"))
    user = database.get_user_by_id(session["user_id"])
    if not user or not user["is_admin"]: return "Unauthorized", 403
    
    database.delete_tutor(target_tutor_id)
    return redirect(url_for("admin", tab="tutors", message="Tutor successfully deleted."))


if __name__ == "__main__":
    # Prevent Windows from going to sleep while the Flask app is running
    # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001) = 0x80000001
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        print("System sleep prevention enabled. (Display can still turn off naturally)")
    except Exception as e:
        print(f"Notice: Could not set sleep prevention: {e}")

    # Host "0.0.0.0" allows the app to be accessible on the local network (LAN)
    app.run(host="0.0.0.0", port=5000, debug=True)
