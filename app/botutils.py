import nextcord.ui
from nextcord import Interaction, ButtonStyle
from nextcord.ui import Button, View

import translationtools


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
