import discord
from PIL import Image, ImageFilter
from io import BytesIO
import pytesseract
import re, os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ===== OCRユーティリティ =====
def preprocess_for_station(img: Image.Image):
    # グレースケール → 二値化 → シャープ化
    proc = img.convert("L").point(lambda x: 0 if x < 140 else 255, '1')
    proc = proc.filter(ImageFilter.SHARPEN)
    return proc

def ocr_japanese(img: Image.Image):
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(img, lang="jpn", config=config)

def ocr_numbers_only(img: Image.Image):
    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:"
    raw = pytesseract.image_to_string(img, lang="eng", config=config)
    raw = raw.replace("O","0").replace("o","0").replace("B","8")
    return raw

def normalize_time_format(line: str):
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', line)
    if m:
        return m.group(1)
    m2 = re.search(r'(\d{6})', line)
    if m2:
        s = m2.group(1)
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    return None

def extract_station_numbers(text: str):
    nums = re.findall(r'駐.*?場\s*(\d{1,2})', text)
    return [n for n in nums if n.isdigit() and 1 <= int(n) <= 12]

# ===== 中央領域切り出し =====
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

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test2":
        await message.channel.send("✅ 駐騎場OCRテストモード起動（Part2〜4プレビュー）")
        return

    if message.attachments:
        await message.channel.send("📥 画像受信！駐騎場番号＆免戦時間OCRテストします…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))
            center_raw = crop_center_area(img)
            blocks = split_preview_smaller_all(center_raw)

            # Part2〜4だけテスト
            for idx, b in enumerate(blocks[1:], start=2):
                # 前処理
                proc = preprocess_for_station(b)

                # 日本語OCR → 駐騎場番号
                jp_text = ocr_japanese(proc)
                station_nums = extract_station_numbers(jp_text)

                # 「免戦」があれば数字OCRでもう一度
                immune_time = None
                if "免戦" in jp_text or "院戦" in jp_text:
                    num_raw = ocr_numbers_only(proc)
                    immune_time = normalize_time_format(num_raw)

                # 元画像・前処理画像送信
                buf_raw = BytesIO(); b.save(buf_raw, format="PNG"); buf_raw.seek(0)
                buf_proc = BytesIO(); proc.save(buf_proc, format="PNG"); buf_proc.seek(0)

                result_msg = f"📸 Part{idx} OCR結果\n```\n{jp_text}\n```"
                if station_nums:
                    result_msg += f"\n✅ 駐騎場番号: {station_nums}"
                if immune_time:
                    result_msg += f"\n⏳ 免戦時間: {immune_time}"

                await message.channel.send(
                    result_msg,
                    files=[
                        discord.File(buf_raw, f"part{idx}_raw.png"),
                        discord.File(buf_proc, f"part{idx}_processed.png")
                    ]
                )

client.run(TOKEN)