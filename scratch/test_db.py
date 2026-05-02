import asyncio
import os
from utils.database import Database

async def test():
    try: os.remove('guardian.db')
    except: pass
    db = Database(db_path='guardian.db')
    await db.connect()
    
    # Insert user with NULL rpc_usage_count
    async with __import__('aiosqlite').connect('guardian.db') as conn:
        await conn.execute("INSERT INTO user_state (user_id) VALUES ('1644262765')")
        # Let's forcefully set rpc_usage_count to NULL because maybe the DEFAULT didn't fire? 
        # Actually INSERT INTO user_state (user_id) VALUES ('123') will use DEFAULT 0.
        await conn.commit()
        
    await db.increment_rpc_usage("1644262765")
    
    state = await db.get_user_state("1644262765")
    print("Value:", dict(state).get("rpc_usage_count"))

asyncio.run(test())
