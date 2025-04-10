# main.py

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
import threading # To run API calls in background
import json # Needed for potential validation

# Import local modules
import config_manager
import tally_connector
import irn_generator
# import validator # Uncomment if using validator (and ensure it's updated if needed)

# --- App Configuration ---
ctk.set_appearance_mode("System") # Modes: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue") # Themes: "blue" (default), "green", "dark-blue"

class TallyEInvoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Tally E-Invoice Bridge")
        self.geometry("1000x600")

        # --- Data ---
        self.pending_invoices = []
        # Load configuration using the manager
        # This handles .env, config.ini, and defaults
        self.config = config_manager.load_config()

        # Update tally_connector's URL based on loaded config
        tally_connector.TALLY_URL = f"http://localhost:{self.config.get('TALLY', 'Port')}"
        print(f"Initial Tally URL set to: {tally_connector.TALLY_URL}")

        # --- Configure grid layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Treeview row expands

        # --- Top Frame (Controls) ---
        self.top_frame = ctk.CTkFrame(self, corner_radius=0)
        self.top_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        self.top_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=0) # Button/entry columns
        self.top_frame.grid_columnconfigure(6, weight=1) # Spacer column

        # Dates
        default_offset_str = self.config.get('APP', 'DefaultFromDateOffset', fallback='7')
        try:
            default_offset = int(default_offset_str)
        except ValueError:
            default_offset = 7 # Fallback if config value is invalid
        today = datetime.now()
        default_from = today - timedelta(days=default_offset)

        self.from_date_label = ctk.CTkLabel(self.top_frame, text="From:")
        self.from_date_label.grid(row=0, column=0, padx=(10, 5), pady=10)
        self.from_date_entry = ctk.CTkEntry(self.top_frame, width=100)
        self.from_date_entry.grid(row=0, column=1, padx=5, pady=10)
        self.from_date_entry.insert(0, default_from.strftime("%d-%m-%Y")) # Tally common format

        self.to_date_label = ctk.CTkLabel(self.top_frame, text="To:")
        self.to_date_label.grid(row=0, column=2, padx=(10, 5), pady=10)
        self.to_date_entry = ctk.CTkEntry(self.top_frame, width=100)
        self.to_date_entry.grid(row=0, column=3, padx=5, pady=10)
        self.to_date_entry.insert(0, today.strftime("%d-%m-%Y"))

        # Fetch Button
        self.fetch_button = ctk.CTkButton(self.top_frame, text="Fetch Invoices", command=self.fetch_invoices_thread)
        self.fetch_button.grid(row=0, column=4, padx=10, pady=10)

        # Config Button
        self.config_button = ctk.CTkButton(self.top_frame, text="Settings", command=self.open_settings)
        self.config_button.grid(row=0, column=5, padx=10, pady=10)


        # --- Treeview Frame (Invoice List) ---
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.tree_frame.grid_rowconfigure(0, weight=1)    # Treeview row expands
        self.tree_frame.grid_columnconfigure(0, weight=1) # Treeview column expands

        # Treeview Style
        style = ttk.Style(self)
        # Basic styling (can be customized further based on CTk theme)
        style.theme_use("clam") # A theme that generally works well
        style.configure("Treeview",
                        background="#2a2d2e", # Darker background
                        foreground="white",
                        rowheight=25,
                        fieldbackground="#343638", # Background of data cells
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#245e85')]) # Selection color
        style.configure("Treeview.Heading",
                        background="#565b5e", # Header background
                        foreground="white",
                        relief="flat",
                        font=('Calibri', 10,'bold'))
        style.map("Treeview.Heading",
                  background=[('active','#3484ba')]) # Header hover color

        # Treeview Widget
        self.tree = ttk.Treeview(self.tree_frame, columns=("MasterID", "VchNo", "Date", "Party", "Amount", "Status", "Error"), show='headings', style="Treeview")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Define headings
        self.tree.heading("MasterID", text="ID")
        self.tree.heading("VchNo", text="Voucher No")
        self.tree.heading("Date", text="Date")
        self.tree.heading("Party", text="Party Name")
        self.tree.heading("Amount", text="Amount")
        self.tree.heading("Status", text="E-Inv Status")
        self.tree.heading("Error", text="Last Error")

        # Define column widths
        self.tree.column("MasterID", width=60, stretch=False, anchor=tk.W)
        self.tree.column("VchNo", width=100, stretch=False, anchor=tk.W)
        self.tree.column("Date", width=90, stretch=False, anchor=tk.W)
        self.tree.column("Party", width=250, anchor=tk.W) # Allow stretch
        self.tree.column("Amount", width=120, stretch=False, anchor=tk.E)
        self.tree.column("Status", width=100, stretch=False, anchor=tk.W)
        self.tree.column("Error", width=300, anchor=tk.W) # Allow stretch

        # Scrollbars (using CTk scrollbars for better theme integration)
        vsb = ctk.CTkScrollbar(self.tree_frame, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ctk.CTkScrollbar(self.tree_frame, command=self.tree.xview, orientation="horizontal")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        # Bind double-click to show details
        self.tree.bind("<Double-1>", self.show_invoice_details)
        # Bind selection change (optional, e.g., to enable/disable generate button)
        # self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # --- Bottom Frame (Actions & Status) ---
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=0)
        self.bottom_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.bottom_frame.grid_columnconfigure(1, weight=1) # Status label expands

        self.generate_button = ctk.CTkButton(self.bottom_frame, text="Generate Selected E-Invoice(s)", command=self.generate_irn_thread)
        self.generate_button.grid(row=0, column=0, padx=10, pady=10)
        # self.generate_button.configure(state="disabled") # Start disabled until selection?

        # Status Label
        self.status_label = ctk.CTkLabel(self.bottom_frame, text="Ready", anchor="w")
        self.status_label.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Initial Tally Check
        self.check_tally_on_start()

    def update_status(self, message, is_error=False):
        """Updates the status bar label."""
        # Use CTk theme colors for errors if desired
        error_color = "#FF5050" # Example error color
        default_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        self.status_label.configure(text=message, text_color=error_color if is_error else default_color)
        self.update_idletasks() # Force GUI update

    def check_tally_on_start(self):
        """Checks Tally connection when the app starts."""
        self.update_status("Checking Tally connection...")
        try:
            if tally_connector.check_tally_connection():
                self.update_status(f"Tally connection OK ({tally_connector.TALLY_URL}). Ready.")
            else:
                self.update_status(f"Tally not running or port not open ({tally_connector.TALLY_URL})!", is_error=True)
                messagebox.showerror("Tally Connection Error", f"Could not connect to Tally ({tally_connector.TALLY_URL}).\nPlease ensure Tally is running, Company is open, and 'Enable ODBC Server' is set to Yes on the configured port.")
        except Exception as e:
             self.update_status(f"Error checking Tally: {e}", is_error=True)

    def fetch_invoices_thread(self):
        """Starts fetching invoices in a background thread."""
        self.fetch_button.configure(state="disabled")
        self.generate_button.configure(state="disabled") # Disable generate during fetch
        self.update_status("Fetching invoices from Tally...")
        thread = threading.Thread(target=self._fetch_invoices_worker, daemon=True)
        thread.start()

    def _fetch_invoices_worker(self):
        """Worker function to fetch invoices."""
        from_date_str = self.from_date_entry.get()
        to_date_str = self.to_date_entry.get()
        # Basic date validation (improve as needed)
        try:
            # Consider validating date logic more robustly if needed
            datetime.strptime(from_date_str, "%d-%m-%Y")
            datetime.strptime(to_date_str, "%d-%m-%Y")
        except ValueError:
            # Schedule GUI updates from the main thread
            self.after(0, self.update_status, "Invalid date format (DD-MM-YYYY).", True)
            self.after(0, messagebox.showerror, "Date Error", "Please enter dates in DD-MM-YYYY format.")
            self.after(0, self.fetch_button.configure, {"state": "normal"})
            return

        try:
            # Fetch data using the connector
            self.pending_invoices = tally_connector.fetch_pending_invoices(from_date_str, to_date_str)
            # Schedule GUI updates from the main thread
            self.after(0, self.populate_tree)
            self.after(0, self.update_status, f"Fetched {len(self.pending_invoices)} pending/failed Sales invoices.")
        except ConnectionError as e:
            self.after(0, self.update_status, f"Tally Connection Error: {e}", True)
            self.after(0, messagebox.showerror, "Tally Error", f"Could not connect or communicate with Tally:\n{e}\nEnsure Tally is running and accessible.")
        except ValueError as e: # Catches errors from parsing Tally response
             self.after(0, self.update_status, f"Processing Error: {e}", True)
             self.after(0, messagebox.showerror, "Data Error", f"Error processing Tally data:\n{e}")
        except Exception as e:
            self.after(0, self.update_status, f"Fetch Error: {e}", True)
            self.after(0, messagebox.showerror, "Error", f"An unexpected error occurred during fetch:\n{e}")
            # Optionally log the full traceback here for debugging
            # import traceback
            # traceback.print_exc()
        finally:
            # Schedule GUI updates from the main thread
            self.after(0, self.fetch_button.configure, {"state": "normal"})
            # Re-enable generate button only if items were selected before fetch? Or enable always?
            self.after(0, self.generate_button.configure, {"state": "normal"})


    def populate_tree(self):
        """Clears and populates the treeview with fetched invoices."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        # Insert new items
        for inv in self.pending_invoices:
            # Truncate long errors for display
            error_msg = inv.get('error') or ""
            display_error = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg

            # Add item with unique IID (using master_id)
            # Ensure values are strings or compatible types for display
            try:
                self.tree.insert("", tk.END, iid=str(inv['master_id']), values=(
                    str(inv.get('master_id', '')),
                    str(inv.get('voucher_no', '')),
                    str(inv.get('date', '')),
                    str(inv.get('party_name', '')),
                    str(inv.get('amount', 'N/A')), # Handle potentially missing amount
                    str(inv.get('status', 'Pending')),
                    display_error
                ))
            except Exception as e:
                print(f"Error adding invoice to tree: {inv.get('voucher_no')} - {e}")
                # Optionally skip this row or show an error marker

    def get_selected_invoice_data(self):
        """Gets the data dictionaries for selected invoices from self.pending_invoices."""
        selected_iids = self.tree.selection() # Returns list of IIDs (master_ids as strings)
        if not selected_iids:
            return None

        selected_invoices_data = []
        found_all = True
        for item_iid in selected_iids:
            # Find the corresponding dictionary in our fetched list (compare as strings)
            invoice_data = next((inv for inv in self.pending_invoices if str(inv.get('master_id')) == item_iid), None)
            if invoice_data:
                selected_invoices_data.append(invoice_data)
            else:
                 messagebox.showwarning("Selection Error", f"Could not find data for selected invoice ID {item_iid}. Please refetch.")
                 found_all = False
                 break # Stop if data mismatch

        return selected_invoices_data if found_all else None

    def generate_irn_thread(self):
        """Starts IRN generation in a background thread for selected invoices."""
        selected_data = self.get_selected_invoice_data()
        if not selected_data:
            messagebox.showinfo("Selection", "Please select one or more 'Pending' or 'Failed' invoices to generate.")
            return

        # Optional: Filter out already generated ones if user selected them by mistake
        invoices_to_process = [inv for inv in selected_data if inv.get('status', 'Pending') != 'Generated']
        if not invoices_to_process:
             messagebox.showinfo("Selection", "All selected invoices seem to be already 'Generated'.")
             return

        num_selected = len(invoices_to_process)

        self.generate_button.configure(state="disabled")
        self.fetch_button.configure(state="disabled") # Disable fetch during generation
        self.update_status(f"Starting E-Invoice generation for {num_selected} invoice(s)...")

        thread = threading.Thread(target=self._generate_irn_worker, args=(invoices_to_process,), daemon=True)
        thread.start()

    def _generate_irn_worker(self, invoices_to_process):
        """Worker function to generate IRNs."""
        generated_count = 0
        failed_count = 0
        total_count = len(invoices_to_process)

        # --- Initial Auth ---
        # Authenticate only once at the beginning if token is not already set/valid
        try:
             if not irn_generator.IRP_AUTH_TOKEN or not irn_generator.SEK: # Check if auth needed
                 self.after(0, self.update_status, "Authenticating with IRP...")
                 if not irn_generator.authenticate_irp():
                     # Auth function already raises ConnectionError on failure
                     # This will be caught by the outer exception handler below
                     pass # Should not reach here if auth fails
                 self.after(0, self.update_status, "IRP Authentication successful.")
        except Exception as auth_e:
             # Schedule GUI updates from the main thread
             self.after(0, self.update_status, f"IRP Auth Error: {auth_e}", True)
             self.after(0, messagebox.showerror, "API Authentication Error", f"Could not authenticate with IRP:\n{auth_e}\nPlease check credentials and network.")
             self.after(0, self.generate_button.configure, {"state": "normal"})
             self.after(0, self.fetch_button.configure, {"state": "normal"})
             return

        # --- Process Each Invoice ---
        for index, inv_data in enumerate(invoices_to_process):
            master_id = inv_data.get('master_id')
            vch_no = inv_data.get('voucher_no', 'N/A')

            if not master_id:
                print(f"Skipping invoice due to missing MasterID: {inv_data}")
                failed_count += 1
                continue # Skip if no ID to update Tally

            # Schedule GUI update for status
            self.after(0, self.update_status, f"Processing {index+1}/{total_count}: VchNo {vch_no}...")
            self.after(0, self.update_tree_item_status, str(master_id), "Processing...", "") # Update GUI

            irn_result = None # To store result from API

            try:
                # 1. Format JSON (CRITICAL STEP - Needs full implementation in irn_generator)
                # This now includes encryption simulation/placeholder
                final_payload_str = irn_generator.format_invoice_json(inv_data)
                if not final_payload_str:
                    # Handle potential errors during JSON creation/encryption if needed
                    raise ValueError("Failed to create/encrypt JSON payload (check data & format_invoice_json).")

                # 2. (Optional but Recommended) Pre-Validation against IRP Schema
                # try:
                #     invoice_dict_for_validation = json.loads(json.loads(final_payload_str)["Data"]) # Double loads if not encrypted
                #     validation_result = validator.validate_invoice_data_for_irn(invoice_dict_for_validation)
                #     if validation_result is not True: # If it returns a list of errors
                #         raise ValueError(f"Pre-validation failed: {'; '.join(validation_result)}")
                # except Exception as val_e:
                #      raise ValueError(f"Pre-validation error: {val_e}")


                # 3. Call IRP API (Generate IRN)
                api_response_text = irn_generator.generate_irn(final_payload_str)

                # 4. Parse (Decrypted) Response
                # Assumes parse_response handles the decrypted text
                irn_result = irn_generator.parse_response(api_response_text) # Needs real decryption in irn_generator

                # 5. Update Tally
                if irn_result and master_id:
                    # Schedule Tally update from the main thread? Or is requests okay in thread?
                    # For simplicity, keeping it here, but consider GUI freezes if Tally is slow.
                    try:
                        update_success, update_msg = tally_connector.update_tally_voucher(master_id, irn_result)
                        if not update_success:
                            # Log Tally update failure but keep API status
                            current_err = irn_result.get('error_msg', '')
                            irn_result['error_msg'] = f"{current_err} | TallyUpd FAILED: {update_msg}".strip()
                            # Count as failure if Tally update fails, even if API succeeded
                            if irn_result['status'] == 'Generated':
                                irn_result['status'] = 'TallyUpdFailed' # Custom status?
                                failed_count += 1
                            else: # API already failed
                                failed_count += 1
                        elif irn_result['status'] == 'Generated':
                             generated_count += 1
                        else: # API returned failure, Tally update likely just saved the failure status
                            failed_count += 1
                    except Exception as tally_e:
                        # Error during the update_tally_voucher call itself
                        print(f"Error calling update_tally_voucher for {vch_no}: {tally_e}")
                        current_err = irn_result.get('error_msg', '')
                        irn_result['error_msg'] = f"{current_err} | TallyUpd EXCEPTION: {tally_e}".strip()
                        irn_result['status'] = 'TallyUpdFailed'
                        failed_count += 1

                else:
                    # Should not happen if parsing is correct & master_id exists
                    raise ValueError("Failed to parse API response or missing MasterID after processing.")

            except Exception as e:
                # Catch errors during JSON formatting, validation, API call, parsing, or Tally update attempt
                error_message = f"Error processing {vch_no}: {e}"
                print(error_message) # Log detailed error to console
                # import traceback # For more detailed debugging
                # traceback.print_exc()
                irn_result = {"status": "Failed", "error_msg": str(e)[:450]} # Store truncated error for Tally UDF
                failed_count += 1
                # Attempt to update Tally with failure status even if error occurred before Tally update step
                try:
                    tally_connector.update_tally_voucher(master_id, irn_result)
                except Exception as tally_update_e:
                    # Log secondary failure, primary error is already in irn_result
                    print(f"Failed to update Tally with error status for {vch_no} after primary error: {tally_update_e}")

            finally:
                 # Schedule Treeview update from the main thread
                 if irn_result and master_id:
                    self.after(0, self.update_tree_item_status, str(master_id), irn_result.get('status', 'Failed'), irn_result.get('error_msg', 'Unknown processing error'))


        # --- Final Status Update (Schedule from main thread) ---
        final_msg = f"Finished. Generated: {generated_count}, Failed/Skipped: {failed_count}."
        self.after(0, self.update_status, final_msg)
        if failed_count > 0:
            self.after(0, messagebox.showwarning, "Generation Complete", f"{final_msg}\nCheck 'Last Error' column for details on failures.")
        else:
             self.after(0, messagebox.showinfo, "Generation Complete", final_msg)

        self.after(0, self.generate_button.configure, {"state": "normal"})
        self.after(0, self.fetch_button.configure, {"state": "normal"})
        # Optional: Auto-refresh the list after generation?
        # self.after(100, self.fetch_invoices_thread) # Add a small delay


    def update_tree_item_status(self, item_iid_str, status, error_message):
        """ Safely updates a specific row in the treeview from the main thread """
        try:
            if self.tree.exists(item_iid_str):
                 # Truncate error for display
                 display_error = (error_message or "")[:100]
                 if len(error_message or "") > 100: display_error += "..."
                 self.tree.set(item_iid_str, column="Status", value=status or "Unknown")
                 self.tree.set(item_iid_str, column="Error", value=display_error)
                 # self.update_idletasks() # Not needed if called via self.after
            else:
                print(f"Warning: Tried to update non-existent tree item {item_iid_str}")
        except Exception as e:
             print(f"Error updating tree item {item_iid_str}: {e}")


    def show_invoice_details(self, event):
        """Shows more details of the selected invoice on double-click."""
        selected_iid = self.tree.focus() # Gets the IID string of the focused item
        if not selected_iid:
            return

        invoice_data = next((inv for inv in self.pending_invoices if str(inv.get('master_id')) == selected_iid), None)

        if invoice_data:
            # Display details in a simple message box or a new window
            # Include more fields if available in inv_data['raw_data']
            details = f"Voucher No: {invoice_data.get('voucher_no', 'N/A')}\n" \
                      f"Date: {invoice_data.get('date', 'N/A')}\n" \
                      f"Party: {invoice_data.get('party_name', 'N/A')}\n" \
                      f"Amount: {invoice_data.get('amount', 'N/A')}\n" \
                      f"Status: {invoice_data.get('status', 'N/A')}\n" \
                      f"Master ID: {invoice_data.get('master_id', 'N/A')}\n\n" \
                      f"Last Error:\n{invoice_data.get('error', 'None')}" # Show full error here
            messagebox.showinfo("Invoice Details", details)
        else:
            messagebox.showwarning("Data Error", "Could not find details for the selected invoice.")

    # def on_tree_select(self, event):
    #     """Enables generate button only if items are selected."""
    #     if self.tree.selection():
    #         self.generate_button.configure(state="normal")
    #     else:
    #         self.generate_button.configure(state="disabled")


    def open_settings(self):
        """Opens the settings dialog window."""
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Settings")
        settings_win.geometry("450x380") # Adjusted height
        settings_win.transient(self) # Keep on top of main window
        settings_win.grab_set() # Modal - block interaction with main window
        settings_win.resizable(False, False)

        # --- Tally Port ---
        tally_frame = ctk.CTkFrame(settings_win)
        tally_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(tally_frame, text="Tally Port:", width=100, anchor="w").pack(side="left", padx=5)
        tally_port_entry = ctk.CTkEntry(tally_frame)
        tally_port_entry.pack(side="left", padx=5, fill="x", expand=True)
        tally_port_entry.insert(0, self.config.get('TALLY', 'Port', fallback='9000'))

        # --- IRP Mode (Sandbox/Production) ---
        irp_frame = ctk.CTkFrame(settings_win)
        irp_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(irp_frame, text="IRP Mode:", width=100, anchor="w").pack(side="left", padx=5)
        irp_mode_options = ["SANDBOX", "PRODUCTION"]
        # Read current mode from config, default to SANDBOX if missing/invalid
        current_mode = self.config.get('IRP_API', 'Mode', fallback='SANDBOX').upper()
        if current_mode not in irp_mode_options: current_mode = 'SANDBOX'
        irp_mode_var = ctk.StringVar(value=current_mode)
        irp_mode_dropdown = ctk.CTkOptionMenu(irp_frame, variable=irp_mode_var, values=irp_mode_options)
        irp_mode_dropdown.pack(side="left", padx=5, fill="x", expand=True)

        # --- User GSTIN (Display Only) ---
        gstin_frame = ctk.CTkFrame(settings_win)
        gstin_frame.pack(pady=10, padx=10, fill="x")
        ctk.CTkLabel(gstin_frame, text="User GSTIN:", width=100, anchor="w").pack(side="left", padx=5)
        user_gstin_val = self.config.get('IRP_API', 'UserGstin', fallback="Not Set (Set in .env)")
        # Mask if needed, e.g., ***********J1ZV
        display_gstin = user_gstin_val
        if len(user_gstin_val) > 4:
             display_gstin = f"{'*'*(len(user_gstin_val)-4)}{user_gstin_val[-4:]}"

        user_gstin_label = ctk.CTkLabel(gstin_frame, text=display_gstin, anchor="w")
        user_gstin_label.pack(side="left", padx=5, fill="x", expand=True)

        # --- API Credentials ---
        cred_frame = ctk.CTkFrame(settings_win)
        cred_frame.pack(pady=(10,0), padx=10, fill="x")
        ctk.CTkLabel(cred_frame, text="API Credentials (Stored in .env / Keyring):").pack(pady=(0,5))

        cred_fields_frame = ctk.CTkFrame(cred_frame) # Inner frame for grid
        cred_fields_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(cred_fields_frame, text="API Username:", width=100, anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        api_user_entry = ctk.CTkEntry(cred_fields_frame)
        api_user_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(cred_fields_frame, text="API Password:", width=100, anchor="w").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        api_pass_entry = ctk.CTkEntry(cred_fields_frame, show="*")
        api_pass_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        cred_fields_frame.grid_columnconfigure(1, weight=1)

        # Load existing credentials using the config manager function
        current_user, _ = config_manager.get_api_credentials() # Checks .env then keyring
        if current_user:
            api_user_entry.insert(0, current_user)
            api_pass_entry.configure(placeholder_text="Enter new password to save to Keyring")
        else:
            api_pass_entry.configure(placeholder_text="Enter username and password to save to Keyring")

        ctk.CTkLabel(cred_frame, text="Note: Settings here save to config.ini.\nCredentials save to OS Keyring (if password entered).\n.env file settings always take precedence if set.",
                     text_color="gray", font=("Segoe UI", 9), justify="left").pack(pady=(0,5), padx=10)

        # --- Save Button ---
        def save_settings():
            """Saves settings to config.ini and credentials to Keyring."""
            # 1. Save non-sensitive settings to config object
            new_tally_port = tally_port_entry.get()
            new_irp_mode = irp_mode_var.get()

            # Basic validation (optional)
            if not new_tally_port.isdigit():
                messagebox.showerror("Invalid Input", "Tally Port must be a number.", parent=settings_win)
                return

            self.config.set('TALLY', 'Port', new_tally_port)
            self.config.set('IRP_API', 'Mode', new_irp_mode)

            # 2. Save the config object to config.ini
            try:
                config_manager.save_config(self.config)
                print("Settings (Port, Mode) saved to config.ini")
            except Exception as cfg_e:
                 messagebox.showerror("Save Error", f"Failed to save settings to config.ini:\n{cfg_e}", parent=settings_win)
                 return # Don't proceed if config save failed

            # 3. Handle Credentials (Save ONLY to Keyring)
            new_user = api_user_entry.get().strip()
            new_pass = api_pass_entry.get() # Don't strip password

            creds_saved_to_keyring = False
            # Only attempt save if password field is not empty
            if new_pass:
                 if not new_user:
                      messagebox.showerror("Input Error", "API Username cannot be empty when saving credentials.", parent=settings_win)
                      return # Stop save

                 print("Attempting to save credentials to Keyring...")
                 if config_manager.set_api_credentials(new_user, new_pass):
                     creds_saved_to_keyring = True
                     # Reset auth tokens in irn_generator as credentials changed
                     irn_generator.IRP_AUTH_TOKEN = None
                     irn_generator.SEK = None
                     print("Credentials saved to Keyring. Auth tokens reset.")
                 else:
                     # set_api_credentials prints errors, show dialog too
                     messagebox.showerror("Credentials Error", "Failed to save credentials to OS Keyring.\nCheck console for details.", parent=settings_win)
                     # Keep settings window open on keyring failure
                     return
            elif new_user and new_user != current_user:
                 # Username changed, but no password entered - warn user, don't save creds
                  messagebox.showwarning("Credentials Info", "Username changed, but no password entered.\nCredentials in Keyring remain unchanged.", parent=settings_win)


            # 4. Confirmation and Cleanup
            if creds_saved_to_keyring:
                messagebox.showinfo("Settings Saved", "Settings saved to config.ini.\nCredentials saved to OS Keyring.", parent=settings_win)
            else:
                 messagebox.showinfo("Settings Saved", "Settings saved to config.ini.\n(Credentials not changed in Keyring).", parent=settings_win)


            settings_win.destroy()

            # 5. Update runtime variables
            # Update Tally URL in the connector module
            tally_connector.TALLY_URL = f"http://localhost:{new_tally_port}"
            print(f"Updated Tally URL in connector: {tally_connector.TALLY_URL}")
            # Reload config in main app instance might be needed if other parts rely on it directly
            # self.config = config_manager.load_config() # Re-load to reflect changes immediately

            self.update_status("Settings saved. Please restart Tally connection check if needed.")
            # Optionally trigger check_tally_on_start again if port changed?


        save_button = ctk.CTkButton(settings_win, text="Save Settings", command=save_settings)
        save_button.pack(pady=20)

# --- Run the App ---
if __name__ == "__main__":
    # Ensure environment variables are loaded early if using .env
    # config_manager handles this internally now when load_config is called.

    app = TallyEInvoiceApp()
    app.mainloop()