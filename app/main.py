import logging
import nextcord
from nextcord import SlashOption
from nextcord.ext import commands
import botutils

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
                                choices=["Normal", "Speed"], required=False),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Wrap your words in \" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False)
):
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, inter.user, user, mode, chat)
        return

    view = botutils.get_view(user, lambda: initiate_duel(inter, inter.user, user, mode, chat))

    await inter.response.send_message(
        f"{user.mention}, you have been challenged to a duel by {inter.user.mention}!", view=view)


@bot.slash_command(
    name="survive",
    description="Start a survival mode game",
    guild_ids=guilds
)
async def survive(
        inter: nextcord.Interaction,
        chat: str = SlashOption(description="Enable chatting during the game.", required=False)
):
    await inter.response.send_message("Let's start a survival game!")
    await initiate_duel(inter, inter.user, inter.user, "survival", chat)


async def initiate_duel(
        inter: nextcord.Interaction, challenger: nextcord.User, challenged: nextcord.User, mode, chat
):
    mode = mode or "Normal"
    chat = chat or "on"
    logger.info(f"{challenger} challenged {challenged} to a duel in {mode} mode with chat {chat}.")

    if mode == "survival":
        await inter.channel.send("Survival game started! You have 3 lives.")
    elif challenged != bot.user:
        await inter.channel.send(f"{challenged.display_name}, as the challenged, you have the right of the first word.")

    current = challenger if challenged == bot.user else challenged
    previous_word = ""
    played_words = set()
    lives = {0: 3} if mode == "survival" else {challenger.id: 3, challenged.id: 3}

    async def wait_callback(check):
        return await bot.wait_for(
            'message', timeout=15.0 if mode == "Speed" else 60.0, check=check)

    while True:
        streak = len(played_words)
        logger.info(f"Streak {streak}, Lives: {lives}")
        current_id = 0 if mode == "survival" else current.id

        if lives[current_id] == 0:
            if mode == "survival":
                await inter.channel.send(f"You have lost all your lives! You survived for {streak} words.")
            else:
                await inter.channel.send(f"{current.mention} has lost all their lives. "
                                         f"{challenger if current == challenged else challenged} wins!")
            return

        async def lose_life(message: str) -> None:
            lives[current_id] -= 1
            await inter.channel.send(f"{message} You have {lives[current_id]} lives remaining.")

        if current == bot.user:
            played_word = await botutils.take_bot_turn(inter, previous_word, played_words)
            if played_word:
                played_words.add(played_word)
                previous_word = played_word
                current = challenger
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
        if mode != "survival":
            current = challenger if current == challenged else challenged


if __name__ == '__main__':
    bot.run("")
