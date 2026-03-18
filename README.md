# קו טלפוני GPT 📞🤖

קו טלפון ישראלי שבו מתקשרים ושואלים שאלות את GPT והוא עונה בקול בחזרה.

> **גרסת ימות המשיח** – מספר ישראלי חינמי + TTS עברי מובנה. ראה `app_yemot.py`.

## איך זה עובד

```
מתקשר → Twilio → השרת שלך → GPT → TTS → Twilio → מתקשר
```

1. הלקוח מתקשר למספר הטלפון
2. Twilio מקשיב לדיבור ומתמלל אותו לטקסט (עברית)
3. הטקסט נשלח ל-GPT שמייצר תשובה
4. OpenAI TTS ממיר את התשובה לאודיו
5. Twilio מנגן את האודיו למתקשר
6. השיחה ממשיכה בצורה רציפה עם זיכרון

---

## דרישות מוקדמות

| שירות | מה צריך | קישור |
|-------|---------|-------|
| **OpenAI** | API Key (GPT + TTS) | [platform.openai.com](https://platform.openai.com) |
| **Twilio** | חשבון + מספר ישראלי (+972) | [twilio.com](https://www.twilio.com) |
| **Python** | גרסה 3.10 ומעלה | |
| **ngrok** | לפיתוח מקומי | [ngrok.com](https://ngrok.com/download) |

### גרסת ימות המשיח (חינם!)

| שירות | מה צריך | קישור |
|-------|---------|-------|
| **OpenAI** | API Key (GPT + Whisper) | [platform.openai.com](https://platform.openai.com) |
| **ימות המשיח** | הרשמה חינמית + תוסף | [yemot.co.il](https://yemot.co.il) |
| **Python** | גרסה 3.10 ומעלה | |
| **ngrok** | לפיתוח מקומי | [ngrok.com](https://ngrok.com/download) |


## התקנה

### 1. שכפל וסביבה

```bash
cd qo-telephoni-gpt
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
```

### 2. קובץ הגדרות

```bash
copy .env.example .env
```

ערוך את `.env` ומלא:

```env
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=ACxxx...
TWILIO_AUTH_TOKEN=xxx...
BASE_URL=https://xxxx.ngrok-free.app   # (ראה סעיף ngrok למטה)
```

### 3. הפעלת השרת

```bash
python app.py
```

השרת רץ על `http://localhost:5000`

---

## הגדרת ngrok (פיתוח מקומי)

Twilio צריך לפנות לשרת שלך דרך כתובת ציבורית. ngrok יוצר מנהרה:

```bash
ngrok http 5000
```

תקבל כתובת כמו: `https://abc123.ngrok-free.app`

עדכן בקובץ `.env`:
```env
BASE_URL=https://abc123.ngrok-free.app
```

---

## הגדרת Twilio

### רכישת מספר ישראלי

1. היכנס ל-[Twilio Console](https://console.twilio.com)
2. **Phone Numbers → Manage → Buy a number**
3. בחר מדינה: **Israel (IL)**
4. בחר מספר עם Voice capabilities
5. רכוש

### הגדרת Webhooks

1. לך ל-**Phone Numbers → Manage → Active numbers**
2. לחץ על המספר שרכשת
3. תחת **Voice Configuration**:

| שדה | ערך |
|-----|-----|
| **A call comes in** | `Webhook` → `https://YOUR_URL/voice` → `HTTP POST` |
| **Call status changes** | `https://YOUR_URL/status` → `HTTP POST` |

---

## בדיקה

- בדוק שהשרת רצ: `http://localhost:5000/health`
- התקשר למספר Twilio
- שאל שאלה בעברית
- GPT יענה לך בקול!

---

## הגדרות אופציונליות

ניתן לשנות בקובץ `.env`:

```env
# מודל GPT
GPT_MODEL=gpt-4o          # יותר חכם (יקר יותר)
GPT_MODEL=gpt-4o-mini     # מהיר וזול (ברירת מחדל)

# קול TTS
TTS_VOICE=nova            # נשמע טוב לעברית
TTS_VOICE=shimmer         # קול נשי אחר
TTS_VOICE=onyx            # קול גברי

# ברכה מותאמת אישית
GREETING_TEXT=שלום! אתה מחובר לתמיכה של חברת XYZ.

# פרומפט מערכת
SYSTEM_PROMPT=אתה נציג שירות לקוחות של חברת XYZ. ענה בעברית בלבד.
```

---

## פריסה לפרודקשן

### Railway (קל ומהיר)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

קבל את ה-URL, עדכן `BASE_URL` ב-Railway environment variables,  
ועדכן את ה-webhook ב-Twilio.

### Render / Heroku

1. העלה ל-GitHub
2. חבר לשירות (Render/Heroku)
3. הגדר environment variables
4. עדכן BASE_URL ו-Twilio webhook

---

## עלויות משוערות

| שירות | עלות משוערת |
|-------|-------------|
| OpenAI GPT-4o-mini | ~$0.002 לשיחה |
| OpenAI TTS | ~$0.015 לכל 1,000 תווים |
| Twilio מספר ישראלי | ~$1-3 לחודש |
| Twilio דקת שיחה | ~$0.02-0.05 לדקה |

---

## מבנה הפרויקט

```
├── app.py              # השרת הראשי
├── requirements.txt    # חבילות Python
├── .env.example        # תבנית הגדרות
├── .gitignore
└── static/
    └── audio/          # קבצי TTS זמניים (נוצר אוטומטית)
```
