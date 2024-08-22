from jisho_api.word import Word


def match_kana(prev: str, curr: str) -> bool:
    return prev[-1] == curr[0] or \
        (prev[-1] == 'ぢ' and curr[0] == 'じ') or \
        (prev[-1] == 'づ' and curr[0] == 'ず') or \
        (prev[-1] == 'ゃ' and (curr[0] == 'や' or prev[-2] == curr[0])) or \
        (prev[-1] == 'ゅ' and (curr[0] == 'ゆ' or prev[-2] == curr[0])) or \
        (prev[-1] == 'ょ' and (curr[0] == 'よ' or prev[-2] == curr[0]))


async def get_dictionary(search: str, previous_word: str, played_words: set['str']) -> dict:
    """
    Uses the Jisho API to get a dictionary of words from the search term
    :param search: The search term
    :param previous_word: Previous word
    :param played_words: Played words
    :return: Dictionary from readings to words
    """
    wr = Word.request(search)
    if not wr:
        return {}

    words = {}
    for x in wr.dict()['data']:
        for y in x['japanese']:
            reading = y['reading']
            if not reading or len(reading) <= 1:
                continue
            if (previous_word and reading[0] != previous_word[-1]) or reading[-1] == 'ん' or reading in played_words:
                continue
            word_info = {'word': y['word'],
                         'meanings': [sense['english_definitions'][0] for sense in x['senses']]}

            if reading in words:
                words[reading].append(word_info)
            else:
                words[reading] = [word_info]

    return words


def romaji_to_hiragana(word: str) -> str or None:
    """
    Converts a string to hiragana, returns None if it isn't valid romanji
    :param word: The word to convert
    :return: The hiragana word
    """
    i = 2 if word[0:2] == "> " else 0
    hiragana_word = ""
    while i < len(word):
        if i + 1 < len(word) and word[i] == word[i + 1]:
            hiragana_word += "っ"  # Small tsu
            i += 1
        for j in range(min(3, len(word) - i), 0, -1):
            if word[i:i + j] in romaji_to_hiragana_dict:
                hiragana_word += romaji_to_hiragana_dict[word[i:i + j]]
                i += j
                break
        else:
            return None

    return hiragana_word


def hiragana_to_katakana(text):
    """
    Converts hiragana to katakana
    :param text: The text to convert
    :return: The converted text
    """
    return ''.join(hiragana_to_katakana_dict[char] for char in text)


romaji_to_hiragana_dict: dict[str, str] = {
    'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
    'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
    'sa': 'さ', 'shi': 'し', 'su': 'す', 'se': 'せ', 'so': 'そ',
    'ta': 'た', 'chi': 'ち', 'tsu': 'つ', 'te': 'て', 'to': 'と',
    'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
    'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ',
    'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
    'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
    'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
    'wa': 'わ', 'wo': 'を', 'n': 'ん',
    'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
    'za': 'ざ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ',
    'da': 'だ', 'di': 'ぢ', 'dzu': 'づ', 'de': 'で', 'do': 'ど',
    'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
    'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
    'kya': 'きゃ', 'kyu': 'きゅ', 'kyo': 'きょ',
    'sha': 'しゃ', 'shu': 'しゅ', 'sho': 'しょ',
    'cha': 'ちゃ', 'chu': 'ちゅ', 'cho': 'ちょ',
    'nya': 'にゃ', 'nyu': 'にゅ', 'nyo': 'にょ',
    'hya': 'ひゃ', 'hyu': 'ひゅ', 'hyo': 'ひょ',
    'mya': 'みゃ', 'myu': 'みゅ', 'myo': 'みょ',
    'rya': 'りゃ', 'ryu': 'りゅ', 'ryo': 'りょ',
    'gya': 'ぎゃ', 'gyu': 'ぎゅ', 'gyo': 'ぎょ',
    'ja': 'じゃ', 'ju': 'じゅ', 'jo': 'じょ',
    'dya': 'ぢゃ', 'dyu': 'ぢゅ', 'dyo': 'ぢょ',
    'bya': 'びゃ', 'byu': 'びゅ', 'byo': 'びょ',
    'pya': 'ぴゃ', 'pyu': 'ぴゅ', 'pyo': 'ぴょ'
}

# Hiragana to Katakana dictionary
hiragana_to_katakana_dict = {
    'あ': 'ア', 'い': 'イ', 'う': 'ウ', 'え': 'エ', 'お': 'オ',
    'か': 'カ', 'き': 'キ', 'く': 'ク', 'け': 'ケ', 'こ': 'コ',
    'さ': 'サ', 'し': 'シ', 'す': 'ス', 'せ': 'セ', 'そ': 'ソ',
    'た': 'タ', 'ち': 'チ', 'つ': 'ツ', 'て': 'テ', 'と': 'ト',
    'な': 'ナ', 'に': 'ニ', 'ぬ': 'ヌ', 'ね': 'ネ', 'の': 'ノ',
    'は': 'ハ', 'ひ': 'ヒ', 'ふ': 'フ', 'へ': 'ヘ', 'ほ': 'ホ',
    'ま': 'マ', 'み': 'ミ', 'む': 'ム', 'め': 'メ', 'も': 'モ',
    'や': 'ヤ', 'ゆ': 'ユ', 'よ': 'ヨ',
    'ら': 'ラ', 'り': 'リ', 'る': 'ル', 'れ': 'レ', 'ろ': 'ロ',
    'わ': 'ワ', 'を': 'ヲ', 'ん': 'ン',
    'が': 'ガ', 'ぎ': 'ギ', 'ぐ': 'グ', 'げ': 'ゲ', 'ご': 'ゴ',
    'ざ': 'ザ', 'じ': 'ジ', 'ず': 'ズ', 'ぜ': 'ゼ', 'ぞ': 'ゾ',
    'だ': 'ダ', 'ぢ': 'ヂ', 'づ': 'ヅ', 'で': 'デ', 'ど': 'ド',
    'ば': 'バ', 'び': 'ビ', 'ぶ': 'ブ', 'べ': 'ベ', 'ぼ': 'ボ',
    'ぱ': 'パ', 'ぴ': 'ピ', 'ぷ': 'プ', 'ぺ': 'ペ', 'ぽ': 'ポ',
    'ゃ': 'ャ', 'ゅ': 'ュ', 'ょ': 'ョ', 'っ': 'ッ'
}
