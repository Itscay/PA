import sounddevice as sd
from assistant.audio.capture import list_input_devices, match_device_index, MicCapture, RingBuffer

devices = list_input_devices()
index = match_device_index(devices, 13)
print(f'match_device_index result: {index}')

info = sd.query_devices(index if index is not None else "input")
print(f'query_devices result: {info["name"]}, rate={info["default_samplerate"]}, ch={info["max_input_channels"]}')

# Try the full probe
mic = MicCapture(RingBuffer(16000), device=13)
try:
    mic.start()
    print("SUCCESS!")
    mic.stop()
except Exception as e:
    print(f'Error: {e}')