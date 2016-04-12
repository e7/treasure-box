#! /usr/bin/env python
# -*- coding:utf-8 -*-


''' config '''
MAX_CONNECTIONS = 1

''' 数据库配置 '''
DB_CONF = {
    "host":"127.0.0.1:3306",
    "dbname":"test",
    "user":"root",
    "password":"root",
}

''' 接口对应的操作 '''
ITFC_CONF = {
    "insert":{
        "void":"1",
        "sql_fmt":"INSERT INTO `user` (`uid`,`email`) VALUES (NULL, %s)",
        "params":("email",)
    },

    "delete":{
        "void":"1",
        "sql_fmt":"DELETE FROM `user` WHERE `uid`=%s",
        "params":("uid",)
    },

    "select":{
        "void":"0",
        "sql_fmt":"SELECT `email` FROM `user` WHERE `uid`=%s",
        "params":("uid",)
    },

    "update":{
        "void":"1",
        "sql_fmt":"UPDATE `user` SET `email`=%s WHERE `uid`=%s",
        "params":("email", "uid")
    }
}
