# SPDX-FileCopyrightText: Copyright (c) 2024 Justin Myers
#
# SPDX-License-Identifier: MIT


import os
import sys

import adafruit_connection_manager

try:
    import board
    import busio
    import digitalio
except (ImportError, NotImplementedError):
    pass

is_microcontroller = sys.implementation.name == "circuitpython"


_global_found_radios = {}
_global_print = True
_global_spi = None


def enable_log(enable):
    global _global_print  # noqa: PLW0603 Using the global statement to update variable is discouraged
    _global_print = enable


def log(value):
    if _global_print:
        print(value)


def get_global_spi():
    global _global_spi  # noqa: PLW0603 Using the global statement to update variable is discouraged
    if _global_spi is None:
        if getattr(board, "SCK1", None):
            _global_spi = busio.SPI(board.SCK1, board.MOSI1, board.MISO1)
        else:
            _global_spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    return _global_spi


def get_pin(env_name, default):
    pin_name = os.getenv(env_name, default)
    pin = getattr(board, pin_name, None)
    if pin is None:
        raise ValueError(f"Pin {pin_name} for {env_name} not found")
    return pin


def get_saved_radio(name):
    if name in _global_found_radios:
        return _global_found_radios[name]["radio"]
    return None


def save_radio(name, radio, pins=None):
    _global_found_radios[name] = {
        "radio": radio,
        "pins": pins,
    }


def connect_radio(radio):
    if not hasattr(radio, "connect"):
        log("Radio does not need to connect")
        return

    if radio.connected:
        log("Already connected")
        return

    ssid = os.getenv("WIFI_SSID")
    if ssid:
        password = os.getenv("WIFI_PASSWORD")
    else:
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

    if ssid is None:
        raise AttributeError("Can't find SSID information in settings.toml")

    log(f"Connecting to SSID: {ssid}")
    try:
        radio.connect(ssid, password)
    except TypeError:
        radio.connect_AP(ssid, password)
    log("Connected")


def deinit_radio(radio):
    match = None
    for key, data in _global_found_radios.items():
        if data["radio"] == radio:
            match = key
            break

    if match is None:
        raise ValueError("Radio not found")

    pins = _global_found_radios[key]["pins"]
    if isinstance(pins, list):
        for pin in pins:
            pin.deinit()

    del _global_found_radios[key]
    del radio


def get_cpython_radio(raise_exception=True):
    radio = get_saved_radio("cpython")
    if radio:
        return radio

    if is_microcontroller and raise_exception:
        raise RuntimeError("CPython library not found")

    radio = adafruit_connection_manager.CPythonNetwork()

    save_radio("cpython", radio)
    log("Running CPython")
    return radio


def get_esp32spi_radio(raise_exception=True):
    radio = get_saved_radio("esp32spi")
    if radio:
        return radio

    try:
        from adafruit_esp32spi import adafruit_esp32spi

    except ImportError as exc:
        if raise_exception:
            raise RuntimeError("ESP32SPI library not found") from exc
        return None

    if getattr(board, "ESP_CS", None) is not None:
        esp32_chip_select_pin = board.ESP_CS
        esp32_ready_pin = board.ESP_BUSY
        esp32_reset_pin = board.ESP_RESET
    else:
        esp32_chip_select_pin = get_pin("ESP32SPI_CHIP_SELECT", "D13")
        esp32_ready_pin = get_pin("ESP32SPI_READY", "D11")
        esp32_reset_pin = get_pin("ESP32SPI_RESET", "D12")

    esp32_chip_select = digitalio.DigitalInOut(esp32_chip_select_pin)
    esp32_ready = digitalio.DigitalInOut(esp32_ready_pin)
    esp32_reset = digitalio.DigitalInOut(esp32_reset_pin)
    spi = get_global_spi()
    radio = adafruit_esp32spi.ESP_SPIcontrol(
        spi, esp32_chip_select, esp32_ready, esp32_reset
    )

    try:
        radio.firmware_version
    except TimeoutError as exc:
        esp32_chip_select.deinit()
        esp32_ready.deinit()
        esp32_reset.deinit()

        if raise_exception:
            raise RuntimeError("ESP32SPI radio not found") from exc
        return None

    save_radio("esp32spi", radio, [esp32_chip_select, esp32_ready, esp32_reset])
    log("Found ESP32SPI")
    return radio


def get_wifi_radio(raise_exception=True):
    radio = get_saved_radio("wifi")
    if radio:
        return radio

    try:
        import wifi
    except ImportError as exc:
        if raise_exception:
            raise RuntimeError("WiFi library not found") from exc
        return None

    radio = wifi.radio

    save_radio("wifi", radio)
    log("Found native Wifi")
    return radio


def get_wiznet5k_radio(raise_exception=True):
    radio = get_saved_radio("wiznet5k")
    if radio:
        return radio

    try:
        from adafruit_wiznet5k import adafruit_wiznet5k

    except ImportError as exc:
        if raise_exception:
            raise RuntimeError("WIZnet5k library not found") from exc
        return None

    wiznet_chip_select_pin = get_pin("WIZNET_CHIP_SELECT", "D10")
    wiznet_chip_select = digitalio.DigitalInOut(wiznet_chip_select_pin)
    spi = get_global_spi()
    try:
        radio = adafruit_wiznet5k.WIZNET5K(spi, wiznet_chip_select, is_dhcp=True)
    except RuntimeError as exc:
        chip_select.deinit()

        if raise_exception:
            raise RuntimeError("WIZnet5k radio not found") from exc
        return None

    save_radio("wiznet5k", radio, [wiznet_chip_select])
    log("Found WIZnet5k")
    return radio


def get_radio(connect=True, force=None):
    radio = None
    log("Detecting radio...")

    if not is_microcontroller:
        radio = get_cpython_radio(raise_exception=False)

    if radio is None and force is None or force == "wifi":
        radio = get_wifi_radio(raise_exception=force)

    if radio is None and force is None or force == "esp32spi":
        radio = get_esp32spi_radio(raise_exception=force)

    if radio is None and force is None or force == "wiznet5k":
        radio = get_wiznet5k_radio(raise_exception=force)

    if radio is None:
        raise RuntimeError("Cannot determine radio")

    if connect:
        connect_radio(radio)

    return radio
