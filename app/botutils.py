import asyncio
import logging

import nextcord.ui
from nextcord import Interaction, ButtonStyle
from nextcord.ui import Button, View

import translationtools

logger = logging.getLogger("shiritori-ref")


def get_view(user: nextcord.User, callback) -> nextcord.ui.view.View:
    accept_button = Button(label="Accept", style=ButtonStyle.green)
    decline_button = Button(label="Decline", style=ButtonStyle.red)

    view = View()
    view.add_item(accept_button)
    view.add_item(decline_button)

    async def accept_callback(interaction: Interaction) -> None:
        if interaction.user != user:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{user.display_name} has accepted the duel!", view=None)
        await callback()

    # Callback function for declining the duel
    async def decline_callback(interaction: Interaction):
        if interaction.user != user:
            await interaction.response.send_message("You cannot accept a duel for someone else!", ephemeral=True)
            return
        await interaction.response.edit_message(content=f"{user.display_name} has declined the duel.", view=None)
        await callback()

    accept_button.callback = accept_callback
    decline_button.callback = decline_callback

    return view


async def take_bot_turn(inter: nextcord.Interaction, previous_word: str, played_words: set[str]) -> str:
    await inter.channel.send(f"My turn!")

    kata = translationtools.hiragana_to_katakana(previous_word)
    words = await translationtools.get_dictionary(previous_word[-1], kata[-1], previous_word, played_words)
    if not words:
        return ""

    word = list(words.keys())[0]
    for i in range(3):
        if i >= len(words[word]):
            break
        match = words[word][i]
        await inter.channel.send(f"{match['word']} ({word}):\n> {', '.join(match['meanings'])}")
    return word


async def take_user_turn(
        inter: nextcord.Interaction,
        current: nextcord.User,
        mode: str, chat: str,
        previous_word: str,
        played_words: set[str],
        wait_callback,
        lose_life,
) -> (bool, str):
    if mode == "survival":
        await inter.channel.send(f"You have 60 seconds for the next word!")
    else:
        await inter.channel.send(f"{current.display_name}, your move!"
                                 f" You have {15 if mode == 'Speed' else 60} seconds to respond.")
    try:
        def check(msg: nextcord.Message):
            return (msg.channel == inter.channel and
                    (mode == "survival" or msg.author.id == current.id) and
                    (chat == "off" or msg.content[0:2] == "> "))

        response: str = (await wait_callback(check)).content.strip("> ")
    except asyncio.TimeoutError:
        await inter.channel.send(f"{current.mention} took too long to respond. You lose!")
        return False, ""

    hiragana = translationtools.romaji_to_hiragana(response)

    logger.info(f"{current.display_name} played {response}")

    async def invalid_word(reason: str):
        await lose_life(f"{hiragana} {reason}")
        return False

    if not await check_valid_word(hiragana, previous_word, played_words, invalid_word):
        return True, ""

    katakana = translationtools.hiragana_to_katakana(hiragana)
    words = await translationtools.get_dictionary(hiragana, katakana, previous_word, played_words)

    logger.info(f"checking for {hiragana} or {katakana} in {words.keys()}")

    if hiragana not in words and katakana not in words:
        return not await invalid_word(f"is not a valid word."), ""

    matches = ((words[hiragana] if hiragana in words else []) +
               (words[katakana] if katakana in words else []))

    for i in range(3):
        if i >= len(matches):
            break
        match = matches[i]
        kanji = match['word'] or katakana
        await inter.channel.send(f"{kanji} ({hiragana}):\n> {', '.join(match['meanings'])}")
    return True, hiragana


async def check_valid_word(hiragana: str, previous_word: str, played_words: set[str], invalid_word) -> bool:

    if not hiragana:
        return await invalid_word("is not a valid Romaji word!")
    if hiragana in played_words:
        return await invalid_word("has already been played!")
    if not translationtools.match_kana(previous_word, hiragana):
        return await invalid_word("does not match the previous word!")
    if hiragana[-1] == 'ん':
        return await invalid_word("ends with ん!")
    return True
