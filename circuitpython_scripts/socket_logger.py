# SPDX-FileCopyrightText: Copyright (c) 2024 Justin Myers
#
# SPDX-License-Identifier: MIT

import sys
import time


def _log_method(obj_hash, method, result, *args, **kwargs):
    print(f"{time.monotonic():<0.3f} | ", end="")
    print(f"{obj_hash:14} - {method:12} | ", end="")
    print(f"result: {str(result):12} | ", end="")

    result_hash = kwargs.pop("result_hash", None)
    if result_hash:
        print(f"socket hash: {result_hash} | ", end="")

    if args:
        str_args = " ".join([str(arg) for arg in args])
        print(f"args: {str_args}", end="")

    print("")


class SocketLogger:
    def __init__(  # noqa: PLR0913 - Too many arguments
        self,
        socket,
        family,
        type,
        proto,
        *,
        enable_log_close=False,
        enable_log_connect=False,
        enable_log_recv_into=False,
        enable_log_send=False,
        enable_log_sendto=False,
        enable_log_settimeout=False,
    ):
        self._socket = socket
        self._family = family
        self._type = type
        self._proto = proto

        self._hash = hash(self._socket)

        # note: we can not easily copy all methods, because calling
        #  `dir(socket)` calls the actual properties and thus can have
        #  bad effects
        other_method_names = [
            "accept",
            "bind",
            "listen",
            "recv",
            "recvfrom_into",
            "sendall",
            "setblocking",
            "setsockopt",
        ]
        if sys.implementation.name != "circuitpython":
            other_method_names.extend(
                [
                    "detach",
                    "fileno",
                    "gettimeout",
                    "getsockopt",
                ]
            )
        for other_method_name in other_method_names:
            other_method = getattr(self._socket, other_method_name, None)
            if other_method:
                setattr(self, other_method_name, other_method)

        self.enable_log(enable_log_close, "close")
        self.enable_log(enable_log_connect, "connect")
        self.enable_log(enable_log_recv_into, "recv_into")
        self.enable_log(enable_log_send, "send")
        self.enable_log(enable_log_sendto, "sendto")
        self.enable_log(enable_log_settimeout, "settimeout")

    def __del__(self):
        _log_method(self._hash, "__del__", None)
        if hasattr(self._socket, "__del__"):
            return self._socket.__del__()

    def __enter__(self):
        _log_method(self._hash, "__enter__", self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _log_method(
            self._hash,
            "__exit__",
            None,
            "exc_type:",
            exc_type,
            "exc_val:",
            exc_val,
            "exc_tb:",
            exc_tb,
        )
        if hasattr(self._socket, "__exit__"):
            return self._socket.__exit__(exc_type, exc_val, exc_tb)

    @property
    def family(self):
        return getattr(self._socket, "family", self._family)

    @property
    def proto(self):
        return getattr(self._socket, "proto", self._proto)

    @property
    def type(self):
        return getattr(self._socket, "type", self._type)

    def _call_method(self, method_name, method, log_args, *args, **kwargs):
        bytes_arg = kwargs.pop("socket_logger_bytes_arg", -1)
        try:
            result = method(*args, **kwargs)
            if bytes_arg == -1:
                _log_method(self._hash, method_name, result, *log_args)
            else:
                result_bytes = bytes(args[bytes_arg][:result])
                _log_method(self._hash, method_name, [result, result_bytes], *log_args)
            return result
        except Exception as exc:
            _log_method(self._hash, method_name, exc, *log_args)
            raise

    def _log_close(self):
        return self._call_method("close", self._socket.close, [])

    def _log_connect(self, address, *args, **kwargs):
        # The *args and **kwargs are for the ESP32SPI and the
        #  _FakeSSLSocket.connect where the ESP32SPI needs a tls_mode
        log_args = ["address:", address[0], "port:", address[1]]
        return self._call_method(
            "connect", self._socket.connect, log_args, address, *args, **kwargs
        )

    def _log_recv_into(self, b, size=0):
        log_args = ["size", size]
        return self._call_method(
            "recv_into",
            self._socket.recv_into,
            log_args,
            b,
            size,
            socket_logger_bytes_arg=0,
        )

    def _log_send(self, b):
        # `b` could be a memoryview, force to bytes
        log_args = ["bytes:", bytes(b)]
        return self._call_method("send", self._socket.send, log_args, b)

    def _log_sendto(self, b, address):
        # `b` could be a memoryview, force to bytes
        log_args = ["bytes:", bytes(b), "address:", address[0], "port:", address[1]]
        return self._call_method("sendto", self._socket.sendto, log_args, b, address)

    def _log_settimeout(self, value):
        log_args = ["value:", value]
        return self._call_method("settimeout", self._socket.settimeout, log_args, value)

    def enable_log(self, enable, method_name):
        native_method = getattr(self._socket, method_name)
        if native_method is None:
            return

        log_method = getattr(self, f"_log_{method_name}", native_method)
        method = log_method if enable else native_method
        setattr(self, method_name, method)


class SocketPoolLogger:
    def __init__(self, socket_pool):
        self._socket_pool = socket_pool

        self._hash = hash(self._socket_pool)

        self._enable_log_close = False
        self._enable_log_connect = False
        self._enable_log_recv_into = False
        self._enable_log_send = False
        self._enable_log_sendto = False
        self._enable_log_settimeout = False

    @property
    def SOCK_DGRAM(self):
        return self._socket_pool.SOCK_DGRAM

    @property
    def SOCK_STREAM(self):
        return self._socket_pool.SOCK_STREAM

    @property
    def AF_INET(self):
        return self._socket_pool.AF_INET

    def getaddrinfo(self, host=None, port=None, family=0, type=0, proto=0, flags=0):  # noqa: PLR0913 - Too many arguments
        log_args = [
            "host:",
            host,
            "port:",
            port,
            "family:",
            family,
            "type:",
            type,
            "proto:",
            proto,
            "flags:",
            flags,
        ]
        try:
            result = self._socket_pool.getaddrinfo(
                host, port, family, type, proto, flags
            )
            _log_method(self._hash, "getaddrinfo", result, *log_args)
            return result
        except Exception as exc:
            _log_method(self._hash, "getaddrinfo", exc, *log_args)
            raise

    def socket(self, family=0, type=0, proto=0, fileno=None):
        log_args = [
            "family:",
            family,
            "type:",
            type,
            "proto:",
            proto,
            "fileno:",
            fileno,
        ]
        try:
            result = self._socket_pool.socket(family=family, type=type, proto=proto)
            _log_method(
                self._hash, "socket", result, *log_args, result_hash=hash(result)
            )
            return SocketLogger(
                result,
                family,
                type,
                proto,
                enable_log_close=self._enable_log_close,
                enable_log_connect=self._enable_log_connect,
                enable_log_recv_into=self._enable_log_recv_into,
                enable_log_send=self._enable_log_send,
                enable_log_sendto=self._enable_log_sendto,
                enable_log_settimeout=self._enable_log_settimeout,
            )
        except Exception as exc:
            _log_method(self._hash, "socket", exc, *log_args)
            raise

    def enable_log_all(self, enable):
        self._enable_log_close = enable
        self._enable_log_connect = enable
        self._enable_log_recv_into = enable
        self._enable_log_send = enable
        self._enable_log_sendto = enable
        self._enable_log_settimeout = enable

    def enable_log_close(self, enable):
        self._enable_log_close = enable

    def enable_log_connect(self, enable):
        self._enable_log_connect = enable

    def enable_log_recv_into(self, enable):
        self._enable_log_recv_into = enable

    def enable_log_send(self, enable):
        self._enable_log_send = enable

    def enable_log_sendto(self, enable):
        self._enable_log_sendto = enable

    def enable_log_settimeout(self, enable):
        self._enable_log_settimeout = enable
