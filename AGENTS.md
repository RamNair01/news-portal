# Personal News Portal

## Project contract

- This is a locally hosted personal dashboard. Do not add hosting, telemetry,
  or external-user features.
- Keep the pipeline resilient: log and skip an individual source failure;
  never prevent the rest of a refresh from completing.
- Deduplicate fetched articles and retain only the last seven days.
- Gmail access must remain read-only and use the minimum OAuth scope.
- Nitter failures must degrade gracefully and remain visible in the Twitter
  section.

## AI integration

- Use the OpenAI Python SDK and the Responses API, authenticated only through
  `OPENAI_API_KEY`. Never log, expose, or commit that key.
- The default model is `gpt-5.6-terra`; it may be overridden with
  `OPENAI_MODEL`.
- The chat panel uses today's headlines as its primary context. Responses are
  concise, direct, explanatory when asked, and critically assess a user's
  interpretation rather than agreeing automatically.

## Working conventions

- Run Python through `uv`; validate changed modules with `uv run python -m
  py_compile ...`.
- Preserve the dashboard's editorial visual character: intentional typography,
  hierarchy, and accessible interaction over generic component styling.
- Keep configuration in `config.yaml` and secrets in `.env`.

## Writing requirements

- Use a clear, concise, natural register. For academic material, use standard
  MSc-thesis structure; for news summaries and interface copy, use the
  appropriate factual or editorial register.
- Make minimal, targeted edits and preserve existing wording when it is sound.
  Flag every change and its reason rather than editing silently.
- Remove repetition and non-essential material. Keep the logical connection
  between paragraphs and sections when tightening a draft.
- Use first-person singular where a personal voice is appropriate. Do not use
  em dashes.
- Avoid inflated significance claims, promotional language, vague attribution,
  superficial `-ing` clauses, AI-vocabulary filler, negative parallelisms,
  forced groups of three, synonym cycling, and excessive connective phrases.
- Prefer precise, sourced claims over generic writing advice or broad claims
  about what “experts” or “observers” think.
