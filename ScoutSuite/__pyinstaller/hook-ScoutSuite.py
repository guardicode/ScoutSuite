from PyInstaller.utils.hooks import collect_data_files, collect_all

datas, binaries, hiddenimports = collect_all('ScoutSuite.providers.aws')
datas.extend(collect_data_files('ScoutSuite', excludes=['__pyinstaller']))
