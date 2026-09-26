import sounddevice as sd

print("Testing MME devices (hostapi=0):")
for idx in [0, 1, 2]:
    try:
        info = sd.query_devices(idx)
        if info['max_input_channels'] > 0:
            stream = sd.InputStream(device=idx, samplerate=44100, channels=min(1, info['max_input_channels']), dtype='float32')
            stream.start()
            print(f'SUCCESS: device {idx} ({info["name"][:40]})')
            stream.stop()
            stream.close()
    except Exception as e:
        print(f'FAIL: device {idx} - {e}')

print('---')
print("Testing DirectSound devices (hostapi=1):")
for idx in [6, 7, 8]:
    try:
        info = sd.query_devices(idx)
        if info['max_input_channels'] > 0:
            stream = sd.InputStream(device=idx, samplerate=44100, channels=min(1, info['max_input_channels']), dtype='float32')
            stream.start()
            print(f'SUCCESS: device {idx} ({info["name"][:40]})')
            stream.stop()
            stream.close()
    except Exception as e:
        print(f'FAIL: device {idx} - {e}')