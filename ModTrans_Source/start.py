import sys

try:
    from modtrans.gui import ModTransGUI
    from modtrans.cli import main as cli_main
except ModuleNotFoundError as e:   # nel repo GitHub la cartella si chiama modtrans_pub
    if e.name != "modtrans":
        raise
    from modtrans_pub.gui import ModTransGUI
    from modtrans_pub.cli import main as cli_main

if __name__ == "__main__":
    if len(sys.argv) > 1:          # es. ModTrans.exe translate <mod> -c config.toml
        cli_main()
    else:
        ModTransGUI().mainloop()
