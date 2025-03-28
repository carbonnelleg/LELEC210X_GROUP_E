import os
from collections.abc import Iterator
from typing import Optional

import click
import serial
import zmq
import numpy as np
import json
import base64
import asyncio

import auth.model_prediction as mp
import common
from common.env import load_dotenv
from common.logging import logger
from leaderboard.submit import submit

from . import PRINT_PREFIX, packet
from . import custom_gui2_interface  # new module import

load_dotenv()

local_hostname = "http://localhost:5000"
local_key = "V_Uy207CdoePKVIQ_vguo_WsAr1iISYoz41FJX-m"

remote_hostname = "http://lelec210x.sipr.ucl.ac.be"
remote_key = "pKRQWoIQTgQ9YLfKFlESrQJ3cHk2ZKnNi1yltxQu"

REMOTE = True


def parse_packet(line: str) -> bytes:
    """Parse a line into a packet."""
    line = line.strip()
    if line.startswith(PRINT_PREFIX):
        return bytes.fromhex(line[len(PRINT_PREFIX):])
    else:
        return None


def hex_to_bytes(ctx: click.Context, param: click.Parameter, value: str) -> bytes:
    """Convert a hex string into bytes."""
    return bytes.fromhex(value)


@click.command()
@click.option(
    "-gui",
    "--gui",
    default=False,
    is_flag=True,
    help="Enable the custom GUI.",
)
@click.option(
    "-i",
    "--input",
    "_input",
    default=None,
    type=click.File("r"),
    help="Where to read the input stream. If not specified, read from TCP address. You can pass '-' to read from stdin.",
)
@click.option(
    "-o",
    "--output",
    default="-",
    type=click.File("w"),
    help="Where to write the output stream. Default to '-', a.k.a. stdout.",
)
@click.option(
    "--serial-port",
    default=None,
    envvar="SERIAL_PORT",
    show_envvar=True,
    help="If specified, read the packet from the given serial port. E.g., '/dev/tty0'. This takes precedence of `--input` and `--tcp-address` options.",
)
@click.option(
    "--tcp-address",
    default="tcp://127.0.0.1:10000",
    envvar="TCP_ADDRESS",
    show_default=True,
    show_envvar=True,
    help="TCP address to be used to read the input stream.",
)
@click.option(
    "-k",
    "--auth-key",
    default=16 * "00",
    envvar="AUTH_KEY",
    callback=hex_to_bytes,
    show_default=True,
    show_envvar=True,
    help="Authentification key (hex string).",
)
@click.option(
    "--authenticate/--no-authenticate",
    default=True,
    is_flag=True,
    help="Enable / disable authentication, useful for skipping authentication step.",
)
@common.click.melvec_length
@common.click.n_melvecs
@common.click.verbosity
def main(
    gui: bool,
    _input: Optional[click.File],
    output: click.File,
    serial_port: Optional[str],
    tcp_address: str,
    auth_key: bytes,
    authenticate: bool,
    melvec_length: int,
    n_melvecs: int,
) -> None:
    """
    Parse packets from the MCU and perform authentication.
    """
    logger.debug(f"Unwrapping packets with auth. key: {auth_key.hex()}")

    how_to_kill = (
        "Use Ctrl-C (or Ctrl-D) to terminate.\nIf that does not work, execute `"
        f"kill {os.getpid()}` in a separate terminal."
    )

    unwrapper = packet.PacketUnwrapper(
        key=auth_key,
        allowed_senders=[0],
        authenticate=authenticate,
    )

    if serial_port:  # Read from serial port

        def reader() -> Iterator[str]:
            ser = serial.Serial(port=serial_port, baudrate=115200)
            ser.reset_input_buffer()
            ser.read_until(b"\n")

            logger.debug(f"Reading packets from serial port: {serial_port}")
            logger.info(how_to_kill)

            while True:
                line = ser.read_until(b"\n").decode("ascii").strip()
                pkt = parse_packet(line)
                if pkt is not None:
                    yield pkt

    elif _input:  # Read from file-like

        def reader() -> Iterator[str]:
            logger.debug(f"Reading packets from input: {_input!s}")
            logger.info(how_to_kill)

            for line in _input:
                pkt = parse_packet(line)
                if pkt is not None:
                    yield pkt

    else:  # Read from ZMQ GNU Radio interface

        def reader() -> Iterator[str]:
            context = zmq.Context()
            socket = context.socket(zmq.SUB)

            socket.setsockopt(zmq.SUBSCRIBE, b"")
            socket.setsockopt(zmq.CONFLATE, 1)  # last msg only.

            socket.connect(tcp_address)

            logger.debug(f"Reading packets from TCP address: {tcp_address}")
            logger.info(how_to_kill)

            while True:
                msg = socket.recv(2 * melvec_length * n_melvecs)
                yield msg

    if gui:
        gui_process = custom_gui2_interface.launch_gui_process()
        logger.info("GUI process launched.")

    input_stream = reader()
    for msg in input_stream:
        try:
            sender, payload = unwrapper.unwrap_packet(msg)
            logger.debug(f"From {sender}, received packet: {payload.hex()}")

            myClass, this_fv, prediction = mp.model_prediction(payload)
            if REMOTE:
                hostname = remote_hostname
                key = remote_key
            else:
                hostname = local_hostname
                key = local_key

            if gui:
                # Prepare the payload for the GUI interface.
                # Note: custom_gui2_interface.send_packet expects current_packet_data as a base64 string.
                gui_data = {
                    "current_class_names": ["chainsaw", "fire", "fireworks", "gun"],
                    "current_class_probas": prediction,
                    "current_feature_vector": this_fv,
                    # Convert raw packet bytes into a base64-encoded string.
                    "current_packet_data": base64.b64encode(payload).decode('utf-8'),
                    "current_choice": myClass,
                    "mel_spec_len": melvec_length,
                    "mel_spec_num": n_melvecs,
                }
                # Schedule the asynchronous send_packet task using the current event loop.
                asyncio.get_event_loop().create_task(
                    custom_gui2_interface.send_packet(gui_data)
                )
                logger.debug("Sent GUI update via custom_gui2_interface.")

            # Checking the threshold and submitting results.
            if myClass is not None:
                submit(myClass, url=hostname, key=key)
                output.write(f'my class is {myClass}\n')
            output.flush()

        except packet.InvalidPacket as e:
            logger.error(f"Invalid packet error: {e.args[0]}")

if __name__ == "__main__":
    main()
