import os
import discord
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pytesseract
import re

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === サーバー番号 ===
server_box = (420, 970, 870, 1040)

# === 駐騎場（番号＋免戦時間） ===
base_y = 1095             # 行1の基準位置
row_height = 310          # 行間
full_box_x = (270, 630)   # 横幅
crop_height = 140         # 高さ余裕 +20

def preprocess_image(img_path, save_path):
    """OCR精度向上用に最適化前処理（拡大・シャープ化・二値化）"""
    img = Image.open(img_path).convert("L")         # グレースケール
    img = img.resize((img.width * 2, img.height * 2))  # 2倍拡大
    img = img.filter(ImageFilter.SHARPEN)           # シャープ化
    img = ImageOps.autocontrast(img)                # コントラスト強調
    img = img.point(lambda x: 0 if x < 160 else 255, '1')  # 二値化
    img.save(save_path)  # 処理後画像を保存
    return img

def ocr_digits_only(img):
    """数字＆コロン専用OCR（複数数字でも拾える）"""
    # --psm 6 → 複数行/ブロックモード
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789:'
    text = pytesseract.image_to_string(img, config=custom_config)
    return text.strip()

def ocr_image(image_path, processed_path):
    """前処理後にOCR"""
    img = preprocess_image(image_path, processed_path)
    return ocr_digits_only(img)

def parse_line_text(text):
    """OCR結果から番号＆免戦時間抽出"""
    # 駐騎場番号（1～12のどれか）
    num_match = re.search(r"\b([1-9]|1[0-2])\b", text)
    number = num_match.group(1) if num_match else "?"
    
    # 時間フォーマット（免戦時間）
    time_match = re.search(r"(\d{1,2}[:：]\d{1,2}[:：]\d{1,2})", text)
    if time_match:
        time_val = time_match.group(1).replace("：", ":")  # 全角→半角
    else:
        time_val = "開戦済"
    
    return number, time_val

def crop_and_ocr(img_path):
    img = Image.open(img_path)

    # ✅ サーバー番号切り出し
    server_crop = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop)
    server_proc = "/tmp/debug_server_proc.png"
    server_text = ocr_image(server_crop, server_proc)

    # ✅ 駐騎場3行OCR
    lines = []
    for i in range(3):
        y1 = base_y + i * row_height

        # 行1だけ少し上げる補正
        if i == 0:
            y1 -= 5
        # 行2だけ100px上補正
        if i == 1:
            y1 -= 100
        # 行3だけ200px上補正
        if i == 2:
            y1 -= 200

        y2 = y1 + crop_height  # 高さ余裕+20
        crop_path = f"/tmp/debug_full_{i+1}.png"
        img.crop((full_box_x[0], y1, full_box_x[1], y2)).save(crop_path)

        # 前処理後の画像パス
        proc_path = f"/tmp/debug_full_proc_{i+1}.png"

        # OCR解析（数字＋コロン限定）
        raw_text = ocr_image(crop_path, proc_path)
        number, time_val = parse_line_text(raw_text)

        lines.append((number, time_val, crop_path, proc_path))

    return server_text, lines, server_proc

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像受信！拡大＆シャープ化で最適化OCR解析します…")

        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_text, lines, server_proc = crop_and_ocr(file_path)

            # OCR結果フォーマット
            result_msg = f"**サーバー番号:** {server_text}\n\n"
            for idx, (num, tval, orig, proc) in enumerate(lines, start=1):
                result_msg += f"行{idx} → 駐騎場番号: {num}, {tval}\n"

            await message.channel.send(result_msg)

            # サーバー番号処理画像
            await message.channel.send("サーバー番号OCR前処理画像", file=discord.File(server_proc))

            # 各行の「元画像＋処理画像」
            for idx, (num, tval, orig, proc) in enumerate(lines, start=1):
                await message.channel.send(
                    f"行{idx} OCR前処理結果",
                    files=[
                        discord.File(orig, filename=f"行{idx}_元画像.png"),
                        discord.File(proc, filename=f"行{idx}_処理画像.png")
                    ]
                )

client.run(TOKEN)