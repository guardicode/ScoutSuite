from PyInstaller.utils.hooks import collect_data_files, collect_all

datas, binaries, hiddenimports = collect_all('ScoutSuite')
datas.extend(collect_data_files('policyuniverse'))
hiddenimports.append('configparser')
