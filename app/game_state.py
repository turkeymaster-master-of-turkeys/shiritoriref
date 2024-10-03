import nextcord

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
        index = self.teams.index(self.current_team)
        self.teams.pop(index)
        if len(self.teams) == 1:
            self.current_team = self.teams[0]
            return True
        self.current_team = self.teams[index % len(self.teams)]
        return False

    async def lose_life(self, message: str, inter: nextcord.Interaction) -> None:
        self.lives[self.current_team.id] -= 1
        await inter.channel.send(f"{message} You have {self.lives[self.current_team.id]} lives remaining.")
