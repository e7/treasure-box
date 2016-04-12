#! /usr/bin/env python
# -*- coding:utf-8 -*-


import socket
import errno
import struct
import time
import json


if "__main__" == __name__:
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    skt.connect(("127.0.0.1", 8889))

    '''
    context = json.dumps({"interface":"insert", "email":"jackzxty@126.com"})
    data = struct.pack("!4I", 1000, 16, len(context), 0)
    skt.sendall(data + context)
    rsp = skt.recv(4096)
    version, start, length, checksum = struct.unpack("!4I", rsp[0:16])
    print version, start, length, checksum
    print(json.loads(rsp[16:]))

    context = json.dumps({"interface":"update", "uid":"1", "email":"chg"})
    data = struct.pack("!4I", 1000, 16, len(context), 0)
    skt.sendall(data + context)
    rsp = skt.recv(4096)
    version, start, length, checksum = struct.unpack("!4I", rsp[0:16])
    print version, start, length, checksum
    print(json.loads(rsp[16:]))

    context = json.dumps({"interface":"delete", "uid":"16"})
    data = struct.pack("!4I", 1000, 16, len(context), 0)
    skt.sendall(data + context)
    rsp = skt.recv(4096)
    version, start, length, checksum = struct.unpack("!4I", rsp[0:16])
    print version, start, length, checksum
    print(json.loads(rsp[16:]))
    '''

    context = json.dumps({"interface":"select", "uid":"26"})
    data = struct.pack("!4I", 1000, 16, len(context), 0)
    skt.sendall(data + context)
    rsp = skt.recv(4096)
    version, start, length, checksum = struct.unpack("!4I", rsp[0:16])
    print version, start, length, checksum
    print(json.loads(rsp[16:]))
