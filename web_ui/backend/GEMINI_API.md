# Gemini API Key Usage

To enable Dave Dev to use Google Gemini (Gemini Pro) for dynamic answers, set the environment variable `GEMINI_API_KEY` in your environment. If both `GEMINI_API_KEY` and `OPENAI_API_KEY` are set, Gemini will be used by default.

## How to set up

1. Obtain a Gemini API key from Google AI Studio: https://aistudio.google.com/app/apikey
2. Add the following to your `.env` file or environment:

    GEMINI_API_KEY=your-gemini-api-key-here

3. Restart your backend server.

## Fallback
- If `GEMINI_API_KEY` is not set, the backend will use `OPENAI_API_KEY` if available.
- If neither is set, only static answers are available.

## Troubleshooting
- Make sure your API key is valid and has access to the Gemini Pro model.
- Check backend logs for error messages if answers are not returned.
