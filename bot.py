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

# 番号と免戦時間を左右で分割
num_box_x  = (270, 400)  # 左側：番号専用
time_box_x = (400, 630)  # 右側：免戦時間専用

def preprocess_image(img_path, save_path):
    """OCR精度向上用 前処理(2倍拡大＋シャープ化＋二値化)"""
    img = Image.open(img_path).convert("L")          # グレースケール
    img = img.resize((img.width * 2, img.height * 2)) # 2倍拡大
    img = img.filter(ImageFilter.SHARPEN)            # シャープ化
    img = ImageOps.autocontrast(img)                 # コントラスト強調
    img = img.point(lambda x: 0 if x < 160 else 255, '1')  # 二値化
    img.save(save_path)
    return img

def ocr_digits_only(img):
    """数字＆コロン限定OCR"""
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789:'
    return pytesseract.image_to_string(img, config=custom_config).strip()

def ocr_image(image_path, processed_path):
    """OCR前処理後に読み取り"""
    img = preprocess_image(image_path, processed_path)
    return ocr_digits_only(img)

def parse_number(text):
    """駐騎場番号(1～12)だけ抽出"""
    m = re.search(r"\b([1-9]|1[0-2])\b", text)
    return m.group(1) if m else "?"

def parse_time(text):
    """免戦時間(HH:MM:SS)抽出"""
    m = re.search(r"\d{1,2}[:：]\d{1,2}[:：]\d{1,2}", text)
    return m.group(0).replace("：", ":") if m else "開戦済"

def crop_and_ocr(img_path):
    img = Image.open(img_path)

    # ✅ サーバー番号OCR
    server_crop = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop)
    server_proc = "/tmp/debug_server_proc.png"
    server_text = ocr_image(server_crop, server_proc)

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

        # 番号だけ切り出し
        num_crop = f"/tmp/num_{i+1}.png"
        img.crop((num_box_x[0], y1, num_box_x[1], y2)).save(num_crop)
        num_proc = f"/tmp/num_proc_{i+1}.png"
        num_text = ocr_image(num_crop, num_proc)
        number = parse_number(num_text)

        # 免戦時間だけ切り出し
        time_crop = f"/tmp/time_{i+1}.png"
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop)
        time_proc = f"/tmp/time_proc_{i+1}.png"
        time_text = ocr_image(time_crop, time_proc)
        time_val = parse_time(time_text)

        lines.append({
            "number": number,
            "time": time_val,
            "num_crop": num_crop,
            "num_proc": num_proc,
            "time_crop": time_crop,
            "time_proc": time_proc
        })

    return server_text, server_proc, lines

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像受信！番号と免戦時間を左右分割してデバッグします…")

        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_text, server_proc, lines = crop_and_ocr(file_path)

            # OCR結果まとめ
            result_msg = f"**サーバー番号:** {server_text}\n\n"
            for idx, line in enumerate(lines, start=1):
                result_msg += f"行{idx} → 駐騎場番号: {line['number']}, {line['time']}\n"

            await message.channel.send(result_msg)

            # サーバー番号の処理画像も送る
            await message.channel.send("サーバー番号OCR前処理画像", file=discord.File(server_proc))

            # 各行のデバッグ画像を送信
            for idx, line in enumerate(lines, start=1):
                await message.channel.send(
                    f"行{idx} デバッグ用画像\n番号OCR & 免戦時間OCR",
                    files=[
                        discord.File(line["num_crop"], filename=f"行{idx}_番号_元画像.png"),
                        discord.File(line["num_proc"], filename=f"行{idx}_番号_処理画像.png"),
                        discord.File(line["time_crop"], filename=f"行{idx}_時間_元画像.png"),
                        discord.File(line["time_proc"], filename=f"行{idx}_時間_処理画像.png"),
                    ]
                )

client.run(TOKEN)