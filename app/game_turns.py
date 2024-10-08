import asyncio
import logging
import random
import re
from typing import Callable, Awaitable

import nextcord.ui
from nextcord import ButtonStyle

import kana_conversion
from game_options import GameOptions, Pace, InputMode
from game_state import GameState
from team import Team
from constants import *

logger = logging.getLogger("shiritori-ref")


class DuelView(nextcord.ui.View):
    def __init__(self,
                 team: Team,
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
            content=f"{self.team.to_string()} {'have' if len(self.team) > 1 else 'has'}  accepted the duel!",
            view=None)
        await self.callback()
        self.stop()

    @nextcord.ui.button(label="Decline", style=ButtonStyle.red)
    async def decline_callback(self, button: nextcord.Button, interaction: nextcord.Interaction):
        if interaction.user not in self.team:
            await interaction.response.send_message("You cannot decline a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=f"{self.team.to_string()} {'have' if len(self.team) > 1 else 'has'}"
                    f" declined the duel.", view=None)
        self.stop()

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content=self.edit_message, view=None)


async def take_bot_turn(
        inter: nextcord.Interaction,
        game_state: GameState,
) -> (str, str):
    """
    Take a turn for the bot. The bot will try to play a word that starts with the last kana of the previous word. If no
    such word exists, the bot will announce their loss.

    :param inter: The interaction object
    :param game_state: The state of the game
    :return: The kana and kanji of the word to play
    """
    prev_kata = kana_conversion.normalise_katakana(game_state.prev_kata) or "ア"
    played_words = game_state.played_words

    await inter.channel.send(f"My turn!")

    words_hira = await kana_conversion.get_words_starting_with(kana_conversion.katakana_to_hiragana(prev_kata))
    hira_candidates = [k for k in words_hira.keys() if
                       kana_conversion.hiragana_to_katakana(k) not in played_words and k[-1] != 'ん']

    logger.info(f"Hira candidates: {hira_candidates}")

    if hira_candidates:
        hira = hira_candidates[random.randint(0, len(hira_candidates) - 1)]
        kata = kana_conversion.hiragana_to_katakana(hira)
        await inter.channel.send(kana_conversion.meaning_to_string(words_hira[hira]))
        return kata, words_hira[hira][0]['word'] or words_hira[hira][0]['reading']

    words_kata = await kana_conversion.get_words_starting_with(prev_kata)
    kata_candidates = [k for k in words_kata.keys() if k not in played_words and k[-1] != 'ン']

    logger.info(f"Kata candidates: {kata_candidates}")

    if kata_candidates:
        kata = kata_candidates[random.randint(0, len(kata_candidates) - 1)]
        await inter.channel.send(kana_conversion.meaning_to_string(words_kata[kata]))
        return kata, kata

    await inter.channel.send("I have no words to play! You win!")

    return "", ""


async def take_user_turn(
        inter: nextcord.Interaction,
        options: GameOptions,
        game_state: GameState,
        wait_for_user_input: Callable[[Callable[[nextcord.Message], bool]], Awaitable[nextcord.Message]],
) -> (bool, str, str, nextcord.User):
    """
    Take a turn for a team. They will be prompted to play a word that starts with the last kana of the previous word. If
    the word is valid, otherwise the meaning of the word will be displayed.

    :param inter: Interaction object
    :param options: Game options
    :param game_state: State of the game
    :param wait_for_user_input: Function to wait for a message
    :return: A tuple containing whether the team should continue, the katakana of the word played, the kanji of the word
    played, and the player who played the word
    """
    await inter.channel.send(f"{game_state.current_team.to_string()}, your move!"
                             f" You have {TIME_SPEED if options.pace == Pace.SPEED else TIME_NORMAL}"
                             f" seconds to respond.")

    if game_state.prev_kata:
        await game_state.announce_previous_word(inter)

    try:
        def check(msg: nextcord.Message):
            logger.info(msg.content[0:2])
            return (msg.channel == inter.channel and msg.author in game_state.current_team and
                    (not options.chat_on or msg.content[0:2] in MESSAGE_BEGIN))

        response_msg = (await wait_for_user_input(check))
    except asyncio.TimeoutError:
        await inter.channel.send(
            f"{game_state.current_team.to_string(mention=True)} took too long to respond. You lose!")
        return False, "", "", None

    # Remove the message beginning indicator
    response: str = re.sub("^" + "|".join([f"({b})" for b in MESSAGE_BEGIN]), "", response_msg.content)
    if response == END_DUEL:
        await inter.channel.send(f"{game_state.current_team.to_string()} has ended the game.")
        return False, "", "", None

    logger.info(f"{response_msg.author.global_name} played {response}")

    if kana_conversion.is_romaji(response):
        if options.input_mode == InputMode.ROMAJI:
            (played_kata, played_kanji) = await process_player_romaji(inter, response, game_state)
            return True, played_kata, played_kanji, response_msg.author
        else:
            await inter.channel.send(f"You can't use romaji in this mode!")
            return True, "", "", None
    elif kana_conversion.is_kana(response) and options.input_mode != InputMode.KANJI:
        (played_kata, played_kanji) = await process_player_kana(inter, response, game_state)
        return True, played_kata, played_kanji, response_msg.author
    else:
        (played_kata, played_kanji) = await process_player_kanji(inter, response, game_state)
        return True, played_kata, played_kanji, response_msg.author


async def process_player_romaji(
        inter: nextcord.Interaction,
        response: str,
        game_state: GameState,
) -> (str, str, int):
    """
    Process a player's response in romaji. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is invalid, the player's team will lose a life.

    :param inter: Interaction object
    :param response: The response of the player
    :param game_state: State of the game
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    romaji = kana_conversion.remove_romaji_long_vowels(response)
    hira, kata = kana_conversion.romaji_to_hira_kata(kana_conversion.kana_to_romaji(response))

    if not kata:
        await inter.channel.send(f"{response} is not a valid romaji word.")
        return "", ""

    async def invalid_word(r: str):
        await game_state.lose_life(f"{', '.join(hira if hira else kata) or response} {r}", inter)

    reasons = [game_state.get_invalid_reasons(k) for k, _ in zip(kata, hira)]
    invalid = [reason for reason in reasons if reason]
    if invalid:
        await invalid_word(invalid[0])
        return "", ""

    words_romaji = {kana_conversion.kana_to_romaji(k): v
                    for k, v in (await kana_conversion.search_jisho(romaji)).items()}
    for k in kata:
        words_romaji.update({kana_conversion.kana_to_romaji(k): v
                             for k, v in (await kana_conversion.search_jisho(k)).items()})
    logger.info(f"Romaji dictionary: {str(words_romaji.keys())}")
    normalised = kana_conversion.kana_to_romaji(kata[0])

    if normalised not in words_romaji and response not in words_romaji:
        await invalid_word(f"is not a valid word.")
        return "", ""

    matches = words_romaji.get(normalised) or words_romaji.get(response)
    await inter.channel.send(kana_conversion.meaning_to_string(matches))
    reading = matches[0]['reading']

    return kana_conversion.hiragana_to_katakana(reading), matches[0]['word'] or matches[0]['reading']


async def process_player_kana(
        inter: nextcord.Interaction,
        response: str,
        game_state: GameState,
) -> (str, str):
    """
    Process a player's response in kana. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is valid, the katakana and kanji of the word will be returned.

    :param inter: Interaction object
    :param response: The response of the player
    :param game_state: State of the game
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    words = await kana_conversion.search_jisho(response)

    if not words:
        await game_state.lose_life(f"{response} is not a valid word.", inter)
        return "", ""

    invalid = game_state.get_invalid_reasons(response)
    if invalid:
        await game_state.lose_life(f"{response} {invalid}", inter)
        return "", ""

    await inter.channel.send(kana_conversion.meaning_to_string(words[response]))

    kata = kana_conversion.hiragana_to_katakana(response)
    kanji = words[response][0]['word'] or words[response][0]['reading']

    return kata, kanji


async def process_player_kanji(
        inter: nextcord.Interaction,
        response: str,
        game_state: GameState,
) -> (str, str):
    """
    Process a player's response in kanji. The response will be checked for validity and the meaning of the word will be
    displayed. If the word is valid, the katakana and kanji of the word will be returned.

    :param inter: Interaction object
    :param response: Response of the player
    :param game_state: State of the game
    :return: Pair containing the katakana and kanji of the word played if the word is valid, otherwise an empty string
    """
    words = await kana_conversion.search_jisho(response)

    if not words:
        await game_state.lose_life(f"{response} is not a valid word.", inter)
        return "", ""

    readings = [w['reading']
                for _, word in words.items()
                for w in word if
                (w['word'] == response if w['word'] else w['reading'] == response)
                and not game_state.get_invalid_reasons(w['reading'])]

    if not readings:
        await game_state.lose_life(f"{response} is not a valid word.", inter)
        return "", ""

    reading = readings[0]
    kata = kana_conversion.hiragana_to_katakana(reading)
    await inter.channel.send(kana_conversion.meaning_to_string(words[reading]))

    return kata, response
