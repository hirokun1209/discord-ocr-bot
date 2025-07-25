import discord
from PIL import Image, ImageFilter
from io import BytesIO
import pytesseract
import re, os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 強力前処理 ===
def preprocess_for_station_strong(img: Image.Image):
    gray = img.convert("L")
    # コントラスト強調
    gray = gray.point(lambda x: min(255, int(x * 1.4)))
    # 二値化(しきい値160)
    binary = gray.point(lambda x: 0 if x < 160 else 255, '1')
    # シャープ化
    sharp = binary.filter(ImageFilter.SHARPEN)
    return sharp

# === 行単位日本語OCR ===
def ocr_japanese_line(img: Image.Image):
    config = "--oem 3 --psm 7"
    return pytesseract.image_to_string(img, lang="jpn", config=config)

# === OCR補正 ===
def normalize_station_text(text: str):
    return (text.replace("須場","騎場")
                .replace("前場","騎場")
                .replace("崎場","騎場")
                .replace("駐須","駐騎")
                .replace("駐前","駐騎")
                .replace("駐崎","駐騎"))

# === 駐騎場番号抽出 ===
def extract_station_number_strict(text: str):
    text = normalize_station_text(text)
    m = re.findall(r'駐騎場\s*(\d{1,2})', text)
    return [x for x in m if x.isdigit() and 1 <= int(x) <= 12]

# === 中央領域切り出し ===
def crop_center_area(img):
    w,h = img.size
    return img.crop((w*0.05, h*0.35, w*0.55, h*0.65))

def split_preview_smaller_all(center_raw):
    w, h = center_raw.size
    parts = []
    part1_h = h // 8
    parts.append(center_raw.crop((0, 0, w, part1_h)))
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

    if message.content.strip() == "!test3":
        await message.channel.send("✅ 駐騎場OCR強力前処理テストモード起動！")
        return

    if message.attachments:
        await message.channel.send("📥 画像受信！強処理OCRテスト中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))
            center_raw = crop_center_area(img)
            blocks = split_preview_smaller_all(center_raw)

            # Part2〜4だけテスト
            for idx, b in enumerate(blocks[1:], start=2):
                proc = preprocess_for_station_strong(b)

                # OCR結果（補正前）
                raw_text = ocr_japanese_line(proc)
                fixed_text = normalize_station_text(raw_text)
                station_nums = extract_station_number_strict(raw_text)

                # 画像送信
                buf_raw = BytesIO(); b.save(buf_raw, format="PNG"); buf_raw.seek(0)
                buf_proc = BytesIO(); proc.save(buf_proc, format="PNG"); buf_proc.seek(0)

                result_msg = (
                    f"📸 Part{idx} OCR結果\n"
                    f"**補正前:**\n```\n{raw_text}\n```\n"
                    f"**補正後:**\n```\n{fixed_text}\n```\n"
                )
                if station_nums:
                    result_msg += f"✅ 抽出駐騎場番号: {station_nums}"

                await message.channel.send(
                    result_msg,
                    files=[
                        discord.File(buf_raw, f"part{idx}_raw.png"),
                        discord.File(buf_proc, f"part{idx}_processed.png")
                    ]
                )

client.run(TOKEN)