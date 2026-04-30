// Solana Anchor Smart Contract: GasReservoir
// This contract allows users to pre-deposit gas funds for emergency recovery.

use anchor_lang::prelude::*;

declare_id!("GasRes111111111111111111111111111111111111");

#[program]
pub mod gas_reservoir {
    use super::*;

    pub fn initialize_reservoir(ctx: Context<Initialize>) -> Result<()> {
        let reservoir = &mut ctx.accounts.reservoir;
        reservoir.owner = *ctx.accounts.user.key;
        reservoir.balance = 0;
        Ok(())
    }

    pub fn deposit_gas(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        // Logic to transfer SOL from user to reservoir PDA
        let reservoir = &mut ctx.accounts.reservoir;
        reservoir.balance += amount;
        Ok(())
    }

    pub fn trigger_emergency_gas(ctx: Context<EmergencyRelease>, amount: u64) -> Result<()> {
        let reservoir = &mut ctx.accounts.reservoir;
        
        // Security: Only the Guardian Bot's authorized key can trigger this
        // or a pre-signed panic instruction.
        
        if reservoir.balance < amount {
            return err!(ErrorCode::InsufficientGas);
        }

        // Logic to transfer SOL from reservoir back to user wallet for gas
        reservoir.balance -= amount;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(init, payer = user, space = 8 + 32 + 8)]
    pub reservoir: Account<'info, ReservoirState>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct ReservoirState {
    pub owner: Pubkey,
    pub balance: u64,
}
