import nextcord


class Team:
    def __init__(self, players: list[nextcord.User]):
        self.players = players
        self.leader = players[0]
        self.id = self.leader.id

    def add_player(self, player):
        self.players.append(player)

    def to_string(self, mention=False) -> str:
        """
        Convert a team to a string. If mention is True, the team members will be mentioned, otherwise their display
        names will be used.

        :param mention: Whether to mention the team members
        :return: String representation of the team
        """
        names = [(user.mention if mention else
                  (user.global_name if user.global_name else user.display_name)) for user in self.players]
        return (", ".join(names[:len(names) - 1]) + f" and {names[-1]}") if len(self.players) > 1 else names[0]

    def __len__(self):
        return len(self.players)

    def __contains__(self, item):
        return item in self.players
