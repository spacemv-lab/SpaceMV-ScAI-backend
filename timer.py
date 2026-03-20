import os
import logging
import httpx
import traceback
from clickhouse_driver import Client
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Log File Path
log_file = "satellite_ingest.log"

# Create log directory
os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

# Log Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(), 
        RotatingFileHandler(
            log_file,
            maxBytes=5*1024*1024,  
            backupCount=1,          
            encoding="utf-8"
        )
    ]
)


# Spatial Target Data Sources
API_URL = "https://api.keeptrack.space/v3/sats"

# Connecting to ClickHouse
client = Client(
    host=os.getenv("CLICKHOUSE_HOST"),
    port=int(os.getenv("CLICKHOUSE_PORT_NATIVE")),
    user=os.getenv("CLICKHOUSE_USER"),
    password=os.getenv("CLICKHOUSE_PASSWORD"),
    database=os.getenv("CLICKHOUSE_DATABASE")
)

def fetch_and_update():
    try:

        # Create database (if it doesn't exist)
        client.execute("CREATE DATABASE IF NOT EXISTS xingzuo")
        logging.info("数据库 xingzuo 已检查或创建")

        # Check if the table exists
        tables = client.execute("SHOW TABLES FROM xingzuo")
        table_names = [t[0] for t in tables]

        # -------------------------------------------------------------------Celestrak------------------------------------------------------------------------------------------
        # Retrieve data
        logging.info("开始从 Celestrak API 获取卫星数据.....................................")
        with httpx.Client(timeout=60) as http_client:
            response = http_client.get(API_URL)
            response.raise_for_status()
            data = response.json()  
        
        keys = [
            "Mass", "adcs", "altName", "bus", "configuration", "country", "diameter",
            "dryMass", "equipment", "launchDate", "launchMass", "launchPad",
            "launchSite", "launchVehicle", "length", "manufacturer", "mission",
            "motor", "name", "owner", "payload", "purpose", "rcs", "shape", "sources",
            "span", "stableDate", "status", "tle1", "tle2", "transmitterFrequencies",
            "type", "vmag"
        ]
        rows = []
        for item in data:
            if not isinstance(item, dict):
                continue

            tle2 = item.get("tle2", "")
            parts = tle2.split()
            ID = parts[1] if len(parts) > 1 else ""

            row = [ID, 0, ""]  # ID, User_create, constellation
            for k in keys:
                if k == 'type':
                    value = item.get(k, -1)  
                elif k == 'vmag':
                    value = str(item.get(k, -1)) 
                else:
                    value = item.get(k, "")
                row.append(value)
            rows.append(tuple(row))
        logging.info(f"获取到 {len(data)} 条卫星数据")

       
        if "satellites" not in table_names:
            # -------------------------------------------------Create User Table-------------------------------------------------
            logging.info("正在创建用户表")
            create_table_sql = """
                                CREATE TABLE xingzuo.account
                                (
                                    id String,
                                    name String,
                                    password String,
                                    email String,
                                    status UInt8,
                                    coverage_analysis_permission UInt8 DEFAULT 0,
                                    create_at DateTime,
                                    updated_at DateTime,
                                    password_salt String
                                )
                                ENGINE = ReplacingMergeTree
                                PRIMARY KEY id
                                ORDER BY id
                                SETTINGS index_granularity = 8192;
                                """
            client.execute(create_table_sql)
            logging.info("用户表创建完成")

            # --------------------------------------------------Create the constellations table--------------------------------------------------
            logging.info("正在创建 constellations 表")
            create_table_sql = """
                               CREATE TABLE xingzuo.constellations
                               (
                                   constellation      String,
                                   constellation_name String,
                                   constellation_type String,
                               ) ENGINE = ReplacingMergeTree
                                PRIMARY KEY constellation
                                ORDER BY constellation; \
                               """
            client.execute(create_table_sql)

           # Insert initial zodiac constellation data
            insert_sql = """
                         INSERT INTO xingzuo.constellations (constellation, constellation_name, constellation_type)
                         VALUES ('1', 'GPS', 1), \
                                ('2', 'Galileo', 1), \
                                ('3', 'Glonass', 1) \
                                ('4', 'Starlink', 2) \
                                ('5', 'BDS', 1) \
                                ('6', 'Gaofen', 3) \
                                ('7', 'Skysat', 3) \
                                ('8', 'Worldview', 3) \
                                ('9', 'Iridium', 2)
                         """
            client.execute(insert_sql)

            logging.info("constellations 表创建完成")

            # ----------------------------------------------------Create the satellites table---------------------------------------------------------
            logging.info("satellites 表不存在，正在创建...")
            create_table_sql = """
            CREATE TABLE xingzuo.satellites
            (
                ID String,
                User_create UInt8 DEFAULT 0,
                constellation String,
                Mass String,
                adcs String,
                altName String,
                bus String,
                configuration String,
                country String,
                diameter String,
                dryMass String,
                equipment String,
                launchDate String,
                launchMass String,
                launchPad String,
                launchSite String,
                launchVehicle String,
                length String,
                manufacturer String,
                mission String,
                motor String,
                name String,
                owner String,
                payload String,
                purpose String,
                rcs String,
                shape String,
                sources String,
                span String,
                stableDate String,
                status String,
                tle1 String,
                tle2 String,
                transmitterFrequencies String,
                type Int8,
                vmag String
            )
            ENGINE = ReplacingMergeTree
            PRIMARY KEY ID
            ORDER BY ID;
            """
            client.execute(create_table_sql)
            logging.info("satellites 表创建完成")

            # Insert Data
            columns = ["ID", "User_create", "constellation"] + keys
            insert_sql = f"INSERT INTO xingzuo.satellites ({', '.join(columns)}) VALUES"
            client.execute(insert_sql, rows, types_check=True)
            logging.info(f"成功插入 {len(rows)} 条卫星数据到 satellites 表")

            match_constellation_sql = ["""
                                      -- GPS
                                      ALTER TABLE satellites
                                      UPDATE constellation = 1
                                      WHERE lower (name) LIKE '%navstar%'
                                        AND payload IS NOT NULL
                                        AND status = '+';
                                      """,
                                      """
                                      -- Galileo
                                      ALTER TABLE satellites
                                      UPDATE constellation = 2
                                      WHERE lower (name) LIKE '%galileo%'
                                        AND payload IS NOT NULL
                                        AND status = '+';
                                      """,
                                      """
                                      -- Glonass
                                      ALTER TABLE satellites
                                      UPDATE constellation = 3
                                      WHERE lower (name) LIKE '%glonass%'
                                        AND payload IS NOT NULL
                                        AND status = '+';
                                      """,
                                      """
                                      -- Gaofen （必须有 gaofen，但不能有 jilin）
                                      ALTER TABLE satellites
                                      UPDATE constellation = 6
                                      WHERE lower (name) LIKE '%gaofen%'
                                        AND lower (name) NOT LIKE '%jilin%'
                                        AND lower (name) NOT LIKE '%tianfu%'
                                        AND payload IS NOT NULL
                                        AND status = '+'; \
                                      """,
                                      """
                                      -- Starlink
                                       ALTER TABLE satellites
                                       UPDATE constellation = 4
                                       WHERE lower (name) LIKE '%starlink%'
                                         AND payload IS NOT NULL
                                         AND status = '+';
                                      """,
                                      """
                                       -- Beidou
                                       ALTER TABLE satellites
                                       UPDATE constellation = 5
                                       WHERE lower (name) LIKE '%beidou%'
                                         AND payload IS NOT NULL
                                         AND status = '+';
                                       """,
                                       """
                                       -- Skysat
                                       ALTER TABLE satellites
                                       UPDATE constellation = 7
                                       WHERE lower (name) LIKE '%skysat%'
                                         AND payload IS NOT NULL
                                         AND status = '+';
                                       """,
                                       """
                                       -- Worldview
                                        ALTER TABLE satellites
                                        UPDATE constellation = 8
                                        WHERE 
                                            (lower(name) LIKE '%worldview%' 
                                             OR lower(name) LIKE '%geoeye%')
                                          AND payload IS NOT NULL
                                          AND status = '+';
                                       """,
                                       """
                                       -- Iridium
                                       ALTER TABLE satellites
                                       UPDATE constellation = 9
                                       WHERE lower (name) LIKE '%iridium%'
                                         AND payload IS NOT NULL
                                         AND status = '+';
                                       """
                                       ]
            for sql in match_constellation_sql:
                client.execute(sql)
            logging.info(f"成功关联星座数据到 satellites 表")

            # -------------------------------------------------Create the sensor_paras table--------------------------------------------------------
            logging.info("正在创建 sensor_paras 表")
            create_table_sql = """
                               CREATE TABLE xingzuo.sensor_paras
                               (
                                   ID           String,
                                   name         String,
                                   sensor_type  Int8 DEFAULT 1,
                                   sensor_value Array(String) DEFAULT ['10', '10', '0', '0', '0', '10', '1']
                               ) ENGINE = ReplacingMergeTree
                PRIMARY KEY ID
                ORDER BY ID; \
                               """
            client.execute(create_table_sql)
            logging.info("sensor_paras 表创建完成")

            rows = client.execute("SELECT ID, name FROM xingzuo.satellites")
            logging.info(f"从 satellites 表获取 {len(rows)} 条数据")

            if rows:
                insert_sql = "INSERT INTO xingzuo.sensor_paras (ID, name) VALUES"
                client.execute(insert_sql, rows)
                logging.info(f"成功插入 {len(rows)} 条数据到 sensor_paras 表")
            else:
                logging.info("satellites 表为空，无数据可插入 sensor_paras 表")

        else:
            logging.info("satellites 表已存在，跳过创建")
            # -----------------------------------------------Update the satellites table--------------------------------------------------------
            existing_ids = set(id[0] for id in client.execute("SELECT ID FROM xingzuo.satellites"))
            belong_users_ids = set(id[0] for id in client.execute("SELECT ID FROM xingzuo.satellites WHERE User_create = 1 "))
            logging.info(f"已有 {len(existing_ids)} 条卫星数据,其中来源于用户的数据有{len(belong_users_ids)}条")

            insert_rows = []
            update_rows = []

            for row in rows:
                ID = row[0]
                if ID in existing_ids:
                    if ID not in belong_users_ids:
                         # Update: Inserting a new version in ReplacingMergeTree will overwrite the old record.
                        update_rows.append(row)
                else:
                    insert_rows.append(row)

            columns = ["ID", "User_create", "constellation"] + keys
            insert_sql = f"INSERT INTO xingzuo.satellites ({', '.join(columns)}) VALUES"

            if insert_rows:
                # add
                client.execute(insert_sql, insert_rows)
                logging.info(f"新增 {len(insert_rows)} 条卫星数据")

            if update_rows:
                # update
                client.execute(insert_sql, update_rows)
                logging.info(f"更新 {len(update_rows)} 条卫星数据")

            merge_sql = f"OPTIMIZE TABLE xingzuo.satellites FINAL"
            client.execute(merge_sql)
            logging.info("卫星数据更新完成")

            match_constellation_sql = ["""
                                       -- GPS
                                       ALTER TABLE satellites
                                       UPDATE constellation = 1
                                       WHERE lower (name) LIKE '%navstar%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Galileo
                                       ALTER TABLE satellites
                                       UPDATE constellation = 2
                                       WHERE lower (name) LIKE '%galileo%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Glonass
                                       ALTER TABLE satellites
                                       UPDATE constellation = 3
                                       WHERE lower (name) LIKE '%glonass%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Gaofen （必须有 gaofen，但不能有 jilin/tianfu）
                                       ALTER TABLE satellites
                                       UPDATE constellation = 6
                                       WHERE lower (name) LIKE '%gaofen%'
                                         AND lower (name) NOT LIKE '%jilin%'
                                         AND lower (name) NOT LIKE '%tianfu%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+'; 
                                       """,
                                       """
                                       -- Starlink
                                       ALTER TABLE satellites
                                       UPDATE constellation = 4
                                       WHERE lower (name) LIKE '%starlink%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Beidou
                                       ALTER TABLE satellites
                                       UPDATE constellation = 5
                                       WHERE lower (name) LIKE '%beidou%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Skysat
                                       ALTER TABLE satellites
                                       UPDATE constellation = 7
                                       WHERE lower (name) LIKE '%skysat%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Worldview
                                       ALTER TABLE satellites
                                       UPDATE constellation = 8
                                       WHERE
                                           (lower (name) LIKE '%worldview%'
                                          OR lower (name) LIKE '%geoeye%')
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """,
                                       """
                                       -- Iridium
                                       ALTER TABLE satellites
                                       UPDATE constellation = 9
                                       WHERE lower (name) LIKE '%iridium%'
                                         AND payload IS NOT NULL
                                         AND User_create = 0
                                         AND status = '+';
                                       """
                                       ]
            for sql in match_constellation_sql:
                client.execute(sql)
            # -------------------------------------------------Update the sensor_paras table----------------------------------------------------
            if insert_rows:
                insert_sql = "INSERT INTO xingzuo.sensor_paras (ID, name) VALUES"
                insert_sensor_rows = []
                for row in insert_rows:
                    insert_sensor = [row[0], row[21]] # 0-ID，21-name
                    insert_sensor_rows.append(insert_sensor)

                client.execute(insert_sql, insert_sensor_rows)
                logging.info(f"新增 {len(insert_rows)} 条卫星传感器数据")
                logging.info("卫星传感器数据更新完成")
            else:
                logging.info("无卫星传感器数据需要更新")          

    except Exception as e:
        logging.error(f"程序出错: {e}")
        logging.error(traceback.format_exc())  

if __name__ == "__main__":
    fetch_and_update()
    scheduler = BlockingScheduler()
    # Run once daily at 3:00 AM
    scheduler.add_job(fetch_and_update, "cron", hour=3, minute=0)
    logging.info("Scheduled task has been initiated. Data will be updated daily at 3:00 AM.")
    scheduler.start()
