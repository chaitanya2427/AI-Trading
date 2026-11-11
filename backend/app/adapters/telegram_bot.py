"""
Telegram Bot Adapter for Remote Monitoring & Proposal Approval
Allows operator to receive trade alerts and safely approve/reject proposals
with strict chat ID whitelist authentication and secret redaction.
"""

from typing import Any, Dict, List, Optional, Set
import httpx

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.db.session import AsyncSessionLocal
from execution.portfolio import portfolio_tracker
from execution.proposal_service import proposal_service
from risk.engine import risk_engine

logger = get_logger("adapters.telegram_bot")


class TelegramBotAdapter:
    """
    Telegram Bot client for notifications and authenticated command handling.
    Safe-by-default: If disabled or unconfigured, functions as a local mock logger.
    """

    def __init__(self) -> None:
        self.enabled: bool = settings.TELEGRAM_BOT_ENABLED
        self.token: Optional[str] = settings.TELEGRAM_BOT_TOKEN
        self.allowed_chat_ids: Set[str] = set()

        if settings.TELEGRAM_ALLOWED_CHAT_IDS:
            self.allowed_chat_ids = {
                cid.strip() for cid in settings.TELEGRAM_ALLOWED_CHAT_IDS.split(",") if cid.strip()
            }

        self.api_url: str = f"https://api.telegram.org/bot{self.token}" if self.token else ""
        logger.info(
            "TelegramBotAdapter initialized (Enabled=%s, AllowedChats=%d)",
            self.enabled,
            len(self.allowed_chat_ids),
        )

    def is_authorized(self, chat_id: Any) -> bool:
        """Enforces chat whitelist authorization."""
        if not self.allowed_chat_ids:
            return False
        return str(chat_id).strip() in self.allowed_chat_ids

    async def send_message(self, chat_id: str, text: str) -> bool:
        """Sends a text message via Telegram API if enabled."""
        if not self.enabled or not self.token:
            logger.info("[TELEGRAM MOCK] Message to %s: %s", chat_id, text)
            return True

        if not self.is_authorized(chat_id):
            logger.warning("Unauthorized attempt to send message to chat_id: %s", chat_id)
            return False

        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return True
                logger.error("Failed to send Telegram message: %s - %s", res.status_code, res.text)
                return False
        except Exception as e:
            logger.error("Error communicating with Telegram API: %s", e)
            return False

    async def broadcast_trade_proposal(self, proposal_dict: Dict[str, Any]) -> None:
        """Broadcasts a newly generated trade proposal to all whitelisted operator chats."""
        prop_id = proposal_dict.get("proposal_id", "UNKNOWN")
        symbol = proposal_dict.get("symbol", "")
        direction = proposal_dict.get("direction", "")
        entry = proposal_dict.get("entry_price", 0.0)
        sl = proposal_dict.get("stop_loss", 0.0)
        target = proposal_dict.get("target", 0.0)
        qty = proposal_dict.get("quantity", 0)
        risk = proposal_dict.get("estimated_risk_inr", 0.0)
        reward = proposal_dict.get("estimated_reward_inr", 0.0)
        strategy = proposal_dict.get("strategy_name", "")

        msg = (
            f"🔔 *TRADE PROPOSAL AWAITING APPROVAL*\n\n"
            f"• *Strategy:* `{strategy}`\n"
            f"• *Instrument:* `{symbol}` ({direction})\n"
            f"• *Qty:* `{qty}`\n"
            f"• *Entry Reference:* `₹{entry:.2f}`\n"
            f"• *Stop Loss:* `₹{sl:.2f}`\n"
            f"• *Target:* `₹{target:.2f}`\n"
            f"• *Risk / Reward:* `₹{risk:.2f} / ₹{reward:.2f}`\n\n"
            f"To Approve:\n`/approve {prop_id}`\n\n"
            f"To Reject:\n`/reject {prop_id} [Reason]`"
        )

        for chat_id in self.allowed_chat_ids:
            await self.send_message(chat_id, msg)

    async def handle_command(self, chat_id: str, command_text: str) -> str:
        """
        Parses and executes an operator command from Telegram.
        Supports /status, /approve <id>, /reject <id>, /squareoff, /kill <reason>.
        """
        if not self.is_authorized(chat_id):
            return "⛔ *Access Denied:* Unauthorized Telegram ID."

        parts = command_text.strip().split()
        if not parts:
            return "Invalid command."

        cmd = parts[0].lower()

        if cmd == "/status":
            summary = portfolio_tracker.get_portfolio_summary()
            status_text = (
                f"📊 *SYSTEM STATUS*\n\n"
                f"• *Risk State:* `{risk_engine.state.status.value if risk_engine.state else 'UNKNOWN'}`\n"
                f"• *Kill Switch:* `{'ACTIVE' if risk_engine.kill_switch_active else 'INACTIVE'}`\n"
                f"• *Starting Capital:* `₹{summary['starting_capital_inr']:.2f}`\n"
                f"• *Realized P&L:* `₹{summary['realized_pnl_inr']:.2f}`\n"
                f"• *Unrealized P&L:* `₹{summary['unrealized_pnl_inr']:.2f}`\n"
                f"• *Statutory Costs:* `₹{summary['total_charges_inr']:.2f}`\n"
                f"• *Net P&L:* `₹{summary['net_pnl_inr']:.2f}`\n"
                f"• *Daily Loss Headroom (₹250 Limit):* `₹{summary['loss_limit_headroom_inr']:.2f}`\n"
                f"• *Open Positions:* `{summary['open_positions_count']}`\n"
                f"• *Mode:* `{summary['execution_mode']} ({summary['provenance']})`"
            )
            return status_text

        elif cmd == "/approve":
            if len(parts) < 2:
                return "⚠️ *Usage:* `/approve <proposal_id>`"
            prop_id = parts[1]
            async with AsyncSessionLocal() as db:
                try:
                    res = await proposal_service.approve_and_execute(
                        proposal_id=prop_id,
                        operator=f"TELEGRAM_{chat_id}",
                        db=db,
                    )
                    if res.get("status") == "EXECUTED":
                        return f"✅ *PROPOSAL EXECUTED*\nOrder ID: `{res['order_id']}`\nFill Price: `₹{res['filled_price']}`"
                    else:
                        return f"❌ *EXECUTION BLOCKED*\nStatus: `{res.get('status')}`\nReason: `{res.get('risk_reason') or res.get('reason')}`"
                except Exception as e:
                    return f"❌ *Error approving proposal:* `{str(e)}`"

        elif cmd == "/reject":
            if len(parts) < 2:
                return "⚠️ *Usage:* `/reject <proposal_id> [Reason]`"
            prop_id = parts[1]
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Rejected by operator via Telegram"
            async with AsyncSessionLocal() as db:
                try:
                    res = await proposal_service.reject_proposal(
                        proposal_id=prop_id,
                        operator=f"TELEGRAM_{chat_id}",
                        reason=reason,
                        db=db,
                    )
                    return f"🛑 *PROPOSAL REJECTED*\nID: `{prop_id}`\nReason: `{reason}`"
                except Exception as e:
                    return f"❌ *Error rejecting proposal:* `{str(e)}`"

        elif cmd == "/kill":
            reason = " ".join(parts[1:]) if len(parts) > 1 else "Emergency Kill Switch triggered via Telegram"
            async with AsyncSessionLocal() as db:
                await risk_engine.trigger_kill_switch(reason, db)
                await portfolio_tracker.square_off_all(reason=f"KILL_SWITCH: {reason}", db=db)
                return f"🚨 *EMERGENCY KILL SWITCH ACTIVATED*\nReason: `{reason}`\nAll positions squared off fail-closed."

        elif cmd == "/squareoff":
            async with AsyncSessionLocal() as db:
                closed = await portfolio_tracker.square_off_all(reason="TELEGRAM_MANUAL_SQUARE_OFF", db=db)
                return f"⏹️ *SQUARED OFF ALL POSITIONS*\nClosed `{len(closed)}` open positions."

        return "Unknown command. Available commands: `/status`, `/approve`, `/reject`, `/squareoff`, `/kill`"


telegram_adapter = TelegramBotAdapter()

