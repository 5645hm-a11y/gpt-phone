"""
GPT Phone Line - ימות המשיח
-----------------------------
Flow:
  1. מתקשר מתקשר למספר ימות המשיח
  2. ימות המשיח שולחים GET לשרת שלנו (/yemot/call)
  3. השרת עונה עם פקודת read_text (TTS עברי מובנה) + record_message
  4. המתקשר מדבר והשאלה נשמרת כקובץ אודיו
  5. ימות המשיח שולחים GET לשרת עם קישור לקובץ (/yemot/answer)
  6. השרת מוריד את הקובץ, מתמלל עם Whisper (OpenAI)
  7. שולח ל-GPT ומקבל תשובה
  8. מחזיר read_text עם תשובת GPT → ימות המשיח מדברים
"""

import os
import logging
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, request, Response
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

REQUEST_LOG_PATH = Path("runtime_requests.log")

app = Flask(__name__)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _log_request_line(message: str) -> None:
    """Writes a compact request trace file for external callback debugging."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with REQUEST_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


@app.before_request
def trace_incoming_request():
    args_preview = dict(request.args)
    _log_request_line(f"{request.method} {request.path} args={args_preview}")

# שמירת היסטוריית שיחה לפי מספר מתקשר
conversations: dict[str, list[dict]] = {}

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "אתה עוזר AI מועיל בשיחת טלפון. "
    "ענה תמיד בעברית, בצורה קצרה וברורה (עד 3 משפטים). "
    "אל תשתמש בסימנים מיוחדים, תבליטים, מספור או כותרות.",
)

GREETING_TEXT = os.getenv(
    "GREETING_TEXT",
    "שלום! אני עוזר בינה מלאכותית. לאחר הצפצוף, אמור את שאלתך.",
)

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")
YEMOT_INPUT_MODE = os.getenv("YEMOT_INPUT_MODE", "voice").strip().lower()
YEMOT_VOICE_SILENCE_SECONDS = os.getenv("YEMOT_VOICE_SILENCE_SECONDS", "6").strip()
YEMOT_VOICE_MAX_SECONDS = os.getenv("YEMOT_VOICE_MAX_SECONDS", "30").strip()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sanitize_tts_text(text: str) -> str:
    clean_text = " ".join((text or "").replace(";", " ").replace(",", " ").replace("-", " ").replace(".", " ").split())
    return clean_text or "לא הצלחתי להבין"


def _yemot_response(body: str) -> Response:
    logger.info("Yemot response: %s", body)
    _log_request_line(f"RESPONSE: {body}")
    return Response(body, mimetype="text/plain; charset=utf-8")


def _yemot_read_response(prompt_text: str, variable_name: str = "QUESTION") -> Response:
    clean_text = _sanitize_tts_text(prompt_text)
    if YEMOT_INPUT_MODE == "record":
        body = f"read=t-{clean_text}={variable_name},,record"
    else:
        body = (
            f"read=t-{clean_text}={variable_name},,voice,,,,record,"
            f"{YEMOT_VOICE_SILENCE_SECONDS},{YEMOT_VOICE_MAX_SECONDS}"
        )
    return _yemot_response(body)


def _yemot_message_response(text: str) -> Response:
    clean_text = _sanitize_tts_text(text)
    body = f"id_list_message=t-{clean_text}"
    return _yemot_response(body)


def _looks_like_recording_reference(value: str) -> bool:
    """Detects when Yemot returns a file/path token instead of free text."""
    if not value:
        return False
    value = value.strip().lower()
    return value.endswith((".wav", ".mp3", ".ogg")) or "/" in value


def _init_conversation(phone: str) -> None:
    conversations[phone] = [{"role": "system", "content": SYSTEM_PROMPT}]


def _gpt_reply(phone: str, user_text: str) -> str:
    if phone not in conversations:
        _init_conversation(phone)

    conversations[phone].append({"role": "user", "content": user_text})

    completion = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=conversations[phone],
        max_tokens=300,
        temperature=0.7,
    )
    reply = completion.choices[0].message.content.strip()
    conversations[phone].append({"role": "assistant", "content": reply})
    return reply


def _transcribe_url(audio_url: str) -> str:
    """מוריד קובץ אודיו מ-URL ומתמלל עם Whisper."""
    tmp_path = "tmp_recording.mp3"
    try:
        urllib.request.urlretrieve(audio_url, tmp_path)
        with open(tmp_path, "rb") as f:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="he",
            )
        return transcript.text.strip()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@app.route("/yemot/call", methods=["GET", "POST"])
def yemot_call():
    """נקודת API ראשית: פתיחת שיחה וגם טיפול בהקלטה חוזרת."""
    phone = request.args.get("ApiPhone") or request.form.get("ApiPhone", "unknown")
    extension = request.args.get("ApiExtension") or request.form.get("ApiExtension", "")

    # hangup event – ימות מודיע על ניתוק
    hangup = request.args.get("hangup") or request.form.get("hangup")
    if hangup == "yes":
        logger.info("[%s] Call ended", phone)
        conversations.pop(phone, None)
        return Response("ok", mimetype="text/plain")

    question_text = (
        request.args.get("QUESTION")
        or request.form.get("QUESTION")
        or request.args.get("question")
        or request.form.get("question")
    )

    logger.info("[%s] Extension: %s, Question: %s", phone, extension, question_text)

    if question_text:
        decoded_question = urllib.parse.unquote_plus(question_text).strip()

        if YEMOT_INPUT_MODE == "record" and _looks_like_recording_reference(decoded_question):
            logger.info("[%s] Recording reference received: %s", phone, decoded_question)
            return _yemot_message_response(
                "ההקלטה התקבלה אבל התקבל רק שם קובץ ללא קישור הורדה"
            )

        if "אין מספיק יחידות" in decoded_question:
            if YEMOT_INPUT_MODE == "voice":
                return _yemot_message_response(
                    "אין מספיק יחידות לזיהוי דיבור בימות טענו יחידות והתקשרו שוב"
                )
            return _yemot_message_response(
                "מצב הקלטה פעיל אך נדרש חיבור קובץ הקלטה לשרת"
            )
        if decoded_question.lower() == "none":
            return _yemot_read_response("לא הצלחתי להבין אנא אמרו שוב את שאלתכם")

        try:
            reply = _gpt_reply(phone, decoded_question)
            logger.info("[%s] GPT: %s", phone, reply)
        except Exception as exc:
            logger.error("GPT error: %s", exc)
            err = str(exc).lower()
            if "insufficient_quota" in err or "429" in err:
                return _yemot_message_response("שירות הבינה מלאכותית לא זמין כרגע עקב מגבלת חשבון")
            return _yemot_read_response("אירעה שגיאה אנא נסו שוב")

        return _yemot_read_response(reply)

    # כניסה לשלוחה - תן greeting וקולט
    if extension:
        logger.info("[%s] Extension %s selected - sending read prompt", phone, extension)
        _init_conversation(phone)
        return _yemot_read_response(GREETING_TEXT)
    
    # תפריט ראשי - תן דרך לבחור שלוחה
    logger.info("[%s] Main menu", phone)
    _init_conversation(phone)
    return _yemot_read_response(GREETING_TEXT)


@app.route("/yemot/answer", methods=["GET", "POST"])
def yemot_answer():
    """
    ימות המשיח שולחים את קישור הקלטת המשתמש כאן.
    פרמטרים אפשריים: ApiPhone, file (URL לקובץ), record (שם קובץ)
    """
    phone = (
        request.args.get("ApiPhone")
        or request.form.get("ApiPhone", "unknown")
    )

    # ימות המשיח שולחים את הקלטה בפרמטר 'file' או 'record'
    audio_url = (
        request.args.get("file")
        or request.form.get("file")
        or request.args.get("record")
        or request.form.get("record")
    )

    logger.info("[%s] Answer received | audio_url=%s", phone, audio_url)

    if not audio_url:
        logger.warning("[%s] No audio URL received", phone)
        return _yemot_read_response("לא קלטתי אנא נסו שוב")

    # תמלול
    try:
        user_text = _transcribe_url(audio_url)
        logger.info("[%s] Transcribed: %s", phone, user_text)
    except Exception as exc:
        logger.error("Whisper error: %s", exc)
        return _yemot_read_response("אירעה שגיאה בתמלול אנא נסו שוב")

    if not user_text:
        return _yemot_read_response("לא הצלחתי להבין אנא דברו שוב")

    # GPT
    try:
        reply = _gpt_reply(phone, user_text)
        logger.info("[%s] GPT: %s", phone, reply)
    except Exception as exc:
        logger.error("GPT error: %s", exc)
        return _yemot_read_response("אירעה שגיאה אנא נסו שוב")

    return _yemot_read_response(reply)


@app.route("/yemot/hangup", methods=["GET", "POST"])
def yemot_hangup():
    """מנקה היסטוריה כשהמתקשר ניתק."""
    phone = request.args.get("ApiPhone") or request.form.get("ApiPhone", "")
    conversations.pop(phone, None)
    logger.info("Call ended: %s", phone)
    return Response("", status=204)


@app.route("/health")
def health():
    return {"status": "ok", "conversations_active": len(conversations)}


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    """הגנה חיצונית מפני שגיאות."""
    logger.error("Global error: %s", exc, exc_info=True)
    fallback = "id_list_message=t-אירעה שגיאה במערכת"
    return Response(fallback, mimetype="text/plain; charset=utf-8", status=200)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
