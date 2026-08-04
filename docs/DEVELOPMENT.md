# Development

## Requirements

- Python 3.11 or newer
- Tkinter
- `truststore`
- `httpx`
- `urllib3`

Install runtime requirements:

```bash
python -m pip install -r requirements-runtime.txt
```

Run the interface:

```bash
python run_app.py
```

Run all tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Run the visual theme test under Linux without a physical display:

```bash
xvfb-run -a python -m unittest tests.unit.test_v3_ui_theme -v
```

Compile-check the package:

```bash
python -m compileall -q archive_scout tests
```

The test workflow runs on Windows, Linux, and Intel macOS using Python 3.11 and 3.12. The build workflow creates Windows x64, Linux x64, and universal macOS packages.

## Release version

The current source release is:

```text
3.0.0-beta.1.2.1
```

The Python package version uses the PEP 440 form `3.0.0b1.post3` in `pyproject.toml`.
