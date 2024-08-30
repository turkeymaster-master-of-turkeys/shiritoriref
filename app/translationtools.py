import logging
from jisho_api.word import Word

logger = logging.getLogger("shiritori-ref")


def match_kana(prev: str, curr: str) -> bool:
    if not prev or not curr:
        return False
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


async def search_jisho(term: str) -> dict:
    """
    Searches the Jisho API for a term
    :param term: Search term
    :return: Dictionary of words
    """
    wr = Word.request(term)
    if not wr:
        return {}
    words = {}
    for x in wr.dict()['data']:
        for y in x['japanese']:
            reading = y['reading']
            if not reading or len(reading) <= 1:
                continue
            word_info = {'word': y['word'],
                         'meanings': [sense['english_definitions'][0] for sense in x['senses']],
                         'reading': reading
                         }

            if reading in words:
                words[reading].append(word_info)
            else:
                words[reading] = [word_info]
    return words


async def get_words_starting_with(word: str) -> dict:
    start = word[-2:] if word[-1] in "ゃゅょャュョァィェォ" else word[-1]
    words = await search_jisho(f"{start}*")
    return {k: v for k, v in words.items() if k.startswith(start)}


def meaning_to_string(meanings: list[dict], num: int = 3) -> str:
    """
    Converts a list of meanings to a string for sending

    :param meanings: List of meanings
    :param num: How many meanings to include
    :return: String of meanings
    """
    out = []
    for i in range(num):
        if i >= len(meanings):
            break
        meaning = meanings[i]
        kanji_reading = f"{meaning['word']} ({meaning['reading']})" if meaning['word'] else meaning['reading']
        out.append(f"{kanji_reading}:\n> {', '.join(meaning['meanings'])}")
    return "\n".join(out)


def remove_romaji_long_vowels(romaji: str) -> str:
    """
    Removes long vowels from a romaji string, does not affect non-romaji characters

    :param romaji: Romaji string    :return:  without long vowels
    """
    return (romaji.replace('aa', 'a')
            .replace('ii', 'i').replace('uu', 'u')
            .replace('ee', 'e').replace('oo', 'o')
            .replace('ou', 'o').replace('ei', 'e'))


def romaji_to_kana(word: str, dictionary: dict[str, str], tsu: str) -> str:
    """
    Converts a string to a list of possible kana, using a specified dictionary

    :param tsu: Small tsu to use
    :param dictionary: The dictionary to use
    :param word: The word to convert
    :return: All possible kana parsings of the word with the dictionary
    """
    i = 0
    kana_word = ""
    for j in range(min(3, len(word) - i), 0, -1):
        if word[i:i + j] in dictionary:
            kana_word += dictionary[word[i:i + j]]
            i += j
            break
    while i < len(word):
        if i + 1 < len(word) and word[i] == word[i + 1] and word[i] != 'n':
            kana_word += tsu  # Small tsu
            i += 1
        for j in range(min(3, len(word) - i), 0, -1):
            if word[i:i + j] in dictionary:
                kana_word += dictionary[word[i:i + j]]
                i += j
                break
        else:
            return ''
    return kana_word


def romaji_to_katakana(word: str) -> tuple[list[str], list[str]]:
    """
    Converts a string to a list of possible katakana
    :param word: The word to convert
    :return: All possible katakana parsings of the word
    """

    kata = romaji_to_kana(word, romaji_to_katakana_dict, 'ッ')
    if not kata:
        return [], []

    words_no_choonpu = ['']
    for c in kata:
        words_n = [w + n_dict[c] for w in words_no_choonpu] if c in 'ナニヌネノ' else []
        words_no_choonpu = [w + c for w in words_no_choonpu] + words_n

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

    words = ['']
    for c in katakana:
        words_n = [w + n_dict[c] for w in words] if c in 'ナニヌネノ' else []
        words = [w + c for w in words] + words_n

    return words, words_no_choonpu


def romaji_to_hira_kata(word: str) -> tuple[list[str], list[str]]:
    """
    Converts a string to a list of possible hiragana and katakana
    :param word: The word to convert
    :return: All possible hiragana and katakana parsings of the word
    """
    if all(c in set_hira for c in word):
        return [word], [hiragana_to_katakana(word)]
    if all(c in set_kata for c in word):
        return [katakana_to_hiragana(word)], [word]

    kata, kata_no_choonpu = romaji_to_katakana(word)
    hira = [katakana_to_hiragana(k) for k in kata_no_choonpu]

    return hira, kata


def kana_to_romaji(kana: str) -> str:
    dictionary = {**hiragana_to_romaji_dict, **katakana_to_romaji_dict}
    romaji = ""
    i = 0
    while True:
        if i >= len(kana):
            break
        if kana[i:i + 2] in dictionary:
            romaji += dictionary[kana[i:i + 2]]
            i += 2
        elif kana[i] in dictionary:
            romaji += dictionary[kana[i]]
            i += 1
        elif kana[i] == 'ー':
            if i > 0 and kana[i - 1] in dictionary:
                romaji += dictionary[kana[i - 1]][-1]
            elif i > 0 and kana[i - 2:i] in dictionary:
                romaji += dictionary[kana[i - 2:i]][-1]
            i += 1
        elif kana[i] in 'っッ':
            if i + 1 < len(kana) and kana[i + 1] in dictionary:
                romaji += dictionary[kana[i + 1]][0]
                i += 1
            else:
                return ""
        else:
            return kana
    return romaji


def hiragana_to_katakana(hira: str) -> str:
    return ''.join(hiragana_to_katakana_dict.get(c, c) for c in hira)


def katakana_to_hiragana(kata: str) -> str:
    hira = ""
    for c in kata:
        if c in katakana_to_hiragana_dict:
            hira += katakana_to_hiragana_dict[c]
        else:
            return ""
    return hira


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

katakana_to_romaji_dict = {v: k for k, v in romaji_to_katakana_dict.items()}
hiragana_to_romaji_dict = {v: k for k, v in romaji_to_hiragana_dict.items()}
hiragana_to_katakana_dict = {**{vh: vk for kk, vk in romaji_to_katakana_dict.items() for
                                kh, vh in romaji_to_hiragana_dict.items() if kk == kh},
                             **{'ゃ': 'ャ', 'ゅ': 'ュ', 'ょ': 'ョ', 'っ': 'ッ'}}
katakana_to_hiragana_dict = {v: k for k, v in hiragana_to_katakana_dict.items()}

set_hira = {v[-1] for _, v in romaji_to_hiragana_dict.items()}
set_hira.union({'っ'})
set_kata = {v[-1] for _, v in romaji_to_katakana_dict.items()}
set_kata.union({'ー', 'ッ', 'ヶ', 'ヵ'})
set_kata_mora = {v for _, v in romaji_to_katakana_dict.items()}

set_a = {'ア', 'カ', 'サ', 'タ', 'ナ', 'ハ', 'マ', 'ヤ', 'ラ', 'ワ', 'ガ', 'ザ', 'ダ', 'バ', 'パ'}
set_i = {'イ', 'キ', 'シ', 'チ', 'ニ', 'ヒ', 'ミ', 'リ', 'ギ', 'ジ', 'ヂ', 'ビ', 'ピ', 'ィ'}
set_u = {'ウ', 'ク', 'ス', 'ツ', 'ヌ', 'フ', 'ム', 'ユ', 'ル', 'グ', 'ズ', 'ヅ', 'ブ', 'プ'}
set_e = {'エ', 'ケ', 'セ', 'テ', 'ネ', 'ヘ', 'メ', 'レ', 'ゲ', 'ゼ', 'デ', 'ベ', 'ペ', 'ェ'}
set_o = {'オ', 'コ', 'ソ', 'ト', 'ノ', 'ホ', 'モ', 'ヨ', 'ロ', 'ゴ', 'ゾ', 'ド', 'ボ', 'ポ', 'ォ'}

n_dict = {
    'な': 'んあ', 'に': 'んい', 'ぬ': 'んう', 'ね': 'んえ', 'の': 'んお',
    'ナ': 'ンア', 'ニ': 'ンイ', 'ヌ': 'ンウ', 'ネ': 'ンエ', 'ノ': 'ンオ'
}
