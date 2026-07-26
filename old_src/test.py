#!/usr/bin/env python
# coding: utf-8
"""更新情報
2023/02/14
- 5回までやり直す
2024/12/03
- 書き込みができなかったら、csvに出力する
- 起動時、csvファイルがあればその内容を書き込み、csvを削除する
- データベースの情報を外に出す
"""

from SpeedTest_chatgpt import do_speedtest
import psycopg2
import datetime
import csv
import time
import os

# デバイスの情報
global device 
device = 'Mac'


# データベースの接続情報を読み込む関数
def load_database_info():
    db_info = {}
    try:
        with open('database_info.txt', 'r') as file:
            for line in file:
                key, value = line.strip().split('=')
                db_info[key] = value
    except Exception as e:
        print(f"データベース接続情報の読み込みに失敗しました: {e}")
    return db_info

# 接続情報を読み込んでデータベースに接続
db_info = load_database_info()
try:
    conn = psycopg2.connect(
        host=db_info.get("host"),
        database=db_info.get("database"),
        user=db_info.get("user"),
        password=db_info.get("password")
    )
except Exception as e:
    print(f"データベースへの接続に失敗しました: {e}")
    exit()

# tableが無ければ、create
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS network_speed_measurements (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT now(),
        download_speed_Mbps NUMERIC(10,3),
        upload_speed_Mbps NUMERIC(10,3),
        device varchar(8)
    )
""")
conn.commit()

# db書き込み
def insert_network_speed(conn, download_speed, upload_speed, device):
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO network_speed_measurements (timestamp, download_speed_Mbps, upload_speed_Mbps, device)
        VALUES (now(), {download_speed}, {upload_speed}, '{device}' )
    """)
    conn.commit()

# CSVファイルに書き込む関数
def write_to_csv(timestamp, download_speed, upload_speed, device):
    with open('network_speed_backup.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, download_speed, upload_speed, device])
    print(f"データベースに書き込めなかったため、CSVファイルに書き込みました: {timestamp}")

# CSVファイルからデータをデータベースに書き込む関数
def load_csv_to_db():
    if os.path.exists('network_speed_backup.csv'):
        with open('network_speed_backup.csv', mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                timestamp, download_speed, upload_speed, device = row
                try:
                    insert_network_speed(conn, float(download_speed), float(upload_speed), device)
                except Exception as e:
                    print(f"CSVデータの挿入時にエラーが発生しました: {e}")
        # データベースに書き込みが完了したらCSVファイルを削除
        os.remove('network_speed_backup.csv')
        print("CSVファイルを削除しました。")

# 測定する
def measurement():
    download_speed, upload_speed = 0, 0
    try_count = 0
    err = 0
    run_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    output_space = '\r\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t'

    print(output_space, end = '\r')
    print('connecting', end = '')

    while download_speed == 0 and upload_speed == 0 and try_count < 5:
        try:
            download_speed, upload_speed = do_speedtest()
        except Exception as e:
            err = e
        finally:
            try_count += 1
            print('.', end = '')
    
    if download_speed == 0 and upload_speed == 0:
        pass
    else:
        download_speed = round(download_speed/1_000_000, 3)  # Mbpsに修正
        upload_speed = round(upload_speed/1_000_000, 3)    # 同上
        try:
            insert_network_speed(conn, download_speed, upload_speed, device)
            write_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            # データベース書き込み失敗時、CSVに書き込む
            write_to_csv(run_time, download_speed, upload_speed, device)
            write_time = 'Failed to write to DB'
        
    # 結果の出力
    print(output_space, end = '\r')
    if try_count == 5:
        print(f'Failure at {run_time}.{err}', end = '\r')
    else:
        print(f'run at {run_time}. write at {write_time}.{output_space}', end = '\r')

# スケジュール設定
import schedule
schedule_every_hour = [':00', ':10', ':20', ':30', ':40', ':50']
for minute in schedule_every_hour:
    schedule.every().hour.at(minute).do(measurement).tag('main')

# メイン
from time import sleep
try:
    # 起動時にCSVファイルの内容をデータベースに書き込み
    time.sleep(10)  # 少し待機してから開始
    print('起動しました')
    load_csv_to_db()

    while True:
        schedule.run_pending()
        sleep(1)
except KeyboardInterrupt as k:
    print('\n中断しました')
    pass
except Exception as e:
    print(e)
finally:
    conn.close()
    print('dbを切断しました')