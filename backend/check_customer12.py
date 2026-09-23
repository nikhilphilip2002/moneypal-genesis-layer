import os

import pg8000


def main() -> None:
    env = {}
    with open(".env", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()

    conn = pg8000.connect(
        host="187.127.189.199",
        port=5432,
        database=env.get("POSTGRES_DB", "moneypal_genesis"),
        user=env.get("NLQ_DB_USER", "postgres"),
        password=env.get("NLQ_DB_PASSWORD"),
    )
    cur = conn.cursor()
    cur.execute("SELECT customer_id FROM gold.customers ORDER BY customer_id")
    ids = [r[0] for r in cur.fetchall()]
    print("gold.customers count:", len(ids))
    print("customer_id=12? ->", 12 in ids)
    print("min:", min(ids) if ids else "-", "max:", max(ids) if ids else "-")
    sample = [i for i in ids if "12" in str(i)]
    print("ids containing '12':", sample[:10])


if __name__ == "__main__":
    main()
