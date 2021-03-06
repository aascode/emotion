import argparse
from collections import Counter
from pathlib import Path

from emotion_recognition.dataset import corpora

parser = argparse.ArgumentParser()
parser.add_argument('--corpus', required=True)
parser.add_argument('--directory', required=True, type=Path)
parser.add_argument('--output', type=Path)


def main():
    args = parser.parse_args()

    corpus_info = corpora[args.corpus]
    emotions = Counter()
    for p in args.directory.glob('*.wav'):
        emotion = corpus_info.get_emotion(p.stem)
        try:
            emotion = corpus_info.emotion_map[emotion]
        except KeyError:
            emotion = 'unknown'
        emotions[emotion] += 1
    print("Emotion distribution:")
    for emotion, count in emotions.items():
        print("{:<10s}: {:d}".format(emotion, count))

    if not args.output:
        return
    with open(args.output, 'w') as fid:
        print("Name,Emotion", file=fid)
        for p in sorted(args.directory.glob('*.wav')):
            emotion = corpus_info.get_emotion(p.stem)
            try:
                emotion = corpus_info.emotion_map[emotion]
            except KeyError:
                emotion = 'unknown'
            print('{},{}'.format(p.stem, emotion), file=fid)


if __name__ == "__main__":
    main()
