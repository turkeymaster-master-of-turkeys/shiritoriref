from enum import Enum


class Pace(Enum):
    SPEED = "speed"
    NORMAL = "normal"

    @staticmethod
    def choices():
        return [pace.value for pace in Pace]


class InputMode(Enum):
    ROMAJI = "romaji"
    KANA = "かな"
    KANJI = "漢字"

    @staticmethod
    def choices():
        return [input_mode.value for input_mode in InputMode]


class GameOptions:
    def __init__(self, pace: Pace, input_mode: InputMode, chat_on: bool):
        self.pace = pace
        self.input_mode = input_mode
        self.chat_on = chat_on
