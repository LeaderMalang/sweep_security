import asyncio
import json
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message

async def simulate_honey_pot_gas_injection(attacker_privkey, bait_address, amount_sol=0.05):
    """Simulates an attacker sending gas to a bait wallet to trigger skimming."""
    client = AsyncClient("https://api.devnet.solana.com")
    attacker_kp = Keypair.from_base58_string(attacker_privkey)
    bait_pubkey = Pubkey.from_string(bait_address)
    
    print(f"🕵️ ATTACKER: Injecting {amount_sol} SOL into Bait Wallet {bait_address}...")
    
    recent_blockhash = await client.get_latest_blockhash()
    ix = transfer(TransferParams(
        from_pubkey=attacker_kp.pubkey(),
        to_pubkey=bait_pubkey,
        lamports=int(amount_sol * 1_000_000_000)
    ))
    
    msg = Message.new_with_blockhash([ix], attacker_kp.pubkey(), recent_blockhash.value.blockhash)
    tx = Transaction([attacker_kp], msg, recent_blockhash.value.blockhash)
    
    res = await client.send_raw_transaction(bytes(tx))
    print(f"✅ Injection Sent: {res}")
    await client.close()

async def simulate_drain_attack(attacker_address, victim_privkey, amount_sol=0.05):
    """Simulates an attacker attempting to drain a monitored wallet."""
    client = AsyncClient("https://api.devnet.solana.com")
    victim_kp = Keypair.from_base58_string(victim_privkey)
    attacker_pubkey = Pubkey.from_string(attacker_address)
    
    print(f"💀 ATTACKER: Attempting to drain {amount_sol} SOL from {victim_kp.pubkey()} to {attacker_address}...")
    
    recent_blockhash = await client.get_latest_blockhash()
    ix = transfer(TransferParams(
        from_pubkey=victim_kp.pubkey(),
        to_pubkey=attacker_pubkey,
        lamports=int(amount_sol * 1_000_000_000)
    ))
    
    msg = Message.new_with_blockhash([ix], victim_kp.pubkey(), recent_blockhash.value.blockhash)
    tx = Transaction([victim_kp], msg, recent_blockhash.value.blockhash)
    
    res = await client.send_raw_transaction(bytes(tx))
    print(f"🚀 Drain Transaction Broadcasted: {res}")
    print("👀 Watch your Telegram bot to see if it detects the Transfer and attempts a rescue!")
    await client.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage:")
        print("  Skim Test: python simulate_attack.py skim [Attacker_Priv] [Bait_Addr]")
        print("  Drain Test: python simulate_attack.py drain [Attacker_Addr] [Victim_Priv]")
        sys.exit(1)
        
    mode = sys.argv[1]
    arg1 = sys.argv[2]
    arg2 = sys.argv[3]
    
    if mode == "skim":
        asyncio.run(simulate_honey_pot_gas_injection(arg1, arg2))
    elif mode == "drain":
        asyncio.run(simulate_drain_attack(arg1, arg2))
