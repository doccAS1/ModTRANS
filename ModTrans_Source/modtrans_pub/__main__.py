import sys

if len(sys.argv) > 1:
    # Se vengono passati argomenti (es. "python -m modtrans translate ..."), usa la CLI
    from .cli import main
    main()
else:
    # Se lanciato senza argomenti (es. "python -m modtrans"), avvia la GUI
    from .gui import ModTransGUI
    app = ModTransGUI()
    app.mainloop()