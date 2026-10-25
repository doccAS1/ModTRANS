try:
    from modtrans.gui import ModTransGUI
except ModuleNotFoundError as e:   # nel repo GitHub la cartella si chiama modtrans_pub
    if e.name != "modtrans":
        raise
    from modtrans_pub.gui import ModTransGUI

if __name__ == "__main__":
    app = ModTransGUI()
    app.mainloop()