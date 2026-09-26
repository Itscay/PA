import sounddevice as sd
import numpy as np
print('Testing microphone recording (3 seconds) on device 1...')
rec = sd.rec(int(3 * 44100), samplerate=44100, channels=1, dtype='float32', device=1)
sd.wait()
max_amp = np.max(np.abs(rec))
print(f'Max amplitude: {max_amp:.6f}')
if max_amp < 0.001:
    print('MICROPHONE STILL SILENT - Check Windows Settings > Privacy > Microphone')
else:
    print('Microphone working')