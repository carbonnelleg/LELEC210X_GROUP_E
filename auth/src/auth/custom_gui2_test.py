import asyncio
import aiohttp
import time
import numpy as np
import base64
import random

# Constants matching expected structure
CLASS_NAMES = ['chainsaw', 'fire', 'fireworks', 'gun']
MEL_SPEC_NUM = 20
MEL_SPEC_LEN = 20

async def send_packets():
    url = "http://127.0.0.1:8090/update"
    packet_counter = 0
    last_time = time.time()
    async with aiohttp.ClientSession() as session:
        while True:
            # Generate random probabilities and normalize them.
            probas = np.random.rand(len(CLASS_NAMES))
            probas /= np.sum(probas)
            # Create a random feature vector (list of lists)
            feature_vector = np.random.rand(MEL_SPEC_NUM, MEL_SPEC_LEN).tolist()
            # Generate random packet data (928 bytes total)
            packet_data = np.random.bytes(12 + 800 + 16)
            # Base64 encode the packet data
            packet_data_b64 = base64.b64encode(packet_data).decode('utf-8')
            # Choose a random class
            current_choice = random.choice(CLASS_NAMES)

            payload = {
                "current_class_names": CLASS_NAMES,
                "current_class_probas": probas.tolist(),
                "current_feature_vector": feature_vector,
                "current_packet_data": packet_data_b64,
                "current_choice": current_choice,
                "mel_spec_len": MEL_SPEC_LEN,
                "mel_spec_num": MEL_SPEC_NUM
            }

            try:
                async with session.post(url, json=payload) as resp:
                    # Optionally, print response status or JSON if needed.
                    # response_json = await resp.json()
                    # print(response_json)
                    pass
            except Exception as e:
                print("Error sending packet:", e)

            packet_counter += 1
            now = time.time()
            if now - last_time >= 1.0:
                print(f"Client: Packets sent per second: {packet_counter / (now - last_time):.2f}")
                packet_counter = 0
                last_time = now

            #await asyncio.sleep(0.1)  # 100ms delay

if __name__ == '__main__':
    asyncio.run(send_packets())
