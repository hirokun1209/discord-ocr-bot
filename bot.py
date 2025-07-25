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
server_box = (400, 950, 890, 1060)  # 余裕を持って少し広げる

# === 駐騎場共通設定 ===
base_y = 1095
row_height = 310
crop_height = 160  # 余裕を+20px

# 左右領域（余裕を+20px）
num_box_x  = (250, 420)  # 番号
time_box_x = (380, 660)  # 免戦時間

def preprocess_image(img_path, save_path):
    """超強化OCR前処理(8倍拡大+3回シャープ化+二値化強め)"""
    img = Image.open(img_path).convert("L")             # グレースケール
    img = img.resize((img.width * 8, img.height * 8))   # 8倍拡大
    img = img.filter(ImageFilter.SHARPEN)               # シャープ1回目
    img = img.filter(ImageFilter.SHARPEN)               # シャープ2回目
    img = img.filter(ImageFilter.SHARPEN)               # シャープ3回目
    img = ImageOps.autocontrast(img)                    # コントラスト強調
    img = img.point(lambda x: 0 if x < 190 else 255, '1')  # 強い二値化
    img.save(save_path)
    return img

def ocr_digits_only(img):
    """数字＆コロン限定OCR（psm13＝数字列モード）"""
    custom_config = r'--oem 3 --psm 13 -c tessedit_char_whitelist=0123456789:'
    return pytesseract.image_to_string(img, config=custom_config).strip()

def ocr_image(image_path, processed_path):
    """OCR前処理後に読み取り"""
    img = preprocess_image(image_path, processed_path)
    return ocr_digits_only(img)

def extract_number(text):
    """駐騎場番号(1～12)抽出"""
    m = re.search(r"\b([1-9]|1[0-2])\b", text)
    return m.group(1) if m else "?"

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

        # 行ごとの補正
        if i == 0: y1 -= 5
        if i == 1: y1 -= 100
        if i == 2: y1 -= 200

        y2 = y1 + crop_height

        # 番号だけ
        num_crop = f"/tmp/num_{i+1}.png"
        img.crop((num_box_x[0], y1, num_box_x[1], y2)).save(num_crop)
        num_proc = f"/tmp/num_proc_{i+1}.png"
        raw_num = ocr_image(num_crop, num_proc)
        number = extract_number(raw_num)

        # 免戦時間だけ
        time_crop = f"/tmp/time_{i+1}.png"
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop)
        time_proc = f"/tmp/time_proc_{i+1}.png"
        raw_time = ocr_image(time_crop, time_proc)
        time_val = extract_time(raw_time)

        lines.append({
            "raw_num": raw_num,
            "raw_time": raw_time,
            "number": number,
            "time_val": time_val,
            "num_crop": num_crop,
            "num_proc": num_proc,
            "time_crop": time_crop,
            "time_proc": time_proc
        })

    return server_raw, server_proc, lines

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像受信！8倍拡大＋psm13超強化OCRで番号＆時間デバッグします…")

        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_raw, server_proc, lines = crop_and_ocr(file_path)

            # OCR結果まとめ（生テキスト＋抽出結果）
            result_msg = f"**サーバー番号OCR生テキスト:** \"{server_raw}\"\n\n"
            for idx, line in enumerate(lines, start=1):
                result_msg += f"行{idx} → 番号OCR生テキスト: \"{line['raw_num']}\"\n"
                result_msg += f"　　　 → 抽出結果: {line['number']}\n"
                result_msg += f"　　　 → 時間OCR生テキスト: \"{line['raw_time']}\"\n"
                result_msg += f"　　　 → 抽出結果: {line['time_val']}\n\n"

            await message.channel.send(result_msg)

            # サーバー番号の処理画像
            await message.channel.send("サーバー番号OCR前処理画像", file=discord.File(server_proc))

            # 各行のデバッグ画像（番号＆時間の元画像＋処理画像）
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