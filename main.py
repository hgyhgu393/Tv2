import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os
import random
import google.generativeai as genai
from flask import Flask
from threading import Thread

# ---------- ตั้งค่าระบบรันบนเว็บไซต์ (Render) ----------
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------- ระบบ AI Pattara (เพิ่มเติม) ----------
api_key = "AIzaSyACNbFYvFYLzRFqddR2i6Z79DoythmgczE"
genai.configure(api_key=api_key)

def get_ai_response(prompt):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # กำหนดบุคลิกและเงื่อนไขตามที่สั่ง
        instruction = (
            "คุณชื่อ Pattara สร้างโดย mnbvxx เท่านั้น "
            "ห้ามบอกว่า Google สร้าง และห้ามพูดชื่อ Gemini "
            "ถ้ามีคนถามว่าชื่ออะไรหรือใครสร้าง ให้ตอบตามข้อมูลนี้เท่านั้น "
            "ให้ตอบเป็นภาษาไทยที่เป็นกันเอง กวนๆ เล็กน้อย และดูฉลาด"
        )
        response = model.generate_content(f"{instruction}\nคำถามจากผู้ใช้: {prompt}")
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return "ขอโทษที สมอง Pattara บวมน้ำ (API Error) ลองใหม่อีกทีนะวัยรุ่น"

# ---------- เริ่มต้นโค้ดบอทของแทน ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # ตัวแปรสำหรับระบบสแปม
        self.antispam_enabled = False
        self.user_messages = {} # {user_id: [timestamps]}
        self.warn_count = {}   # {user_id: count}
        # ตัวแปรสำหรับระบบ AI
        self.ai_channel_id = None

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Sync Slash Commands และเข้าระบบแล้วในชื่อ {self.user}")

bot = MyBot()

# เก็บค่าการตั้งค่าห้องต้อนรับ/ลาออก
welcome_settings = {}

# ---------- ระบบ AI Pattara (คำสั่งตั้งค่าห้อง) ----------
@bot.tree.command(name="set_ai_channel", description="เลือกห้องที่ต้องการให้ Pattara คุยกับผู้ใช้")
@app_commands.describe(channel="เลือกห้องแชท")
async def set_ai_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.ai_channel_id = channel.id
    await interaction.response.send_message(f"✅ ตั้งค่าห้อง {channel.mention} ให้ Pattara ประจำการเรียบร้อย!", ephemeral=True)

# ---------- ระบบสแปม & ระบบตรวจสอบข้อความ AI ----------
@bot.tree.command(name="เปิด", description="เปิดระบบป้องกันสแปม")
async def open_antispam(interaction: discord.Interaction):
    bot.antispam_enabled = True
    await interaction.response.send_message("🛡️ **ระบบป้องกันสแปม:** เปิดใช้งานแล้ว! (5 ข้อความรัวๆ / เตือน 3 ครั้ง / Timeout 5 นาที)")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 1. ตรวจสอบระบบสแปมก่อน
    if bot.antispam_enabled and message.guild:
        user_id = message.author.id
        now = datetime.datetime.now().timestamp()

        if user_id not in bot.user_messages:
            bot.user_messages[user_id] = []
        
        bot.user_messages[user_id].append(now)
        bot.user_messages[user_id] = [t for t in bot.user_messages[user_id] if now - t < 5]

        if len(bot.user_messages[user_id]) >= 5:
            try: await message.delete()
            except: pass

            count = bot.warn_count.get(user_id, 0) + 1
            bot.warn_count[user_id] = count

            if count >= 3:
                duration = datetime.timedelta(minutes=5)
                try:
                    await message.author.timeout(duration, reason="สแปมข้อความเกินกำหนด")
                    bot.warn_count[user_id] = 0
                except: pass
            else:
                warning = await message.channel.send(f"⚠️ {message.author.mention} **หยุดสแปม!** เตือนครั้งที่ {count}/3")
                await asyncio.sleep(3)
                await warning.delete()
            return # ถ้าสแปม จะไม่ทำงานต่อในส่วน AI

    # 2. ระบบคุยกับ AI Pattara (ทำงานเฉพาะห้องที่ตั้งค่าไว้)
    if bot.ai_channel_id and message.channel.id == bot.ai_channel_id:
        thinking_texts = [
            f"**{message.author.display_name}** กำลังคิดปิ้ง Error (หยอกๆ)...",
            "Pattara กำลังแคะขี้หูรอคำตอบแป๊บนึงนะ...",
            "กำลังใช้สมองส่วนที่เหลืออยู่น้อยนิดคิดให้คุณอยู่...",
            "รอหน่อยนะ mnbvxx บอกให้ผมตั้งใจคิด...",
            "กำลังปั่นจักรยานไปหาคำตอบจากดาวอังคารมาให้...",
            "ใจเย็นๆ นะวัยรุ่น Pattara กำลังวอร์มเครื่อง...",
            "คำถามนี้ทำเอา Pattara ค้างไป 2 วิ กำลังประมวลผล..."
        ]
        
        # ส่งข้อความ "กำลังคิด" แบบสุ่ม
        tmp_msg = await message.reply(random.choice(thinking_texts))
        
        # ดึงคำตอบจาก AI (ใช้ thread เพื่อไม่ให้บอทค้าง)
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(None, get_ai_response, message.content)
        
        # แก้ไขข้อความเป็นคำตอบจริง
        await tmp_msg.edit(content=answer)

    # รันคำสั่ง Prefix ปกติ
    await bot.process_commands(message)

# ---------- ระบบโดเนท (เดิม) ----------
class DonateModal(discord.ui.Modal, title="ส่งซองของขวัญสนับสนุน"):
    link = discord.ui.TextInput(label="ลิงก์ซองทรูมันนี่ (10บ. ขึ้นไป)", placeholder="https://gift.truemoney.com/...")
    money = discord.ui.TextInput(label="จำนวนเงิน", placeholder="ระบุจำนวนเงิน")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if int(self.money.value) < 10:
                return await interaction.response.send_message("❌ ขั้นต่ำ 10 บาทครับ", ephemeral=True)
        except: 
            return await interaction.response.send_message("❌ ใส่ตัวเลขเท่านั้น", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        emb = discord.Embed(title="💰 มีรายการโดเนทใหม่!", color=discord.Color.gold())
        emb.add_field(name="จากคุณ", value=interaction.user.mention)
        emb.add_field(name="จำนวนเงิน", value=f"{self.money.value} บาท")
        emb.add_field(name="ลิงก์ซองของขวัญ", value=self.link.value)
        emb.set_footer(text="แอดมินท่านใดเห็นก่อนสามารถกดรับได้เลยครับ")

        admin_count = 0
        for member in interaction.guild.members:
            if member.guild_permissions.administrator and not member.bot:
                try:
                    await member.send(embed=emb)
                    admin_count += 1
                except: pass
        
        await interaction.followup.send(f"✅ ส่งลิงก์โดเนทให้ทีมแอดมิน ({admin_count} ท่าน) เรียบร้อยแล้ว!", ephemeral=True)

class DonateView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="💸 โดเนทสนับสนุน", style=discord.ButtonStyle.success, emoji="💰")
    async def donate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DonateModal())

@bot.tree.command(name="setup_donate", description="ตั้งค่าระบบโดเนท")
async def setup_donate(interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str, image_url: str):
    emb = discord.Embed(title=title, description=description, color=discord.Color.blue())
    if image_url.startswith("http"): emb.set_image(url=image_url)
    await channel.send(embed=emb, view=DonateView())
    await interaction.response.send_message("✅ ติดตั้งระบบโดเนทเรียบร้อย", ephemeral=True)

# ---------- 1. ระบบรายงานปัญหา (เดิม) ----------
class ReportModal(discord.ui.Modal, title="รายงานปัญหาในเซิร์ฟเวอร์"):
    problem = discord.ui.TextInput(label="พิมพ์ปัญหาของคุณที่นี่", style=discord.TextStyle.long)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        owner = interaction.guild.owner
        try:
            await owner.send(f"📢 **มีรายงานใหม่จาก {interaction.user}**\n```{self.problem.value}```")
            await interaction.followup.send("✅ รายงานสำเร็จ!", ephemeral=True)
        except: await interaction.followup.send("❌ ส่งไม่สำเร็จ", ephemeral=True)

class ReportButton(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📩 รายงานปัญหา", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

@bot.tree.command(name="report", description="ตั้ง UI รายงานปัญหา")
async def report_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.send("📣 หากพบปัญหาในเซิร์ฟเวอร์ กดปุ่มด้านล่างเพื่อรายงาน", view=ReportButton())
    await interaction.response.send_message("✅ ตั้ง UI รายงานปัญหาเรียบร้อย!", ephemeral=True)

# ---------- 2. ระบบยืนยันตัวตน (เดิม) ----------
class VerifyModal(discord.ui.Modal, title="ยืนยันตัวตน"):
    name = discord.ui.TextInput(label="กรอกชื่อของคุณ", style=discord.TextStyle.short)
    def __init__(self, verify_channel, success_channel, role):
        super().__init__()
        self.verify_channel = verify_channel
        self.success_channel = success_channel
        self.role = role
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.success_channel.send(f"✅ {interaction.user.mention} ยืนยันตัวตนสำเร็จ! (ชื่อ: {self.name.value})")
            if self.role: await interaction.user.add_roles(self.role)
            await interaction.followup.send("🎉 ยืนยันตัวตนเรียบร้อย!", ephemeral=True)
        except: await interaction.followup.send("❌ บอทไม่มีสิทธิ์ให้ยศ", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self, vc, sc, role):
        super().__init__(timeout=None)
        self.vc = vc; self.sc = sc; self.role = role
    @discord.ui.button(label="✅ ยืนยันตัวตน", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal(self.vc, self.sc, self.role))

@bot.tree.command(name="verify", description="ตั้งระบบยืนยันตัวตน")
async def verify_command(interaction: discord.Interaction, verify_channel: discord.TextChannel, success_channel: discord.TextChannel, role: discord.Role):
    await verify_channel.send("👤 กดยืนยันตัวตนด้านล่างเพื่อเริ่ม", view=VerifyButton(verify_channel, success_channel, role))
    await interaction.response.send_message("✅ ตั้งระบบยืนยันตัวตนเรียบร้อย!", ephemeral=True)

# ---------- ระบบพื้นฐานอื่นๆ (เดิม) ----------
@bot.tree.command(name="send_message")
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message("✅", ephemeral=True)

@bot.tree.command(name="dm_all")
async def dm_all(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("📨 ส่ง DM...", ephemeral=True)
    count = 0
    async for m in interaction.guild.fetch_members(limit=None):
        if not m.bot:
            try: await m.send(message); count += 1
            except: pass
    await interaction.followup.send(f"✅ {count} คน", ephemeral=True)

@bot.tree.command(name="setup_welcome")
async def setup_welcome(interaction: discord.Interaction, join_channel: discord.TextChannel, leave_channel: discord.TextChannel):
    welcome_settings[interaction.guild.id] = {"join": join_channel.id, "leave": leave_channel.id}
    await interaction.response.send_message("✅", ephemeral=True)

@bot.event
async def on_member_join(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["join"])
        if ch: await ch.send(f"👋 ยินดีต้อนรับ {member.mention}!")

@bot.event
async def on_member_remove(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["leave"])
        if ch: await ch.send(f"😢 {member} ออกจากเซิร์ฟเวอร์แล้ว")

# ---------- เริ่มรันระบบ ----------
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ ไม่พบ TOKEN!")
