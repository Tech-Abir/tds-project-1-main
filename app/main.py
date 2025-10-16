from fastapi import FastAPI, Request, BackgroundTasks
import os
import json
import base64
from dotenv import load_dotenv
from app.llm_generator import generate_app_code, decode_attachments
from app.github_utils import (
    create_repo,
    create_or_update_file,
    create_or_update_binary_file,
    enable_pages,
    generate_mit_license,
)
from app.notify import notify_evaluation_server

load_dotenv()

USER_SECRET = os.getenv("USER_SECRET")
USERNAME = os.getenv("GITHUB_USERNAME")
PROCESSED_PATH = "/tmp/processed_requests.json"

app = FastAPI()


# === Persistence for processed requests ===
def load_processed():
    if os.path.exists(PROCESSED_PATH):
        try:
            return json.load(open(PROCESSED_PATH))
        except json.JSONDecodeError:
            return {}
    return {}


def save_processed(data):
    json.dump(data, open(PROCESSED_PATH, "w"), indent=2)


# === Background task ===
def process_request(data):
    round_num = data.get("round", 1)
    task_id = data["task"]
    print(f"⚙ Starting background process for task {task_id} (round {round_num})")

    attachments = data.get("attachments", [])
    saved_attachments = decode_attachments(attachments)
    print("Attachments saved:", saved_attachments)

    # Step 1: Get or create repo BEFORE any round 2 logic
    try:
        repo = create_repo(task_id, description=f"Auto-generated app for task: {data['brief']}")
    except Exception as e:
        print(f"❌ Failed to create/get repo {task_id}: {e}")
        return

    # Optional: fetch previous README for round 2
    prev_readme = None
    if round_num == 2:
        try:
            readme_file = repo.get_contents("README.md")
            prev_readme = readme_file.decoded_content.decode("utf-8", errors="ignore")
            print("📖 Loaded previous README for round 2 context.")
        except Exception:
            prev_readme = None

    # Step 2: Generate app code using AI Pipe
    gen = generate_app_code(
        data["brief"],
        attachments=attachments,
        checks=data.get("checks", []),
        round_num=round_num,
        prev_readme=prev_readme
    )

    files = gen.get("files", {})
    saved_info = gen.get("attachments", [])

    # Step 3: Round-specific logic
    if round_num == 1:
        print("🏗 Round 1: Building fresh repo...")

        # Add attachments first
        for att in saved_info:
            try:
                with open(att["path"], "rb") as f:
                    content_bytes = f.read()
                # Save text or binary appropriately
                if att["mime"].startswith("text") or att["name"].endswith((".md", ".csv", ".json", ".txt")):
                    text = content_bytes.decode("utf-8", errors="ignore")
                    create_or_update_file(repo, f"attachments/{att['name']}", text, f"Add attachment {att['name']}")
                else:
                    create_or_update_binary_file(repo, f"attachments/{att['name']}", content_bytes, f"Add binary {att['name']}")
                    b64 = base64.b64encode(content_bytes).decode("utf-8")
                    create_or_update_file(repo, f"attachments/{att['name']}.b64", b64, f"Backup {att['name']}.b64")
            except Exception as e:
                print(f"⚠ Attachment commit failed ({att['name']}): {e}")

    else:
        print("🔁 Round 2: Revising existing repo...")

    # Step 4: Commit generated files
    for fname, content in files.items():
        try:
            create_or_update_file(repo, fname, content, f"Add/Update {fname} for round {round_num}")
        except Exception as e:
            print(f"⚠ Failed to commit {fname}: {e}")

    # Step 5: Add MIT license
    try:
        mit_text = generate_mit_license()
        create_or_update_file(repo, "LICENSE", mit_text, "Add MIT license")
    except Exception as e:
        print(f"⚠ Failed to add LICENSE: {e}")

    # Step 6: Enable GitHub Pages (round 1) or reuse
    pages_url = None
    try:
        if round_num == 1:
            pages_ok = enable_pages(task_id)
            pages_url = f"https://{USERNAME}.github.io/{task_id}/" if pages_ok else None
        else:
            pages_url = f"https://{USERNAME}.github.io/{task_id}/"
    except Exception as e:
        print(f"⚠ Failed to enable Pages: {e}")

    # Step 7: Get latest commit SHA
    try:
        commit_sha = repo.get_commits()[0].sha
    except Exception:
        commit_sha = None

    # Step 8: Notify evaluation server
    payload = {
        "email": data["email"],
        "task": data["task"],
        "round": round_num,
        "nonce": data["nonce"],
        "repo_url": repo.html_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
    }

    try:
        notify_evaluation_server(data.get("evaluation_url"), payload)
    except Exception as e:
        print(f"⚠ Failed to notify evaluation server: {e}")

    # Step 9: Save processed
    processed = load_processed()
    key = f"{data['email']}::{data['task']}::round{round_num}::nonce{data['nonce']}"
    processed[key] = payload
    save_processed(processed)

    print(f"✅ Finished round {round_num} for {task_id}")


@app.get("/", response_class=HTMLResponse)
def root():
    return """
    <html>
        <head>
            <title>Welcome</title>
        </head>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1>🚀 TDS Project Space is Running!</h1>
            <p>Use the API endpoint <code>/api-endpoint</code> to send round payloads.</p>
        </body>
    </html>
    """
    
# === Main endpoint ===
@app.post("/api-endpoint")
async def receive_request(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("📩 Received request:", data)

    # Step 0: Verify secret
    if data.get("secret") != USER_SECRET:
        print("❌ Invalid secret received.")
        return {"error": "Invalid secret"}

    # Step 1: Check for duplicates
    processed = load_processed()
    key = f"{data['email']}::{data['task']}::round{data['round']}::nonce{data['nonce']}"

    if key in processed:
        print(f"⚠ Duplicate request detected for {key}. Re-notifying only.")
        prev = processed[key]
        try:
            notify_evaluation_server(data.get("evaluation_url"), prev)
        except Exception as e:
            print(f"⚠ Failed to re-notify evaluation server: {e}")
        return {"status": "ok", "note": "duplicate handled & re-notified"}

    # Step 2: Schedule background task
    background_tasks.add_task(process_request, data)

    # Step 3: Immediate HTTP 200 acknowledgment
    return {"status": "accepted", "note": f"processing round {data['round']} started"}
