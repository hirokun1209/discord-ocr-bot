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

# ===== OCRユーティリティ =====
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

# ===== サーバー番号専用OCR =====
def ocr_server_id(img: Image.Image):
    # モノクロ化 & コントラスト強化
    proc = img.convert("L").point(lambda x: 0 if x < 140 else 255, '1')
    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789sS[]"
    raw = pytesseract.image_to_string(proc, lang="eng", config=config)
    raw = raw.replace("O","0").replace("o","0")
    m = re.findall(r'\[?s?(\d{3,4})\]?', raw, re.IGNORECASE)
    return (m[-1] if m else None), proc

# ===== 切り出し領域 =====
def crop_center_area(img):
    w,h = img.size
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.65))

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
    return parts

def extract_station_numbers(text):
    nums = re.findall(r'駐.*?場\s*(\d+)', text)
    return [n for n in nums if n.isdigit() and 1 <= int(n) <= 12]

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（サーバーOCRプレビュー付き版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、分割→OCRプレビューします…")

        for attachment in message.attachments:
            img_data = await attachment.read()

            # ファイルタイムスタンプ取得
            tmp_path = f"/tmp/{attachment.filename}"
            with open(tmp_path, "wb") as f:
                f.write(img_data)
            stat = os.stat(tmp_path)
            base_dt = datetime.fromtimestamp(stat.st_mtime)
            base_time_str = base_dt.strftime("%H:%M:%S")

            img = Image.open(BytesIO(img_data))
            center_raw = crop_center_area(img)
            blocks = split_preview_smaller_all(center_raw)

            # === Part1: サーバー番号OCR + プレビュー ===
            server_img = blocks[0]
            server_id, proc_img = ocr_server_id(server_img)

            buf1 = BytesIO(); server_img.save(buf1, format="PNG"); buf1.seek(0)
            buf2 = BytesIO(); proc_img.save(buf2, format="PNG"); buf2.seek(0)
            await message.channel.send(
                f"📸 Part1 サーバー番号OCR結果: {server_id if server_id else '読めず'}",
                files=[
                    discord.File(buf1, "server_raw.png"),
                    discord.File(buf2, "server_processed.png")
                ]
            )

            # === Part2〜4: 駐騎場番号＆免戦時間 + プレビュー ===
            pairs = []
            for idx, b in enumerate(blocks[1:], start=2):
                text = ocr_text(b, psm=4)
                station_nums = extract_station_numbers(text)

                # プレビュー画像送信
                tmp_buf = BytesIO(); b.save(tmp_buf, format="PNG"); tmp_buf.seek(0)
                await message.channel.send(
                    f"📸 Part{idx} OCR結果:\n{text}",
                    file=discord.File(tmp_buf, f"center_part_{idx}.png")
                )

                if station_nums and ("免戦" in text or "院戦" in text):
                    raw_time = ocr_time_line(b)
                    t = normalize_time_format(raw_time)
                    if t:
                        pairs.append((station_nums[0], t))

            # === 最終結果出力 ===
            if server_id and pairs:
                results = [f"📸 スクショ基準時間: {base_time_str} / サーバー: {server_id}"]
                for st, immune_t in pairs:
                    hms = list(map(int, immune_t.split(":"))); hms += [0]*(3-len(hms))
                    end_dt = (base_dt + timedelta(hours=hms[0], minutes=hms[1], seconds=hms[2])).time()
                    results.append(f"越域駐騎場{st} → 終了 {end_dt.strftime('%H:%M:%S')}")
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send("⚠️ サーバー or 駐騎場/免戦時間が読めませんでした")

client.run(TOKEN)