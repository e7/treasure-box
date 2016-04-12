#! /usr/bin/env python
# -*- coding:utf-8 -*-


'''
协议格式
[版本(4) | 内容起始偏移(4) | 内容长度(4) | 内容校验码(4) | 扩展区 | 内容]
'''


import os
import sys
import time
import struct
import errno
import socket
import json
import logging
# import my_store.crash_on_ipy
import torndb

from my_store.config import *
from functools import partial
from tornado.ioloop import IOLoop
from tornado.process import fork_processes
from tornado.netutil import bind_sockets


def string2addr(addr_name):
    return ()


def addr2string(addr_tuple):
    ip, port = addr_tuple
    return ip + ":" + str(port)


class MyStoreServer(object):
    def __init__(self, io_loop, sock_lsn, pool_size):
        self._io_loop = io_loop
        self._sock_lsn = sock_lsn
        self._cli_conn = {} # 连接集

        # mysql连接池
        if pool_size < 1:
            pool_size = 1
        if pool_size > 64:
            pool_size = 64
        self._db_ps_pool = [] # db进程池
        self._db_ps_inuse = {} # 被使用的db进程
        sock_pairs = []
        for i in xrange(pool_size):
            sock_pairs.append(socket.socketpair())
        for i in xrange(pool_size):
            pid = os.fork()

            parent, child = sock_pairs[i]
            if pid:
                # in parent
                child.close()
                self._io_loop.add_handler(
                    parent.fileno(), partial(self.handle_rsp, parent),
                    self._io_loop.READ | self._io_loop.ERROR
                )
                parent.setblocking(0)
                self._db_ps_pool.append({"_pid":pid, "_pipe":parent})
            else:
                # in child
                parent.close()
                self._db_process_proc(child)


    def _release_conn(self, conn):
        skt = conn["socket"]
        del self._cli_conn[addr2string(skt.getpeername())] # 从连接集中剔除
        self._io_loop.remove_handler(skt.fileno()) # 停止监视
        skt.close()


    ''' DB进程 '''
    def _db_process_proc(self, pipe):
        Running = True
        db_conn = torndb.Connection(
            host = DB_CONF["host"],
            database = DB_CONF["dbname"],
            user = DB_CONF["user"],
            password = DB_CONF["password"]
        )

        while Running:
            rsp = {}
            rsp_data = {}
            message = json.loads(pipe.recv(4096))
            rsp["_idx"] = message["_idx"]
            rsp["_peer"] = message["_peer"]
            rsp["_start_ofst"] = message["_start_ofst"]
            itfc_name = message["interface"]

            # 不支持的接口
            if itfc_name not in ITFC_CONF:
                rsp_data["result"] = "401"
                rsp_data["message"] = "unknown interface"
                rsp["_response"] = json.dumps(rsp_data)
                pipe.sendall(json.dumps(rsp))
                continue

            # 执行接口配置
            itfc_obj = ITFC_CONF[itfc_name]
            sql_fmt = itfc_obj["sql_fmt"]
            missing_arg = ""
            paddings = []

            for i in itfc_obj["params"]:
                try:
                    paddings.append(message[i])
                except Exception as e:
                    missing_arg = i
                    break
            if len(missing_arg) > 0:
                logging.error("missing argument:{}".format(missing_arg))
                rsp_data["result"] = "402"
                rsp_data["message"] = "missing arguments"
                rsp["_response"] = json.dumps(rsp_data)
                pipe.sendall(json.dumps(rsp))
                continue

            if int(itfc_obj["void"]):
                try:
                    db_conn.execute(sql_fmt, *paddings)
                    rsp_data["result"] = "200"
                    rsp_data["message"] = "success"
                except Exception as e:
                    logging.debug("db error:" + str(e))
                    rsp_data["result"] = "500"
                    rsp_data["message"] = "exec sql failed"
            else:
                try:
                    data = db_conn.query(sql_fmt, *paddings)
                    if len(data) > 0:
                        rsp_data["result"] = "200"
                        rsp_data["message"] = "success"
                        rsp_data["data"] = data
                    else:
                        rsp_data["result"] = "404"
                        rsp_data["message"] = "not found"
                except Exception as e:
                    logging.debug("db error:" + str(e))
                    rsp_data["result"] = "500"
                    rsp_data["message"] = "exec sql failed"

            rsp["_response"] = json.dumps(rsp_data)
            pipe.sendall(json.dumps(rsp))
            # end of while

        db_conn.close()
        sys.exit(0)


    ''' 响应回调 '''
    def handle_rsp(self, pipe, fd, events):
        # 回收db连接
        try:
            data = json.loads(pipe.recv(4096))
            db_ps = self._db_ps_inuse[data["_idx"]]
            del self._db_ps_inuse[data["_idx"]]
        except socket.error as e:
            assert(0)
        except ValueError as e:
            assert(0)

        self._db_ps_pool.append(db_ps)

        logging.debug("got response from backend process")

        # 数据处理
        conn = self._cli_conn[data["_peer"]]
        rslt_data = json.dumps(data["_response"])
        start_ofst = int(data["_start_ofst"])
        conn["socket"].sendall(
            struct.pack("!4I", 1000, start_ofst, len(rslt_data), 0) + rslt_data
        )


    ''' 请求回调 '''
    def handle_req(self, conn, fd, events):
        rsp = {}
        skt = conn["socket"]

        if len(self._db_ps_pool) == 0:
            # 过载保护
            try:
                skt.recv(4096)
            except socket.error as e:
                self._release_conn(conn)

            rsp["result"] = "501"
            rsp["message"] = "system busy"
            skt.sendall(json.dumps(rsp))
            return

        try:
            rbuf = skt.recv(4096)
        except socket.error as e:
            self._release_conn(conn)
            return

        if len(rbuf) == 0:
            # client closed
            self._release_conn(conn)
            return

        conn["rbuf"] += rbuf

        # 协议检查
        if len(conn["rbuf"]) < 16:
            # 内容不足以解析
            logging.debug("cant parse header, length not enough")
            return
        version, start_ofst, length, checksum = struct.unpack(
            "!4I", conn["rbuf"][0:16]
        )
        if (version != 1000 or length < 8 or length > 4096):
            rsp["result"] = "400"
            rsp["message"] = "bad request"
            skt.sendall(json.dumps(rsp))
            self._release_conn(conn)
            return
        context_data = conn["rbuf"][start_ofst : (start_ofst+length)]
        if len(context_data) != length:
            # 内容不足以解析
            logging.debug("cant parse body, length not enough")
            return

        conn["rbuf"] = conn["rbuf"][start_ofst+length :] # 清缓冲

        try:
            cli_obj = json.loads(context_data)
        except ValueError as e:
            rsp["result"] = "400"
            rsp["message"] = "bad request"
            skt.sendall(json.dumps(rsp))
            return

        if "interface" not in cli_obj:
            rsp["result"] = "400"
            rsp["message"] = "bad request"
            skt.sendall(json.dumps(rsp))
            return

        logging.debug("got request: {}".format(cli_obj["interface"]))

        # 心跳
        if "ping" == cli_obj["interface"]:
            rsp["result"] = "200"
            rsp["message"] = "pong"
            skt.sendall(json.dumps(rsp))
            return

        # 分配db进程
        db_ps = self._db_ps_pool.pop(0)
        self._db_ps_inuse[db_ps["_pid"]] = db_ps # 用pid做索引

        # 发送请求
        cli_obj["_start_ofst"] = start_ofst
        cli_obj["_idx"] = db_ps["_pid"]
        cli_obj["_peer"] = addr2string(skt.getpeername())
        try:
            db_ps["_pipe"].sendall(json.dumps(cli_obj))
        except socket.error as e:
            if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            else:
                # 队列满
                rsp["result"] = "501"
                rsp["message"] = "system busy"
                skt.sendall(json.dumps(rsp))
                self._release_conn(conn)


    ''' 连接回调 '''
    def handle_connection(self, fd, events):
        if len(self._cli_conn) == MAX_CONNECTIONS:
            # 过载保护
            try:
                conn_skt, addr = self._sock_lsn.accept()
            except socket.error as e:
                if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
            conn_skt.close()
            return

        try:
            conn_skt, addr = self._sock_lsn.accept()
        except socket.error as e:
            if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return

        conn_skt.setblocking(0)
        connection = {"socket":conn_skt, "rbuf":""}
        self._cli_conn[addr2string(addr)] = connection
        self._io_loop.add_handler(conn_skt.fileno(),
                                  partial(self.handle_req, connection),
                                  self._io_loop.READ | self._io_loop.ERROR)


if "__main__" == __name__:
    logging.basicConfig(
        level = logging.DEBUG,
        format = ("%(asctime)s %(filename)s"
            + "[line:%(lineno)d] %(levelname)s %(message)s"
        ),
        datefmt = "%Y.%m.%d %H:%M:%S",
        filename = "my_store.log",
        filemode = "a"
    )

    sock_lsn = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock_lsn.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_lsn.setblocking(0)
    sock_lsn.bind(("", 8889))
    sock_lsn.listen(1)

    while True:
        try:
            # 父进程要么exit，要么抛异常，不会返回
            task_id = fork_processes(num_processes = 1, max_restarts = 1)
        except RuntimeError as e:
            logging.error("fork failed: {}".format(e))
            time.sleep(60) # 重启间隔
        else:
            # 子进程
            break

    io_loop = IOLoop.current()
    server = MyStoreServer(io_loop, sock_lsn, 1)
    io_loop.add_handler(sock_lsn.fileno(),
                        server.handle_connection,
                        io_loop.READ | io_loop.ERROR)
    io_loop.start()
