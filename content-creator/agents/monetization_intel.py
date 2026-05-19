import re
import json
import random
from core import ollama_client as ollama


SYSTEM_PROMPT = "You are a monetization expert. Return ONLY valid JSON."

VIEWS_MULTIPLIER = {"10k": 0.01, "100k": 0.1, "1m": 1.0, "10m": 10.0}


async def run(niche: str, views: str) -> dict:
    models = await ollama.list_models()
    model = ollama.pick_model(models, ["mistral:7b", "llama3:8b", "phi3:mini"])
    mult = VIEWS_MULTIPLIER.get(views, 1.0)

    prompt = f"""Generate monetization intelligence for a {niche} content creator with {views} monthly views.

Return JSON:
{{
  "niche": "{niche}",
  "total_monthly": 8500,
  "best_cpm": "12.50",
  "affiliate_count": 8,
  "deal_rate": 2500,
  "profit_score": 8,
  "revenue_streams": {{
    "adsense": 2000,
    "affiliate": 3000,
    "sponsor": 2500,
    "merch": 700,
    "member": 300
  }},
  "affiliates": [
    {{"name": "Program Name", "commission": "30%", "cookie": "90 days", "epc": "2.40", "status": "OPEN"}},
    {{"name": "Program Name", "commission": "25%", "cookie": "30 days", "epc": "1.80", "status": "OPEN"}},
    {{"name": "Program Name", "commission": "15%", "cookie": "60 days", "epc": "3.20", "status": "OPEN"}},
    {{"name": "Program Name", "commission": "20%", "cookie": "45 days", "epc": "1.50", "status": "OPEN"}}
  ],
  "brand_deals": [
    {{"category": "Software/SaaS", "integration": "Dedicated", "rate_10k": 500, "rate_100k": 3500}},
    {{"category": "E-commerce", "integration": "Mention", "rate_10k": 200, "rate_100k": 1500}},
    {{"category": "Finance", "integration": "Dedicated", "rate_10k": 800, "rate_100k": 5000}}
  ],
  "cpm_by_country": [
    {{"country": "United States", "cpm": 12.5}},
    {{"country": "United Kingdom", "cpm": 9.8}},
    {{"country": "Australia", "cpm": 8.4}},
    {{"country": "Canada", "cpm": 7.9}},
    {{"country": "Germany", "cpm": 7.2}}
  ],
  "strategy": {{
    "plan": "Day 1-7: Set up affiliate links for top 3 programs\\nDay 8-14: Pitch 5 brands in your niche\\nDay 15-21: Launch membership/community\\nDay 22-30: Review and double down on top performer",
    "quick_wins": [
      "Sign up for Amazon Associates today — 24hr setup",
      "Add affiliate links to existing video descriptions",
      "Create a simple Notion template to sell for $9-29"
    ]
  }}
}}

Make it realistic for {niche} with {views} monthly views. Scale revenue appropriately. Return only JSON."""

    try:
        response = await ollama.generate(model, prompt, system=SYSTEM_PROMPT)
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            _scale(data, mult)
            return data
    except Exception:
        pass

    return _fallback(niche, mult)


def _scale(data: dict, mult: float):
    for k in ["total_monthly", "deal_rate"]:
        if k in data:
            data[k] = int(data[k] * mult)
    if "revenue_streams" in data:
        for k in data["revenue_streams"]:
            data["revenue_streams"][k] = int(data["revenue_streams"][k] * mult)


def _fallback(niche: str, mult: float) -> dict:
    base = {
        "niche":          niche,
        "total_monthly":  int(8500 * mult),
        "best_cpm":       f"{random.uniform(5, 20):.2f}",
        "affiliate_count": random.randint(5, 15),
        "deal_rate":      int(2500 * mult),
        "profit_score":   random.randint(6, 9),
        "revenue_streams": {
            "adsense":   int(2000 * mult),
            "affiliate": int(3000 * mult),
            "sponsor":   int(2500 * mult),
            "merch":     int(700 * mult),
            "member":    int(300 * mult),
        },
        "affiliates": [
            {"name": "Amazon Associates",  "commission": "3-10%",  "cookie": "24 hours", "epc": "1.20", "status": "OPEN"},
            {"name": "ShareASale",         "commission": "5-50%",  "cookie": "30 days",  "epc": "2.80", "status": "OPEN"},
            {"name": "ClickBank",          "commission": "10-75%", "cookie": "60 days",  "epc": "3.50", "status": "OPEN"},
            {"name": "Impact Radius",      "commission": "5-30%",  "cookie": "45 days",  "epc": "2.10", "status": "OPEN"},
        ],
        "brand_deals": [
            {"category": "Software/SaaS",  "integration": "Dedicated", "rate_10k": int(500*mult),  "rate_100k": int(3500*mult)},
            {"category": "E-commerce",     "integration": "Mention",   "rate_10k": int(200*mult),  "rate_100k": int(1500*mult)},
            {"category": "Finance",        "integration": "Dedicated", "rate_10k": int(800*mult),  "rate_100k": int(5000*mult)},
        ],
        "cpm_by_country": [
            {"country": "United States", "cpm": 12.5},
            {"country": "United Kingdom", "cpm": 9.8},
            {"country": "Australia",      "cpm": 8.4},
            {"country": "Canada",         "cpm": 7.9},
            {"country": "Germany",        "cpm": 7.2},
        ],
        "strategy": {
            "plan": f"Week 1: Pick top 3 affiliate programs for {niche}\nWeek 2: Pitch 5 brands via email\nWeek 3: Launch digital product\nWeek 4: Review and scale what worked",
            "quick_wins": [
                "Add affiliate links to your top 5 videos now",
                "Create a free lead magnet → paid upsell",
                "Email 10 brands in your niche with a rate card",
            ],
        },
    }
    return base
