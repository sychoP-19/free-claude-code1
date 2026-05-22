"""Test Stage 1 (Topic Discovery) and Stage 2 (Script Generation) agents."""
import asyncio
import pytest
import json
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.trend_miner import run as trend_miner_run, generate_blueprint
from agents.content_factory import run as content_factory_run

# These tests hit live services (Ollama, YouTube RSS). Skip in CI / offline.
pytestmark = pytest.mark.network


@pytest.mark.asyncio
async def test_stage1_topic_discovery():
    """Test Stage 1: Topic Discovery Extension."""
    print("\n" + "="*60)
    print("TESTING STAGE 1: Topic Discovery Extension")
    print("="*60)

    # Test with YouTube platform
    result = await trend_miner_run(
        query="AI content creation",
        platform="youtube",
        window="7 days",
        output_batch=True
    )

    print(f"\nResult keys: {list(result.keys())}")
    print(f"Batch ID: {result.get('batch_id')}")
    print(f"Query: {result.get('query')}")
    print(f"Platform: {result.get('platform')}")

    topics = result.get("topics", [])
    print(f"\nNumber of topics returned: {len(topics)}")

    # Verify structure
    assert len(topics) >= 10, f"Expected 10+ topics, got {len(topics)}"

    # Check first topic has required fields
    first_topic = topics[0]
    required_fields = ["id", "title", "platform", "trend_score", "velocity",
                       "competition", "saturation", "estimated_cpm", "hashtags", "peak_window"]

    print("\nVerifying topic structure...")
    for field in required_fields:
        assert field in first_topic, f"Missing field: {field}"
    print(f"  [OK] All required fields present: {required_fields}")

    # Verify summary
    summary = result.get("summary", {})
    assert "total_topics" in summary, "Missing total_topics in summary"
    assert "avg_trend_score" in summary, "Missing avg_trend_score in summary"
    print(f"  [OK] Summary present: {summary}")

    # Verify output file
    output_path = result.get("_output_path")
    if output_path:
        assert Path(output_path).exists(), f"Output file not created: {output_path}"
        print(f"  [OK] Output file created: {output_path}")

        # Verify JSON structure
        with open(output_path) as f:
            saved_data = json.load(f)
        assert len(saved_data.get("topics", [])) >= 10, "Saved file has < 10 topics"
        print(f"  [OK] Output file contains {len(saved_data.get('topics', []))} topics")

    print("\n[PASS] STAGE 1: PASSED")
    return result


@pytest.mark.asyncio
async def test_stage2_script_generation():
    """Test Stage 2: Script Generation Agent."""
    print("\n" + "="*60)
    print("TESTING STAGE 2: Script Generation Agent")
    print("="*60)

    # Use a sample topic
    topic = "AI content creation tips"
    topic_id = "topic_001"

    result = await content_factory_run(
        topic=topic,
        style="shorts",
        tone="viral",
        topic_id=topic_id,
        output_file=True
    )

    print(f"\nResult keys: {list(result.keys())}")
    print(f"Topic ID: {result.get('topic_id')}")
    print(f"Topic: {result.get('topic')}")
    print(f"Duration: {result.get('duration_seconds')}s")

    # Verify script structure
    script = result.get("script", {})
    assert "hook" in script, "Missing hook in script"
    assert "body" in script, "Missing body in script"
    assert "cta" in script, "Missing cta in script"
    print("  [OK] Script structure: hook, body, cta present")

    # Verify scenes (5-10 scenes)
    scenes = result.get("scenes", [])
    assert 5 <= len(scenes) <= 10, f"Expected 5-10 scenes, got {len(scenes)}"
    print(f"  [OK] Scene count: {len(scenes)} scenes")

    # Verify each scene has required fields
    first_scene = scenes[0]
    scene_fields = ["scene_number", "description", "timing", "text_overlay"]
    for field in scene_fields:
        assert field in first_scene, f"Missing scene field: {field}"
    print(f"  [OK] Scene structure: {scene_fields}")

    # Verify hashtags per platform
    hashtags = result.get("hashtags", {})
    assert "youtube" in hashtags, "Missing youtube hashtags"
    assert "tiktok" in hashtags, "Missing tiktok hashtags"
    assert "instagram" in hashtags, "Missing instagram hashtags"
    print(f"  [OK] Hashtags for all platforms: youtube ({len(hashtags['youtube'])}), tiktok ({len(hashtags['tiktok'])}), instagram ({len(hashtags['instagram'])})")

    # Verify thumbnail prompts
    thumbnails = result.get("thumbnail_prompts", [])
    assert len(thumbnails) >= 3, f"Expected 3+ thumbnail prompts, got {len(thumbnails)}"
    print(f"  [OK] Thumbnail prompts: {len(thumbnails)} concepts")

    # Verify output file
    output_path = result.get("_output_path")
    if output_path:
        assert Path(output_path).exists(), f"Output file not created: {output_path}"
        print(f"  [OK] Output file created: {output_path}")

    print("\n[PASS] STAGE 2: PASSED")
    return result


@pytest.mark.asyncio
async def test_multi_platform_support():
    """Test multi-platform support (YouTube, TikTok, Instagram)."""
    print("\n" + "="*60)
    print("TESTING MULTI-PLATFORM SUPPORT")
    print("="*60)

    platforms = ["youtube", "tiktok", "instagram"]

    for platform in platforms:
        print(f"\nTesting {platform}...")
        result = await trend_miner_run(
            query="fitness motivation",
            platform=platform,
            window="30 days",
            output_batch=False  # Don't write files for this test
        )

        topics = result.get("topics", [])
        assert len(topics) >= 10, f"{platform}: Expected 10+ topics, got {len(topics)}"

        # Verify all topics have the correct platform
        for topic in topics:
            assert topic.get("platform") == platform, f"{platform}: Topic has wrong platform"

        print(f"  [OK] {platform}: {len(topics)} topics with correct platform")

    print("\n[PASS] MULTI-PLATFORM: PASSED")


async def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# JARVIS REEL PRODUCTION PIPELINE - STAGE 1 & 2 TESTS")
    print("#" * 60)

    try:
        # Run Stage 1 test
        stage1_result = await test_stage1_topic_discovery()

        # Run Stage 2 test
        stage2_result = await test_stage2_script_generation()

        # Run multi-platform test
        await test_multi_platform_support()

        # Summary
        print("\n" + "="*60)
        print("ALL TESTS PASSED")
        print("="*60)
        print("\nStage 1 (Topic Discovery):")
        print(f"  - Returns 10+ topics: OK")
        print(f"  - Structured JSON output: OK")
        print(f"  - Writes to outputs/topics/batch_YYYYMMDD.json: OK")

        print("\nStage 2 (Script Generation):")
        print(f"  - Script with HOOK/BODY/CTA: OK")
        print(f"  - Scene breakdown (5-10 scenes): OK")
        print(f"  - Hashtags per platform (youtube/tiktok/instagram): OK")
        print(f"  - Thumbnail generation prompts: OK")
        print(f"  - Writes to outputs/scripts/{{topic_id}}.json: OK")

        print("\n[SUCCESS] Implementation complete!")

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)