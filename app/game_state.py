import nextcord

from app import kana_conversion
from app.team import Team


class GameState:
    def __init__(self, teams: list[Team]):
        self.teams = teams
        self.current_team = teams[0]
        self.lives = {team.id: 3 for team in teams}
        self.num_words_played = {user: 0 for team in teams for user in team.players}
        self.prev_kata = ""
        self.prev_kanji = ""
        self.played_words = set()

    def knockout_team(self) -> bool:
        """
        Remove the current team from the game. If only one team remains, declare them the winner.

        :return: True if only one team remains, False otherwise
        """
        index = self.teams.index(self.current_team)
        self.teams.pop(index)
        if len(self.teams) == 1:
            self.current_team = self.teams[0]
            return True
        self.current_team = self.teams[index % len(self.teams)]
        return False

    async def lose_life(self, reason: str, inter: nextcord.Interaction) -> None:
        """
        Remove a life from the current team and announce to the channel.

        :param reason: Reason for losing a life
        :param inter: Interaction object
        :return:
        """
        self.lives[self.current_team.id] -= 1
        await inter.channel.send(f"{reason} You have {self.lives[self.current_team.id]} lives remaining.")

    def get_invalid_reasons(self, kata: str) -> str:
        """
        Check if a word is invalid current game state. The word will be checked for the following conditions:
        - If the word is empty
        - If the word is only one mora
        - If the word has already been played
        - If the word does not match the previous word
        - If the word ends with ん

        :param kata: Katakana of the word to check
        :return: String containing the reason the word is invalid, or an empty string if the word is valid
        """
        prev_kata = self.prev_kata
        if not prev_kata:
            return ""
        elif not kata:
            return "is not a valid Romaji word!"
        elif kata in kana_conversion.set_mora:
            return "is only one mora!"
        elif kata in self.played_words:
            return "has already been played!"
        elif not kana_conversion.match_kana(prev_kata, kana_conversion.hiragana_to_katakana(kata)):
            return "does not match the previous word!"
        elif kata[-1] == 'ン':
            return "ends with ん!"
        return ""

    def get_streak(self) -> int:
        """
        Get the current game streak.

        :return: Current streak
        """
        return len(self.played_words)

    async def announce_streak(self, inter: nextcord.Interaction) -> None:
        """
        Announce the current streak of the game.

        :param inter: Interaction object
        :return:
        """
        streak = self.get_streak()
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

    async def announce_previous_word(self, inter: nextcord.Interaction) -> None:
        """
        Announce the previous word played in the game.

        :param inter: Interaction object
        :return:
        """
        last_kata = kana_conversion.normalise_katakana(self.prev_kata)[-1] \
            if self.prev_kata[-1] not in "ャュョァィェォ" else self.prev_kata[-2:]
        last_hira = kana_conversion.katakana_to_hiragana(last_kata)
        romaji = kana_conversion.kana_to_romaji(self.prev_kata)
        last_romaji = kana_conversion.kana_to_romaji(last_kata)
        await inter.channel.send(
            f"The word was: {self.prev_kanji} ({romaji})\n"
            f"The letter to start is:"
            f" {last_hira or last_kata} ({last_romaji})")
