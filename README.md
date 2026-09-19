# World War Telegram Bot — Railway Edition

نسخه‌ی آماده‌ی استقرار ربات جنگ جهانی روی GitHub + Railway.

## ساختار

- `main.py` — کد اصلی ربات
- `requirements.txt` — وابستگی Python
- `.gitignore` — جلوگیری از آپلود دیتابیس و Secretها
- `.env.example` — نمونه‌ی متغیرهای محیطی

## اجرای محلی

```bash
pip install -r requirements.txt
python main.py
```

در اجرای محلی می‌توانید `BOT_TOKEN` و سایر تنظیمات را به‌صورت Environment Variable تعریف کنید.

## استقرار روی Railway

1. Repository را در GitHub بسازید و این فایل‌ها را Push کنید.
2. در Railway یک Project بسازید و Repository را به‌عنوان Source انتخاب کنید.
3. یک Volume به همان Service اضافه کنید.
4. Mount Path را دقیقاً روی این مقدار قرار دهید:

```text
/app/data
```

5. در Variables این موارد را تنظیم کنید:

```text
BOT_TOKEN=توکن جدید ربات
ADMIN_IDS=7443146366,8524573838,5856916684
NEWS_CHANNEL=@worldwarrr74
DB_PATH=/app/data/warbot.db
TELEGRAM_PROVIDER_TOKEN=
TELEGRAM_CURRENCY=IRR
PAYMENT_CARD_NUMBER=
PAYMENT_CARD_HOLDER=
```

6. Deploy کنید.

Railway با وجود `main.py` می‌تواند برنامه را با Python اجرا کند. اگر لازم بود Start Command را دستی تنظیم کنید:

```text
python main.py
```

## ماندگاری اطلاعات بازیکنان

دیتابیس بازی در:

```text
/app/data/warbot.db
```

ذخیره می‌شود.

چون `/app/data` روی Railway Volume قرار دارد، اطلاعات SQLite با Restart و Redeploy سرویس باقی می‌ماند.

**فایل `warbot.db` را داخل GitHub قرار ندهید.**

## امنیت

توکن ربات و اطلاعات پرداخت نباید داخل GitHub قرار بگیرند.

اگر توکن قبلی ربات قبلاً در یک فایل عمومی یا Repository قرار گرفته، قبل از Deploy یک توکن جدید از BotFather بگیرید و فقط آن را در Railway Variables قرار دهید.
