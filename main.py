# main.py

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDateEdit, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QProgressBar
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from tally_connector import fetch_pending_invoices, update_tally_voucher

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tally E-Invoice Integration")
        self.setGeometry(100, 100, 1200, 800)

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("From Date:"))
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        controls_layout.addWidget(self.from_date)

        controls_layout.addWidget(QLabel("To Date:"))
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        controls_layout.addWidget(self.to_date)

        self.fetch_button = QPushButton("Fetch Invoices")
        self.fetch_button.clicked.connect(self.fetch_invoices)
        controls_layout.addWidget(self.fetch_button)

        self.generate_button = QPushButton("Generate E-Invoice")
        self.generate_button.clicked.connect(self.generate_einvoice)
        controls_layout.addWidget(self.generate_button)

        layout.addLayout(controls_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["Select", "Voucher No", "Date", "Party Name", "GSTIN", "Destination", "Taxable Amt", "CGST", "SGST", "IGST"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Status bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

    def fetch_invoices(self):
        """Fetch invoices from Tally."""
        try:
            from_date = self.from_date.date().toString("dd-MM-yyyy")
            to_date = self.to_date.date().toString("dd-MM-yyyy")

            invoices = fetch_pending_invoices(from_date, to_date)
            self.table.setRowCount(len(invoices))

            for row, invoice in enumerate(invoices):
                self.table.setItem(row, 1, QTableWidgetItem(invoice['voucher_number']))
                self.table.setItem(row, 2, QTableWidgetItem(invoice['date']))
                self.table.setItem(row, 3, QTableWidgetItem(invoice['party_name']))
                self.table.setItem(row, 4, QTableWidgetItem(invoice['party_gstin']))
                self.table.setItem(row, 5, QTableWidgetItem(invoice['destination']))
                self.table.setItem(row, 6, QTableWidgetItem(str(invoice['taxable_amount'])))
                self.table.setItem(row, 7, QTableWidgetItem(str(invoice['cgst_amount'])))
                self.table.setItem(row, 8, QTableWidgetItem(str(invoice['sgst_amount'])))
                self.table.setItem(row, 9, QTableWidgetItem(str(invoice['igst_amount'])))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch invoices: {e}")

    def generate_einvoice(self):
        """Generate e-invoice for selected vouchers."""
        QMessageBox.information(self, "Info", "E-Invoice generation functionality is not implemented yet.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())