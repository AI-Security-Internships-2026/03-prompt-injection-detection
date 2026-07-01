# Garak Prompt Injection Test Results

## Target Model
- Model: GPT-2 (openai-community/gpt2)
- Source: HuggingFace
- Type: Real LLM (not dummy test model)

## Test Configuration
- Tool: Garak v0.15.1
- Probes: promptinject
- Date: 28-06-2026
- Total attempts per probe: 1,280

## Results

| Probe | Attacks Succeeded | Total Attempts | Attack Success Rate |
|---|---|---|---|
| HijackHateHumans | 240 | 1280 | 18.75% |
| HijackKillHumans | 363 | 1280 | 28.36% |
| HijackLongPrompt | 147 | 1280 | 11.48% |
| **Average** | **250** | **1280** | **19.53%** |

## Key Findings
- GPT-2 is genuinely vulnerable to prompt injection attacks
- HijackKillHumans probe had highest success rate (28.36%)
- HijackLongPrompt had lowest success rate (11.48%) — suggesting longer prompts provide more context resistance
- Compare to dummy test model: 0% (meaningless) vs GPT-2: 19.53% (real vulnerability)

## What These Numbers Mean
- 1 in 5 attacks on average successfully hijacked GPT-2's output
- The model was most vulnerable to violence-related injection attempts
- Longer prompts reduced attack success — useful insight for defence design

## Next Steps
- Build automated test harness (src/test_harness.py) to log these results programmatically
- Test against more capable models when API access available
- Use these results as baseline to evaluate our detector