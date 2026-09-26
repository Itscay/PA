import sounddevice as sd
for i, dev in enumerate(sd.query_devices()):
    if dev['max_input_channels'] > 0:
        print(f'[{i}] {dev["name"]}, hostapi={dev["hostapi"]}, ch={dev["max_input_channels"]}, sr={dev["default_samplerate"]}')