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

    async def on_fail():
        await inter.channel.send(f"I have no words starting with {previous_word[-1]}. I lose!")

    words = await translationtools.get_dictionary(previous_word[-1], previous_word, played_words)
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
                    (mode != "survival" and msg.author.id == current.id) and
                    (chat != "on" or msg.content[0:2] == "> "))

        response: nextcord.Message = await wait_callback(check)
    except asyncio.TimeoutError:
        await inter.channel.send(f"{current.mention} took too long to respond. You lose!")
        return False, ""

    hiragana = translationtools.romaji_to_hiragana(response.content.strip("\""))

    logger.info(f"{current.display_name} played {hiragana}")

    if not hiragana:
        await lose_life(f"{response.content.strip("\"")} is not a valid Romaji word!")
        return True, ""

    if hiragana in played_words:
        await lose_life(f"{hiragana} has already been played!")
        return True, ""

    if not translationtools.match_kana(previous_word, hiragana):
        await lose_life(f"{hiragana} does not start with {previous_word[-1]}!")
        return True, ""

    if hiragana[-1] == 'ん':
        await lose_life(f"{hiragana} ends with ん!")
        return True, ""

    words = await translationtools.get_dictionary(hiragana, previous_word, played_words)
    katakana = translationtools.hiragana_to_katakana(hiragana)

    logger.info(f"checking for {hiragana} or {katakana} in {words.keys()}")

    if hiragana not in words and katakana not in words:
        await lose_life(f"{hiragana} is not a valid word.")
        return True, ""

    if hiragana in words:
        matches = words[hiragana]
    else:
        matches = words[katakana]

    for i in range(3):
        if i >= len(matches):
            break
        match = matches[i]
        kanji = match['word'] or katakana
        await inter.channel.send(f"{kanji} ({hiragana}):\n> {', '.join(match['meanings'])}")
    return True, hiragana
