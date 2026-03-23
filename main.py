import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os
from flask import Flask
from threading import Thread
from groq import Groq  # เพิ่ม library สำหรับ AI

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

# ---------- ตั้งค่า AI Groq (JemiZ) ----------
GROQ_API_KEY = "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"
client_groq = Groq(api_key=GROQ_API_KEY)

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
        self.active_ai_channels = {} # {guild_id: channel_id}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Sync Slash Commands และเข้าระบบแล้วในชื่อ {self.user}")

bot = MyBot()

# เก็บค่าการตั้งค่าห้องต้อนรับ/ลาออก
welcome_settings = {}

# ---------- ระบบ AI JemiZ (เพิ่มเติม) ----------
@bot.tree.command(name="setup_ai", description="เลือกห้องที่ต้องการให้ JemiZ ตอบโต้")
@app_commands.describe(channel="เลือกห้องแชทสำหรับคุยกับ AI")
async def setup_ai(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.active_ai_channels[interaction.guild_id] = channel.id
    await interaction.response.send_message(f"🤖 **JemiZ AI:** พร้อมใช้งานแล้วที่ห้อง {channel.mention} (สร้างโดย TANZ)", ephemeral=True)

# ---------- ระบบสแปม (เพิ่มเติม) ----------
@bot.tree.command(name="เปิด", description="เปิดระบบป้องกันสแปม")
async def open_antispam(interaction: discord.Interaction):
    bot.antispam_enabled = True
    await interaction.response.send_message("🛡️ **ระบบป้องกันสแปม:** เปิดใช้งานแล้ว! (5 ข้อความรัวๆ / เตือน 3 ครั้ง / Timeout 5 นาที)")

@bot.event
async def on_message(message):
    # ป้องกันบอทตอบตัวเอง
    if message.author.bot:
        return

    # 1. ระบบ AI JemiZ (เช็คว่าห้องนี้ตั้งค่าให้ AI ตอบไหม)
    if message.guild and bot.active_ai_channels.get(message.guild.id) == message.channel.id:
        async with message.channel.typing():
            try:
                chat_completion = client_groq.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "คุณคือ AI ชื่อ JemiZ ผู้สร้างคือ TANZ เท่านั้น ตอบคำถามอย่างเป็นกันเองและฉลาดที่สุด"},
                        {"role": "user", "content": message.content}
                    ],
                    model="llama3-8b-8192",
                )
                response = chat_completion.choices[0].message.content
                await message.reply(response)
            except Exception as e:
                print(f"AI Error: {e}")

    # 2. ตรวจสอบระบบสแปม (โค้ดเดิมของแทน)
    if bot.antispam_enabled and message.guild:
        user_id = message.author.id
        now = datetime.datetime.now().timestamp()

        if user_id not in bot.user_messages:
            bot.user_messages[user_id] = []
        
        bot.user_messages[user_id].append(now)
        bot.user_messages[user_id] = [t for t in bot.user_messages[user_id] if now - t < 5]

        if len(bot.user_messages[user_id]) >= 5:
            try:
                await message.delete()
            except:
                pass

            count = bot.warn_count.get(user_id, 0) + 1
            bot.warn_count[user_id] = count

            if count >= 3:
                duration = datetime.timedelta(minutes=5)
                try:
                    await message.author.timeout(duration, reason="สแปมข้อความเกินกำหนด")
                    try:
                        await message.author.send(f"⚠️ คุณถูกระงับการพิมพ์ในเซิร์ฟเวอร์ {message.guild.name} เป็นเวลา 5 นาที เนื่องจากสแปม")
                    except:
                        pass
                    bot.warn_count[user_id] = 0
                    bot.user_messages[user_id] = []
                except:
                    pass
            else:
                warning = await message.channel.send(f"⚠️ {message.author.mention} **หยุดสแปม!** เตือนครั้งที่ {count}/3")
                await asyncio.sleep(3)
                await warning.delete()

    # รันคำสั่ง Prefix ปกติของแทน (ถ้ามี)
    await bot.process_commands(message)

# ---------- 1. ระบบรายงานปัญหา (โค้ดเดิมของแทน) ----------
class ReportModal(discord.ui.Modal, title="รายงานปัญหาในเซิร์ฟเวอร์"):
    problem = discord.ui.TextInput(label="พิมพ์ปัญหาของคุณที่นี่", style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        owner = interaction.guild.owner
        try:
            await owner.send(f"📢 **มีรายงานใหม่จาก {interaction.user}**\n```{self.problem.value}```")
            embed = discord.Embed(title="✅ รายงานสำเร็จ!", description="ระบบได้ส่งข้อความไปหาเจ้าของเซิร์ฟแล้ว", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            embed = discord.Embed(title="❌ ส่งไม่สำเร็จ", description="ไม่สามารถส่ง DM ไปหาเจ้าของเซิร์ฟได้", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

class ReportButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="📩 รายงานปัญหา", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

@bot.tree.command(name="report", description="ตั้ง UI รายงานปัญหาในห้องที่เลือก")
async def report_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.send("📣 หากพบปัญหาในเซิร์ฟเวอร์ กดปุ่มด้านล่างเพื่อรายงาน", view=ReportButton())
    await interaction.response.send_message("✅ ตั้ง UI รายงานปัญหาเรียบร้อย!", ephemeral=True)

# ---------- 2. ระบบยืนยันตัวตน (โค้ดเดิมของแทน) ----------
class VerifyModal(discord.ui.Modal, title="ยืนยันตัวตน"):
    name = discord.ui.TextInput(label="กรอกชื่อของคุณ", style=discord.TextStyle.short)
    def __init__(self, verify_channel, success_channel, role):
        super().__init__()
        self.verify_channel = verify_channel
        self.success_channel = success_channel
        self.role = role

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        try:
            await self.success_channel.send(f"✅ {user.mention} ยืนยันตัวตนสำเร็จ! (ชื่อ: {self.name.value})")
            if self.role:
                await user.add_roles(self.role)
            embed = discord.Embed(title="🎉 ยืนยันตัวตนเรียบร้อย!", description=f"ขอบคุณ {user.mention}", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ บอทไม่มีสิทธิ์ให้ยศ กรุณาตรวจสอบสิทธิ์ใน Server Settings → Roles", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self, verify_channel, success_channel, role):
        super().__init__(timeout=None)
        self.verify_channel = verify_channel
        self.success_channel = success_channel
        self.role = role
    @discord.ui.button(label="✅ ยืนยันตัวตน", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal(self.verify_channel, self.success_channel, self.role))

@bot.tree.command(name="verify", description="ตั้งระบบยืนยันตัวตน")
async def verify_command(interaction: discord.Interaction, verify_channel: discord.TextChannel, success_channel: discord.TextChannel, role: discord.Role):
    await verify_channel.send("👤 กดยืนยันตัวตนด้านล่างเพื่อเริ่ม", view=VerifyButton(verify_channel, success_channel, role))
    await interaction.response.send_message("✅ ตั้งระบบยืนยันตัวตนเรียบร้อย!", ephemeral=True)

# ---------- 3. ส่งข้อความไปยังห้อง (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="send_message", description="ส่งข้อความไปยังห้องที่เลือก")
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message("✅ ส่งข้อความเรียบร้อย!", ephemeral=True)

# ---------- 4. ส่ง DM ทุกคน (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="dm_all", description="ส่ง DM ไปหาทุกคนในเซิร์ฟเวอร์")
async def dm_all(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("📨 กำลังส่ง DM ...", ephemeral=True)
    count = 0
    async for member in interaction.guild.fetch_members(limit=None):
        if not member.bot:
            try:
                await member.send(message)
                count += 1
            except:
                pass
    await interaction.followup.send(f"✅ ส่งข้อความถึง {count} คนแล้ว!", ephemeral=True)

# ---------- 5. ส่ง DM หนึ่งคน (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="dm_one", description="ส่ง DM ไปหาสมาชิกที่เลือก")
async def dm_one(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        await member.send(message)
        await interaction.response.send_message(f"✅ ส่งข้อความถึง {member} แล้ว!", ephemeral=True)
    except:
        await interaction.response.send_message("❌ ไม่สามารถส่งข้อความได้ (ปิด DM)", ephemeral=True)

# ---------- 6. ตั้งค่าห้องแจ้งคนเข้า/ออก (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="setup_welcome", description="ตั้งค่าห้องแจ้งคนเข้าออก")
async def setup_welcome(interaction: discord.Interaction, join_channel: discord.TextChannel, leave_channel: discord.TextChannel):
    welcome_settings[interaction.guild.id] = {"join": join_channel.id, "leave": leave_channel.id}
    await interaction.response.send_message("✅ ตั้งค่าห้องแจ้งคนเข้าออกเรียบร้อย!", ephemeral=True)

@bot.event
async def on_member_join(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["join"])
        if ch: await ch.send(f"👋 ยินดีต้อนรับ {member.mention} เข้าสู่เซิร์ฟเวอร์!")

@bot.event
async def on_member_remove(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["leave"])
        if ch: await ch.send(f"😢 {member} ได้ออกจากเซิร์ฟเวอร์แล้ว")

# ---------- เริ่มรันระบบ ----------
if __name__ == "__main__":
    keep_alive()
    # ดึง Token จาก Environment Variable ของ Render (ชื่อ TOKEN ตามที่ต้องการ)
    token = os.environ.get('TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ ไม่พบ TOKEN ใน Environment Variables!")
