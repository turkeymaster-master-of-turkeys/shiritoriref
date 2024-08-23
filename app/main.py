import logging
import os

import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
import botutils
from dotenv import load_dotenv

load_dotenv()

intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)
guilds = [643165990695206920, 931645765980393624]

logger = logging.getLogger("shiritori-ref")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='app.log',
    filemode='a'
)
logger.addHandler(logging.StreamHandler())


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')


@bot.slash_command(
    name="duel",
    description="Challenge someone to a duel",
    guild_ids=guilds,
)
async def duel(
        inter: nextcord.Interaction,
        user: nextcord.User = SlashOption(description="The person you want to duel", required=True),
        mode: str = SlashOption(description="The mode of the duel. Default: Normal",
                                choices=["normal", "speed"], required=False),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Start words with \"> \" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False)
):
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, [[inter.user], [user]], mode, chat)
        return

    view = botutils.get_view([user], lambda: initiate_duel(inter, [[user], [inter.user]], mode, chat))

    await inter.response.send_message(
        f"{user.mention}, you have been challenged to a duel by {inter.user.mention}!", view=view)


@bot.slash_command(
    name="survive",
    description="Start a survival mode game",
    guild_ids=guilds
)
async def survive(
        inter: nextcord.Interaction,
        players: str = SlashOption(description="The players in the game", required=False),
        chat: str = SlashOption(description="Enable chatting during the game.", required=False)
):
    players = list(set(bot.parse_mentions(players) + [inter.user])) if players else [inter.user]
    await inter.response.send_message("Let's start a survival game!")
    await initiate_duel(inter, [players], "survival", chat)


@bot.slash_command(
    name="battle",
    description="Challenge a team to a duel",
    guild_ids=guilds,
)
async def battle(
        inter: nextcord.Interaction,
        team1: str = SlashOption(description="The first team", required=True),
        team2: str = SlashOption(description="The second team", required=True),
        team3: str = SlashOption(description="The third team", required=False),
        team4: str = SlashOption(description="The fourth team", required=False),
        team5: str = SlashOption(description="The fifth team", required=False),
        mode: str = SlashOption(description="The mode of the duel. Default: Normal",
                                choices=["normal", "speed"], required=False),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Start words with \"> \" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False)
):
    team_1 = list(set(bot.parse_mentions(team1)))
    team_2 = list(set(bot.parse_mentions(team2)))
    team_3 = list(set(bot.parse_mentions(team3))) if team3 else []
    team_4 = list(set(bot.parse_mentions(team4))) if team4 else []
    team_5 = list(set(bot.parse_mentions(team5))) if team5 else []

    if len(team_1 + team_2 + team_3 + team_4 + team_5) != len(set(team_1 + team_2 + team_3 + team_4 + team_5)):
        await inter.response.send_message("The same person cannot be in multiple teams!", ephemeral=True)
        return

    teams = [team for team in [team_1, team_2, team_3, team_4, team_5] if team]
    t = team_1 + team_2 + team_3 + team_4 + team_5
    t.pop(t.index(inter.user))

    view = botutils.get_view(t, lambda: initiate_duel(inter, teams, mode, chat))

    await inter.response.send_message(f"{inter.user.display_name} has requested a battle!\n" +
                                      " vs ".join([botutils.team_to_string(team, mention=True) for team in teams]),
                                      view=view)


async def initiate_duel(
        inter: nextcord.Interaction, teams: list[list[nextcord.User]], mode, chat
):
    mode = mode or "normal"
    chat = chat or "on"

    if mode in ["normal", "speed"]:
        logger.info(f"{botutils.team_to_string(teams[0])} challenged {teams[1]}"
                    f" to a duel in {mode} mode with chat {chat}.")

    if mode == "survival":
        await inter.channel.send(f"Survival game started! {botutils.team_to_string(teams[0])}, you have 3 lives.")
    elif teams[1][0] != bot.user:
        await inter.channel.send(f"{botutils.team_to_string(teams[0])},"
                                 f" as the challenged, you have the right of the first word.")
    else:
        await inter.channel.send(f"Please note: this is an experimental feature and may not function correctly.")

    current = teams[0]
    previous_word = ""
    played_words = set()
    lives = {team[0].id: 3 for team in teams}

    async def wait_callback(check):
        return await bot.wait_for('message', timeout=15.0 if mode == "speed" else 60.0, check=check)

    while True:
        streak = len(played_words)
        logger.info(f"Streak {streak}, Lives: {lives}")
        current_id = current[0].id

        if lives[current_id] == 0:
            if mode == "survival":
                await inter.channel.send(f"You have lost all your lives! {botutils.team_to_string(current)},"
                                         f" you survived for {streak} words.")
                return
            else:
                await inter.channel.send(f"{botutils.team_to_string(current)} {"have" if len(current) > 1 else "has"}"
                                         f" lost all their lives. ")
                teams.pop(teams.index(current))
                if len(teams) == 1:
                    await inter.channel.send(f"{botutils.team_to_string(teams[0])} has won!")
                    return

        async def lose_life(message: str) -> None:
            lives[current_id] -= 1
            await inter.channel.send(f"{message} You have {lives[current_id]} lives remaining.")

        if current == bot.user:
            played_word = await botutils.take_bot_turn(inter, previous_word)
            if played_word:
                played_words.add(played_word)
                previous_word = played_word
                current = teams[(teams.index(current) + 1) % len(teams)]
                continue
            else:
                return

        if streak != 0 and streak % 5 == 0:
            if streak % 100 == 0:
                await inter.channel.send(f"The streak is {streak}!")
                await inter.channel.send(f"https://tenor.com/view/orangutan-driving-gif-24461244")
            if streak % 50 == 0:
                await inter.channel.send(f"The streak is {streak}! :orangutan::orangutan::orangutan:")
            if streak % 25 == 0:
                await inter.channel.send(f"The streak is {streak}! :fire::fire::fire:")
            elif streak % 10 == 0:
                await inter.channel.send(f"The streak is {streak}! :fire:")
            else:
                await inter.channel.send(f"The streak is {streak}!")

        (cont, played_word) = await botutils.take_user_turn(
            inter, current, mode, chat, previous_word, played_words, wait_callback, lose_life
        )

        if not cont:
            return
        if not played_word:
            continue

        played_words.add(played_word)
        previous_word = played_word
        current = teams[(teams.index(current) + 1) % len(teams)]


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
