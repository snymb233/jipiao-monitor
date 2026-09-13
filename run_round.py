# -*- coding: utf-8 -*-
"""供 Windows 计划任务调用的单轮抓取入口。
带文件锁：若上一轮尚未跑完，本轮直接跳过，避免重叠请求触发途牛风控。
"""
import os
import sys
import msvcrt
import subprocess
import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

lock_file = open('.round.lock', 'w')
try:
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print('{} 上一轮仍在运行，本轮跳过'.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
    sys.exit(0)

lock_file.write(str(os.getpid()))
lock_file.flush()
try:
    print('{} 开始一轮全量抓取'.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
    result = subprocess.run(
        [sys.executable, 'main.py', '-c', 'config.yaml', '--once'])
    print('{} 本轮结束, exit={}'.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        result.returncode), flush=True)
finally:
    lock_file.seek(0)
    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    lock_file.close()
