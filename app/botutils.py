import asyncio
import logging
import random
from typing import Callable, Awaitable

import nextcord.ui
from nextcord import ButtonStyle

import translationtools

logger = logging.getLogger("shiritori-ref")


class DuelView(nextcord.ui.View):
    def __init__(self,
                 team: list[nextcord.User],
                 callback: Callable[[], Awaitable[None]],
                 edit_message: str
                 ):
        super().__init__(timeout=180)
        self.team = team
        self.callback = callback
        self.message = None
        self.edit_message = edit_message

    @nextcord.ui.button(label="Accept", style=ButtonStyle.green)
    async def accept_callback(self, interaction: nextcord.Interaction):
        if interaction.user not in self.team:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=f"{team_to_string(self.team)} {'have' if len(self.team) > 1 else 'has'}  accepted the duel!",
            view=None)
        self.stop()
        await self.callback()

    @nextcord.ui.button(label="Decline", style=ButtonStyle.red)
    async def decline_callback(self, interaction: nextcord.Interaction):
        if interaction.user not in self.team:
            await interaction.response.send_message("You cannot decline a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{team_to_string(self.team)} {'have' if len(self.team) > 1 else 'has'}"
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
        mode: str, chat: str,
        words_state: dict[str, str],
        wait_callback: Callable[[Callable[[nextcord.Message], bool]], Awaitable[nextcord.Message]],
        lose_life: Callable[[str], Awaitable[None]],
) -> (bool, str, str, nextcord.User):
    await inter.channel.send(f"{team_to_string(current)}, your move!"
                             f" You have {15 if mode == 'Speed' else 60} seconds to respond.")

    if words_state['prev_kata']:
        await announce_previous_word(inter, words_state['prev_kata'], words_state['prev_kanji'])

    try:
        def check(msg: nextcord.Message):
            return (msg.channel == inter.channel and msg.author in current and
                    (chat == "off" or msg.content[0:2] == "> "))

        response_msg = (await wait_callback(check))
    except asyncio.TimeoutError:
        await inter.channel.send(f"{team_to_string(current, mention=True)} took too long to respond. You lose!")
        return False, "", "", None

    response: str = response_msg.content[2 if response_msg.content.startswith("> ") else 0:].lower()
    if response == "> end":
        await inter.channel.send(f"{team_to_string(current)} has ended the game.")
        return False, "", "", None

    logger.info(f"{response_msg.author.global_name} played {response}")

    if translationtools.is_romaji(response):
        return await process_player_romaji(inter, response, response_msg.author, words_state, lose_life)
    elif translationtools.is_kana(response):
        return await process_player_kana(inter, response, response_msg.author, words_state, lose_life)
    else:
        return await process_player_kanji(inter, response, response_msg.author, words_state, lose_life)


async def process_player_romaji(
        inter: nextcord.Interaction,
        response: str,
        author: nextcord.User,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (bool, str, str, int):
    romaji = translationtools.remove_romaji_long_vowels(response)
    hira, kata = translationtools.romaji_to_hira_kata(translationtools.kana_to_romaji(response))

    if not kata:
        await inter.channel.send(f"{response} is not a valid romaji word.")
        return True, "", "", None

    async def invalid_word(r: str):
        await lose_life(f"{', '.join(hira if hira else kata) or response} {r}")
        return True

    reasons = [get_invalid_reasons(k, words_state) for k, _ in zip(kata, hira)]
    invalid = [reason for reason in reasons if reason]
    if invalid:
        return await invalid_word(invalid[0]), "", "", None

    words_romaji = {translationtools.kana_to_romaji(k): v
                    for k, v in (await translationtools.search_jisho(romaji)).items()}
    for k in kata:
        words_romaji.update({translationtools.kana_to_romaji(k): v
                             for k, v in (await translationtools.search_jisho(k)).items()})
    logger.info(f"Romaji dictionary: {str(words_romaji.keys())}")
    normalised = translationtools.kana_to_romaji(kata[0])

    if normalised not in words_romaji and response not in words_romaji:
        return await invalid_word(f"is not a valid word."), "", "", None

    matches = words_romaji.get(normalised) or words_romaji.get(response)
    await inter.channel.send(translationtools.meaning_to_string(matches))
    reading = matches[0]['reading']

    return True, translationtools.hiragana_to_katakana(reading), matches[0]['word'] or matches[0]['reading'], author


async def process_player_kana(
        inter: nextcord.Interaction,
        response: str,
        author: nextcord.User,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (bool, str, str, int):
    words = await translationtools.search_jisho(response)

    if not words:
        await lose_life(f"{response} is not a valid word.")
        return True, "", "", None

    invalid = get_invalid_reasons(response, words_state)
    if invalid:
        await lose_life(f"{response} {invalid}")
        return True, "", "", None

    await inter.channel.send(translationtools.meaning_to_string(words[response]))

    kata = translationtools.hiragana_to_katakana(response)
    kanji = words[response][0]['word'] or words[response][0]['reading']

    return True, kata, kanji, author


async def process_player_kanji(
        inter: nextcord.Interaction,
        response: str,
        author: nextcord.User,
        words_state: dict[str, str],
        lose_life: Callable[[str], Awaitable[None]],
) -> (bool, str, str, int):
    words = await translationtools.search_jisho(response)

    if not words:
        await lose_life(f"{response} is not a valid word.")
        return True, "", "", None

    readings = [w['reading'] for _, word in words.items() for w in word if w['word'] == response and
                not get_invalid_reasons(w['reading'], words_state)]
    if not readings:
        await lose_life(f"{response} is not a valid word.")
        return True, "", "", None

    reading = readings[0]
    kata = translationtools.hiragana_to_katakana(reading)
    await inter.channel.send(translationtools.meaning_to_string(words[reading]))

    return True, kata, response, author


async def announce_previous_word(inter: nextcord.Interaction, prev_kata: str, prev_kanji: str) -> None:
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
    names = [(user.mention if mention else
              (user.global_name if user.global_name else user.display_name)) for user in team]
    return (", ".join(names[:len(names) - 1]) + f" and {names[-1]}") if len(team) > 1 else names[0]
