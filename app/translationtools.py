import logging

from jisho_api.word import Word

logger = logging.getLogger("shiritori-ref")


def match_kana(prev: str, curr: str) -> bool:
    if not prev:
        return True
    p = normalise_katakana(prev)
    c = normalise_katakana(curr)
    logger.info(f"Matching {p} with {c}")
    for i in range(min(len(p), len(c))):
        if p[len(p) - 1 - i:] == c[:i + 1]:
            return True
    return False


def normalise_katakana(katakana: str) -> str:
    def choonpu_to_kana(kana: str) -> str:
        return kana in set_a and 'ア' or \
            kana in set_e and 'エ' or \
            kana in set_i and 'イ' or \
            kana in set_o and 'オ' or \
            kana in set_u and 'ウ' or \
            kana

    kata = katakana[0]
    for i in range(1, len(katakana)):
        kata = kata + (katakana[i] if katakana[i] != 'ー' else choonpu_to_kana(katakana[i - 1]))
    normal_map = {
        'ヂ': 'ジ', 'ヅ': 'ズ',
        'ャ': 'ヤ', 'ュ': 'ユ', 'ョ': 'ヨ',
        'ァ': 'ア', 'ィ': 'イ', 'ゥ': 'ウ', 'ェ': 'エ', 'ォ': 'オ'
    }
    return ''.join(normal_map.get(c, c) for c in kata)


async def get_dictionary(hira: str, kata: str) -> dict:
    """
    Uses the Jisho API to get a dictionary of words from the search term
    :param hira: The hiragana term
    :param kata: The katakana term
    :return: Dictionary from readings to words
    """
    wr1 = Word.request(hira) if hira else None
    wr2 = Word.request(kata)
    if not wr1 and not wr2:
        return {}

    dictionary = (wr1.dict()['data'] if wr1 else []) + (wr2.dict()['data'] if wr2 else [])

    words = {}
    for x in dictionary:
        for y in x['japanese']:
            reading = y['reading']
            if not reading or len(reading) <= 1:
                continue
            word_info = {'word': y['word'],
                         'meanings': [sense['english_definitions'][0] for sense in x['senses']]}

            if reading in words:
                words[reading].append(word_info)
            else:
                words[reading] = [word_info]

    return words


def romanji_to_kana(word: str, dictionary: dict[str, str], tsu: str) -> str or None:
    """
    Converts a string to kana, using a specified dictionary returns None if it isn't valid romanji
    :param tsu: Small tsu to use
    :param dictionary: The dictionary to use
    :param word: The word to convert
    :return: The hiragana word
    """
    i = 0
    kana_word = ""
    for j in range(min(3, len(word) - i), 0, -1):
        if word[i:i + j] in dictionary:
            kana_word += dictionary[word[i:i + j]]
            i += j
    while i < len(word):
        if i + 1 < len(word) and word[i] == word[i + 1]:
            kana_word += tsu  # Small tsu
            i += 1
        for j in range(min(3, len(word) - i), 0, -1):
            if word[i:i + j] in dictionary:
                kana_word += dictionary[word[i:i + j]]
                i += j
                break
        else:
            return None

    return kana_word


def romanji_to_hiragana(word) -> str or None:
    return romanji_to_kana(word, romaji_to_hiragana_dict, 'っ')


def romaji_to_katakana(word: str) -> str or None:
    """
    Converts a string to katakana, returns None if it isn't valid romanji
    :param word: The word to convert
    :return: The katakana word
    """
    kata = romanji_to_kana(word, romaji_to_katakana_dict, 'ッ')
    if not kata:
        return None

    def convert_choonpu(char, next_char):
        if char in set_a and next_char == 'ア' or \
                char in set_e and (next_char == 'エ' or next_char == 'イ') or \
                char in set_i and next_char == 'イ' or \
                char in set_o and (next_char == 'オ' or next_char == 'ウ') or \
                char in set_u and next_char == 'ウ' or \
                char == 'エ' and next_char == 'イ' or \
                char == 'オ' and next_char == 'ウ':
            return 'ー'
        return next_char

    katakana = ""
    for i in range(len(kata) - 1, -1, -1):
        if i == 0:
            katakana = kata[i] + katakana
        else:
            katakana = convert_choonpu(kata[i - 1], kata[i]) + katakana
    return katakana


def katakana_to_romanji(kata: str) -> str:
    return ''.join([katakana_to_romanji_dict.get(k, k) for k in kata])


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

romaji_to_katakana_dict: dict[str, str] = {
    'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ',
    'ka': 'カ', 'ki': 'キ', 'ku': 'ク', 'ke': 'ケ', 'ko': 'コ',
    'sa': 'サ', 'shi': 'シ', 'su': 'ス', 'se': 'セ', 'so': 'ソ',
    'ta': 'タ', 'chi': 'チ', 'tsu': 'ツ', 'te': 'テ', 'to': 'ト',
    'na': 'ナ', 'ni': 'ニ', 'nu': 'ヌ', 'ne': 'ネ', 'no': 'ノ',
    'ha': 'ハ', 'hi': 'ヒ', 'fu': 'フ', 'he': 'ヘ', 'ho': 'ホ',
    'ma': 'マ', 'mi': 'ミ', 'mu': 'ム', 'me': 'メ', 'mo': 'モ',
    'ya': 'ヤ', 'yu': 'ユ', 'yo': 'ヨ',
    'ra': 'ラ', 'ri': 'リ', 'ru': 'ル', 're': 'レ', 'ro': 'ロ',
    'wa': 'ワ', 'n': 'ン',
    'ga': 'ガ', 'gi': 'ギ', 'gu': 'グ', 'ge': 'ゲ', 'go': 'ゴ',
    'za': 'ザ', 'ji': 'ジ', 'zu': 'ズ', 'ze': 'ゼ', 'zo': 'ゾ',
    'da': 'ダ', 'dzu': 'ヅ', 'de': 'デ', 'do': 'ド',
    'ba': 'バ', 'bi': 'ビ', 'bu': 'ブ', 'be': 'ベ', 'bo': 'ボ',
    'pa': 'パ', 'pi': 'ピ', 'pu': 'プ', 'pe': 'ペ', 'po': 'ポ',
    'kya': 'キャ', 'kyu': 'キュ', 'kyo': 'キョ',
    'sha': 'シャ', 'shu': 'シュ', 'sho': 'ショ',
    'cha': 'チャ', 'chu': 'チュ', 'cho': 'チョ',
    'nya': 'ニャ', 'nyu': 'ニュ', 'nyo': 'ニョ',
    'hya': 'ヒャ', 'hyu': 'ヒュ', 'hyo': 'ヒョ',
    'mya': 'ミャ', 'myu': 'ミュ', 'myo': 'ミョ',
    'rya': 'リャ', 'ryu': 'リュ', 'ryo': 'リョ',
    'gya': 'ギャ', 'gyu': 'ギュ', 'gyo': 'ギョ',
    'ja': 'ジャ', 'ju': 'ジュ', 'jo': 'ジョ',
    'dya': 'ヂャ', 'dyu': 'ヂュ', 'dyo': 'ヂョ',
    'bya': 'ビャ', 'byu': 'ビュ', 'byo': 'ビョ',
    'pya': 'ピャ', 'pyu': 'ピュ', 'pyo': 'ピョ',
    'wi': 'ウィ', 'we': 'ウェ', 'wo': 'ウォ',
    'va': 'ヴァ', 'vi': 'ヴィ', 'vu': 'ヴ', 've': 'ヴェ', 'vo': 'ヴォ',
    'fa': 'ファ', 'fi': 'フィ', 'fe': 'フェ', 'fo': 'フォ',
    'ti': 'ティ', 'tu': 'トゥ', 'di': 'ディ', 'du': 'ドゥ',
    'je': 'ジェ', 'she': 'シェ', 'che': 'チェ',
    'tsa': 'ツァ', 'tsi': 'ツィ', 'tse': 'ツェ', 'tso': 'ツォ'
}

katakana_to_romanji_dict = {v: k for k, v in romaji_to_katakana_dict.items()}

set_a = {'ア', 'カ', 'サ', 'タ', 'ナ', 'ハ', 'マ', 'ヤ', 'ラ', 'ワ', 'ガ', 'ザ', 'ダ', 'バ', 'パ'}
set_i = {'イ', 'キ', 'シ', 'チ', 'ニ', 'ヒ', 'ミ', 'リ', 'ギ', 'ジ', 'ヂ', 'ビ', 'ピ', 'ィ'}
set_u = {'ウ', 'ク', 'ス', 'ツ', 'ヌ', 'フ', 'ム', 'ユ', 'ル', 'グ', 'ズ', 'ヅ', 'ブ', 'プ'}
set_e = {'エ', 'ケ', 'セ', 'テ', 'ネ', 'ヘ', 'メ', 'レ', 'ゲ', 'ゼ', 'デ', 'ベ', 'ペ', 'ェ'}
set_o = {'オ', 'コ', 'ソ', 'ト', 'ノ', 'ホ', 'モ', 'ヨ', 'ロ', 'ゴ', 'ゾ', 'ド', 'ボ', 'ポ', 'ォ'}
