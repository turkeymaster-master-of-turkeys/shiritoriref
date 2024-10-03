import asyncio
import logging
import random
import re
from typing import Callable, Awaitable

import nextcord.ui
from nextcord import ButtonStyle

import translationtools
from constants import *

logger = logging.getLogger("shiritori-ref")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='app.log',
    filemode='a'
)
logger.addHandler(logging.StreamHandler())


class DuelView(nextcord.ui.View):
    def __init__(self,
                 team: list[nextcord.User],
                 callback: Callable[[], Awaitable[None]],
                 edit_message: str
                 ):
        super().__init__(timeout=DUEL_TIMEOUT)
        self.team = team
        self.callback = callback
        self.message = None
        self.edit_message = edit_message

    @nextcord.ui.button(label="Accept", style=ButtonStyle.green)
    async def accept_callback(self, button: nextcord.Button, interaction: nextcord.Interaction):
        if interaction.user not in self.team:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=f"{team_to_string(self.team)} {'have' if len(self.team) > 1 else 'has'}  accepted the duel!",
            view=None)
        await self.callback()
        self.stop()

    @nextcord.ui.button(label="Decline", style=ButtonStyle.red)
    async def decline_callback(self, button: nextcord.Button, interaction: nextcord.Interaction):
        if interaction.user not in self.team:
            await interaction.response.send_message("You cannot decline a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=f"{team_to_string(self.team)} {'have' if len(self.team) > 1 else 'has'}"
                    f" declined the duel.", view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content=self.edit_message, view=None)


async def take_bot_turn(
        inter: nextcord.Interaction,
        words_state: dict,
) -> (str, str):
    """
    Take a turn for the bot. The bot will try to play a word that starts with the last kana of the previous word. If no
    such word exists, the bot will announce their loss.

    :param inter: The interaction object
    :param words_state: The state of the game
    :return: The kana and kanji of the word to play
    """
    prev_kata = translationtools.normalise_katakana(words_state['prev_kata']) or "ア"
    played_words = words_state['played_words']

    await inter.channel.send(f"My turn!")

    words_hira = await translationtools.get_words_starting_with(translationtools.katakana_to_hiragana(prev_kata))
    hira_candidates = [k for k in words_hira.keys() if
                       translationtools.hiragana_to_katakana(k) not in played_words and k[-1] != 'ん']

    logger.info(f"Hira candidates: {hira_candidates}")

    if hira_candidates:
        hira = hira_candidates[random.randint(0, len(hira_candidates) - 1)]
        kata = translationtools.hiragana_to_katakana(hira)
        await inter.channel.send(translationtools.meaning_to_string(words_hira[hira]))
        return kata, words_hira[hira][0]['word'] or words_hira[hira][0]['reading']

    words_kata = await translationtools.get_words_starting_with(prev_kata)
    kata_candidates = [k for k in words_kata.keys() if k not in played_words and k[-1] != 'ン']

    logger.info(f"Kata candidates: {kata_candidates}")

    if kata_candidates:
        kata = kata_candidates[random.randint(0, len(kata_candidates) - 1)]
        await inter.channel.send(translationtools.meaning_to_string(words_kata[kata]))
        return kata, kata

    await inter.channel.send("I have no words to play! You win!")

    return "", ""


async def take_user_turn(
        inter: nextcord.Interaction,
        current: list[nextcord.User],
        pace: str, input_mode: str, chat: str,
        words_state: dict[str, str],
        wait_callback: Callable[[Callable[[nextcord.Message], bool]], Awaitable[nextcord.Message]],
        lose_life: Callable[[str], Awaitable[None]],
) -> (bool, str, str, nextcord.User):
    """
    Take a turn for a team. They will be prompted to play a word that starts with the last kana of the previous word. If
    the word is invalid, lose_life will be called, otherwise the meaning of the word will be displayed.

    :param inter: Interaction object
    :param current: Team that is currently playing
    :param pace: Pace of the game (normal or fast)
    :param input_mode: Mode of input (romaji, kana, kanji)
    :param chat: Whether chat is enabled
    :param words_state: State of the game
    :param wait_callback: Function to wait for a message
    :param lose_life: Function to call when a team loses a life
    :return: A tuple containing whether the team should continue, the katakana of the word played, the kanji of the word
    played, and the player who played the word
    """
    await inter.channel.send(f"{team_to_string(current)}, your move!"
                             f" You have {TIME_SPEED if pace == PACE_SPEED else TIME_NORMAL} seconds to respond.")

    if words_state['prev_kata']:
        await announce_previous_word(inter, words_state['prev_kata'], words_state['prev_kanji'])

    try:
        def check(msg: nextcord.Message):
            logger.info(msg.content[0:2])
            return (msg.channel == inter.channel and msg.author in current and
                    (chat == "off" or msg.content[0:2] in MESSAGE_BEGIN))

        response_msg = (await wait_callback(check))
    except asyncio.TimeoutError:
        await inter.channel.send(f"{team_to_string(current, mention=True)} took too long to respond. You lose!")
        return False, "", "", None

    # Remove the message beginning indicator
    response: str = re.sub("^" + "|".join([f"({b})" for b in MESSAGE_BEGIN]), "", response_msg.content)
    if response == END_DUEL:
        await inter.channel.send(f"{team_to_string(current)} has ended the game.")
        return False, "", "", None

    logger.info(f"{response_msg.author.global_name} played {response}")

    if translationtools.is_romaji(response):
        if input_mode == INPUT_ROMAJI:
            (played_kata, played_kanji) = await process_player_romaji(inter, response, words_state, lose_life)
            return True, played_kata, played_kanji, response_msg.author
        else:
            await inter.channel.send(f"You can't use romaji in this mode!")
            return True, "", "", None
    elif translationtools.is_kana(response) and input_mode != INPUT_KANJI:
        (played_kata, played_kanji) = await process_player_kana(inter, response, words_state, lose_life)
        return True, played_kata, played_kanji, response_msg.author
    else:
        (played_kata, played_kanji) = await process_player_kanji(inter, response, words_state, lose_life)
        return True, played_kata, played_kanji, response_msg.author


async def process_player_romaji(
        inter: nextcord.Interaction,
        response: str,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (str, str, int):
    """
    Process a player's response in romaji. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is invalid, the player will lose_life will be called.

    :param inter: Interaction object
    :param response: The response of the player
    :param words_state: State of the game
    :param lose_life: Function to call when a player loses a life
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    romaji = translationtools.remove_romaji_long_vowels(response)
    hira, kata = translationtools.romaji_to_hira_kata(translationtools.kana_to_romaji(response))

    if not kata:
        await inter.channel.send(f"{response} is not a valid romaji word.")
        return "", ""

    async def invalid_word(r: str):
        await lose_life(f"{', '.join(hira if hira else kata) or response} {r}")

    reasons = [get_invalid_reasons(k, words_state) for k, _ in zip(kata, hira)]
    invalid = [reason for reason in reasons if reason]
    if invalid:
        await invalid_word(invalid[0])
        return "", ""

    words_romaji = {translationtools.kana_to_romaji(k): v
                    for k, v in (await translationtools.search_jisho(romaji)).items()}
    for k in kata:
        words_romaji.update({translationtools.kana_to_romaji(k): v
                             for k, v in (await translationtools.search_jisho(k)).items()})
    logger.info(f"Romaji dictionary: {str(words_romaji.keys())}")
    normalised = translationtools.kana_to_romaji(kata[0])

    if normalised not in words_romaji and response not in words_romaji:
        await invalid_word(f"is not a valid word.")
        return "", ""

    matches = words_romaji.get(normalised) or words_romaji.get(response)
    await inter.channel.send(translationtools.meaning_to_string(matches))
    reading = matches[0]['reading']

    return translationtools.hiragana_to_katakana(reading), matches[0]['word'] or matches[0]['reading']


async def process_player_kana(
        inter: nextcord.Interaction,
        response: str,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (str, str):
    """
    Process a player's response in kana. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is invalid, then lose_life will be called. If the word is valid, the katakana and kanji of
    the word will be returned.

    :param inter: Interaction object
    :param response: The response of the player
    :param words_state: State of the game
    :param lose_life: Function to call when a player loses a life
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    words = await translationtools.search_jisho(response)

    if not words:
        await lose_life(f"{response} is not a valid word.")
        return "", ""

    invalid = get_invalid_reasons(response, words_state)
    if invalid:
        await lose_life(f"{response} {invalid}")
        return "", ""

    await inter.channel.send(translationtools.meaning_to_string(words[response]))

    kata = translationtools.hiragana_to_katakana(response)
    kanji = words[response][0]['word'] or words[response][0]['reading']

    return kata, kanji


async def process_player_kanji(
        inter: nextcord.Interaction,
        response: str,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (str, str):
    """
    Process a player's response in kanji. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is invalid, then lose_life will be called. If the word is valid, the katakana and kanji of
    the word will be returned.

    :param inter: Interaction object
    :param response: Response of the player
    :param words_state: State of the game
    :param lose_life: Function to call when a player loses a life
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    words = await translationtools.search_jisho(response)

    if not words:
        await lose_life(f"{response} is not a valid word.")
        return "", ""

    readings = [w['reading']
                for _, word in words.items()
                for w in word if
                (w['word'] == response if w['word'] else w['reading'] == response)
                and not get_invalid_reasons(w['reading'], words_state)]

    if not readings:
        await lose_life(f"{response} is not a valid word.")
        return "", ""

    reading = readings[0]
    kata = translationtools.hiragana_to_katakana(reading)
    await inter.channel.send(translationtools.meaning_to_string(words[reading]))

    return kata, response


async def announce_previous_word(inter: nextcord.Interaction, prev_kata: str, prev_kanji: str) -> None:
    """
    Announce the previous word played in the game.

    :param inter: Interaction object
    :param prev_kata: Katakana of the previous word
    :param prev_kanji: Kanji of the previous word
    :return:
    """
    last_kata = translationtools.normalise_katakana(prev_kata)[-1] \
        if prev_kata[-1] not in "ャュョァィェォ" else prev_kata[-2:]
    last_hira = translationtools.katakana_to_hiragana(last_kata)
    romaji = translationtools.kana_to_romaji(prev_kata)
    last_romaji = translationtools.kana_to_romaji(last_kata)
    await inter.channel.send(
        f"The word was: {prev_kanji} ({romaji})\n"
        f"The letter to start is:"
        f" {last_hira or last_kata} ({last_romaji})")


def get_invalid_reasons(
        kata: str, words_state: dict[str, str]
) -> str:
    """
    Check if a word is invalid for the current game state. The word will be checked for the following conditions:
    - If the word is empty
    - If the word is only one mora
    - If the word has already been played
    - If the word does not match the previous word
    - If the word ends with ん

    :param kata: Katakana of the word to check
    :param words_state: State of the game
    :return: String containing the reason the word is invalid, or an empty string if the word is valid
    """
    prev_kata = words_state['prev_kata']
    if not prev_kata:
        return ""
    elif not kata:
        return "is not a valid Romaji word!"
    elif kata in translationtools.set_kata_mora:
        return "is only one mora!"
    elif kata in words_state['played_words']:
        return "has already been played!"
    elif not translationtools.match_kana(prev_kata, translationtools.hiragana_to_katakana(kata)):
        return "does not match the previous word!"
    elif kata[-1] == 'ン':
        return "ends with ん!"
    return ""


async def announce_streak(inter: nextcord.Interaction, streak: int) -> None:
    """
    Announce the current streak of the game.

    :param inter: Interaction object
    :param streak: Streak of the game
    :return:
    """
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


def team_to_string(team: list[nextcord.User], mention=False) -> str:
    """
    Convert a team to a string. If mention is True, the team members will be mentioned, otherwise their display names
    will be used.

    :param team: Team to convert
    :param mention: Whether to mention the team members
    :return: String representation of the team
    """
    names = [(user.mention if mention else
              (user.global_name if user.global_name else user.display_name)) for user in team]
    return (", ".join(names[:len(names) - 1]) + f" and {names[-1]}") if len(team) > 1 else names[0]
