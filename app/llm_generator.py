import os
import base64
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()
AI_PIPE_API_KEY = os.getenv("AI_PIPE_API_KEY")

TMP_DIR = Path("/tmp/llm_attachments")
TMP_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Attachment utilities
# -----------------------------
def decode_attachments(attachments):
    saved = []
    for att in attachments or []:
        name = att.get("name") or "attachment"
        url = att.get("url", "")
        if not url.startswith("data:"):
            continue
        try:
            header, b64data = url.split(",", 1)
            mime = header.split(";")[0].replace("data:", "")
            data = base64.b64decode(b64data)
            path = TMP_DIR / name
            with open(path, "wb") as f:
                f.write(data)
            saved.append({"name": name, "path": str(path), "mime": mime, "size": len(data)})
        except Exception as e:
            print(f"⚠ Failed to decode attachment {name}: {e}")
    return saved

def summarize_attachment_meta(saved):
    summaries = []
    for s in saved:
        nm = s["name"]
        p = s["path"]
        mime = s.get("mime", "")
        try:
            if mime.startswith("text") or nm.endswith((".md", ".txt", ".json", ".csv")):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    preview = f.read(1000).replace("\n", "\\n")[:1000]
                summaries.append(f"- {nm} ({mime}): preview: {preview}")
            else:
                summaries.append(f"- {nm} ({mime}): {s['size']} bytes")
        except Exception as e:
            summaries.append(f"- {nm} ({mime}): (could not read preview: {e})")
    return "\\n".join(summaries)

# -----------------------------
# Helper functions
# -----------------------------
def _strip_code_block(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            return parts[1].strip()
    return text.strip()

def generate_readme_fallback(brief: str, checks=None, attachments_meta=None, round_num=1):
    checks_text = "\\n".join(checks or [])
    att_text = attachments_meta or ""
    return f"""# Auto-generated README (Round {round_num})

**Project brief:** {brief}

**Attachments:**
{att_text}

**Checks to meet:**
{checks_text}

## Setup
1. Open `index.html` in a browser.
2. No build steps required.

## Notes
This README was generated as a fallback (AI Pipe did not return an explicit README).
"""

# -----------------------------
# Main generation function
# -----------------------------
def generate_app_code(brief: str, attachments=None, checks=None, round_num=1, prev_readme=None):
    saved = decode_attachments(attachments or [])
    attachments_meta = summarize_attachment_meta(saved)

    context_note = ""
    if round_num == 2 and prev_readme:
        context_note = f"\n### Previous README.md:\n{prev_readme}\n\nRevise and enhance this project according to the new brief below.\n"

    prompt = f"""
You are a professional web developer assistant.

### Round
{round_num}

### Task
{brief}

{context_note}

### Attachments (if any)
{attachments_meta}

### Evaluation checks
{checks or []}

### Output format rules:
1. Produce a complete web app (HTML/JS/CSS inline if needed) satisfying the brief.
2. Output must contain **two parts only**:
   - index.html (main code)
   - README.md (starts after a line containing exactly: ---README.md---)
3. README.md must include:
   - Overview
   - Setup
   - Usage
   - If Round 2, describe improvements made from previous version.
4. Do not include any commentary outside code or README.
"""

    # -----------------------------
    # AI Pipe API call
    # -----------------------------
    try:
        AI_PIPE_ENDPOINT = "https://aipipe.org/openai/v1/responses"

        resp = requests.post(
            AI_PIPE_ENDPOINT,
            headers={"Authorization": f"Bearer {AI_PIPE_API_KEY}"},
            json={"model": "gpt-5", "input": prompt},
            timeout=60
        )
        resp.raise_for_status()
        resp_json = resp.json()
        print("✅ Full AI Pipe response received.")

        # Extract generated HTML + README
        text = ""
        if resp_json.get("output") and len(resp_json["output"]) > 1:
            message_block = resp_json["output"][1]  # second block usually contains assistant message
            if "content" in message_block and len(message_block["content"]) > 0:
                text = message_block["content"][0].get("text", "")

        if not text:
            print("⚠ AI Pipe returned empty output, using fallback.")
            raise ValueError("Empty AI Pipe output")

    except Exception as e:
        print(f"⚠ AI Pipe API failed, using fallback HTML: {e}")
        text = f"""
<html>
  <head><title>Fallback App</title></head>
  <body>
    <h1>Hello (fallback)</h1>
    <p>This app was generated as a fallback because AI Pipe failed. Brief: {brief}</p>
  </body>
</html>

---README.md---
{generate_readme_fallback(brief, checks, attachments_meta, round_num)}
"""

    # -----------------------------
    # Split code and README
    # -----------------------------
    if "---README.md---" in text:
        code_part, readme_part = text.split("---README.md---", 1)
        code_part = _strip_code_block(code_part)
        readme_part = _strip_code_block(readme_part)
    else:
        code_part = _strip_code_block(text)
        readme_part = generate_readme_fallback(brief, checks, attachments_meta, round_num)

    # -----------------------------
    # Optional: save generated files locally
    # -----------------------------
    output_dir = Path("./generated_app")
    output_dir.mkdir(exist_ok=True)
    with open(output_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(code_part)
    with open(output_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_part)
    print(f"✅ Generated files saved to {output_dir.resolve()}")

    return {"files": {"index.html": code_part, "README.md": readme_part}, "attachments": saved}
