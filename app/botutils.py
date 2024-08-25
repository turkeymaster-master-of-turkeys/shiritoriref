import asyncio
import logging
import random
import nextcord.ui
from nextcord import Interaction, ButtonStyle
from nextcord.ui import Button, View

import translationtools

logger = logging.getLogger("shiritori-ref")


def get_view(team: list[nextcord.User], callback) -> nextcord.ui.view.View:
    accept_button = Button(label="Accept", style=ButtonStyle.green)
    decline_button = Button(label="Decline", style=ButtonStyle.red)

    view = View()
    view.add_item(accept_button)
    view.add_item(decline_button)

    async def accept_callback(interaction: Interaction) -> None:
        if interaction.user not in team:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{team_to_string(team)} {"have" if len(team) > 1 else "has"}"
                                                        f" accepted the duel!", view=None)
        await callback()

    # Callback function for declining the duel
    async def decline_callback(interaction: Interaction):
        if interaction.user not in team:
            await interaction.response.send_message("You cannot decline a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{team_to_string(team)} {"have" if len(team) > 1 else "has"}"
                                                        f" declined the duel.", view=None)

    accept_button.callback = accept_callback
    decline_button.callback = decline_callback

    return view


async def take_bot_turn(
        inter: nextcord.Interaction,
        words_state: dict[str, str],
) -> (str, str):
    prev_hira = words_state['prev_hira'] or "あ"
    prev_kata = words_state['prev_kata'] or "ア"
    played_words = words_state['played_words']

    await inter.channel.send(f"My turn!")

    words_hira = await translationtools.get_words_starting_with(prev_hira)
    hira_candidates = [k for k in words_hira.keys() if
                       translationtools.hiragana_to_katakana(k) not in played_words and k[-1] != 'ん']

    logger.info(f"Hira candidates: {hira_candidates}")

    if hira_candidates:
        hira = hira_candidates[0]
        kata = translationtools.hiragana_to_katakana(hira)
        await inter.channel.send(translationtools.meaning_to_string(words_hira[hira], hira, kata))
        return hira, kata

    words_kata = await translationtools.get_words_starting_with(prev_kata)
    kata_candidates = [k for k in words_kata.keys() if k not in played_words and k[-1] != 'ン']

    logger.info(f"Kata candidates: {kata_candidates}")

    if kata_candidates:
        kata = kata_candidates[random.randint(0, len(kata_candidates) - 1)]
        await inter.channel.send(translationtools.meaning_to_string(words_kata[kata], "", kata))
        return "", kata

    await inter.channel.send("I have no words to play! You win!")

    return "", ""


async def take_user_turn(
        inter: nextcord.Interaction,
        current: list[nextcord.User],
        mode: str, chat: str,
        words_state: dict[str, str],
        wait_callback,
        lose_life,
) -> (bool, str, str, int):
    prev_kata = words_state['prev_kata']
    prev_hira = words_state['prev_hira']
    played_words = words_state['played_words']

    if mode == "survival":
        await inter.channel.send(f"You have 60 seconds for the next word!")
    else:
        await inter.channel.send(f"{team_to_string(current)}, your move!"
                                 f" You have {15 if mode == 'Speed' else 60} seconds to respond.")

    if prev_kata:
        await announce_previous_word(inter, prev_kata, prev_hira)

    try:
        def check(msg: nextcord.Message):
            return (msg.channel == inter.channel and msg.author in current and
                    (chat == "off" or msg.content[0:2] == "> "))

        response_msg = (await wait_callback(check))
    except asyncio.TimeoutError:
        if mode == "survival":
            await inter.channel.send(f"You took too long to respond. Game over! The streak was {len(played_words)}.")
        else:
            await inter.channel.send(f"{team_to_string(current, mention=True)} took too long to respond. You lose!")
        return False, "", "", -1

    return await process_player_response(inter, response_msg, current, words_state, lose_life)


async def process_player_response(
        inter: nextcord.Interaction,
        response_msg: nextcord.Message,
        current: list[nextcord.User],
        words_state: dict[str, str],
        lose_life,
) -> (bool, str, str, int):
    response: str = response_msg.content.strip("> ").lower()
    if response == "> end":
        await inter.channel.send(f"{team_to_string(current)} has ended the game.")
        return False, "", "", -1

    hiragana = translationtools.romanji_to_hiragana(response)
    katakana = translationtools.romanji_to_katakana(response)

    logger.info(f"{team_to_string(current)} played {response}")

    async def invalid_word(reason: str):
        await lose_life(f"{(hiragana if hiragana else katakana) or response} {reason}")
        return False

    if not await check_valid_word(katakana, hiragana, words_state, invalid_word):
        return True, "", "", -1

    words_hira = {}
    if hiragana:
        words_hira = await translationtools.search_jisho(hiragana)
        logger.info(f"Checking for {hiragana} in {words_hira.keys()}")
    words_kata = await translationtools.search_jisho(katakana)
    logger.info(f"Checking for {katakana} in {words_kata.keys()}")

    if (not hiragana or hiragana not in words_hira) and katakana not in words_kata:
        return not await invalid_word(f"is not a valid word."), "", "", -1

    matches = ((words_hira[hiragana] if hiragana in words_hira else []) +
               (words_kata[katakana] if katakana in words_kata else []))

    await inter.channel.send(translationtools.meaning_to_string(matches, hiragana, katakana))

    return True, katakana, hiragana, response_msg.author.id


async def announce_previous_word(inter: nextcord.Interaction, prev_kata: str, prev_hira: str) -> None:
    last_hira = (prev_hira[-1] if prev_hira[-1] not in "ゃゅょ" else prev_hira[-2:]) if prev_hira else ""
    last = translationtools.normalise_katakana(prev_kata)[-1] if prev_kata[-1] not in "ャュョ" else prev_kata[-2:]
    romanji = translationtools.hiragana_to_romanji(prev_hira) if prev_hira else (
        translationtools.katakana_to_romanji(prev_kata))
    await inter.channel.send(
        f"The word was: {prev_hira or prev_kata} ({romanji})\n"
        f"The letter to start is:"
        f" {last_hira or last} ({translationtools.katakana_to_romanji(last)})")


async def check_valid_word(
        kata: str, hira: str, words_state: dict[str, str], invalid_word
) -> bool:
    prev_kata = words_state['prev_kata']
    prev_hira = words_state['prev_hira']
    if not prev_kata and not prev_hira:
        return True
    if not kata:
        return await invalid_word("is not a valid Romaji word!")
    if kata in words_state['played_words']:
        return await invalid_word("has already been played!")
    if not translationtools.match_kana(prev_kata, kata) and not translationtools.match_kana(prev_hira, hira):
        return await invalid_word("does not match the previous word!")
    if kata[-1] == 'ン':
        return await invalid_word("ends with ん!")
    return True


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
