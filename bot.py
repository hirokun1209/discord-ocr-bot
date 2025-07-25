import os
import discord
from PIL import Image
import pytesseract

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
crop_height = 120         # 下に10px伸ばした高さ

def ocr_image(image_path):
    """OCRで文字読み取り"""
    text = pytesseract.image_to_string(Image.open(image_path), lang="eng+osd+jpn")
    return text.strip()

def parse_line_text(text):
    """OCR結果から番号＆免戦時間抽出（ざっくり）"""
    # 数字だけの駐騎場番号を探す
    import re
    num_match = re.search(r"\d{1,2}", text)
    number = num_match.group(0) if num_match else "?"
    
    # 時間フォーマットを探す
    time_match = re.search(r"\d{2}:\d{2}:\d{2}", text)
    if time_match:
        time_val = time_match.group(0)
    else:
        # 免戦時間が無ければ「開戦済」
        time_val = "開戦済"
    
    return number, time_val

def crop_and_ocr(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    # ✅ サーバー番号切り出し
    server_crop = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop)
    server_text = ocr_image(server_crop)

    # ✅ 駐騎場3行OCR
    lines = []
    for i in range(3):
        y1 = base_y + i * row_height

        # 行2だけ100px上補正
        if i == 1:
            y1 -= 100

        # 行3だけ200px上補正
        if i == 2:
            y1 -= 200

        y2 = y1 + crop_height
        crop_path = f"/tmp/debug_full_{i+1}.png"
        img.crop((full_box_x[0], y1, full_box_x[1], y2)).save(crop_path)

        # OCR解析
        raw_text = ocr_image(crop_path)
        number, time_val = parse_line_text(raw_text)
        lines.append((number, time_val))

    return server_text, lines

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像受信！OCRでサーバー番号＋駐騎場情報を解析します…")

        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_text, lines = crop_and_ocr(file_path)

            # OCR結果フォーマット
            result_msg = f"**サーバー番号:** {server_text}\n\n"
            for idx, (num, tval) in enumerate(lines, start=1):
                result_msg += f"行{idx} → 駐騎場番号: {num}, {tval}\n"

            await message.channel.send(result_msg)

client.run(TOKEN)