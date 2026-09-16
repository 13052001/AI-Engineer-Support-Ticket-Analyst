import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import init_db
from app.query_engine import execute

def setup_module():
    if os.path.exists("support_tickets.db"):
        os.remove("support_tickets.db")
    init_db("support_tickets.csv")

def test_open_count():
    p={"intent":"count","filters":{"status":"Open"},"metric":"count","group_by":None,"limit":20}
    assert execute(p)["data"][0]["value"] == 111

def test_critical_unresolved():
    p={"intent":"count","filters":{"priority":"Critical","status":"unresolved"},"metric":"count","group_by":None,"limit":20}
    assert execute(p)["data"][0]["value"] == 31

def test_technical_rating():
    p={"intent":"aggregate","filters":{"category":"Technical"},"metric":"avg_customer_rating","group_by":None,"limit":20}
    assert execute(p)["data"][0]["value"] == 3.74
