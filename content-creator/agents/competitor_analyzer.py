try:
    from skill_utils import web_search_exa
except ModuleNotFoundError:
    async def web_search_exa(query: str, **_):  # type: ignore[misc]
        return []

class CompetitorAnalyzer:
    async def analyze_velocity(self, topic: str, platforms: list) -> dict:
        # Fetch competitor content for the same topic
        search_query = f"top performing {topic} videos on {', '.join(platforms)}"
        competitor_data = await web_search_exa(query=search_query, numResults=5)
        
        # Analyze metrics (dummy logic for now, enhanced via LLM prompt)
        return {
            "topic": topic,
            "competitors": competitor_data,
            "cross_platform_opportunity": "high" if len(platforms) > 1 else "low"
        }
