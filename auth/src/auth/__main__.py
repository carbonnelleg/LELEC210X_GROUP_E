import os
from collections.abc import Iterator
from typing import Optional

import click
import serial
import zmq
import numpy as np
import requests
import json

import auth.model_prediction as mp
import common
from common.env import load_dotenv
from common.logging import logger
from leaderboard.submit import submit

import auth.custom_gui as cg

from . import PRINT_PREFIX, packet

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
    help="Where to read the input stream. Default to '-', a.k.a. stdout.",
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
        allowed_senders=[
            0,
        ],
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
                packet = parse_packet(line)
                if packet is not None:
                    yield packet

    elif _input:  # Read from file-like

        def reader() -> Iterator[str]:
            logger.debug(f"Reading packets from input: {_input!s}")
            logger.info(how_to_kill)

            for line in _input:
                packet = parse_packet(line)
                if packet is not None:
                    yield packet

    else:  # Read from zmq GNU Radio interface

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
        gui_object, app = cg.generate_gui_thread()
    else:
        gui_object = None
        app = None

    input_stream = reader()
    for msg in input_stream:
        try:
            sender, payload = unwrapper.unwrap_packet(msg)
            logger.debug(f"From {sender}, received packet: {payload.hex()}")
            # myType = type(payload)
            # output.write(f'my type is {myType}\n')
            # myClass = int.from_bytes(payload, 'big')%5
            myClass, this_fv, prediction = mp.model_prediction(payload)
            if REMOTE:
                hostname = remote_hostname
                key = remote_key
            else:
                hostname = local_hostname
                key = local_key

            if gui and app is not None and gui_object is not None:
                gui_object.update_gui_params(  # Update the GUI
                    current_choice=myClass,
                    current_packet_data=payload,
                    current_feature_vector=this_fv,
                    current_class_names=mp.classnames,
                    current_class_probas=prediction,
                )
            
            #Checking the threshold
            if myClass is None:
                pass
            else:
                submit(myClass, url=hostname, key=key)
                output.write(f'my class is {myClass}\n')
            # output.write(PRINT_PREFIX + payload.hex() + "\n")
            output.flush()
            
            if gui and app is not None and gui_object is not None:
                app.processEvents() # Update the GUI

        except packet.InvalidPacket as e:
            logger.error(
                f"Invalid packet error: {e.args[0]}",
            )
