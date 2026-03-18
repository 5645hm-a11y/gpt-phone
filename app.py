"""
GPT Phone Line - קו טלפוני GPT
-------------------------------
משתמשים מתקשרים, מדברים, ו-GPT עונה להם חזרה בטלפון.
Flow:
  1. הלקוח מתקשר
  2. Twilio מפעיל webhook ל-/voice
  3. Twilio מקשיב לדיבור ומתמלל (he-IL)
  4. /respond שולח לGPT ומקבל תשובה
  5. OpenAI TTS ממיר את התשובה לאודיו
  6. Twilio מנגן את האודיו ומחכה לשאלה הבאה
"""

import os
import uuid
import logging
from pathlib import Path

from flask import Flask, request, Response, send_file
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# שמירת היסטוריית שיחה לפי CallSid
conversations: dict[str, list[dict]] = {}

# תיקיית אודיו TTS
AUDIO_DIR = Path("static") / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ברירת מחדל לפרומפט המערכת
DEFAULT_SYSTEM_PROMPT = (
    "אתה עוזר AI מועיל בשיחת טלפון. "
    "ענה תמיד בעברית, בצורה קצרה וברורה (עד 3 משפטים), "
    "כיוון שהתשובה תושמע בטלפון. "
    "אל תשתמש בסימני מיוחדים, תבליטים, מספור, או כותרות."
)

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)
GREETING_TEXT = os.getenv("GREETING_TEXT", "שלום! אני עוזר AI. שאל אותי כל שאלה.")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")
TTS_VOICE = os.getenv("TTS_VOICE", "nova")
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "he-IL")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _base_url() -> str:
    """מחזיר את ה-BASE_URL מה-.env או מה-request."""
    return os.getenv("BASE_URL", request.url_root.rstrip("/"))


def _init_conversation(call_sid: str) -> None:
    conversations[call_sid] = [{"role": "system", "content": SYSTEM_PROMPT}]


def _gather_block(action: str) -> Gather:
    """מחזיר Gather מוגדר לעברית."""
    return Gather(
        input="speech",
        action=action,
        language=TTS_LANGUAGE,
        speech_timeout="auto",
        timeout=6,
    )


def _gpt_reply(call_sid: str, user_text: str) -> str:
    """שולח הודעה ל-GPT ומחזיר תשובה."""
    if call_sid not in conversations:
        _init_conversation(call_sid)

    conversations[call_sid].append({"role": "user", "content": user_text})

    completion = openai_client.chat.completions.create(
        model=GPT_MODEL,
        messages=conversations[call_sid],
        max_tokens=300,
        temperature=0.7,
    )
    reply = completion.choices[0].message.content.strip()
    conversations[call_sid].append({"role": "assistant", "content": reply})
    return reply


def _tts_url(text: str) -> str | None:
    """מייצר קובץ אודיו TTS ומחזיר URL ציבורי."""
    try:
        audio_id = uuid.uuid4().hex
        audio_path = AUDIO_DIR / f"{audio_id}.mp3"

        tts = openai_client.audio.speech.create(
            model="tts-1",
            voice=TTS_VOICE,
            input=text,
            response_format="mp3",
        )
        tts.stream_to_file(str(audio_path))

        return f"{_base_url()}/audio/{audio_id}"
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@app.route("/voice", methods=["POST"])
def voice():
    """ה-webhook הראשוני – מנגן ברכה ומתחיל להאזין."""
    call_sid = request.form.get("CallSid", "unknown")
    _init_conversation(call_sid)
    logger.info("Incoming call  [%s]", call_sid[:8])

    response = VoiceResponse()
    gather = _gather_block("/respond")

    # נסה TTS של OpenAI לברכה, אחרת Twilio TTS
    greeting_url = _tts_url(GREETING_TEXT)
    if greeting_url:
        gather.play(greeting_url)
    else:
        gather.say(GREETING_TEXT, voice="Polly.Ruti-Neural", language="he-IL")

    response.append(gather)
    response.redirect("/voice")   # אם לא הייתה קלט – התחל מחדש
    return Response(str(response), mimetype="text/xml")


@app.route("/respond", methods=["POST"])
def respond():
    """מקבל תמלול מ-Twilio, שולח ל-GPT, ומנגן תשובה."""
    call_sid = request.form.get("CallSid", "unknown")
    speech = request.form.get("SpeechResult", "").strip()
    response = VoiceResponse()

    if not speech:
        logger.info("[%s] No speech detected", call_sid[:8])
        gather = _gather_block("/respond")
        no_input_url = _tts_url("לא הצלחתי לשמוע. אנא חזור על שאלתך.")
        if no_input_url:
            gather.play(no_input_url)
        else:
            gather.say("לא הצלחתי לשמוע. אנא חזור על שאלתך.",
                       voice="Polly.Ruti-Neural", language="he-IL")
        response.append(gather)
        response.redirect("/voice")
        return Response(str(response), mimetype="text/xml")

    logger.info("[%s] User: %s", call_sid[:8], speech)

    try:
        reply = _gpt_reply(call_sid, speech)
        logger.info("[%s] GPT: %s", call_sid[:8], reply)
    except Exception as exc:
        logger.error("GPT error: %s", exc)
        reply = "מצטער, אירעה שגיאה. אנא נסה שוב."

    audio_url = _tts_url(reply)

    gather = _gather_block("/respond")
    if audio_url:
        gather.play(audio_url)
    else:
        gather.say(reply, voice="Polly.Ruti-Neural", language="he-IL")

    response.append(gather)
    response.redirect("/voice")
    return Response(str(response), mimetype="text/xml")


@app.route("/audio/<audio_id>")
def serve_audio(audio_id: str):
    """מגיש קבצי אודיו TTS ל-Twilio."""
    # מניעת path traversal
    if not audio_id.isalnum() or len(audio_id) != 32:
        return "Invalid ID", 400

    audio_path = AUDIO_DIR / f"{audio_id}.mp3"
    if not audio_path.exists():
        return "Not found", 404

    return send_file(str(audio_path), mimetype="audio/mpeg")


@app.route("/status", methods=["POST"])
def call_status():
    """מנקה היסטוריית שיחה כשהשיחה מסתיימת."""
    call_sid = request.form.get("CallSid", "")
    status = request.form.get("CallStatus", "")
    if status in ("completed", "failed", "busy", "no-answer", "canceled"):
        conversations.pop(call_sid, None)
        logger.info("Call ended [%s] status=%s", call_sid[:8], status)
    return Response("", status=204)


@app.route("/health")
def health():
    return {"status": "ok", "conversations_active": len(conversations)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
