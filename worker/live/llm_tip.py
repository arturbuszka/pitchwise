"""Tactical LLM tips from player position snapshots."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a football tactical analyst. "
    "Given a series of player positions on the pitch (x=0-105m from left goal, y=0-68m from bottom touchline), "
    "give ONE concise tactical observation (1-3 sentences). "
    "Focus on formation shape, defensive/offensive balance, space to exploit, or pressing triggers. "
    "Be direct and specific. Respond in English."
)


def _build_prompt(snapshots: list[dict]) -> str:
    if not snapshots:
        return "No position data available."

    lines = []
    for snap in snapshots[-10:]:  # last 10 snapshots (~5s of data)
        ts = snap.get("timestamp", 0)
        players = snap.get("players", [])
        player_lines = []
        for p in players:
            cls = p.get("cls", "?")
            tid = p.get("track_id", "?")
            px = p.get("pitch_x")
            py = p.get("pitch_y")
            if px is not None and py is not None:
                player_lines.append(f"  {cls} #{tid}: ({px:.1f}m, {py:.1f}m)")
        if player_lines:
            lines.append(f"t={ts:.1f}s:\n" + "\n".join(player_lines))

    return "Recent player positions:\n\n" + "\n\n".join(lines)


async def get_tactical_tip(snapshots: list[dict], settings) -> str:
    """Call LLM with recent position snapshots and return a tactical tip string."""
    if not settings.llm_api_key:
        return ""

    try:
        import httpx

        prompt = _build_prompt(snapshots)
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 150,
            "temperature": 0.4,
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        base_url = settings.llm_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("LLM tip request failed")
        return ""
