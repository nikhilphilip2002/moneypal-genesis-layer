import os
import sys
import time
import glob
import ctypes
import ctypes.util

# Ensure libz is loaded on NixOS if missing from standard loader path
if not ctypes.util.find_library("z"):
    zlib_paths = glob.glob("/nix/store/*-zlib-*/lib/libz.so.1")
    for zpath in zlib_paths:
        try:
            ctypes.CDLL(zpath)
            break
        except Exception:
            pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 library is not installed in the environment.")
    sys.exit(1)


def test_connection():
    host = os.environ.get("POSTGRES_HOST", "192.168.1.183")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    dbname = os.environ.get("POSTGRES_DB", "moneypaldb")
    user = os.environ.get("POSTGRES_USER", "moneypal")
    password = os.environ.get("POSTGRES_PASSWORD", "moneypal123")

    print(f"Testing PostgreSQL database connection:")
    print(f"  Host:     {host}")
    print(f"  Port:     {port}")
    print(f"  Database: {dbname}")
    print(f"  User:     {user}")

    start_time = time.time()
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        latency = (time.time() - start_time) * 1000
        print(f"\nStatus: CONNECTED SUCCESSFULLY (Latency: {latency:.2f} ms)")
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"Server Version: {version}")

        cur.execute("""
            SELECT table_schema, COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            GROUP BY table_schema;
        """)
        schemas = cur.fetchall()
        print("\nSchemas:")
        for schema, count in schemas:
            print(f"  - {schema}: {count} tables")

        cur.close()
        conn.close()
        return True
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        print(f"\nStatus: CONNECTION FAILED (Latency: {latency:.2f} ms)")
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
