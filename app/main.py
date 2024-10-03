import logging
import os

import nextcord
from dotenv import load_dotenv
from nextcord import SlashOption
from nextcord.ext import commands

import game_turns
from app.game_options import *
from app.game_state import GameState
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
        pace: str = SlashOption(description=f"The pace of the duel. Normal - 60s, Speed - 15s. Default: {Pace.NORMAL}",
                                choices=Pace.choices(), required=False, default=Pace.NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the duel. "
                                                  f"Default: {InputMode.ROMAJI}",
                                      choices=InputMode.choices(),
                                      required=False, default=InputMode.ROMAJI),
        chat_on: bool = SlashOption(description="Enable chatting during the duel. Start words with \"> \" or \"、\" "
                                                "to submit in chat mode. Default: true",
                                    required=False, default=True)
) -> None:
    if user == inter.user:
        await inter.response.send_message("You cannot duel yourself!", ephemeral=True)
        return

    options = GameOptions(Pace(pace), InputMode(input_mode), chat_on)

    if user == bot.user:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, [Team([inter.user]), Team([user])], options)
        return

    view = game_turns.DuelView(
        Team([user]), lambda: initiate_duel(inter, [Team([user]), Team([inter.user])], options),
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
        pace: str = SlashOption(description=f"The pace of the game. Normal - 60s, Speed - 15s. Default: {Pace.NORMAL}",
                                choices=Pace.choices(), required=False, default=Pace.NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the game. "
                                                  f"Default: {InputMode.ROMAJI}",
                                      choices=InputMode.choices(),
                                      required=False, default=InputMode.ROMAJI),
        chat_on: bool = SlashOption(description="Enable chatting during the duel. Start words with \"> \" or \"、\" "
                                                "to submit in chat mode. Default: on",
                                    required=False, default=True)
) -> None:
    players = Team(list(set(bot.parse_mentions(players) + [inter.user])) if players else [inter.user])
    options = GameOptions(Pace(pace), InputMode(input_mode), chat_on)
    if vs_ref:
        await inter.response.send_message("Let's practice shiritori!")
        await initiate_duel(inter, [players, Team([bot.user])], options)
    else:
        await inter.response.send_message("Let's start a survival game!")
        await initiate_duel(inter, [players], options)


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
        pace: str = SlashOption(description=f"The pace of the battle. Normal - 60s, Speed - 15s. "
                                            f"Default: {Pace.NORMAL}",
                                choices=Pace.choices(), required=False, default=Pace.NORMAL),
        input_mode: str = SlashOption(description="The lowest allowed level input mode of the battle. "
                                                  f"Default: {InputMode.ROMAJI}",
                                      choices=InputMode.choices(),
                                      required=False, default=InputMode.ROMAJI),
        chat_on: bool = SlashOption(description="Enable chatting during the duel. Start words with \"> \" or \"、\" "
                                                "to submit in chat mode. Default: on",
                                    required=False, default=True)
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

    options = GameOptions(Pace(pace), InputMode(input_mode), chat_on)

    if bot.user in all_players:
        await inter.response.send_message("Lets practice Shiritori!")
        await initiate_duel(inter, teams, options)
        return

    view = game_turns.DuelView(
        Team(all_players), lambda: initiate_duel(inter, teams, options),
        "The battle request has timed out.")
    view.message = await inter.response.send_message(
        f"{inter.user.display_name} has requested a {pace} battle in {input_mode}!\n" +
        " vs ".join([team.to_string(mention=True) for team in teams]),
        view=view)


async def initiate_duel(
        inter: nextcord.Interaction, teams: list[Team], options: GameOptions
) -> None:
    """
    Initiates a duel or battle.

    :param inter: Interaction object
    :param teams: List of teams
    :param options: Game options
    :return:
    """
    if bot.user not in [u for team in teams for u in team.players]:
        await inter.channel.send(f"{teams[0].to_string()},"
                                 f" as the challenged, you have the right of the first word.")
    game_state = GameState(teams)

    async def wait_for_user_input(check) -> nextcord.Message:
        return await bot.wait_for(
            'message', timeout=TIME_SPEED if options.pace == Pace.SPEED else TIME_NORMAL, check=check)

    while True:
        logger.info(
            f"Streak {game_state.get_streak()}, Lives: {game_state.lives}, Words played: {game_state.num_words_played}")
        current_id = game_state.current_team.id

        if game_state.lives[current_id] <= 0:
            await inter.channel.send(
                f"{game_state.current_team.to_string()} {'have' if len(game_state.current_team) > 1 else 'has'}"
                f" lost all their lives. ")
            finished = game_state.knockout_team()
            if finished:
                await inter.channel.send(f"{game_state.current_team.to_string(mention=True)} has won!")
                break

        # Bot's turn
        if bot.user in game_state.current_team:
            (played_kata, played_kanji) = await game_turns.take_bot_turn(inter, game_state)
            logger.info(f"Bot played {played_kata}")
            if played_kata:
                game_state.prev_kata = played_kata
                game_state.prev_kanji = played_kanji
                game_state.played_words.add(played_kata)
                game_state.current_team = teams[(teams.index(game_state.current_team) + 1) % len(teams)]
                game_state.num_words_played[bot.user] += 1
                continue
            else:
                break

        await game_state.announce_streak(inter)

        # User's turn
        (is_alive, played_kata, played_kanji, player) = await game_turns.take_user_turn(
            inter, options, game_state, wait_for_user_input
        )

        if not is_alive:
            finished = game_state.knockout_team()
            if finished:
                await inter.channel.send(f"{game_state.current_team.to_string(mention=True)} has won!")
                break
            continue
        if not played_kata:
            continue

        game_state.prev_kata = played_kata
        game_state.prev_kanji = played_kanji
        game_state.played_words.add(played_kata)
        game_state.current_team = teams[(teams.index(game_state.current_team) + 1) % len(teams)]
        game_state.num_words_played[player] += 1

    # The game has ended
    await inter.channel.send(
        f"The final streak was {game_state.get_streak()}!\n" +
        "\n".join([f"{user.global_name or user.display_name} played {num} words"
                   for user, num in game_state.num_words_played.items()]))


if __name__ == '__main__':
    bot.run(os.getenv("TOKEN"))
