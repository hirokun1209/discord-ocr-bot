import os
import discord
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import re

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === サーバー番号 ===
server_box = (420, 970, 870, 1040)

# === 駐騎場共通設定 ===
base_y = 1095
row_height = 310
crop_height = 140  # 下に余裕+20

# 右側(免戦時間)のOCR領域（+10px広げる）
time_box_x = (390, 640)

def preprocess_image(img_path, save_path):
    """OCR精度向上用 前処理(4倍拡大＋2回シャープ化＋二値化)"""
    img = Image.open(img_path).convert("L")            # グレースケール
    img = img.resize((img.width * 4, img.height * 4))  # 4倍拡大
    img = img.filter(ImageFilter.SHARPEN)              # 1回目シャープ化
    img = img.filter(ImageFilter.SHARPEN)              # 2回目シャープ化
    img = ImageOps.autocontrast(img)                   # コントラスト強化
    img = img.point(lambda x: 0 if x < 180 else 255, '1')  # 二値化（しっかりめ）
    img.save(save_path)
    return img

def ocr_digits_only(img):
    """数字＆コロン限定OCR（psm8→短い数字列に強い）"""
    custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789:'
    return pytesseract.image_to_string(img, config=custom_config).strip()

def ocr_image(image_path, processed_path):
    """OCR前処理後に読み取り"""
    img = preprocess_image(image_path, processed_path)
    return ocr_digits_only(img)

def extract_time(text):
    """免戦時間(HH:MM:SS)抽出・補正"""
    m = re.search(r"\d{1,2}[:：]?\d{1,2}[:：]?\d{1,2}", text)
    if m:
        time_val = m.group(0).replace("：", ":")
        # 042137 → 04:21:37 の補正
        if len(time_val) == 6 and ":" not in time_val:
            time_val = f"{time_val[0:2]}:{time_val[2:4]}:{time_val[4:6]}"
        return time_val
    return "開戦済"

def crop_and_ocr(img_path):
    img = Image.open(img_path)

    # ✅ サーバー番号OCR
    server_crop = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop)
    server_proc = "/tmp/debug_server_proc.png"
    server_raw = ocr_image(server_crop, server_proc)

    lines = []
    for i in range(3):
        y1 = base_y + i * row_height

        # 行1だけ微調整
        if i == 0:
            y1 -= 5
        # 行2だけ100px上げる
        if i == 1:
            y1 -= 100
        # 行3だけ200px上げる
        if i == 2:
            y1 -= 200

        y2 = y1 + crop_height

        # 右側(免戦時間)だけ切り出し
        time_crop = f"/tmp/time_{i+1}.png"
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop)
        time_proc = f"/tmp/time_proc_{i+1}.png"
        raw_text = ocr_image(time_crop, time_proc)
        time_val = extract_time(raw_text)

        lines.append({
            "raw_text": raw_text,    # OCR生テキスト
            "time_val": time_val,    # 正規表現抽出結果
            "time_crop": time_crop,
            "time_proc": time_proc
        })

    return server_raw, server_proc, lines

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像受信！4倍拡大＋psm8で右側OCR強化テストします…")

        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_raw, server_proc, lines = crop_and_ocr(file_path)

            # OCR結果まとめ（生テキスト＋抽出結果）
            result_msg = f"**サーバー番号OCR生テキスト:** \"{server_raw}\"\n\n"
            for idx, line in enumerate(lines, start=1):
                result_msg += f"行{idx} → OCR生テキスト: \"{line['raw_text']}\"\n"
                result_msg += f"　　　 → 抽出結果: {line['time_val']}\n"

            await message.channel.send(result_msg)

            # サーバー番号の処理画像も送る
            await message.channel.send("サーバー番号OCR前処理画像", file=discord.File(server_proc))

            # 各行の右側OCRデバッグ画像を送信
            for idx, line in enumerate(lines, start=1):
                await message.channel.send(
                    f"行{idx} 免戦時間OCRデバッグ用画像\n元画像 & 処理後画像",
                    files=[
                        discord.File(line["time_crop"], filename=f"行{idx}_時間_元画像.png"),
                        discord.File(line["time_proc"], filename=f"行{idx}_時間_処理画像.png"),
                    ]
                )

client.run(TOKEN)