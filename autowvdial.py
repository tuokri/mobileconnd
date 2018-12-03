#!/usr/bin/env python3

"""Automatic dialing script for wvdial."""

import argparse
import logging
import os
import serial
import signal
import sys
import subprocess as sp
import time

BAUDRATE = 57600
TIMEOUT_DEFAULT = 60
TIMEOUT = TIMEOUT_DEFAULT
WVDIAL_HANDLE = None


class SystemdHandler(logging.Handler):
    # http://0pointer.de/public/systemd-man/sd-daemon.html
    PREFIX = {
        # EMERG <0>
        # ALERT <1>
        logging.CRITICAL: "<2>",
        logging.ERROR: "<3>",
        logging.WARNING: "<4>",
        # NOTICE <5>
        logging.INFO: "<6>",
        logging.DEBUG: "<7>",
        logging.NOTSET: "<7>"
    }

    def __init__(self, stream=sys.stdout):
        self.stream = stream
        logging.Handler.__init__(self)
        self.formatter = logging.Formatter("%(name)s:%(levelname)s:%(message)s")

    def emit(self, record):
        try:
            msg = self.PREFIX[record.levelno] + self.format(record) + "\n"
            self.stream.write(msg)
            self.stream.flush()
        except Exception:
            self.handleError(record)


logger = logging.getLogger("autowvdial")
logger.setLevel(logging.DEBUG)
logger.addHandler(SystemdHandler())


def wait_for_modem(modem_devfile):
    """Wait until modem device file is found or timed out.
    After device file is found, wait until serial port is usable.
    :param modem_devfile: Device file path of the modem.
    """
    logger.info("waiting for modem: %s", modem_devfile)
    start = time.time()
    while not timed_out(start):
        if os.path.exists(modem_devfile):
            logger.info("modem '%s' found", modem_devfile)
        time.sleep(0.05)

    logger.info("waiting for modem '%s' serial port to be ready", modem_devfile)
    start = time.time()
    while not timed_out(start):
        try:
            with serial.Serial(modem_devfile, timeout=TIMEOUT, write_timeout=TIMEOUT) as ser:
                logger.info("modem '%s' serial port ready", modem_devfile)
                return
        except serial.SerialException:
            pass
        time.sleep(0.05)


def enter_sim_pin(modem_devfile, pin):
    """Attempt entering SIM PIN until success, error or timed out.
    :param modem_devfile: Device file path of the modem.
    :param pin: SIM PIN.
    """
    logger.info("entering SIM PIN")
    try:
        with serial.Serial(modem_devfile, BAUDRATE, timeout=TIMEOUT, write_timeout=TIMEOUT) as ser:
            logger.info("opening serial port: %s", modem_devfile)
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write("AT+CPIN={}\r\n".format(pin).encode())
            buf = ""
            last_recv = ""
            start = time.time()
            while not timed_out(start):
                buf += buf + ser.read(ser.in_waiting).decode()
                if "\r\n" in buf:
                    lines = buf.split("\r\n")
                    if lines[-2]:
                        last_recv = lines[-2]
                    buf = lines[-1]
                    if last_recv == "OK":
                        logger.info("SIM PIN entered succesfully")
                        return
                    else:
                        logger.error("received '%s' while entering SIM PIN", last_recv)
                        logger.error("message buffer: %s", buf)
                        return
            logger.error("timed out entering SIM PIN")
    except serial.SerialException as se:
        logger.error("error entering SIM PIN: %s", se)
    except Exception as e:
        logger.error("error entering SIM PIN: %s", e)


def dial(dialer):
    """Start wvdial.
    :param dialer: Name of the wvdial config file dialer entry.
    """
    global WVDIAL_HANDLE
    logger.info("dialing: %s", dialer)
    WVDIAL_HANDLE = sp.Popen(
        ["wvdial", dialer], stdout=sp.PIPE, stderr=sp.PIPE)
    _, err = WVDIAL_HANDLE.communicate()
    if WVDIAL_HANDLE.returncode != os.EX_OK:
        logger.error("wvdial stderr buffer: %s", err)
        sys.exit(1)


def timed_out(start, timeout=TIMEOUT):
    """
    :param start: Start time in seconds.
    :param timeout: Timeout duration in seconds.
    :return: True if timed out, else False.
    """
    if timeout == 0:
        return False
    if start + timeout >= time.time():
        return False

    logger.warning("timed out with timeout=%d", timeout)
    return True


def exit_gracefully(signo, _):
    logger.info("exiting gracefully, signo=%d", signo)
    try:
        WVDIAL_HANDLE.send_signal(signal.SIGTERM)
        logger.info("sent SIGTERM to wvdial")
    except Exception as e:
        logger.error("exit error: %s", e)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, exit_gracefully)
    signal.signal(signal.SIGTERM, exit_gracefully)

    parser = argparse.ArgumentParser("Autodialer script for wvdial.")
    parser.add_argument("modem")
    parser.add_argument("pin")
    parser.add_argument(
        "-d",
        "--dialer",
        default="Dialer Defaults",
        help="dialer entry in wvdial config file, default = %(default)s")
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=TIMEOUT_DEFAULT,
        help="timeout for waiting modem and entering SIM PIN, default = %(default)s")
    args = parser.parse_args()

    global TIMEOUT
    TIMEOUT = args.timeout

    logger.info("starting autowvdial, timeout=%s", TIMEOUT)
    wait_for_modem(args.modem)
    enter_sim_pin(args.modem, args.pin)
    dial(args.dialer)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        exit_gracefully()
