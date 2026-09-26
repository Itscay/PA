import sounddevice as sd
info = sd.query_devices(13)
print(f'Device 13: {info["name"]}')
print(f'Max input channels: {info["max_input_channels"]}')
print(f'Default sample rate: {info["default_samplerate"]}')