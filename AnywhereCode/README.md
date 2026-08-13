# AnywhereCode

**Build a real Android app on your phone. No laptop. No Android Studio. No credit card.**

This directory holds the `anyplace` Python package. The full documentation —
quickstart, APK builds, free-token setup, contributing — lives in the
[repository README](../README.md).

```bash
pip install -e .
anyplace
```

## Tests

```bash
python3 test_e2e.py     # 9 tests — end-to-end with a mock LLM
python3 test_eas.py     # 42 tests — EAS cloud builds + OmniRoute provider
```

Both run offline with no API keys.

## Layout

```
anyplace/
├── cli/          command interface, config wizard, QR rendering
├── core/         plan → code → git → agentic pipeline → EAS builds
├── config/       API keys, platform detection (Termux vs desktop)
├── templates/    project boilerplate (structure only, not design)
└── mcp/          MCP server so Claude can drive the tool
```

## License

MIT
