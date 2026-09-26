import sounddevice as sd
try:
    info = sd.query_devices(13)
    print(f'Device 13: {info["name"]}, rate={info["default_samplerate"]}, ch={info["max_input_channels"]}')
    sd.check_input_settings(device=13, samplerate=44100, channels=1, dtype='float32')
    print('check_input_settings OK for 1ch')
except Exception as e:
    print(f'Error: {e}')