#!/usr/bin/env python3
"""Rebuild the original ambient tracks and motion studies. Requires numpy and ffmpeg."""
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT/'website/assets/media'
RATE = 32000
DURATION = 64


def score(seed, root, brightness):
    rng = np.random.default_rng(seed)
    n = RATE * DURATION
    t = np.arange(n, dtype=np.float64) / RATE
    stereo = np.zeros((n, 2), dtype=np.float64)
    chords = [[0, 7, 14, 17], [-3, 4, 9, 14], [-5, 2, 7, 12], [-2, 5, 10, 14]]
    for bar, notes in enumerate(chords):
        start = bar * 16
        relative = t - start
        envelope = np.minimum(np.clip(relative / 4, 0, 1), np.clip((20 - relative) / 5, 0, 1))
        for j, note in enumerate(notes):
            frequency = 440 * 2 ** ((root + note - 69) / 12)
            for channel in (0, 1):
                detune = 1 + (channel * 2 - 1) * .0009
                pad = np.sin(2*np.pi*frequency*detune*t + j)
                pad += brightness*.22*np.sin(2*np.pi*frequency*2*detune*t)
                pad += .08*np.sin(2*np.pi*frequency*3*t)
                stereo[:, channel] += pad*envelope*.09*(.86+.14*np.sin(t*.3+j))
        for beat in range(8):
            begin = start + beat*2 + .15
            length = 5
            index = int(begin*RATE)
            count = min(length*RATE, n-index)
            if count <= 0:
                continue
            local = np.arange(count)/RATE
            note = notes[(beat+bar) % len(notes)] + 24
            hz = 440*2**((root+note-69)/12)
            bell = (np.sin(2*np.pi*hz*local)+.18*np.sin(2*np.pi*hz*2.003*local))*np.exp(-local/1.3)
            bell *= np.clip(local/.025, 0, 1)*.075
            pan = rng.uniform(.2,.8)
            stereo[index:index+count, 0] += bell*np.sqrt(pan)
            stereo[index:index+count, 1] += bell*np.sqrt(1-pan)
    # Gentle feedback-free delay gives a little depth without copied audio samples.
    dry = stereo.copy()
    for delay, amount in ((.38,.17),(.73,.10),(1.17,.07)):
        offset = int(delay*RATE)
        stereo[offset:] += dry[:-offset, ::-1]*amount
    fade = np.minimum(np.clip(t/3, 0, 1), np.clip((DURATION-t)/5, 0, 1))
    stereo *= fade[:, None]
    stereo *= .78/max(1e-8, np.max(np.abs(stereo)))
    return (stereo*32767).astype('<i2')


def run(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *map(str,args)], check=True)


def main():
    with tempfile.TemporaryDirectory(prefix='3xi-media-') as tmp:
        folder = Path(tmp)
        for seed, root, bright, name in [(31,45,.6,'low-tide'),(32,50,.9,'canopy'),(33,48,.4,'warm-concrete')]:
            path = folder/(name+'.wav')
            with wave.open(str(path), 'wb') as output:
                output.setnchannels(2); output.setsampwidth(2); output.setframerate(RATE)
                output.writeframes(score(seed, root, bright).tobytes())
            run('-i',path,'-c:a','libmp3lame','-b:a','128k', '-metadata','artist=3xi Atlas',
                '-metadata','title='+name.replace('-',' ').title(),folder/(name+'.mp3'))
            (folder/(name+'.mp3')).replace(MEDIA/(name+'.mp3'))
            print('Built',name+'.mp3',flush=True)
        for name, image, track in [('coast','volcanic-coast','low-tide'),('forest','forest-light','canopy'),('space','quiet-architecture','warm-concrete')]:
            motion = "scale=1920:1280,crop=1920:1080,zoompan=z='1.025+on*0.00009':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=384:s=1280x720:fps=24,fade=t=in:d=0.7,fade=t=out:st=15.2:d=0.8"
            run('-i',MEDIA/(image+'.webp'),'-i',folder/(track+'.wav'),'-vf',motion,
                '-af','afade=t=out:st=14:d=2','-t','16','-c:v','libx264','-preset','medium',
                '-threads','4','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k',
                '-movflags','+faststart',folder/(name+'.mp4'))
            (folder/(name+'.mp4')).replace(MEDIA/(name+'.mp4'))
            print('Built',name+'.mp4',flush=True)


if __name__ == '__main__':
    main()
