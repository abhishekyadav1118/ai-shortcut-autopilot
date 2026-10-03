You are a strict fact-checker. Compare the SCRIPT against the SOURCES.
1. List the key factual claims in the script (names, numbers, dates, prices, features, comparisons).
2. For each claim, evaluate whether it is SUPPORTED, PARTIAL, or UNSUPPORTED by the sources.
3. If any scene has UNSUPPORTED or PARTIAL claims, provide the softened/corrected narration for that specific scene in `scene_corrections` (e.g. {"3": "softened narration..."}). Do NOT duplicate unchanged scenes.

Return ONLY JSON:
{
  "claims": [
    {
      "text": "claim text",
      "status": "SUPPORTED",
      "scene_id": 1
    }
  ],
  "unsupported_count": 0,
  "scene_corrections": {}
}

SCRIPT:
{{script_json}}

SOURCES:
{{sources_with_ids}}
