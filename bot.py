import discord
from PIL import Image
from io import BytesIO
import pytesseract
import re, os
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== OCR共通 =====
def ocr_text(img: Image.Image, psm=4):
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang="jpn+eng", config=config)

def ocr_time_line(img: Image.Image):
    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:"
    return pytesseract.image_to_string(img, lang="eng", config=config)

def normalize_time_format(line: str):
    line = line.replace("O","0").replace("o","0").replace("B","8")
    m = re.search(r'(\d{6})', line)
    if m:
        raw = m.group(1)
        return f"{raw[0:2]}:{raw[2:4]}:{raw[4:6]}"
    m2 = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', line)
    if m2:
        return m2.group(1)
    return None

# ===== 切り出し領域 =====
def crop_center_area(img):
    w,h = img.size
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.65))  # 中央確定範囲

def split_preview_smaller_all(center_raw):
    w, h = center_raw.size
    parts = []
    # Part1 = 1/8
    part1_h = h // 8
    parts.append(center_raw.crop((0, 0, w, part1_h)))
    # 残りを4分割 → 3枚だけ使う
    remaining_height = h - part1_h
    block_h = remaining_height // 4
    y_start = part1_h
    for _ in range(3):
        y_end = y_start + block_h
        parts.append(center_raw.crop((0, y_start, w, y_end)))
        y_start = y_end
    return parts  # 4枚

def extract_server_id(text):
    m = re.findall(r'\[s?(\d{2,4})\]', text, re.IGNORECASE)
    return m[-1] if m else None

def extract_station_numbers(text):
    nums = re.findall(r'駐.*?場\s*(\d+)', text)
    valid = []
    for n in nums:
        if n.isdigit() and 1 <= int(n) <= 12:
            valid.append(n)
    return valid

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（ファイルタイムスタンプ基準版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、ファイルのタイムスタンプを基準時間にします…")

        for attachment in message.attachments:
            img_data = await attachment.read()

            # 一時保存してタイムスタンプ取得
            tmp_path = f"/tmp/{attachment.filename}"
            with open(tmp_path, "wb") as f:
                f.write(img_data)

            stat = os.stat(tmp_path)
            # ファイルの更新時刻
            base_dt = datetime.fromtimestamp(stat.st_mtime)
            base_time_str = base_dt.strftime("%H:%M:%S")

            # 画像読み込み
            img = Image.open(BytesIO(img_data))

            # === 中央OCR領域を4分割 ===
            center_raw = crop_center_area(img)
            blocks = split_preview_smaller_all(center_raw)

            # 1枚目(サーバー番号)
            server_text = ocr_text(blocks[0])
            server_id = extract_server_id(server_text)

            # 残りブロック：駐騎場番号＋免戦時間
            pairs = []
            for b in blocks[1:]:
                text = ocr_text(b, psm=4)
                station_nums = extract_station_numbers(text)
                if station_nums:
                    # 免戦中行があるか探す
                    if "免戦" in text or "院戦" in text:
                        raw_time = ocr_time_line(b)
                        t = normalize_time_format(raw_time)
                        if t:
                            pairs.append((station_nums[0], t))

            if not server_id:
                await message.channel.send("⚠️ サーバー番号が読めませんでした")
                return
            if not pairs:
                await message.channel.send("⚠️ 駐騎場番号＋免戦時間が読めませんでした")
                return

            # === 基準時間(ファイルの撮影時刻) + 免戦時間を足す ===
            results = [f"📸 スクショ撮影基準時間: {base_time_str}\nサーバー番号: {server_id}"]
            for st, immune_t in pairs:
                hms = list(map(int, immune_t.split(":")))
                while len(hms) < 3: hms.append(0)
                end_dt = (base_dt + timedelta(hours=hms[0], minutes=hms[1], seconds=hms[2])).time()
                results.append(f"越域駐騎場{st} → 終了予定 {end_dt.strftime('%H:%M:%S')}")

            await message.channel.send("\n".join(results))

client.run(TOKEN)