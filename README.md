## Pyinstaller fork

This for adds api to ScoutSuite. Also, pyinstaller hooks are added,
so that it would be possible to package scoutsuite into a binary.

For an official repo go to https://github.com/nccgroup/ScoutSuite

To run hooks do:

Upgrade pip: 

`python -m pip install -U pip`

Install this package with the optional test and docs requirements:

`pip install -e .[test,docs]`

Run the tests; see also notes on this:

`python -m PyInstaller.utils.run_tests --include_only ScoutSuite.`

If test fails, try building manually: 

1. Open shell in `ScoutSuite/__pyinstaller/packet_test`
2. `pyinstaller --clean -F ./packaging_test.py`
3. `.\dist\packaging_test.exe m0nk3y -s localhost:5000` to see if it works
