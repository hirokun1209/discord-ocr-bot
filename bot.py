import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

CENTER_OCR_CONFIG = "--oem 3 --psm 6"  # 中央OCRは複数行解析
BASE_OCR_CONFIG = "--oem 3 --psm 7"    # 基準時間は1行解析

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def preprocess_image(img: Image.Image) -> Image.Image:
    """OCR前に画像を強化処理（精度向上版）"""
    img = img.resize((img.width * 4, img.height * 4))  # 4倍拡大で文字潰れを防止
    img = img.convert("L")  # グレースケール
    img = ImageEnhance.Contrast(img).enhance(3.5)  # コントラストさらに強く
    img = img.point(lambda p: 255 if p > 170 else 0)  # 白黒化（細い文字も残す）
    img = img.filter(ImageFilter.SHARPEN)
    return img

def crop_top_right(img: Image.Image) -> Image.Image:
    """右上(基準時間) → ピンポイントで高さ7〜13%"""
    w, h = img.size
    return img.crop((w * 0.75, h * 0.07, w * 0.98, h * 0.13))

def crop_center_area(img: Image.Image) -> Image.Image:
    """中央OCR → 右を削って高さ35〜65%、横10〜50%"""
    w, h = img.size
    return img.crop((w * 0.1, h * 0.35, w * 0.5, h * 0.65))

def clean_ocr_text(text: str) -> str:
    """OCR結果の不要文字・誤認補正"""
    text = text.replace("を奪取しました", "")
    text = text.replace("奪取撃破数", "")
    text = text.replace("警備撃破数", "")
    text = text.replace("駐脱場", "駐騎場")
    text = text.replace("駐聴場", "駐騎場")
    text = text.replace("越域駐豚場", "越域駐騎場")
    # OCR誤認識の補正
    text = re.sub(r"(\d)[;；](\d)", r"\1:\2", text)  # 23;23 → 23:23
    text = re.sub(r"O(\d)", r"0\1", text)  # O3:25 → 03:25
    return text

def extract_base_time(text: str) -> str:
    """基準時間(HH:MM:SS)を抽出"""
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text)
    return m.group(1) if m else None

def extract_server_id(text: str) -> str:
    """サーバー番号(最後の1〜999を採用)"""
    server_matches = re.findall(r'\[s\d{2,4}\]', text, re.IGNORECASE)
    valid_servers = []
    for s in server_matches:
        num = int(re.search(r'\d{2,4}', s).group())
        if 1 <= num <= 999:
            valid_servers.append(num)
    return str(valid_servers[-1]) if valid_servers else "???"

def extract_station_numbers(text: str):
    """駐騎場番号（1〜12のみ有効）"""
    raw_stations = re.findall(r'駐騎場\s*(\d+)', text)
    return [n for n in dict.fromkeys(raw_stations) if 1 <= int(n) <= 12]

def extract_times(text: str):
    """免戦時間（HH:MM:SS / HH:MM / MM:SS対応、6時間以内だけ有効）"""
    raw_times = re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text)
    immune_times = []
    for t in raw_times:
        parts = t.split(':')
        if len(parts) == 3:
            h, m, s = map(int, parts)
        elif len(parts) == 2:
            first, second = map(int, parts)
            if first < 6:
                h, m, s = first, second, 0  # HH:MM
            else:
                h, m, s = 0, first, second  # MM:SS
            t = f"{h:02}:{m:02}:{s:02}"
        else:
            continue
        if 0 <= h <= 6:  # 最大6時間まで有効
            immune_times.append(t)
    return immune_times

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、OCR精度強化版で処理中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間OCR（右上ピンポイント） ===
            base_img = preprocess_image(crop_top_right(img))
            base_img.save("/tmp/debug_base.png")
            await message.channel.send(file=discord.File("/tmp/debug_base.png", "base_debug.png"))
            base_text = pytesseract.image_to_string(base_img, lang="jpn+eng", config=BASE_OCR_CONFIG)
            base_time = extract_base_time(base_text)

            # === 中央OCR（駐騎場情報のみ・右50%まで） ===
            center_img = preprocess_image(crop_center_area(img))
            center_img.save("/tmp/debug_center.png")
            await message.channel.send(file=discord.File("/tmp/debug_center.png", "center_debug.png"))
            center_text_raw = pytesseract.image_to_string(center_img, lang="jpn+eng", config=CENTER_OCR_CONFIG)
            center_text = clean_ocr_text(center_text_raw)

            # OCR結果から駐騎場行だけ抽出
            lines = [line for line in center_text.splitlines() if "駐騎場" in line]
            filtered_text = "\n".join(lines)

            # デバッグOCR結果
            await message.channel.send(f"⏫ 基準時間OCR:\n```\n{base_text}\n```")
            await message.channel.send(f"📄 中央OCR結果(全体):\n```\n{center_text_raw}\n```")
            await message.channel.send(f"📄 駐騎場行だけ抽出:\n```\n{filtered_text}\n```")

            # サーバー番号 / 駐騎場番号 / 免戦時間抽出（駐騎場行だけから）
            server_id = extract_server_id(filtered_text)
            station_numbers = extract_station_numbers(filtered_text)
            immune_times = extract_times(filtered_text)

            # 基準時間が読めなかった場合
            if not base_time:
                await message.channel.send("⚠️ 基準時間が右上から読み取れませんでした")
                return

            # データ数が一致しない場合は警告
            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"基準時間: {base_time}\n"
                    f"サーバー番号: {server_id}\n"
                    f"駐騎場番号({len(station_numbers)}件): {', '.join(station_numbers) if station_numbers else 'なし'}\n"
                    f"免戦時間({len(immune_times)}件): {', '.join(immune_times) if immune_times else 'なし'}"
                )
                return

            # === 基準時間 + 免戦時間 計算 ===
            base_dt = datetime.strptime(base_time, "%H:%M:%S")
            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}"
                h, m, s = map(int, t.split(":"))
                end_dt = (base_dt + timedelta(hours=h, minutes=m, seconds=s)).time()
                results.append(f"{station_name}({server_id}) {end_dt.strftime('%H:%M:%S')}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send(
                    f"基準時間: {base_time}\nサーバー番号: {server_id}\n⚠️ 有効な駐騎場番号 or 免戦時間なし"
                )

client.run(TOKEN)