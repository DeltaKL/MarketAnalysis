from PyInstaller.utils.hooks import collect_data_files

# Collect Tcl and Tk data files
datas = collect_data_files('tkinter')