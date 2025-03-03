key = [0x00]*16
key = bytes(key)
iv = [0x00]*16
iv = bytes(iv)

import binascii

message = b"000003200000000000060004000200020004000200010000000000000000000000000000000000000000000000000000001e000d00090008000b0010001b001300090006000500060006000a000b000b00080005000a0013000600050002000200030003000100010001000000000000000000020001000100000000000100000004000500030002000300010001000100000000000000000000000000000000000000000000000000070005000100010003000400030001000000000000000000000000000000000000000000000000000500040002000100020002000200000000000000000000000000000000000000000000000000000003000300030002000100010001000000000000000000000000000000000000000000000000000000030003000300020003000200010000000000000000000000000000000000000000000000000000000700050003000000020003000000000000000000000000000000000000000000000000000000000007000700020002000200010002000000000000000000000000000000000000000000000000000000030004000300020004000400010000000000000000000000000000000000000000000000000000000e0006000300020003000400020001000000000000000000000002000300000000000000000000000800060002000200030001000000000000000000000000000000000000000000000000000000000008000500010002000200020001000000000000000000000000000000000000000000000000000000080005000400030002000100020000000000000000000000000000000000000000000000000000000b0006000300020003000200010001000000000000000000000000000000000000000000000000000600060002000200030002000100000000000000000000000000000000000000000000000000000007000700060003000200030001000000000000000000000000000000000000000000000000000000080005000100010002000200020000000000000000000000000000000000000000000000000000000500070002000200040002000100000000000000000000000000000000000000000000000000000caaa4ef95352be2b2884c7b6a142944"
message = binascii.unhexlify(message)

# AES-CMAC : 0x763cbcde81df9131bf897712c088edad

true_message = message[:-16]
true_tag = message[-16:]


from cryptography.hazmat.primitives.cmac import CMAC
from cryptography.hazmat.primitives.ciphers import algorithms, Cipher, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac

def compute_aes_cmac(key, message):
    """
    Compute AES-CMAC using the provided key and message.
    """
    # Create a CMAC object
    cmac = CMAC(algorithms.AES(key), backend=default_backend())
    cmac.update(message)
    return cmac.finalize()

def compute_gmac(key, message):
    """
    Compute AES-GCM MAC (GMAC) using the provided key, IV, and message.
    GMAC is computed by authenticating the additional data (message) without encrypting any plaintext.
    """
    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(iv),
        backend=default_backend()
    )
    encryptor = cipher.encryptor()
    encryptor.authenticate_additional_data(message)
    # Finalize to complete tag computation
    encryptor.finalize()
    return encryptor.tag

def compute_cbc_mac(key, message):
    # Pad message to multiple of 16 bytes
    padded_len = ((len(message) + 15) // 16) * 16
    padded_msg = message + b'\x00' * (padded_len - len(message))
    
    # Use CBC mode with zero IV
    zero_iv = bytes([0] * 16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(zero_iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_msg) + encryptor.finalize()
    
    # Return the last block as the tag
    return ciphertext[-16:]


def verify_message(name, tag_func):
    tag = tag_func(key, true_message)
    print("Computed", name, "\t:", binascii.hexlify(tag).decode())
    print("Expected mac:     \t:", binascii.hexlify(true_tag).decode())
    if binascii.hexlify(tag) == binascii.hexlify(true_tag):
        print("\033[92mVerification successful!\033[0m")  # Green color for success
    else:
        print("\033[91mVerification failed!\033[0m")  # Red color for failure

verify_message("AES-CMAC", compute_aes_cmac)
verify_message("AES-GCM", compute_gmac)
verify_message("AES-CBC", compute_cbc_mac)

new_cmac = CMAC(algorithms.AES(key), backend=default_backend())
new_cmac.update(bytes(16))
print("New CMAC: ", binascii.hexlify(new_cmac.finalize()).decode())