import logging
import os

import nextcord
from dotenv import load_dotenv
from nextcord import SlashOption
from nextcord.ext import commands

import game_turns
from app.team import Team
from constants import *

load_dotenv()

intents = nextcord.Intents.all()
bot = commands.Bot(intents=intents)

logger = logging.getLogger("shiritori-ref")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')


@bot.slash_command(
    name="duel",
    description="Challenge someone to a duel",
    guild_ids=GUILDS,
)
async def duel(
        inter: nextcord.Interaction,
        user: nextcord.User = SlashOption(description="The person you want to duel", required=True),
        pace: str = SlashOption(description="The pace of the duel. Normal - 60s, Speed - 15s. Default: normal",
                                choices=[PACE_NORMAL, PACE_SPEED], required=False, default=PACE_NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the duel. Default: romaji",
                                      choices=[INPUT_ROMAJI, INPUT_KANA, INPUT_KANJI],
                                      required=False, default=INPUT_ROMAJI),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Start words with \"> \" or \"、 \" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False, default="on")
) -> None:
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, [Team([inter.user]), Team([user])], pace, input_mode, chat)
        return

    view = game_turns.DuelView(
        Team([user]), lambda: initiate_duel(inter, [Team([user]), Team([inter.user])], pace, input_mode, chat),
        "The duel request has timed out.")
    view.message = await inter.response.send_message(
        f"{user.mention}, you have been challenged to a"
        f" {pace} duel in {input_mode} by {inter.user.mention}!", view=view)


@bot.slash_command(
    name="survive",
    description="Start a survival mode game",
    guild_ids=GUILDS
)
async def survive(
        inter: nextcord.Interaction,
        players: str = SlashOption(description="The players in the game", required=False),
        vs_ref: bool = SlashOption(description="Play against the bot. default: true", required=False, default=True),
        pace: str = SlashOption(description="The pace of the game. Normal - 60s, Speed - 15s. Default: normal",
                                choices=[PACE_NORMAL, PACE_SPEED], required=False, default=PACE_NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the game. Default: romaji",
                                      choices=[INPUT_ROMAJI, INPUT_KANA, INPUT_KANJI],
                                      required=False, default=INPUT_ROMAJI),
        chat: str = SlashOption(description="Enable chatting during the game.", required=False)
) -> None:
    players = Team(list(set(bot.parse_mentions(players) + [inter.user])) if players else [inter.user])
    if vs_ref:
        await inter.response.send_message("Let's practice shiritori!")
        await initiate_duel(inter, [players, Team([bot.user])], pace, input_mode, chat)
    else:
        await inter.response.send_message("Let's start a survival game!")
        await initiate_duel(inter, [players], pace, input_mode, chat)


@bot.slash_command(
    name="battle",
    description="Challenge a team to a duel",
    guild_ids=GUILDS,
)
async def battle(
        inter: nextcord.Interaction,
        team1: str = SlashOption(description="The first team", required=True),
        team2: str = SlashOption(description="The second team", required=True),
        team3: str = SlashOption(description="The third team", required=False),
        team4: str = SlashOption(description="The fourth team", required=False),
        team5: str = SlashOption(description="The fifth team", required=False),
        pace: str = SlashOption(description="The pace of the battle. Normal - 60s, Speed - 15s. Default: normal",
                                choices=[PACE_NORMAL, PACE_SPEED], required=False, default=PACE_NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the battle. Default: romaji",
                                      choices=[INPUT_ROMAJI, INPUT_KANA, INPUT_KANJI],
                                      required=False, default=INPUT_ROMAJI),
        chat: str = SlashOption(description="Enable chatting during the duel."
                                            " Start words with \"> \" or \"、\" to submit in chat mode. Default: on",
                                choices=["on", "off"], required=False, default="on")
) -> None:
    team_1 = list(set(bot.parse_mentions(team1)))
    team_2 = list(set(bot.parse_mentions(team2)))
    team_3 = list(set(bot.parse_mentions(team3))) if team3 else []
    team_4 = list(set(bot.parse_mentions(team4))) if team4 else []
    team_5 = list(set(bot.parse_mentions(team5))) if team5 else []

    if len(team_1 + team_2 + team_3 + team_4 + team_5) != len(set(team_1 + team_2 + team_3 + team_4 + team_5)):
        await inter.response.send_message("The same person cannot be in multiple teams!", ephemeral=True)
        return

    teams = [Team(team) for team in [team_1, team_2, team_3, team_4, team_5] if team]
    all_players = team_1 + team_2 + team_3 + team_4 + team_5
    if inter.user not in all_players:
        await inter.response.send_message("You cannot challenge a team for someone else!", ephemeral=True)
        return
    all_players.pop(all_players.index(inter.user))

    if bot.user in all_players:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, teams, pace, input_mode, chat)
        return

    view = game_turns.DuelView(
        Team(all_players), lambda: initiate_duel(inter, teams, pace, input_mode, chat),
        "The battle request has timed out.")
    view.message = await inter.response.send_message(
        f"{inter.user.display_name} has requested a {pace} battle in {input_mode}!\n" +
        " vs ".join([team.to_string(mention=True) for team in teams]),
        view=view)


async def initiate_duel(
        inter: nextcord.Interaction, teams: list[Team], pace: str, input_mode: str, chat: str
) -> None:
    """
    Initiates a duel or battle.

    :param inter: Interaction object
    :param teams: List of teams
    :param pace: Pace of the game
    :param input_mode: Input mode
    :param chat: "on" or "off"
    :return:
    """
    if bot.user not in [u for team in teams for u in team.players]:
        await inter.channel.send(f"{teams[0].to_string()},"
                                 f" as the challenged, you have the right of the first word.")

    current_team = teams[0]
    words_state = {
        "prev_kata": "",
        "prev_kanji": "",
        "played_words": set()
    }
    lives = {team.id: 3 for team in teams}
    num_words_played = {user: 0 for team in teams for user in team.players}

    async def wait_callback(check):
        return await bot.wait_for('message', timeout=TIME_SPEED if pace == PACE_SPEED else TIME_NORMAL, check=check)

    async def knockout_team(team: Team) -> Team or None:
        index = teams.index(team)
        teams.pop(index)
        if len(teams) == 1:
            await inter.channel.send(f"{teams[0].to_string(mention=True)} has won!")
            return None
        return teams[index % len(teams)]

    while True:
        streak = len(words_state['played_words'])
        logger.info(f"Streak {streak}, Lives: {lives}, Words played: {num_words_played}")
        current_id = current_team[0].id

        async def lose_life(message: str) -> None:
            lives[current_id] -= 1
            await inter.channel.send(f"{message} You have {lives[current_id]} lives remaining.")

        if lives[current_id] <= 0:
            await inter.channel.send(f"{current_team.to_string()} {'have' if len(current_team) > 1 else 'has'}"
                                     f" lost all their lives. ")
            current_team = await knockout_team(current_team)
            if not current_team:
                break

        # Bot's turn
        if bot.user in current_team:
            (played_kata, played_kanji) = await game_turns.take_bot_turn(inter, words_state)
            logger.info(f"Bot played {played_kata}")
            if played_kata:
                words_state = {
                    "prev_kata": played_kata,
                    "prev_kanji": played_kanji,
                    "played_words": words_state['played_words'].union({played_kata})
                }
                current_team = teams[(teams.index(current_team) + 1) % len(teams)]
                num_words_played[bot.user] += 1
                continue
            else:
                break

        await game_turns.announce_streak(inter, streak)

        # User's turn
        (cont, played_kata, played_kanji, player) = await game_turns.take_user_turn(
            inter, current_team, pace, input_mode, chat, words_state, wait_callback, lose_life
        )

        if not cont:
            current_team = await knockout_team(current_team)
            if not current_team:
                break
            continue
        if not played_kata:
            continue

        words_state = {
            "prev_kata": played_kata,
            "prev_kanji": played_kanji,
            "played_words": words_state['played_words'].union({played_kata})
        }
        current_team = teams[(teams.index(current_team) + 1) % len(teams)]
        num_words_played[player] += 1

    # The game has ended
    await inter.channel.send(
        f"The final streak was {streak}!\n" +
        "\n".join([f"{user.global_name or user.display_name} played {num} words"
                   for user, num in num_words_played.items()]))


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
