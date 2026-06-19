import os
import re
import time
import shutil
from typing import Optional, Dict, List, Tuple

import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

# ==================== تنظیمات ====================
TOKEN = os.environ.get("TOKEN")
MAX_PER_USER = 5
TIME_WINDOW = 3600
# =================================================

user_requests: Dict[int, List[float]] = {}


def is_instagram_url(url: str) -> bool:
    return bool(re.search(r"instagram\.com/(p|reel|tv)/", url))


def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    now = time.time()
    if user_id not in user_requests:
        user_requests[user_id] = []

    user_requests[user_id] = [
        t for t in user_requests[user_id]
        if now - t < TIME_WINDOW
    ]

    remaining = MAX_PER_USER - len(user_requests[user_id])

    if remaining <= 0:
        wait = int(TIME_WINDOW - (now - user_requests[user_id][0]))
        return False, wait

    user_requests[user_id].append(now)
    return True, remaining - 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! به بات دانلود اینستاگرام خوش اومدی!\n\n"
        "📌 فقط لینک پست یا ریلز اینستاگرام رو بفرست.\n"
        "⚠️ محدودیت: {} درخواست در ساعت".format(MAX_PER_USER)
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()

    if not is_instagram_url(url):
        await update.message.reply_text(
            "❌ لینک اینستاگرام معتبر نیست!\n\nمثال: https://www.instagram.com/reel/abc123/"
        )
        return

    allowed, info = check_rate_limit(user_id)
    if not allowed:
        minutes = info // 60
        await update.message.reply_text(
            "⛔ به محدودیت رسیدی!\n\n⏳ {} دقیقه دیگه دوباره امتحان کن.".format(
                minutes)
        )
        return

    msg = await update.message.reply_text("⏳ در حال دانلود... لطفاً صبر کن")

    download_dir = "downloads/{}".format(user_id)
    os.makedirs(download_dir, exist_ok=True)

    try:
        ydl_opts = {
            "outtmpl": "{}/video.%(ext)s".format(download_dir),
            "format": "mp4/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "cookiefile": "instagram.com_cookies.txt",
        }

        ydl_opts["format"] = "mp4/best[ext=mp4]/best"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            caption = info_dict.get("description") or "بدون کپشن"
            video_url = info_dict.get("url")

        video_file = None
        for f in os.listdir(download_dir):
            if f.startswith("video") and (f.endswith(".mp4") or f.endswith(".webm")):
                video_file = os.path.join(download_dir, f)
                break

        if video_file:
            file_size = os.path.getsize(video_file) / (1024 * 1024)

            if file_size > 50:
                await msg.edit_text(
                    "❌ فایل خیلی بزرگه ({:.1f}MB)!\nتلگرام فقط تا ۵۰MB قبول میکنه.".format(
                        file_size)
                )
            else:
                await msg.edit_text("📤 در حال آپلود...")
                with open(video_file, "rb") as v:
                    await update.message.reply_video(
                        video=video_url,
                        caption="📝 کپشن:\n\n{}".format(caption[:900]),
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=300,
                    )
                await msg.delete()
        else:
            await msg.edit_text("❌ فایل ویدیو پیدا نشد!")

    except Exception as e:
        await msg.edit_text("❌ خطا:\n{}".format(str(e)))

    finally:
        if os.path.exists(download_dir):
            shutil.rmtree(download_dir)


def main():
    os.makedirs("downloads", exist_ok=True)
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .read_timeout(300)
        .write_timeout(300)
        .connect_timeout(300)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات شروع به کار کرد!")
    app.run_polling()


if __name__ == "__main__":
    main()
