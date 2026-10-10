# Brief: model prices for finishing the model runs on a paid tier

**Question:** what would it cost to finish runs (a) and (b) (P10, D34) on a paid API tier, and which three providers or models are cheapest while still doing the job (a vision model for extraction, a text model for the merge, both returning JSON that matches a schema)?
**Asked by:** the Manager, through the lead. Written by the researcher on 2026-10-08. Every price was read on 2026-10-08 from the provider's own page.

Tags:
- **[docs]**: the file or URL was read.
- **[docs\*]**: known only from a search summary or a forum post, not from the provider's documentation.
- **[unverified]**: not confirmed.
- **[design]**: a recommendation from this brief.

## 1. What our code asks of a model

- **One provider per run.** `LLM_PROVIDER`, `LLM_BASE_URL` and `LLM_API_KEY` are global, so `EXTRACT_MODEL` and `MERGE_MODEL` must be served by the same endpoint and key. **[docs]** `backend/app/config.py:49-59`
- **`anthropic` path:** the output is the input of one tool, `record_output`, with `input_schema`. No `thinking` field is sent. **[docs]** `backend/app/digest/llm.py:319-377`
- **`openai` path:** it sends `response_format: {"type": "json_object"}` (JSON mode) with the schema pasted into the system prompt, and `max_completion_tokens`. It does not send `json_schema`, so the schema is not enforced server-side. Pydantic validation and one retry are the guard. No reasoning setting is sent. **[docs]** `llm.py:380-426`
- **`gemini` path:** native `generateContent` with `responseJsonSchema`, falling back to `responseSchema`. It sends no `thinkingConfig`, and it counts `thoughtsTokenCount` as output. **[docs]** `llm.py:429-509`
- **Thinking runs at each model's default**, since no path sends a switch to turn it off. Thinking tokens also count against `LLM_MAX_OUTPUT_TOKENS` (default 4096). **[docs]** `llm.py`, `.env.example:30-31`
- **The model name is part of the cache key**, so after a model change every call the run makes is paid. **[docs]** `llm.py:113-127`
- **Volume yardstick:** the last full digest (2026-10-02, Claude models) made 514 calls, 473 for extraction and 41 for the merge. It used 1,728,515 input and 329,989 output tokens. **[docs]** `README.md` "Cost per case". Runs (a) and (b) re-run only part of that (README), so a full digest is the upper bound.
  - Image tokens and tokenizers differ by provider. Anthropic says its 4.7+ tokenizer gives about 30% more tokens than its earlier one. Groq counts 2,048 tokens per image, and Qwen counts h×w/1024+2. **[docs]** the pricing pages below, https://console.groq.com/docs/vision, https://www.alibabacloud.com/help/en/model-studio/vision-model
  - So treat the "full digest" column as a yardstick, not a quote.

## 2. The table

Prices are standard paid tier, USD per 1M tokens, for prompts under any long-context threshold; our prompts are 1.5k to 10k tokens.
- **Full digest** = 1.7285 × in + 0.3300 × out, computed by the researcher from the yardstick above.
- **"+think"** means the model thinks by default on our code, and that output is billed on top.
- **Wire** is the `LLM_PROVIDER` value our code would use.

| Provider | Model id | In | Out | Vision | Schema output | Wire | Entry paid RPM | Full digest | Source (read 2026-10-08) |
|---|---|---|---|---|---|---|---|---|---|
| Google | `gemini-3.8-flash` | 0.75 (1.50 from 2027-01-01) | 3.75 (7.50 from 2027-01-01) | yes | yes, native | gemini | not published; see AI Studio | $2.53 +think | https://ai.google.dev/gemini-api/docs/pricing, .../docs/models/gemini-3.8-flash |
| Google | `gemini-3.1-flash-lite` | 0.25 | 1.50 | yes | yes, native | gemini | not published | $0.93 (default thinking level not stated) | same pricing page, .../docs/models/gemini-3.1-flash-lite |
| Google | `gemini-3.5-flash-lite` | 0.30 | 2.50 | yes | yes, native | gemini | not published | $1.34 +think (`minimal`) | same pricing page, .../docs/models/gemini-3.5-flash-lite |
| Google | `gemini-3.1-pro-preview` (newest Pro; paid only) | 2.00 | 12.00 | unclear (page not read) | unclear | gemini | not published | $7.42 | same pricing page |
| OpenAI | `gpt-6-luna` | 0.10 | 0.50 | yes | yes (we use JSON mode) | openai | 5,000 (Build) | $0.34 +think | https://developers.openai.com/api/docs/pricing, .../docs/models/gpt-6-luna |
| OpenAI | `gpt-5.6-luna` | 0.20 | 1.20 | yes | yes (JSON mode) | openai | 5,000 | $0.74 +think | .../docs/models/gpt-5.6-luna |
| OpenAI | `gpt-5.4-nano` | 0.20 | 1.25 | yes | yes (JSON mode) | openai | 5,000 | $0.76 | .../docs/models/gpt-5.4-nano |
| OpenAI | `gpt-5.4-mini` | 0.75 | 4.50 | yes | yes (JSON mode) | openai | 5,000 | $2.78 | .../docs/models/gpt-5.4-mini |
| OpenAI | `gpt-4.1-mini` | 0.40 | 1.60 | yes | yes (JSON mode) | openai | 5,000 | $1.22 | .../docs/models/gpt-4.1-mini |
| OpenAI | `gpt-4.1` | 2.00 | 8.00 | unclear (page not read) | unclear | openai | unclear | $6.10 | pricing page only |
| DeepSeek | `deepseek-flash` (V4.1 Flash) | 0.30 peak, 0.15 off-peak | 1.20 peak, 0.60 off-peak | yes | JSON mode only (`json_object`; no `json_schema`) | openai, or anthropic via `/anthropic` | no RPM limit; 2,500 concurrent requests | $0.91 peak, $0.46 off-peak +think | https://api-docs.deepseek.com/quick_start/pricing, .../api/create-chat-completion |
| DeepSeek | `deepseek-v4-pro` | 1.32 peak, 0.66 off-peak | 3.96 peak, 1.98 off-peak | **no** | JSON mode only | openai | 500 concurrent | merge only | same |
| Anthropic | `claude-haiku-5-5` | 0.10 (prompts up to 100k) | 0.50 | yes | yes (tool use; structured outputs GA) | anthropic | 1,000 (Start) | $0.34 +think | https://platform.claude.com/docs/en/about-claude/pricing, .../models/overview |
| Anthropic | `claude-haiku-4-5-20251001` (legacy) | 1.00 | 5.00 | yes | yes | anthropic | 1,000 | $3.38 | same |
| Anthropic | `claude-sonnet-5` (legacy) | 2.00 | 10.00 | yes | yes | anthropic | 1,000 | $6.76 +think | same |
| Anthropic | `claude-sonnet-5-5` | 2.00 | 10.00 | yes | yes | anthropic | 1,000 | $6.76 +think | same |
| Mistral | `mistral-small-2603` (Small 4) | 0.15 | 0.60 | unclear (the card's modality field is blank; the launch post says yes **[docs\*]**) | yes ("Structured Outputs") | openai [unverified] | not published (console) | $0.46 | https://docs.mistral.ai/models/mistral-small-4-0-26-03 |
| Mistral | `mistral-large-2512` (Large 3) | 0.50 | 1.50 | yes (listed on the vision page) | yes | openai [unverified] | not published | $1.36 | https://docs.mistral.ai/models/mistral-large-3-25-12, https://mistral.ai/pricing |
| Mistral | Medium 3.5 (v26.04; API id not shown) | 1.50 | 7.50 | yes ("multimodal") | yes | openai [unverified] | not published | $5.07 | https://docs.mistral.ai/models/model-cards/mistral-medium-3-5-26-04 |
| Alibaba | `qwen3.7-flash` (Singapore) | 0.03 (up to 32K) | 0.13 | yes | JSON mode; schema not enforced with images | openai | 15,000 | $0.09 +think | https://www.alibabacloud.com/help/en/model-studio/model-pricing, .../vision-model, .../json-mode |
| Alibaba | `qwen3-vl-flash` (Singapore) | 0.05 (up to 32K) | 0.40 | yes | JSON mode | openai | 1,200 | $0.22 | same, .../rate-limit |
| xAI | `grok-4.20-0309-non-reasoning` | 1.25 | 2.50 | yes | yes | openai (Chat Completions is "legacy" **[docs\*]**) | 37 requests/s | $2.99 | https://docs.x.ai/docs/models, .../developers/models/grok-4.20-0309-non-reasoning |
| xAI | `grok-4.3` | 1.25 | 2.50 | yes | yes | openai | 37 requests/s | $2.99 +think | .../developers/models/grok-4.3 |
| Groq | `qwen/qwen3.8-27b` (preview) | 0.80 | 4.00 | yes (max 3 images) | JSON mode | openai | 1,000 (Developer) | $2.70 | https://console.groq.com/docs/models, .../docs/vision |

Notes on the table:
- **Mistral's model cards** show two prices without labels; in and out is the order on the page. **[docs]**
- **Together** lists "Qwen3.8 Flash" at $0.15/$0.47, the same price as Alibaba. Its docs name no vision model with structured output, and its serverless tier is "best-effort", so it adds nothing over a first-party API. **[docs]** https://www.together.ai/pricing, https://docs.together.ai/docs/rate-limits
- **`gemini-2.5-flash-lite`** ($0.10/$0.40) is limited to users who used it before. **[docs]** https://ai.google.dev/gemini-api/docs/models

## 3. Thinking, cache and batch

**Thinking or reasoning: on by default, billed as output, and how to turn it off.**
- **Gemini:**
  - 3.8 and 3.7 Flash default to `medium`, and the lowest level is `low`; `minimal` is rejected, so thinking can't be turned off. 3.5 Flash-Lite defaults to `minimal`.
  - "Response pricing is the sum of output tokens and thinking tokens."
  - **[docs]** https://ai.google.dev/gemini-api/docs/thinking, .../models/gemini-3.8-flash
- **Claude:**
  - Haiku 5.5, Sonnet 5 and Sonnet 5.5 think adaptively when no `thinking` field is sent. Haiku 4.5 does not.
  - `thinking: {"type": "disabled"}` turns it off on Haiku 5.5 and Sonnet 5, but Sonnet 5.5 rejects it.
  - Thinking is billed as output and counts toward `max_tokens`.
  - **[docs]** https://platform.claude.com/docs/en/build-with-claude/thinking
- **OpenAI:**
  - `gpt-6-luna` and `gpt-5.6-luna` default to `medium`, and `none` is allowed. `gpt-5.4-nano` and `gpt-5.4-mini` default to `none`. `gpt-4.1-mini` has no reasoning step.
  - Reasoning tokens are billed as output, and OpenAI suggests reserving 25,000 tokens when you start out.
  - **[docs]** the model pages above, https://developers.openai.com/api/docs/guides/reasoning
- **DeepSeek:**
  - Thinking is on by default at effort `high`; `thinking: {"type": "disabled"}` or `reasoning_effort: "none"` turns it off.
  - It reports `completion_tokens_details.reasoning_tokens`. Whether `completion_tokens` includes them is not stated, so our cost figure could undercount **[unverified]**.
  - **[docs]** https://api-docs.deepseek.com/guides/thinking_mode
- **Qwen:**
  - qwen3.7-flash and qwen3.8-flash think by default; `enable_thinking: false` turns it off. "Thinking content is billed by Output Token."
  - JSON mode in thinking mode "may return content that is not strictly valid JSON".
  - **[docs]** https://www.alibabacloud.com/help/en/model-studio/deep-thinking, .../json-mode
- **xAI:** `grok-4.3` defaults to effort `low`, and `none` is allowed. The page doesn't say how reasoning is billed. **[docs]**

**Cached input, per 1M tokens:** Gemini 3.8 Flash $0.075 and 3.1 Flash-Lite $0.025; OpenAI luna $0.01 and nano $0.02; Claude Haiku 5.5 $0.01 on a hit; DeepSeek $0.006 peak; xAI $0.20; Qwen hits at 10% of input; Mistral "up to 90%" off. **[docs]** the pages in the table. Our code sets no explicit cache, so only automatic prefix caching could apply **[unverified]**.

**Batch API, for reference only** (our code doesn't batch): 50% off at Gemini, OpenAI, Anthropic, Mistral, and Qwen's flash models; 20% off at xAI; DeepSeek lists none. **[docs]** the pages in the table

## 4. Getting to a paid tier, and reliability

- **Gemini Tier 1:**
  - Link a billing account in AI Studio; the upgrade "typically takes effect instantly". Spend caps are $10 per rolling 10 minutes and a $250 tier cap. Per-model RPM appears only in AI Studio. **[docs]** https://ai.google.dev/gemini-api/docs/rate-limits
  - A Tier 1 user posts 1,000 RPM for 3.6 Flash **[docs\*]**.
  - The free tier of 3.8 Flash is reported at 20 requests per day **[docs\*]** https://discuss.ai.google.dev/t/gemini-3-8-flash-free-tier-20-rpd-is-too-limited-for-practical-evaluation/180609. A full digest is 514 calls.
- **Gemini data use:** on the free tier, content is "used to improve our products"; on the paid tier it is not. **[docs]** pricing page. That matters for a real person's medical file.
- **Gemini 503s:**
  - Google publishes no guarantee for Standard paid traffic: "actual capacity may vary".
  - A forum reply (Nov 2025) says "requests from paid tiers are prioritized … during periods of high traffic" **[docs\*]** https://discuss.ai.google.dev/t/api-not-working-overload-error-code-503/109376, while Tier 1 users still report 503s **[docs\*]**.
  - Only Priority inference is "non-sheddable" (`service_tier: priority`, 75 to 100% more) **[docs]** https://ai.google.dev/gemini-api/docs/priority-inference. It is documented for the Interactions API; whether `generateContent` accepts it is **[unverified]**.
- **OpenAI:** Build tier at $5 in credit purchases ($500 a month): 5,000 RPM and 2M TPM for luna, nano, mini and 4.1-mini. **[docs]** https://developers.openai.com/api/docs/guides/rate-limits
- **Anthropic:** Start tier gives 1,000 RPM per model with a $500 monthly cap. New organizations "may start in the Evaluation tier, with limits below the standard limits". **[docs]** https://platform.claude.com/docs/en/api/rate-limits
- **DeepSeek:**
  - The limit is concurrency, not RPM. Under load, it holds a request open for up to 10 minutes, sending blank lines; our timeout is 180 s. **[docs]** https://api-docs.deepseek.com/quick_start/rate_limit
  - JSON mode "may occasionally return empty content". **[docs]** https://api-docs.deepseek.com/guides/json_mode
  - Its privacy policy says it stores personal data "in People's Republic of China". **[docs]** https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html
- **Alibaba:** limits are set per account and "independent of billing". There is 1M free tokens per model for 90 days, in Singapore only. **[docs]** .../rate-limit, .../model-pricing
- **xAI:** tiers come from cumulative spend; Tier 0 starts at $0 **[docs\*]**. **Mistral:** paid tiers need the Scale plan, and the numbers are shown only in the console **[docs\*]**. **Groq:** preview models are "for evaluation purposes only" **[docs]**.

## 5. The three cheapest that do the job

At our volume, every candidate except the Pro and Sonnet class costs under $3 for a full digest, and the price differences are cents. So pick on fit **[design]**. Quality on our scanned pages is **[unverified]** for every model here.

1. **Anthropic `claude-haiku-5-5`, both roles:**
   - $0.10/$0.50, so about $0.34 for a full digest before thinking.
   - The `anthropic` path ran the 2026-10-02 full digest end to end (README), and its tool schema is the strongest guard we have.
   - Change (pipeline): send `thinking: {"type": "disabled"}`, or raise `LLM_MAX_OUTPUT_TOKENS`.
   - If the merge needs more, `claude-sonnet-5` covers its 41 calls under the same key.
2. **OpenAI `gpt-5.4-nano`:**
   - $0.20/$1.25, about $0.76, with no code change, since reasoning defaults to `none`.
   - `gpt-6-luna` costs half that once pipeline sends `reasoning_effort: "none"` or `"low"`.
   - Build tier after a $5 purchase. The code uses JSON mode only.
3. **Google Gemini on paid Tier 1, using the key the Manager already has:**
   - No code change, and the schema is enforced natively.
   - `gemini-3.1-flash-lite` is about $0.93, or keep `gemini-3.8-flash` at about $2.53 (its prices double on 2027-01-01).
   - Billing also stops Google using the content. A forum reply says paid traffic is served first under load, but paid users still report 503s **[docs\*]**.

Cheaper on paper, but not ranked:
- **qwen3.7-flash** (about $0.09) and **qwen3-vl-flash** (about $0.22): no schema enforcement with images; thinking is on by default; the URL needs a workspace id.
- **deepseek-flash** (about $0.46 to $0.91): JSON mode only, an empty-content bug, and storage in the PRC.
- **Mistral Small 4** (about $0.46): vision is not confirmed on its card.

## Rules for the builders

1. One provider per run: both models must be served by the same `LLM_PROVIDER`, `LLM_BASE_URL` and `LLM_API_KEY`.
2. Set all four `*_PRICE_*` to this table's standard prices; for DeepSeek use peak prices, since the cost figure has one rate.
3. A new model name misses the cache for every call it makes: run the estimate first (P10, `cli reextract --dry-run`).
4. No path turns thinking off: Haiku 5.5, gpt-6-luna, Gemini 3.8 Flash, DeepSeek and qwen3.7-flash bill it as output, and it can fill the 4,096 cap and cut the JSON.
5. To turn thinking off, the per-provider fields are: Anthropic `thinking: {"type":"disabled"}`; OpenAI `reasoning_effort: "none"` (xAI's field name is unverified); DeepSeek `thinking: {"type":"disabled"}`; Qwen `enable_thinking: false`; Gemini 3.8 Flash can only go down to thinking level `low`.
6. The `openai` path is JSON mode, not `json_schema`: keep the Pydantic validation and the one retry; never trust the shape.
7. The `openai` path sends `max_completion_tokens`, but DeepSeek documents only `max_tokens`; check this before a run (also unverified for Mistral, Qwen and xAI).
8. Sending the real matter to DeepSeek (PRC storage) or to Gemini's free tier (used to improve products) is a Manager call, not a builder's.
9. Gemini Tier 1: read the per-model RPM in AI Studio into `EXTRACT_RPM` and `MERGE_RPM`, and stay under $10 per rolling 10 minutes.
10. Before switching, make one live call, then run a few pages on a database copy (the D30 rule).
