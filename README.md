# GPT Phone Line - ימות המשיח

פרויקט קו טלפוני מבוסס GPT בעברית.

המימוש הראשי כרגע הוא דרך ימות המשיח, עם API טקסטואלי בפורמט key=value.

## סטטוס נוכחי

- מסלול ראשי פעיל: app_yemot.py
- נתמך מצב voice (ברירת מחדל): זיהוי דיבור בצד ימות המשיח
- נתמך מצב record: קבלת הפניה להקלטה במקום טקסט
- ברירת מחדל לדיבור ימות: Osnat עם tts_rate=2 בקבצי ext.ini
- מסלול Twilio עדיין קיים בקובץ app.py, אבל אינו המסלול הראשי בפרויקט

## איך הזרימה עובדת (ימות)

1. שיחה נכנסת לשלוחה שהוגדרה כ-api בימות המשיח
2. ימות פונה לשרת בנתיב /yemot/call
3. השרת מחזיר read= עם prompt למתקשר + בקשת קלט
4. המתקשר מדבר
5. הטקסט נשלח בפרמטר QUESTION
6. השרת שולח את הטקסט ל-OpenAI ומחזיר תשובה ב-read=
7. ימות מקריא את התשובה

## דרישות

- Python 3.10+
- מפתח OpenAI תקין
- שלוחה בימות המשיח מסוג API
- טאנל ציבורי לשרת המקומי (Cloudflare Tunnel או ngrok)

## התקנה מהירה (Windows)

1. התקנת תלויות:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. יצירת קובץ הגדרות:

```powershell
Copy-Item .env.example .env
```

3. עריכת .env עם הערכים שלך:

```env
OPENAI_API_KEY=sk-...
BASE_URL=https://your-public-url
GPT_MODEL=gpt-4o-mini
GREETING_TEXT=שלום! אני עוזר בינה מלאכותית. לאחר הצפצוף, אמור את שאלתך.
PORT=5000
FLASK_DEBUG=false

# voice או record
YEMOT_INPUT_MODE=voice

# רלוונטי רק למצב voice
YEMOT_VOICE_SILENCE_SECONDS=6
YEMOT_VOICE_MAX_SECONDS=30
```

## הרצת השרת

```powershell
.\.venv\Scripts\python.exe app_yemot.py
```

בדיקת בריאות:

```powershell
Invoke-WebRequest http://localhost:5000/health -UseBasicParsing
```

## חשיפה ציבורית (Tunnel)

### אפשרות 1: Cloudflare Tunnel

```powershell
.\.tools\cloudflared\cloudflared.exe tunnel --url http://localhost:5000
```

### אפשרות 2: ngrok

```powershell
.\.tools\ngrok\ngrok.exe http 5000
```

את כתובת ה-https שקיבלת מעדכנים ב-BASE_URL וב-api_link של ימות.

## הגדרת ימות המשיח

בקבצי ההעלאה, נדרש:

```ini
type=api
api_link=https://YOUR_TUNNEL_URL/yemot/call
voice=Osnat
tts_voice=Osnat
tts_rate=2
```

הקבצים הרלוונטיים בפרויקט:

- yemot_upload/ext.ini
- yemot_upload/1/ext.ini
- yemot_upload/7/ext.ini

ארטיפקטים מוכנים להעלאה:

- ext_for_extension_1.zip
- yemot_upload_v2.zip

## נקודות קצה חשובות

- /yemot/call: נקודת ה-API הראשית לשיחה
- /yemot/answer: נתיב לקליטת הקלטה (אם עובדים במודל הקלטות)
- /yemot/hangup: ניקוי session/היסטוריה בסיום שיחה
- /health: בדיקת תקינות שרת

## משתני סביבה נתמכים (ימות)

- OPENAI_API_KEY
- BASE_URL
- GPT_MODEL
- GREETING_TEXT
- SYSTEM_PROMPT
- PORT
- FLASK_DEBUG
- YEMOT_INPUT_MODE
- YEMOT_VOICE_SILENCE_SECONDS
- YEMOT_VOICE_MAX_SECONDS

## תקלות נפוצות

1. ההודעה: "אין מספיק יחידות לשימוש בזיהוי דיבור"
    הפתרון: לטעון יחידות זיהוי דיבור בימות או לעבור זמנית ל-record.

2. השרת מחזיר שגיאה בפתיחה
    בדוק OPENAI_API_KEY, ושאין תהליך Python ישן שמחזיק פורט 5000.

3. ימות לא מגיע לשרת
    בדוק שהטאנל פעיל ושה-api_link מצביע בדיוק ל-/yemot/call.

4. תשובות GPT לא חוזרות
    ייתכן מגבלת quota בחשבון OpenAI (429 / insufficient_quota).

## מבנה פרויקט

```text
.
├── app_yemot.py
├── app.py
├── requirements.txt
├── .env.example
├── yemot_upload/
├── ext_for_extension_1.zip
└── yemot_upload_v2.zip
```

## אבטחה

- לא לשמור מפתחות אמיתיים ב-Git
- אם מפתח API נחשף, לבצע rotation מיידי דרך OpenAI
