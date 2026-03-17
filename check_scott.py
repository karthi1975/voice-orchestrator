from app.config.settings import get_settings
from sqlalchemy import create_engine, text

settings = get_settings('production')
engine = create_engine(settings.DATABASE_URL)
conn = engine.connect()

homes = conn.execute(text("SELECT home_id, name, ha_url, ha_webhook_id FROM homes WHERE home_id='scott_home'")).fetchall()
print('=== HOMES ===')
for h in homes:
    print(h)

mappings = conn.execute(text("SELECT scene_name, webhook_id, is_active FROM scene_webhook_mappings WHERE home_id='scott_home'")).fetchall()
print('=== SCENE MAPPINGS ===')
for m in mappings:
    print(m)

conn.close()
