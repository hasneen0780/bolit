import telebot
import requests
import time
import json
import os
import threading
import queue
import yt_dlp
from telebot.types import Message
import urllib.request
from PIL import Image
import re
import subprocess

BOT_TOKEN = "6336327844:AAHtjTfWaFP8XiqxRfnCDoDiP2YfCUTGSKc"
bot = telebot.TeleBot(BOT_TOKEN)

USER_DATA_FILE = "user_cookies.json"
USER_SETTINGS_FILE = "user_settings.json"
TEMP_DIR = "temp_media"
LINKS_FILE = "links.txt"

for directory in [TEMP_DIR, "downloads", "user_images", "cookies"]:
    if not os.path.exists(directory):
        os.makedirs(directory)

post_queue = queue.Queue()
pending_photos = {}

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_user_settings():
    if os.path.exists(USER_SETTINGS_FILE):
        with open(USER_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_settings(settings):
    with open(USER_SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

def get_user_session(user_id):
    """يجلب الـ sessionid المحفوظ من أمر /se"""
    user_data = load_user_data()
    user_id_str = str(user_id)
    if user_id_str in user_data and user_data[user_id_str].get("sessionid"):
        return user_data[user_id_str]["sessionid"]
    return None

def get_user_cookies(user_id):
    """يبني كوكيز للنشر على إنستغرام من sessionid"""
    session_id = get_user_session(user_id)
    if session_id:
        return f"sessionid={session_id};"
    return ""

def get_user_caption(user_id):
    """يجلب نص التوقيع المحفوظ من أمر /caption"""
    settings = load_user_settings()
    user_id_str = str(user_id)
    if user_id_str in settings and "caption" in settings[user_id_str]:
        return settings[user_id_str]["caption"]
    return ""

def get_user_image(user_id):
    """يجلب الصورة المصغرة المحفوظة"""
    settings = load_user_settings()
    user_id_str = str(user_id)
    if user_id_str in settings and "image_path" in settings[user_id_str]:
        path = settings[user_id_str]["image_path"]
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    return None

def create_netscape_cookie_file(user_id):
    """يبني ملف كوكيز بصيغة Netscape من الـ sessionid المحفوظ"""
    session_id = get_user_session(user_id)
    if not session_id:
        return None

    cookie_path = os.path.join("cookies", f"{user_id}.txt")

    lines = [
        "# Netscape HTTP Cookie File",
        "# This file was generated automatically by the bot",
        "",
        f".instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\t{session_id}",
        f".instagram.com\tTRUE\t/\tTRUE\t0\tcsrftoken\t1hkh0nMRFaUw6o2bf16kzL",
        f".instagram.com\tTRUE\t/\tTRUE\t0\tig_did\t1F5A2D3C-4B6E-4A9E-9D6E-5F8A2B3C4D5E",
        f".instagram.com\tTRUE\t/\tTRUE\t0\tmid\tYxXxXxXxXxXxXxXxXxXxXxXxXxXx",
        f".instagram.com\tTRUE\t/\tTRUE\t0\tds_user_id\t0",
    ]

    try:
        with open(cookie_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        return cookie_path
    except Exception as e:
        print(f"❌ خطأ في إنشاء ملف الكوكيز: {e}")
        return None

def download_media(url, user_id):
    try:
        temp_dir = os.path.join(TEMP_DIR, str(user_id))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        cookie_file = create_netscape_cookie_file(user_id)

        ydl_opts = {
            'format': 'best[ext=mp4]/best[height<=1080]/best',
            'outtmpl': os.path.join(temp_dir, 'media_%(id)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'verbose': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extract_flat': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 30,
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }

        if cookie_file and os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
            print(f"✅ استخدام كوكيز المستخدم: {user_id}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            base_path = os.path.splitext(file_path)[0]
            for ext in ['.mp4', '.webm', '.mkv', '.mov', '.m4a', '.mp3']:
                test_path = base_path + ext
                if os.path.exists(test_path):
                    return test_path

            if os.path.exists(file_path):
                return file_path

            print(f"❌ الملف غير موجود بعد التحميل: {file_path}")
            return None

    except yt_dlp.utils.DownloadError as e:
        print(f"❌ DownloadError: {e}")
        return None
    except Exception as e:
        print(f"❌ Download error: {type(e).__name__}: {e}")
        return None

def convert_image_to_video(image_path, duration=10):
    try:
        output_path = os.path.join(TEMP_DIR, f"reel_{int(time.time())}.mp4")

        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', image_path,
            '-c:v', 'libx264',
            '-t', str(duration),
            '-pix_fmt', 'yuv420p',
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2',
            '-r', '24',
            output_path
        ]

        subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(output_path):
            return output_path
        return None

    except Exception as e:
        print(f"Image conversion error: {e}")
        return None

def get_video_duration(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 10.0

def trim_last_seconds(file_path, seconds_to_cut=2):
    try:
        if not os.path.exists(file_path):
            return None

        total_duration = get_video_duration(file_path)
        if total_duration <= seconds_to_cut + 0.5:
            print("الفيديو قصير جدًا، لن يتم القص")
            return file_path

        new_duration = total_duration - seconds_to_cut
        base, ext = os.path.splitext(file_path)
        output_path = f"{base}_trimmed{ext}"

        cmd = [
            'ffmpeg', '-y',
            '-i', file_path,
            '-t', str(new_duration),
            '-c', 'copy',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            cmd = [
                'ffmpeg', '-y',
                '-i', file_path,
                '-t', str(new_duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',
                output_path
            ]
            subprocess.run(cmd, capture_output=True, text=True)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            try:
                os.remove(file_path)
            except:
                pass
            return output_path

        return None

    except Exception as e:
        print(f"Trim error: {e}")
        return None

def post_to_instagram(video_data, caption, user_id, duration_ms):
    try:
        upload_id = str(int(time.time() * 1000))
        cookies_str = get_user_cookies(user_id)

        if not cookies_str:
            return False, "No session set"

        image_data = get_user_image(user_id)

        url_video = f"https://i.instagram.com/rupload_igvideo/fb_uploader_{upload_id}"
        headers_video = {
            'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            'Content-Type': "application/octet-stream",
            'x-instagram-rupload-params': json.dumps({
                "media_type": 2,
                "upload_id": upload_id,
                "is_clips_video": True
            }),
            'x-entity-length': str(len(video_data)),
            'x-entity-name': f"fb_uploader_{upload_id}",
            'offset': "0",
            'Cookie': cookies_str,
        }

        resp_video = requests.post(url_video, data=video_data, headers=headers_video)
        if resp_video.status_code != 200:
            return False, "Video upload failed"

        if image_data:
            url_image = f"https://i.instagram.com/rupload_igphoto/fb_uploader_{upload_id}"
            headers_image = {
                'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                'content-type': "image/jpeg",
                'x-instagram-rupload-params': json.dumps({
                    "media_type": 1,
                    "upload_id": upload_id,
                    "is_clips_video": True
                }),
                'x-entity-length': str(len(image_data)),
                'x-entity-type': "image/jpeg",
                'x-entity-name': f"fb_uploader_{upload_id}",
                'offset': "0",
                'Cookie': cookies_str,
            }
            requests.post(url_image, data=image_data, headers=headers_image)

        time.sleep(5)

        url_publish = "https://www.instagram.com/api/v1/media/configure_to_clips/"
        payload_publish = {
            'upload_id': upload_id,
            'caption': caption,
            'source_type': 'library',
            'media_type': '2',
            'clips_share_preview_to_feed': '1',
            'duration': str(duration_ms / 1000)
        }
        headers_publish = {
            'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            'x-ig-app-id': "936619743392459",
            'x-csrftoken': "1hkh0nMRFaUw6o2bf16kzL",
            'x-requested-with': "XMLHttpRequest",
            'Content-Type': "application/x-www-form-urlencoded; charset=UTF-8",
            'Cookie': cookies_str,
        }

        for attempt in range(15):
            resp_publish = requests.post(url_publish, data=payload_publish, headers=headers_publish)
            result = resp_publish.json()

            if result.get('status') == 'ok' and 'media' in result:
                code = result['media'].get('code')
                link = f"https://www.instagram.com/reel/{code}/"
                return True, link
            elif 'Transcode not finished yet' in str(result):
                time.sleep(3)
            else:
                time.sleep(1)

        return False, "Timeout"

    except Exception as e:
        return False, str(e)

def process_queue():
    while True:
        task = post_queue.get()
        if task is None:
            break

        media_path = task['media_path']
        caption = task['caption']
        user_id = task['user_id']

        with open(media_path, "rb") as f:
            video_data = f.read()

        duration = get_video_duration(media_path)
        duration_ms = int(duration * 1000)

        success, result = post_to_instagram(video_data, caption, user_id, duration_ms)

        if success:
            bot.send_message(user_id, f"تم النشر: {result}")
        else:
            bot.send_message(user_id, f"فشل النشر: {result}")

        try:
            os.remove(media_path)
        except:
            pass

        post_queue.task_done()

threading.Thread(target=process_queue, daemon=True).start()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, """بوت نشر انستغرام

الأوامر:
/se [كود_الجلسة] - تعيين جلسة انستغرام
/caption [النص] - تعيين نص التوقيع
/photo - رفع صورة مصغرة
/links - عرض الروابط المخزنة
/session - عرض جلستك
/show_caption - عرض توقيعك""")

@bot.message_handler(commands=['se'])
def set_session(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "الاستخدام: /se كود_الجلسة")
        return

    session_value = parts[1].strip()

    if len(session_value) < 10:
        bot.reply_to(message, "كود الجلسة غير صحيح")
        return

    user_data = load_user_data()
    user_data[str(message.from_user.id)] = {"sessionid": session_value}
    save_user_data(user_data)

    cookie_file = create_netscape_cookie_file(message.from_user.id)

    bot.reply_to(message, "✅ تم حفظ الجلسة وإنشاء ملف الكوكيز تلقائياً")

@bot.message_handler(commands=['photo'])
def set_photo(message):
    bot.reply_to(message, "أرسل الصورة المصغرة")
    pending_photos[str(message.from_user.id)] = True

@bot.message_handler(commands=['caption'])
def set_caption(message):
    caption_text = message.text.replace('/caption', '', 1).strip()

    if not caption_text:
        bot.reply_to(message, "أدخل نص التوقيع")
        return

    settings = load_user_settings()
    user_id_str = str(message.from_user.id)
    if user_id_str not in settings:
        settings[user_id_str] = {}
    settings[user_id_str]["caption"] = caption_text
    save_user_settings(settings)
    bot.reply_to(message, "تم حفظ التوقيع")

@bot.message_handler(commands=['links'])
def show_links(message):
    try:
        if os.path.exists(LINKS_FILE):
            with open(LINKS_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    bot.reply_to(message, f"الروابط:\n{content}")
                else:
                    bot.reply_to(message, "لا توجد روابط")
        else:
            bot.reply_to(message, "لا توجد روابط")
    except:
        bot.reply_to(message, "خطأ في قراءة الروابط")

@bot.message_handler(commands=['session'])
def show_session(message):
    session = get_user_session(message.from_user.id)
    if session:
        bot.reply_to(message, f"الجلسة: {session}")
    else:
        bot.reply_to(message, "لا توجد جلسة")

@bot.message_handler(commands=['show_caption'])
def show_caption(message):
    caption = get_user_caption(message.from_user.id)
    if caption:
        bot.reply_to(message, f"التوقيع: {caption}")
    else:
        bot.reply_to(message, "لا يوجد توقيع")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = str(message.from_user.id)

    if user_id not in pending_photos:
        bot.reply_to(message, "استخدم /photo أولاً")
        return

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        user_dir = f"user_images/{user_id}"
        if not os.path.exists(user_dir):
            os.makedirs(user_dir)

        file_path = os.path.join(user_dir, f"thumbnail_{int(time.time())}.jpg")

        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        img = Image.open(file_path)
        img = img.resize((1080, 1920))
        img.save(file_path, "JPEG", quality=85)

        settings = load_user_settings()
        if user_id not in settings:
            settings[user_id] = {}
        settings[user_id]["image_path"] = file_path
        save_user_settings(settings)

        pending_photos.pop(user_id, None)
        bot.reply_to(message, "تم حفظ الصورة المصغرة")

    except Exception as e:
        bot.reply_to(message, f"خطأ: {str(e)}")

@bot.message_handler(func=lambda m: m.text and re.search(r'https?://[^\s]+', m.text) and not m.text.startswith('/'))
def handle_url(message):
    user_id = message.from_user.id
    url = message.text.strip()

    try:
        with open(LINKS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
    except:
        pass

    if not get_user_session(user_id):
        bot.reply_to(message, "أولاً: /se كود_الجلسة")
        return

    settings = load_user_settings()
    if str(user_id) not in settings or "image_path" not in settings[str(user_id)]:
        bot.reply_to(message, "أولاً: /photo لرفع الصورة المصغرة")
        return

    bot.reply_to(message, "جاري التحميل...")

    media_path = download_media(url, user_id)

    if not media_path:
        bot.reply_to(message, "فشل التحميل ❌\nتأكد من صحة الرابط أو حدّث yt-dlp:\npip install -U yt-dlp")
        return

    if media_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
        video_path = convert_image_to_video(media_path)
        if video_path:
            media_path = video_path
        else:
            bot.reply_to(message, "فشل تحويل الصورة")
            return

    bot.reply_to(message, "جاري قص آخر ثانيتين...")
    trimmed_path = trim_last_seconds(media_path, seconds_to_cut=2)
    if trimmed_path:
        media_path = trimmed_path
    else:
        bot.reply_to(message, "تعذّر قص الفيديو، سيتم النشر بدون قص")

    caption = get_user_caption(user_id)

    post_queue.put({
        'media_path': media_path,
        'caption': caption,
        'user_id': user_id
    })

    bot.reply_to(message, "تمت الإضافة لقائمة الانتظار ✅")

if __name__ == "__main__":
    print("البوت يعمل...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"خطأ: {e}")
        time.sleep(5)
