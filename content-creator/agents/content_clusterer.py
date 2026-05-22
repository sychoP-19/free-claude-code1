from core import ollama_client as ollama
import json

class ContentClusterer:
    async def cluster(self, topics: list) -> dict:
        """Groups similar trending topics into cohesive Master Topics."""
        models = await ollama.list_models()
        model = ollama.pick_model(models, ["mistral:7b", "llama3:8b"])
        
        prompt = f"""Cluster these trending topics into logical groups (Master Topics):
{json.dumps(topics)}

Return JSON: {{"MasterTopicName": ["topic1", "topic2"]}}"""
        
        try:
            response = await ollama.generate(model, prompt)
            return json.loads(response)
        except Exception:
            return {"Uncategorized": topics}
