"""List of speech corpora metadata."""

import re
from typing import Callable, Dict, List, Optional, Set


class CorpusInfo:
    """Represents metadata for a generic speech corpus.

    Parameters:
    -----------
    name: str
        The corpus name.
    get_speaker: callable
        A function that takes a clip name as argument and returns the
        corresponding speaker.
    male_speakers: list of str
        List of male speakers.
    female_speakers: list of str
        List of female speakers.
    speakers: list of str
        List of all speakers. At least one of speakers, male_speakers,
        female_speakers must be present. If speakers is not present, it will be
        the union of male_speakers and female_speakers.
    """
    def __init__(self,
                 name: str,
                 get_speaker: Callable[[str], str],
                 male_speakers: List[str] = [],
                 female_speakers: List[str] = [],
                 speakers: List[str] = [],
                 speaker_groups: List[Set[str]] = []):
        self.name = name

        self.male_speakers = male_speakers
        self.female_speakers = female_speakers
        self.speakers = speakers
        if self.male_speakers and self.female_speakers:
            all_speakers = self.male_speakers + self.female_speakers
            if self.speakers and set(self.speakers) != set(all_speakers):
                raise ValueError("Given speaker list inconsistent with male "
                                 "and female speakers.")
            else:
                self.speakers = all_speakers
        if len(self.speakers) == 0:
            raise ValueError(
                "There must be at least one speaker for this corpus.")

        if speaker_groups:
            self.speaker_groups = speaker_groups
        else:
            self.speaker_groups = [{x} for x in self.speakers]
        self.get_speaker = get_speaker

    def get_speaker(self, name: str) -> str:
        raise NotImplementedError()

    def get_speaker_group(self, name: str) -> int:
        for idx, g in enumerate(self.speaker_groups):
            if name in g:
                return idx


class EmotionalCorpusInfo(CorpusInfo):
    """Represents metadata for an emotional speech corpus.

    Parameters:
    -----
    name: str
        The corpus name.
    emotion_map: dict
        A mapping from corpus emotion labels to English emotion words.
    get_emotion: callable
        Function that takes a clip name and returns the corresponding corpus
        emotion label present.
    """
    def __init__(self,
                 name: str,
                 emotion_map: Dict[str, str] = {},
                 get_emotion: Optional[Callable[[str], str]] = None,
                 **kwargs):
        super().__init__(name, **kwargs)
        self.emotion_map = emotion_map
        self.get_emotion = get_emotion

    def get_emotion(self, name: str) -> str:
        raise NotImplementedError()


corpora: Dict[str, EmotionalCorpusInfo] = {
    'cafe': EmotionalCorpusInfo(
        'cafe',
        emotion_map={
            'C': 'anger',
            'D': 'disgust',
            'J': 'happiness',
            'N': 'neutral',
            'P': 'fear',
            'S': 'surprise',
            'T': 'sadness'
        },
        male_speakers=['01', '03', '05', '07', '09', '11'],
        female_speakers=['02', '04', '06', '08', '10', '12'],
        get_emotion=lambda n: n[3],
        get_speaker=lambda n: n[:2]
    ),
    'crema-d': EmotionalCorpusInfo(
        'crema-d',
        emotion_map={
            'A': 'anger',
            'D': 'disgust',
            'F': 'fear',
            'H': 'happiness',
            'S': 'sadness',
            'N': 'neutral',
        },
        speakers=[
            '1042', '1070', '1030', '1087', '1061', '1086', '1026', '1017',
            '1039', '1082', '1032', '1015', '1062', '1012', '1046', '1010',
            '1014', '1064', '1080', '1023', '1056', '1066', '1035', '1074',
            '1068', '1027', '1043', '1065', '1076', '1060', '1019', '1011',
            '1075', '1008', '1006', '1025', '1053', '1058', '1085', '1069',
            '1024', '1084', '1033', '1054', '1090', '1013', '1038', '1072',
            '1036', '1088', '1071', '1005', '1057', '1029', '1020', '1073',
            '1050', '1007', '1031', '1003', '1002', '1079', '1040', '1047',
            '1077', '1078', '1049', '1051', '1041', '1052', '1083', '1016',
            '1034', '1009', '1055', '1048', '1018', '1091', '1045', '1022',
            '1004', '1089', '1067', '1059', '1063', '1001', '1021', '1028',
            '1044', '1037', '1081'
        ],
        get_emotion=lambda n: n[9],
        get_speaker=lambda n: n[:4]
    ),
    'demos': EmotionalCorpusInfo(
        'demos',
        emotion_map={
            'rab': 'anger',
            'tri': 'sadness',
            'gio': 'happiness',
            'pau': 'fear',
            'dis': 'disgust',
            'col': 'guilt',
            'sor': 'surprise'
        },
        male_speakers=[
            '02', '03', '04', '05', '08', '09', '10', '11', '12', '14', '15',
            '16', '18', '19', '23', '24', '25', '26', '27', '28', '30', '33',
            '34', '39', '41', '50', '51', '52', '53', '58', '59', '63', '64',
            '65', '66', '67', '68', '69'
        ],
        female_speakers=[
            '01', '17', '21', '22', '29', '31', '36', '37', '38', '40', '43',
            '45', '46', '47', '49', '54', '55', '56', '57', '60', '61'
        ],
        get_emotion=lambda n: n[-6:-3],
        get_speaker=lambda n: n[-9:-7]
    ),
    'emodb': EmotionalCorpusInfo(
        'emodb',
        emotion_map={
            'W': 'anger',
            'L': 'boredom',
            'E': 'disgust',
            'A': 'fear',
            'F': 'happiness',
            'T': 'sadness',
            'N': 'neutral'
        },
        male_speakers=['03', '10', '11', '12', '15'],
        female_speakers=['08', '09', '13', '14', '16'],
        get_emotion=lambda n: n[5],
        get_speaker=lambda n: n[:2]
    ),
    'emofilm': EmotionalCorpusInfo(
        'emofilm',
        emotion_map={
            'ans': 'fear',
            'dis': 'disgust',
            'gio': 'happiness',
            'rab': 'anger',
            'tri': 'sadness'
        },
        speakers=['en', 'es', 'it'],
        get_emotion=lambda n: n[2:5],
        get_speaker=lambda n: n[-2:]
    ),
    'enterface': EmotionalCorpusInfo(
        'enterface',
        emotion_map={
            'an': 'anger',
            'di': 'disgust',
            'fe': 'fear',
            'ha': 'happiness',
            'sa': 'sadness',
            'su': 'surprise'
        },
        speakers=['s' + str(i) for i in range(1, 45) if i != 6],
        get_emotion=lambda n: n[-4:-2],
        get_speaker=lambda n: n[:n.find('_')]
    ),
    'iemocap': EmotionalCorpusInfo(
        'iemocap',
        emotion_map={
            'ang': 'anger',
            'hap': 'happiness',
            'sad': 'sadness',
            'neu': 'neutral'
        },
        male_speakers=['01M', '02M', '03M', '04M', '05M'],
        female_speakers=['01F', '02F', '03F', '04F', '05F'],
        speaker_groups=[{'01M', '01F'}, {'02M', '02F'}, {'03M', '03F'},
                        {'04M', '04F'}, {'05M', '05F'}],
        get_emotion=lambda n: n[-3:],
        get_speaker=lambda n: n[3:6]
    ),
    'jl': EmotionalCorpusInfo(
        'jl',
        emotion_map={
            'angry': 'anger',
            'sad': 'sadness',
            'neutral': 'neutral',
            'happy': 'happiness',
            'excited': 'excitedness'
        },
        male_speakers=['male1', 'male2'],
        female_speakers=['female1', 'female2'],
        get_emotion=lambda n: re.match(r'^\w+\d_([a-z]+)_.*$', n).group(1),
        get_speaker=lambda n: n[:n.find('_')]
    ),
    'msp-improv': EmotionalCorpusInfo(
        'msp-improv',
        emotion_map={
            'A': 'anger',
            'H': 'happiness',
            'S': 'sadness',
            'N': 'neutral'
        },
        male_speakers=['M01', 'M02', 'M03', 'M04', 'M05', 'M06'],
        female_speakers=['F01', 'F02', 'F03', 'F04', 'F05', 'F06'],
        speaker_groups=[{'M01', 'F01'}, {'M02', 'F02'}, {'M03', 'F03'},
                        {'M04', 'F04'}, {'M05', 'F05'}, {'M06', 'F06'}],
        get_emotion=lambda n: n[-1],
        get_speaker=lambda n: n[5:8]
    ),
    'portuguese': EmotionalCorpusInfo(
        'portuguese',
        emotion_map={
            'angry': 'anger',
            'disgust': 'disgust',
            'fear': 'fear',
            'happy': 'happiness',
            'sad': 'sadness',
            'neutral': 'neutral',
            'surprise': 'surprise'
        },
        speakers=['A', 'B'],
        get_emotion=lambda n: re.match(
            r'^\d+[sp][AB]_([a-z]+)\d+$', n).group(1),
        get_speaker=lambda n: n[n.find('_') - 1]
    ),
    'ravdess': EmotionalCorpusInfo(
        'ravdess',
        emotion_map={
            '01': 'neutral',
            '02': 'calm',
            '03': 'happiness',
            '04': 'sadness',
            '05': 'anger',
            '06': 'fear',
            '07': 'disgust',
            '08': 'surprise'
        },
        male_speakers=['{:02d}'.format(i) for i in range(1, 25, 2)],
        female_speakers=['{:02d}'.format(i) for i in range(2, 25, 2)],
        get_emotion=lambda n: n[6:8],
        get_speaker=lambda n: n[-2:]
    ),
    'savee': EmotionalCorpusInfo(
        'savee',
        emotion_map={
            'a': 'anger',
            'd': 'disgust',
            'f': 'fear',
            'h': 'happiness',
            'n': 'neutral',
            'sa': 'sadness',
            'su': 'surprise'
        },
        speakers=['DC', 'JE', 'JK', 'KL'],
        get_emotion=lambda n: n[3] if n[4].isdigit() else n[3:5],
        get_speaker=lambda n: n[:2]
    ),
    'semaine': EmotionalCorpusInfo(
        'semaine',
        emotion_map={},
        speakers=['{:02d}'.format(i) for i in range(1, 25) if i not in [7, 8]],
        get_speaker=lambda n: n[:2]
    ),
    'shemo': EmotionalCorpusInfo(
        'shemo',
        emotion_map={
            'A': 'anger',
            'H': 'happiness',
            'N': 'neutral',
            'S': 'sadness',
            'W': 'surprise'
        },
        male_speakers=['M{:02d}'.format(i) for i in range(1, 57)],
        female_speakers=['F{:02d}'.format(i) for i in range(1, 32)],
        get_emotion=lambda n: n[3],
        get_speaker=lambda n: n[:3]
    ),
    'smartkom': EmotionalCorpusInfo(
        'smartkom',
        emotion_map={
            'Neutral': 'neutral',
            'Freude_Erfolg': 'happiness',
            'Uberlegen_Nachdenken': 'pondering',
            'Ratlosigkeit': 'helplessness',
            'Arger_Miserfolg': 'anger',
            'Uberraschung_Verwunderung': 'surprise',
            'Restklasse': 'unknown'
        },
        speakers=[
            'AAA', 'AAB', 'AAC', 'AAD', 'AAE', 'AAF', 'AAG', 'AAH', 'AAI',
            'AAJ', 'AAK', 'AAL', 'AAM', 'AAN', 'AAO', 'AAP', 'AAQ', 'AAR',
            'AAS', 'AAT', 'AAU', 'AAV', 'AAW', 'AAX', 'AAY', 'AAZ', 'ABA',
            'ABB', 'ABC', 'ABD', 'ABE', 'ABF', 'ABG', 'ABH', 'ABI', 'ABJ',
            'ABK', 'ABL', 'ABM', 'ABN', 'ABO', 'ABP', 'ABQ', 'ABR', 'ABS',
            'AIS', 'AIT', 'AIU', 'AIV', 'AIW', 'AIX', 'AIY', 'AIZ', 'AJA',
            'AJB', 'AJC', 'AJD', 'AJE', 'AJF', 'AJG', 'AJH', 'AJI', 'AJJ',
            'AJK', 'AJL', 'AJM', 'AJN', 'AJO', 'AJP', 'AJQ', 'AJR', 'AJS',
            'AJT', 'AJU', 'AJV', 'AJW', 'AJX', 'AJY', 'AJZ', 'AKA', 'AKB',
            'AKC', 'AKD', 'AKE', 'AKF', 'AKG'
        ],
        get_speaker=lambda n: n[8:11]
    ),
    'tess': EmotionalCorpusInfo(
        'tess',
        emotion_map={
            'angry': 'anger',
            'disgust': 'disgust',
            'fear': 'fear',
            'happy': 'happiness',
            'ps': 'surprise',
            'sad': 'sadness',
            'neutral': 'neutral'
        },
        speakers=['OAF', 'YAF'],
        get_emotion=lambda n: n[n.rfind('_') + 1:],
        get_speaker=lambda n: n[:3]
    ),

    'accentdb': CorpusInfo(
        'accentDB',
        get_speaker=lambda n: n[:n.rfind('_')],
        speakers=[
            'australian_s01', 'australian_s01', 'bangla_s01', 'bangla_s02',
            'indian_s01', 'indian_s02', 'malayalam_s01', 'malayalam_s02',
            'malayalam_s03', 'odiya_s01', 'telugu_s01', 'telugu_s02',
            'welsh_s01'
        ]
    ),
    'esf': CorpusInfo(
        'ESF',
        get_speaker=lambda n: n[-2:],
        speakers=['JA', 'MA', 'RA', 'AN', 'LA', 'SA', 'VI'],
    ),
    'leap': CorpusInfo(
        'Leap',
        get_speaker=lambda n: n[:2],
        speakers=[
            'ab', 'ai', 'aj', 'aw', 'ax', 'ay', 'az', 'ba', 'bb', 'bc', 'bd',
            'be', 'bf', 'bg', 'bh', 'bi', 'bj', 'bk', 'bl', 'bm', 'bn', 'bo',
            'bp', 'bq', 'br', 'bs', 'bt', 'bu', 'bv', 'bw', 'bx', 'by', 'bz',
            'ca', 'cb', 'cc', 'cd', 'ce', 'cf', 'cg', 'ch', 'ci', 'cl', 'cm',
            'cn', 'cp', 'cq', 'cr', 'dv', 'ev'
        ]
    )
}
