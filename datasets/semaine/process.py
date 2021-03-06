import argparse
import re
from pathlib import Path
from xml.etree import ElementTree as et

import numpy as np
import soundfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session_dir", type=Path, default="Sessions")
    parser.add_argument("output_dir", type=Path, default="combined")
    args = parser.parse_args()

    recordings = {}
    session_dirs = args.session_dir.glob('*')
    for session_dir in session_dirs:
        session_id = int(session_dir.stem)

        session_file = session_dir / 'session.xml'
        session_xml = et.parse(session_file).getroot()
        recording = int(session_xml.attrib['recording'])
        character = session_xml.attrib['character']

        files = session_dir.glob('*')
        word_annotations_user = next((f for f in files if re.search(
            r'wordLevel_alignedTranscript.*_user', f)), None)
        word_annotations_operator = next((f for f in files if re.search(
            r'wordLevel_alignedTranscript.*_operator', f)), None)
        aligned_transcript = next((f for f in files if re.search(
            r'[^_]alignedTranscript_[0-9]+.*\.txt', f)), None)
        feeltraces = [f for f in files if re.search(
            r'[AR][0-9].*\.txt', f)]
        annotations = {}
        for trace in feeltraces:
            match = re.search(
                r'[AR]([0-9]+)[RS]([0-9]+)TUC(Ob|Po|Pr|Sp)2?D([AEPV])\.txt',
                trace
            )
            if match:
                rater = int(match.group(1))
                emotion = {'A': 'Activation', 'E': 'Expectation', 'P': 'Power',
                           'V': 'Valence'}[match.group(4)]
                if emotion not in annotations:
                    annotations[emotion] = {}
                annotations[emotion][rater] = trace
        operator_audio = next((f for f in files if re.search(
            r'Operator HeadMounted.*\.wav', f)), None)
        user_audio = next((f for f in files if re.search(
            r'User HeadMounted.*\.wav', f)), None)
        if recording not in recordings:
            recordings[recording] = []
        session_info = (session_id,
                        character,
                        operator_audio,
                        word_annotations_operator,
                        user_audio,
                        word_annotations_user,
                        aligned_transcript,
                        annotations)
        recordings[recording].append(session_info)

    for recording, sessions in sorted(recordings.items()):
        duration = 0
        concat_user_audio = []
        concat_operator_audio = []
        concat_words_user = ''
        concat_words_operator = ''
        concat_transcript = ''
        emotion_data = {}
        sessions.sort(key=lambda x: x[0])
        print("Recording {}:".format(recording))
        for (session_id,
             character,
             operator_audio,
             word_annotations_operator,
             user_audio,
             word_annotations_user,
             aligned_transcript,
             annotations) in sessions:
            if (character.lower() in ['beginning', 'end', 'forbidden']
                    or not word_annotations_user):
                continue

            audio, _ = soundfile.read(user_audio)
            concat_user_audio.append(audio.data)
            audio, _ = soundfile.read(operator_audio)
            concat_operator_audio.append(audio.data)

            print('\t', word_annotations_operator)
            print('\t', word_annotations_user)
            print('\t', aligned_transcript)

            for emotion in annotations:
                rater_data = []
                for rater in annotations[emotion]:
                    trace = annotations[emotion][rater]
                    rater_data.append(
                        np.fromfile(trace, sep=' ').reshape((-1, 2)))

                # Clip rows to size of smallest array across raters
                smallest = np.argmin([x.shape[0] for x in rater_data])
                max_size = np.max([x.shape[0] for x in rater_data])
                num_indices = rater_data[smallest].shape[0]
                for i in range(len(rater_data)):
                    rater_data[i] = rater_data[i][:num_indices, :]

                min_size = num_indices
                print('\t', emotion, len(rater_data), rater_data[0].shape)
                if max_size - min_size > 2:
                    print("\t\t WARNING: Raters difference: ",
                          max_size - min_size)
                mean_values = np.stack(
                    [x[:, 1] for x in rater_data], axis=0).mean(0)
                mean_raters = np.stack(
                    [rater_data[0][:, 0], mean_values], axis=1)
                mean_raters[:, 0] += (duration / 1000)

                if emotion not in emotion_data:
                    emotion_data[emotion] = mean_raters
                else:
                    emotion_data[emotion] = np.concatenate(
                        [emotion_data[emotion], mean_raters], axis=0)

            # Clip rows to size of smallest array across emotions
            smallest_emotion = min(
                emotion_data, key=lambda e: emotion_data[e].shape[0])
            max_size = max([emotion_data[e].shape[0] for e in emotion_data])
            num_indices = emotion_data[smallest_emotion].shape[0]
            for e in emotion_data:
                emotion_data[e] = emotion_data[e][:num_indices, :]

            min_size = num_indices
            if max_size - min_size > 2:
                print("\t WARNING: Emotions difference: ", max_size - min_size)

            if aligned_transcript:
                with open(aligned_transcript) as fid:
                    concat_transcript += fid.read()
            if word_annotations_user:
                with open(word_annotations_user) as fid:
                    for line in fid:
                        m = re.search(
                            r'([0-9]+) ([0-9]+) ([A-Z\'"?.<>]+)', line)
                        if m:
                            line = '{} {} {}\n'.format(
                                int(m.group(1)) + duration,
                                int(m.group(2)) + duration,
                                m.group(3))
                        concat_words_user += line
            if word_annotations_operator:
                with open(word_annotations_operator) as fid:
                    for line in fid:
                        m = re.search(
                            r'([0-9]+) ([0-9]+) ([A-Z\'"?.<>]+)', line)
                        if m:
                            line = '{} {} {}\n'.format(
                                int(m.group(1)) + duration,
                                int(m.group(2)) + duration,
                                m.group(3))
                        concat_words_operator += line
            duration += int(1000 * len(audio) / 16000)

        if len(emotion_data.keys()) < 4:
            continue

        concat_user_audio = np.array(concat_user_audio)
        concat_operator_audio = np.array(concat_operator_audio)

        output_dir = args.output_dir / str(recording)
        output_dir.mkdir(exist_ok=True)
        soundfile.write(output_dir / 'user_audio.wav', concat_user_audio,
                        samplerate=16000)
        soundfile.write(output_dir / 'operator_audio.wav',
                        concat_operator_audio, samplerate=16000)
        with open(output_dir / 'transcript.txt', 'w') as fid:
            fid.write(concat_transcript)
        with open(output_dir / 'words_user.txt', 'w') as fid:
            fid.write(concat_words_user)
        with open(output_dir / 'words_operator.txt', 'w') as fid:
            fid.write(concat_words_operator)
        with open(output_dir / 'emotions.txt', 'w') as fid:
            fid.write("Time")
            sorted_emotions = sorted(emotion_data.keys())  # For consistency
            for emotion in sorted_emotions:
                fid.write(' ' + emotion)
            fid.write('\n')
            for i in range(emotion_data['Valence'].shape[0]):
                fid.write('{:.2f}'.format(emotion_data['Valence'][i, 0]))
                for emotion in sorted_emotions:
                    fid.write(' {:.4f}'.format(emotion_data[emotion][i, 1]))
                fid.write('\n')


if __name__ == "__main__":
    main()
