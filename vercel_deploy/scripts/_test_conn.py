from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

urls = [
    "postgresql://postgres.tloenjfdzsjhrraaqlcy:WX3UcvF3BdLYpaSo@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require",
    "postgresql://postgres.tloenjfdzsjhrraaqlcy:WX3UcvF3BdLYpaSo@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require",
]
for url in urls:
    try:
        e = create_engine(url, poolclass=NullPool)
        with e.connect() as c:
            n = c.execute(text("select count(*) from products")).scalar()
            print("OK", url.split("@")[1].split("/")[0], "products=", n)
    except Exception as ex:
        print("FAIL", url.split("@")[1].split("/")[0], "->", ex)
