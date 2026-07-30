import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import os
import asyncio
from datetime import datetime
from typing import Literal
import base64
import requests

# ================= GitHub Sync Configuration =================
GITHUB_TOKEN = osdjgUIHDSUHG
GITHUB_REPO = "faresx100/kings-league"

def update_github_data():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/data.json"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # 1. جلب sha للملف الموجود على GitHub
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    # 2. قراءة الملف المحلي وتشفيره
    with open("data.json", "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "message": "Auto-update data.json from Discord Bot",
        "content": content
    }

    # إضافة sha فقط إذا كان الملف موجوداً سابقاً
    if sha:
        payload["sha"] = sha

    # 3. إرسال التحديث وطباعة النتيجة في CMD
    res = requests.put(url, json=payload, headers=headers)

    if res.status_code in [200, 201]:
        print("✅ تم تحديث البيانات على GitHub بنجاح!")
    else:
        print(f"❌ فشل التحديث على GitHub! رمز الخطأ: {res.status_code}")
        print(res.json())

# ================= CONFIGURATION =================
TOKEN = "idsUIHSERUosjkedifjSIEJF"
GUILD_ID = 1399563718580244692

# Channel IDs
ADMIN_APP_CHANNEL_ID = 1402003214785708114
SIGNING_CHANNEL_ID   = 1401008749581308015
ROSTER_CHANNEL_ID    = 1401009153706823690
FIXTURES_CHANNEL_ID  = 1401013041490956410
RESULT_CHANNEL_ID    = 1401013712147447979
LOANS_CHANNEL_ID     = 1531979357793419304
RELEASE_CHANNEL_ID   = 1531980077863010334

# Role IDs
MANAGER_ROLE_ID    = 1400489346087391263
CO_MANAGER_ROLE_ID = 1400490121240903792

KINGS_LEAGUE_LOGO = "https://i.imgur.com/8Q9Z5b3.png"
MAX_NEWS_ITEMS = 8
# =================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Helpers for data management
def load_data():
    if not os.path.exists('data.json'):
        return {
            "standings": [], "news": [], "matches": [], "rosters": {},
            "last_fixtures": [], "top_scorers": {}, "top_assists": {},
            "man_of_the_match": None,
            "team_of_the_week": {"GK": "N/A", "CB": "N/A", "CM": "N/A", "LST": "N/A", "RST": "N/A"}
        }
    with open('data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_website_news(data, title, content, badge="NEWS"):
    if "news" not in data:
        data["news"] = []
    data["news"].insert(0, {
        "title": title,
        "content": content,
        "badge": badge,
        "timestamp": datetime.now().strftime("%H:%M - %b %d")
    })
    if len(data["news"]) > MAX_NEWS_ITEMS:
        data["news"] = data["news"][:MAX_NEWS_ITEMS]

# Permission & Role Checks
def is_team_leader(interaction: discord.Interaction) -> bool:
    user_role_ids = [r.id for r in interaction.user.roles]
    return (
        MANAGER_ROLE_ID in user_role_ids
        or CO_MANAGER_ROLE_ID in user_role_ids
        or interaction.user.guild_permissions.administrator
    )

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator

def get_team_role(user: discord.Member) -> discord.Role:
    return next((r for r in user.roles if r.id not in [MANAGER_ROLE_ID, CO_MANAGER_ROLE_ID] and r.name != "@everyone"), None)

@bot.event
async def on_ready():
    print(f"✅ Kings League Bot is online as {bot.user}!")
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("⚡️ All slash commands synced successfully with updated permissions & Role IDs!")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# ==========================================
# 1. PRIVATE DM APPLICATION WORKFLOW (/apply)
# ==========================================

class AdminApproveView(discord.ui.View):
    def __init__(self, applicant_id, co_mention, team_name, team_abbr, logo_url):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.co_mention = co_mention
        self.team_name = team_name
        self.team_abbr = team_abbr
        self.logo_url = logo_url

    @discord.ui.button(label="Approve Team", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only server Administrators can approve teams!", ephemeral=True)
            return

        # 💡 منع التعليق
        await interaction.response.defer()

        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)

        m_role = guild.get_role(MANAGER_ROLE_ID)
        if applicant and m_role:
            await applicant.add_roles(m_role)

        if self.co_mention and self.co_mention.lower() not in ["none", "n/a", "no"]:
            co_id = ''.join(filter(str.isdigit, self.co_mention))
            if co_id:
                co_member = guild.get_member(int(co_id))
                co_role = guild.get_role(CO_MANAGER_ROLE_ID)
                if co_member and co_role:
                    await co_member.add_roles(co_role)

        team_role = await guild.create_role(name=self.team_name, color=discord.Color.blue())
        if applicant:
            await applicant.add_roles(team_role)

        data = load_data()
        data["standings"].append({
            "name": self.team_name,
            "abbr": self.team_abbr,
            "logo": self.logo_url,
            "pts": 0, "mp": 0, "w": 0, "l": 0, "gf": 0, "ga": 0
        })
        data["rosters"][self.team_name] = [applicant.display_name if applicant else "Manager"]
        add_website_news(data, "NEW TEAM JOINED", f"{self.team_name} ({self.team_abbr}) has officially joined Kings League!", "NEW TEAM")
        
        save_data(data)
        update_github_data() # 🚀 رفع البيانات

        button.disabled = True
        button.label = "Approved ✅"
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(f"🎉 Team **{self.team_name}** approved and added to official standings!")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("❌ Only server Administrators can reject teams!", ephemeral=True)
            return

        button.disabled = True
        button.label = "Rejected ❌"
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="apply", description="Open for EVERYONE: Submit a team registration application via Direct Messages (DM)")
async def apply(interaction: discord.Interaction):
    user = interaction.user

    try:
        dm_channel = await user.create_dm()
        await interaction.response.send_message("📩 Application started! Please check your **Direct Messages (DMs)** to complete registration.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("❌ Could not open DMs! Please enable 'Allow Direct Messages from server members' in your Settings.", ephemeral=True)
        return

    def check(m):
        return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

    try:
        await dm_channel.send("📋 **KINGS LEAGUE TEAM APPLICATION**\n\n**Step 1/6:** What is your **Full Team Name**? (e.g. Barcelona FC)")
        msg_name = await bot.wait_for('message', check=check, timeout=120.0)
        team_name = msg_name.content

        await dm_channel.send("**Step 2/6:** What is your **Team Abbreviation**? (e.g. BAR)")
        msg_abbr = await bot.wait_for('message', check=check, timeout=120.0)
        team_abbr = msg_abbr.content.upper()

        await dm_channel.send("**Step 3/6:** Do you have a Co-Manager? Please **mention them** (e.g. `@Username`), or type `None` if none.")
        msg_co = await bot.wait_for('message', check=check, timeout=120.0)
        co_mention = msg_co.content

        await dm_channel.send("**Step 4/6:** Please upload/send an image file of your **Official Team Logo**.")
        def check_img(m):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel) and len(m.attachments) > 0

        msg_logo = await bot.wait_for('message', check=check_img, timeout=120.0)
        logo_url = msg_logo.attachments[0].url

        await dm_channel.send("**Step 5/6:** Please upload/send an image file of your **Latest Activity Check**.")
        msg_act = await bot.wait_for('message', check=check_img, timeout=120.0)
        activity_url = msg_act.attachments[0].url

        await dm_channel.send("**Step 6/6:** How many total members are in your team right now? (Send a number)")
        def check_num(m):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel) and m.content.isdigit()
        
        msg_num = await bot.wait_for('message', check=check_num, timeout=120.0)
        member_count = msg_num.content

        admin_channel = bot.get_channel(ADMIN_APP_CHANNEL_ID)
        embed = discord.Embed(title="📋 NEW TEAM REGISTRATION APPLICATION", color=discord.Color.gold())
        embed.add_field(name="Applicant Manager", value=user.mention, inline=True)
        embed.add_field(name="Full Team Name", value=team_name, inline=True)
        embed.add_field(name="Abbreviation", value=team_abbr, inline=True)
        embed.add_field(name="Co-Manager Mention", value=co_mention, inline=True)
        embed.add_field(name="Member Count", value=member_count, inline=True)
        embed.set_thumbnail(url=logo_url)
        embed.set_image(url=activity_url)

        view = AdminApproveView(
            applicant_id=user.id,
            co_mention=co_mention,
            team_name=team_name,
            team_abbr=team_abbr,
            logo_url=logo_url
        )
        await admin_channel.send(embed=embed, view=view)
        await dm_channel.send("✅ **Application Submitted!** Staff members will review your request shortly.")

    except asyncio.TimeoutError:
        await dm_channel.send("⏱️ **Application Timed Out.** Please type `/apply` in the server to try again.")
    except Exception as e:
        await dm_channel.send(f"❌ An error occurred during submission: {e}")

# ==========================================
# 2. MANAGER COMMANDS (/sign, /release, /loan)
# ==========================================

class SignConfirmationView(discord.ui.View):
    def __init__(self, manager: discord.Member, player: discord.Member, team_name: str, in_game_name: str, team_role: discord.Role, team_logo: str):
        super().__init__(timeout=120)
        self.manager = manager
        self.player = player
        self.team_name = team_name
        self.in_game_name = in_game_name
        self.team_role = team_role
        self.team_logo = team_logo

    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This offer is not for you!", ephemeral=True)
            return

        # 💡 منع التعليق هنا
        await interaction.response.defer()

        await self.player.add_roles(self.team_role)

        data = load_data()
        if self.team_name not in data["rosters"]:
            data["rosters"][self.team_name] = []
        data["rosters"][self.team_name].append(self.in_game_name)

        add_website_news(data, "PLAYER TRANSFER", f"{self.in_game_name} ({self.player.mention}) signed for {self.team_name}!", "SIGNING")
        
        save_data(data)
        update_github_data() # 🚀 رفع البيانات

        current_count = len(data["rosters"][self.team_name])

        sign_channel = bot.get_channel(SIGNING_CHANNEL_ID)
        embed = discord.Embed(
            title="📝 OFFICIAL SIGNING",
            description=f"**{self.player.mention}** has officially transferred to **{self.team_name}**!\n\n**Team Roster Count:** `{current_count}/8`",
            color=discord.Color.green()
        )
        embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
        embed.set_thumbnail(url=self.team_logo)
        await sign_channel.send(embed=embed)

        roster_channel = bot.get_channel(ROSTER_CHANNEL_ID)
        roster_embed = discord.Embed(title=f"🛡 {self.team_name} Updated Roster", color=discord.Color.gold())
        roster_text = "\n".join([f"• {p}" for p in data["rosters"][self.team_name]])
        roster_embed.add_field(name="Players Registered", value=roster_text or "No players", inline=False)
        roster_embed.set_thumbnail(url=self.team_logo)
        await roster_channel.send(embed=roster_embed)

        await interaction.followup.send(f"✅ Contract accepted! You joined **{self.team_name}**.")

    @discord.ui.button(label="Decline Offer", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            return
        await interaction.response.send_message("❌ Contract offer declined.", ephemeral=True)

@bot.tree.command(name="sign", description="For Managers/Co-Managers: Sign a player to your team roster")
@app_commands.describe(
    player="Select the Discord member you want to sign",
    player_in_game_name="Write the in-game display name / gamertag of the player"
)
async def sign(interaction: discord.Interaction, player: discord.Member, player_in_game_name: str):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return

    team_role = get_team_role(interaction.user)
    if not team_role:
        await interaction.response.send_message("❌ Team Error: Could not detect your team role!", ephemeral=True)
        return

    data = load_data()
    team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)

    # Fancy & Clean DM Contract Offer Embed
    offer_embed = discord.Embed(
        title="📝 OFFICIAL CONTRACT OFFER",
        description=f"You have received a formal offer to join **{team_role.name}** for Kings League VRFS.",
        color=discord.Color.gold()
    )
    offer_embed.set_author(name=f"{team_role.name} Management", icon_url=team_logo)
    offer_embed.set_thumbnail(url=team_logo)
    offer_embed.add_field(name="Club Name", value=f"**{team_role.name}**", inline=True)
    offer_embed.add_field(name="Submitted By", value=interaction.user.mention, inline=True)
    offer_embed.add_field(name="Registered Gamertag", value=f"`{player_in_game_name}`", inline=False)
    offer_embed.set_footer(text="Kings League VRFS • Select an option below to respond", icon_url=KINGS_LEAGUE_LOGO)

    view = SignConfirmationView(interaction.user, player, team_role.name, player_in_game_name, team_role, team_logo)
    await interaction.response.send_message(f"📨 Transfer offer sent privately to {player.mention}!", ephemeral=True)
    
    try:
        await player.send(embed=offer_embed, view=view)
    except Exception:
        await interaction.followup.send(f"❌ Failed to send DM to {player.mention}. Their DMs might be closed.", ephemeral=True)


@bot.tree.command(name="release", description="For Managers/Co-Managers: Release a player from your team roster")
@app_commands.describe(player="Select the player you want to remove/release from your team")
async def release(interaction: discord.Interaction, player: discord.Member):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return
        
    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    team_role = get_team_role(interaction.user)
    if not team_role or team_role not in player.roles:
        await interaction.followup.send("❌ Release Error: This player does not belong to your team!", ephemeral=True)
        return

    await player.remove_roles(team_role)

    data = load_data()
    team_logo = next((t["logo"] for t in data["standings"] if t["name"] == team_role.name), KINGS_LEAGUE_LOGO)

    if team_role.name in data["rosters"]:
        data["rosters"][team_role.name] = [p for p in data["rosters"][team_role.name] if player.display_name not in p]

    add_website_news(data, "PLAYER RELEASED", f"{player.display_name} ({player.mention}) has been released from {team_role.name}.", "RELEASE")
    
    save_data(data)
    update_github_data() # 🚀 رفع البيانات

    rel_channel = bot.get_channel(RELEASE_CHANNEL_ID)
    embed = discord.Embed(
        title="🔴 CONTRACT TERMINATED",
        description=f"**{player.mention}** has been released from **{team_role.name}**.",
        color=discord.Color.red()
    )
    embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
    embed.set_thumbnail(url=team_logo)
    await rel_channel.send(embed=embed)

    roster_channel = bot.get_channel(ROSTER_CHANNEL_ID)
    roster_embed = discord.Embed(title=f"🛡 {team_role.name} Updated Roster", color=discord.Color.gold())
    roster_text = "\n".join([f"• {p}" for p in data["rosters"].get(team_role.name, [])])
    roster_embed.add_field(name="Players Registered", value=roster_text or "No players", inline=False)
    roster_embed.set_thumbnail(url=team_logo)
    await roster_channel.send(embed=roster_embed)

    await interaction.followup.send(f"✅ Released {player.mention} from **{team_role.name}** successfully.", ephemeral=True)


async def emergency_loan_timer(guild: discord.Guild, player: discord.Member, team_role: discord.Role):
    await asyncio.sleep(2400) # 40 Minutes
    if team_role in player.roles:
        await player.remove_roles(team_role)
        data = load_data()
        if team_role.name in data["rosters"]:
            data["rosters"][team_role.name] = [p for p in data["rosters"][team_role.name] if player.display_name not in p]
        add_website_news(data, "E-LOAN EXPIRED", f"Emergency 40-minute loan for {player.display_name} at {team_role.name} has concluded.", "E-LOAN")
        
        save_data(data)
        update_github_data() # 🚀 رفع البيانات عند انتهاء الإعارة

@bot.tree.command(name="loan", description="For Managers/Co-Managers: Loan a player (Standard or Emergency 40-min Loan)")
@app_commands.describe(
    loan_type="Choose type: 'Loan' (Standard >=3 matches) or 'E-Loan' (Emergency 40 mins)",
    player="Select the player to borrow/loan to your team",
    duration_or_notes="Write duration or match time (e.g., '3 Matches' or 'Match vs Real Madrid at 9 PM')"
)
async def loan(interaction: discord.Interaction, loan_type: Literal['Loan', 'E-Loan'], player: discord.Member, duration_or_notes: str):
    if not is_team_leader(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only Managers or Co-Managers can use this command!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    team_role = get_team_role(interaction.user)
    if not team_role:
        await interaction.followup.send("❌ Team Error: Could not detect your team role!", ephemeral=True)
        return

    await player.add_roles(team_role)

    data = load_data()
    if team_role.name not in data["rosters"]:
        data["rosters"][team_role.name] = []
    data["rosters"][team_role.name].append(f"{player.display_name} ({loan_type})")

    add_website_news(data, f"{loan_type.upper()} ARRIVAL", f"{player.mention} joined {team_role.name} on a {loan_type}! ({duration_or_notes})", "LOAN")
    
    save_data(data)
    update_github_data() # 🚀 رفع البيانات

    loan_chan = bot.get_channel(LOANS_CHANNEL_ID)
    embed = discord.Embed(
        title=f"🔄 NEW {loan_type.upper()}",
        description=f"**{player.mention}** joined **{team_role.name}**!\n**Type:** {loan_type}\n**Details:** {duration_or_notes}",
        color=discord.Color.purple()
    )
    embed.set_author(name="Kings League VRFS", icon_url=KINGS_LEAGUE_LOGO)
    await loan_chan.send(embed=embed)

    if loan_type == "E-Loan":
        asyncio.create_task(emergency_loan_timer(interaction.guild, player, team_role))
        await interaction.followup.send(f"✅ Emergency Loan (40 mins countdown) active for {player.mention}!", ephemeral=True)
    else:
        await interaction.followup.send(f"✅ Regular Loan logged for {player.mention}!", ephemeral=True)

# ==========================================
# 3. ADMINISTRATOR ONLY COMMANDS
# ==========================================

@bot.tree.command(name="result", description="ADMIN ONLY: Submit match scores and update website standings & stats")
@app_commands.describe(
    team1="Select the first team role",
    score1="Goals scored by Team 1",
    team2="Select the second team role",
    score2="Goals scored by Team 2",
    team1_scorers="Mention players who scored for Team 1 (Repeat mention if multiple goals, e.g. @Player @Player)",
    team2_scorers="Mention players who scored for Team 2",
    team1_assists="Mention players who assisted for Team 1",
    team2_assists="Mention players who assisted for Team 2",
    cb_clean_sheets="Mention CB players who kept a clean sheet (Leave empty if none)",
    gk_clean_sheets="Mention GK players who kept a clean sheet (Leave empty if none)"
)
async def result(
    interaction: discord.Interaction,
    team1: discord.Role, score1: int,
    team2: discord.Role, score2: int,
    team1_scorers: str = "", team2_scorers: str = "",
    team1_assists: str = "", team2_assists: str = "",
    cb_clean_sheets: str = "", gk_clean_sheets: str = ""
):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can record match results!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    data = load_data()

    for t in data["standings"]:
        if t["name"] == team1.name:
            t["mp"] += 1; t["gf"] += score1; t["ga"] += score2
            if score1 > score2: t["w"] += 1; t["pts"] += 3
            elif score1 == score2: t["pts"] += 1
            else: t["l"] += 1
        elif t["name"] == team2.name:
            t["mp"] += 1; t["gf"] += score2; t["ga"] += score1
            if score2 > score1: t["w"] += 1; t["pts"] += 3
            elif score1 == score2: t["pts"] += 1
            else: t["l"] += 1

    data["standings"].sort(key=lambda x: (x["pts"], x["gf"] - x["ga"]), reverse=True)

    scorers = (team1_scorers + " " + team2_scorers).split()
    for sc in scorers:
        if sc.strip():
            data["top_scorers"][sc] = data["top_scorers"].get(sc, 0) + 1
            if data["top_scorers"][sc] >= 2:
                add_website_news(data, "PERFORMANCE HIGHLIGHT", f"Player {sc} scored {data['top_scorers'][sc]} goals in recent matches!", "TOP SCORER")

    assists = (team1_assists + " " + team2_assists).split()
    for ast in assists:
        if ast.strip():
            data["top_assists"][ast] = data["top_assists"].get(ast, 0) + 1

    res_chan = bot.get_channel(RESULT_CHANNEL_ID)
    embed = discord.Embed(title="⚽️ MATCH RESULT", description=f"**{team1.mention} {score1} - {score2} {team2.mention}**", color=discord.Color.gold())
    if team1_scorers or team2_scorers: embed.add_field(name="Scorers", value=f"{team1.name}: {team1_scorers}\n{team2.name}: {team2_scorers}", inline=False)
    if cb_clean_sheets or gk_clean_sheets: embed.add_field(name="Clean Sheets", value=f"CB: {cb_clean_sheets} | GK: {gk_clean_sheets}", inline=False)
    await res_chan.send(embed=embed)

    save_data(data)
    update_github_data() # 🚀 رفع البيانات
    
    await interaction.followup.send("✅ Result recorded and website updated!", ephemeral=True)


@bot.tree.command(name="fixtures", description="ADMIN ONLY: Generate new match fixtures without repeating last round")
@app_commands.describe(
    team1="Select Team Role 1", team2="Select Team Role 2",
    team3="Select Team Role 3", team4="Select Team Role 4",
    team5="Select Team Role 5", team6="Select Team Role 6"
)
async def fixtures(interaction: discord.Interaction, team1: discord.Role, team2: discord.Role, team3: discord.Role, team4: discord.Role, team5: discord.Role, team6: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can generate fixtures!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    teams = [team1, team2, team3, team4, team5, team6]
    data = load_data()

    pairs = []
    for _ in range(20):
        shuffled = teams.copy()
        random.shuffle(shuffled)
        candidate = [(shuffled[0], shuffled[1]), (shuffled[2], shuffled[3]), (shuffled[4], shuffled[5])]
        last = data.get("last_fixtures", [])
        if not any({p1.name, p2.name} in [set(lp) for lp in last] for p1, p2 in candidate):
            pairs = candidate
            break
    if not pairs: pairs = candidate

    data["last_fixtures"] = [[p1.name, p2.name] for p1, p2 in pairs]

    web_matches = []
    embed = discord.Embed(title="⚽️ KINGS LEAGUE FIXTURES", color=discord.Color.gold())

    for idx, (t1, t2) in enumerate(pairs, 1):
        t1_info = next((i for i in data["standings"] if i["name"] == t1.name), {"abbr": t1.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})
        t2_info = next((i for i in data["standings"] if i["name"] == t2.name), {"abbr": t2.name[:3].upper(), "logo": KINGS_LEAGUE_LOGO})

        embed.add_field(name=f"Match {idx}", value=f"🛡 **{t1.name}** VS 🛡 **{t2.name}**", inline=False)
        web_matches.append({
            "header": f"Match {idx}", "t1_name": t1_info["abbr"], "t1_logo": t1_info["logo"],
            "t2_name": t2_info["abbr"], "t2_logo": t2_info["logo"], "status": "UPCOMING"
        })

    data["matches"] = web_matches
    
    save_data(data)
    update_github_data() # 🚀 رفع البيانات

    fix_chan = bot.get_channel(FIXTURES_CHANNEL_ID)
    await fix_chan.send(embed=embed)
    await interaction.followup.send("✅ Fixtures generated and sent!", ephemeral=True)


@bot.tree.command(name="man_of_the_match", description="ADMIN ONLY: Set Man of the Match and display on the website")
@app_commands.describe(
    player="Select the player awarded Man of the Match",
    performance_reason="Write why they won (e.g., 'Scored 3 goals & 1 assist vs Barca')"
)
async def man_of_the_match(interaction: discord.Interaction, player: discord.Member, performance_reason: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can set Man of the Match!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    data = load_data()
    data["man_of_the_match"] = {"name": player.display_name, "avatar": player.display_avatar.url, "details": performance_reason}
    add_website_news(data, "MAN OF THE MATCH", f"{player.display_name} awarded Man of the Match! ({performance_reason})", "MOTM")
    
    save_data(data)
    update_github_data() # 🚀 رفع البيانات
    
    await interaction.followup.send(f"🌟 Set Man of the Match to {player.mention}!", ephemeral=True)


@bot.tree.command(name="team_of_the_week", description="ADMIN ONLY: Update Team of the Week (5 lineup positions) on website")
@app_commands.describe(
    gk="Select Goalkeeper player",
    cb="Select Center Back player",
    cm="Select Central Midfielder player",
    lst="Select Left Striker player",
    rst="Select Right Striker player"
)
async def team_of_the_week(interaction: discord.Interaction, gk: discord.Member, cb: discord.Member, cm: discord.Member, lst: discord.Member, rst: discord.Member):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can set Team of the Week!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    data = load_data()
    data["team_of_the_week"] = {
        "GK": gk.display_name, "CB": cb.display_name, "CM": cm.display_name, "LST": lst.display_name, "RST": rst.display_name
    }
    add_website_news(data, "TEAM OF THE WEEK", "The official Team of the Week lineup has been updated!", "TOTW")
    
    save_data(data)
    update_github_data() # 🚀 رفع البيانات
    
    await interaction.followup.send("⭐️ Team of the Week updated on website!", ephemeral=True)


@bot.tree.command(name="restart", description="ADMIN ONLY: Reset all league data and website records")
async def restart(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ Permission Denied: Only server Administrators can reset league data!", ephemeral=True)
        return

    # 💡 منع التعليق هنا
    await interaction.response.defer(ephemeral=True)

    save_data({
        "standings": [], "news": [], "matches": [], "rosters": {},
        "last_fixtures": [], "top_scorers": {}, "top_assists": {},
        "man_of_the_match": None,
        "team_of_the_week": {"GK": "N/A", "CB": "N/A", "CM": "N/A", "LST": "N/A", "RST": "N/A"}
    })
    
    update_github_data() # 🚀 رفع البيانات
    
    await interaction.followup.send("🔄 Data completely reset!", ephemeral=True)

bot.run(TOKEN)
