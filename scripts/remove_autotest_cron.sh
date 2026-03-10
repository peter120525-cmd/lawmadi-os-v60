#!/bin/bash
# 자동 테스트 cron 제거 (3일 후 자동 실행)
crontab -l 2>/dev/null | grep -v 'auto_test.py' | grep -v 'remove_autotest_cron' | crontab -
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto test cron removed (3-day expiry)" >> /data/data/com.termux/files/home/lawmadi-os-v60/logs/auto_test.log
