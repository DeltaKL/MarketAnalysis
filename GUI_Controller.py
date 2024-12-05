from tkinter.scrolledtext import ScrolledText

from degiro_connector.trading.models.credentials import Credentials
import logging
import os
from dotenv import load_dotenv, set_key, unset_key
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import threading
import json
from JSON_Grabber import DegiroConnector
from Generator import DataProcessor, PDFGenerator, APIHandler
import traceback
import keyring
from datetime import datetime
import queue

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('financial_report_app.log')])

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # This will show all log messages

# # Add a StreamHandler for console output
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.DEBUG)
# console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# logger.addHandler(console_handler)

load_dotenv()

degiro_username = os.getenv('DEGIRO_USERNAME')
degiro_password = os.getenv('DEGIRO_PASSWORD')
perplexity_api_key = os.getenv('PERPLEXITY_API_KEY')

os.environ['TCL_LIBRARY'] = r'C:\Users\daanv\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'
os.environ['TK_LIBRARY'] = r'C:\Users\daanv\AppData\Local\Programs\Python\Python313\tcl\tk8.6'


class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
        self.formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    def emit(self, record):
        self.log_queue.put(record)

    def format(self, record):
        return self.formatter.format(record)


class ConsoleUi:
    def __init__(self, frame, log_queue):
        self.frame = frame
        self.log_queue = log_queue

        self.scrolled_text = ScrolledText(frame, state='disabled', height=4)
        self.scrolled_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        self.scrolled_text.configure(font='TkFixedFont')
        self.scrolled_text.tag_config('DEBUG', foreground='gray')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=1)

        self.frame.after(100, self.poll_log_queue)

    def display(self, record):
        msg = self.format(record)
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        self.scrolled_text.yview(tk.END)

    def poll_log_queue(self):
        while True:
            try:
                record = self.log_queue.get(block=False)
                self.display(record)
            except queue.Empty:
                break
        self.frame.after(100, self.poll_log_queue)

    def format(self, record):
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        return formatter.format(record)

# class ConsoleUi:
#     def __init__(self, frame):
#         self.frame = frame
#         self.scrolled_text = ScrolledText(frame, state='disabled', height=12)
#         self.scrolled_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
#         # self.scrolled_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
#         self.scrolled_text.configure(font='TkFixedFont')
#         self.scrolled_text.tag_config('INFO', foreground='black')
#         self.scrolled_text.tag_config('DEBUG', foreground='gray')
#         self.scrolled_text.tag_config('WARNING', foreground='orange')
#         self.scrolled_text.tag_config('ERROR', foreground='red')
#         self.scrolled_text.tag_config('CRITICAL', foreground='red', underline=1)
#
#     def display(self, record):
#         msg = record
#         self.scrolled_text.configure(state='normal')
#         self.scrolled_text.insert(tk.END, msg + '\n', record.split(':')[0])
#         self.scrolled_text.configure(state='disabled')
#         self.scrolled_text.yview(tk.END)

class GUIController:
    def __init__(self, master):
        self.use_perplexity = None
        self.master = master
        self.master.title("Company Financial Report Generator")
        self.master.geometry("600x500")
        self.degiro_connector = None
        self.selected_companies = []
        self.use_perplexity_api = tk.BooleanVar(value=True)
        self.advanced_settings_window = None

        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        self.setup_ui(main_frame)
        self.load_saved_credentials()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        # self.console = ConsoleUi(self.console_frame)
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(0, weight=1)
        self.log_queue = setup_logging()
        self.console = ConsoleUi(self.console_frame, self.log_queue)

        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        logger.addHandler(self.queue_handler)

        self.frame_process_queue()
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        logger.addHandler(self.queue_handler)

    def frame_process_queue(self):
        try:
            while True:
                record = self.log_queue.get_nowait()
                formatted_message = self.queue_handler.format(record)
                self.console_text.config(state=tk.NORMAL)
                self.console_text.insert(tk.END, formatted_message + '\n')
                self.console_text.config(state=tk.DISABLED)
                self.console_text.see(tk.END)
        except queue.Empty:
            self.master.after(100, self.frame_process_queue)

    def setup_ui(self, main_frame):
        # Login Frame (Top Left)
        login_frame = ttk.LabelFrame(main_frame, text="Degiro Login")
        login_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=5, pady=5)

        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, sticky=tk.W)
        self.username_entry = ttk.Entry(login_frame)
        self.username_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky=tk.W)
        self.password_entry = ttk.Entry(login_frame, show="*")
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Button(login_frame, text="Connect", command=self.connect_to_degiro).grid(row=2, column=0, sticky=tk.W)
        self.logout_button = ttk.Button(login_frame, text="Logout", command=self.logout_from_degiro, state=tk.DISABLED)
        self.logout_button.grid(row=2, column=1, sticky=tk.E)

        ttk.Button(login_frame, text="Save Credentials", command=self.save_credentials).grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self.connection_status = ttk.Label(login_frame, text="Not Connected", foreground="red")
        self.connection_status.grid(row=4, column=0, columnspan=2, sticky=tk.W)
        self.use_perplexity_checkbox = ttk.Checkbutton(login_frame, text="Use Perplexity API", variable=self.use_perplexity_api)
        self.use_perplexity_checkbox.grid(row=6, column=0, columnspan=3, sticky=tk.W)
        ttk.Button(login_frame, text="Settings", command=self.show_advanced_settings).grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # Core Frame (Center)
        core_frame = ttk.Frame(main_frame)
        core_frame.grid(row=0, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        ttk.Label(core_frame, text="Company Search").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(core_frame)
        self.search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.search_entry.bind('<Return>', lambda event: self.search_companies())
        ttk.Button(core_frame, text="Search", command=self.search_companies).grid(row=0, column=2)

        self.search_results = tk.Listbox(core_frame, height=10)
        self.search_results.grid(row=1, column=0, columnspan=3, sticky=(tk.W + tk.E))
        self.search_results.bind('<Double-1>', self.on_double_click)

        ttk.Button(core_frame, text="Add Selected", command=self.add_company).grid(row=2, column=2)

        ttk.Label(core_frame, text="Selected Companies").grid(row=3, column=0, columnspan=3)

        self.selected_companies_list = tk.Listbox(core_frame, height=10)
        self.selected_companies_list.grid(row=4, columnspan=3, sticky=(tk.W, tk.E))

        ttk.Button(core_frame, text="Remove Selected", command=self.remove_company).grid(row=5, columnspan=True)

        ttk.Button(core_frame, text="Generate Reports", command=self.generate_reports).grid(columnspan=True, pady=(10))

        # Console Frame (Bottom)
        self.console_frame = ttk.LabelFrame(main_frame, text="Console")
        self.console_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.console_text = scrolledtext.ScrolledText(self.console_frame, height=3, wrap=tk.WORD)
        self.console_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.console_text.config(state=tk.DISABLED)
        ttk.Button(self.console_frame, text="Full Log", command=self.show_full_console).grid(row=0, column=1,sticky=(tk.E))

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=10)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)  # Console row

        login_frame.columnconfigure(1, weight=1)
        core_frame.columnconfigure(1, weight=1)

    def on_closing(self):
        if self.degiro_connector:
            try:
                self.degiro_connector.disconnect()
            except:
                pass
        self.master.destroy()

    def show_advanced_settings(self):
        if self.advanced_settings_window is not None:
            self.advanced_settings_window.lift()
            return

        self.advanced_settings_window = tk.Toplevel(self.master)
        self.advanced_settings_window.title("Advanced Settings")
        self.advanced_settings_window.geometry("600x400")
        self.advanced_settings_window.protocol("WM_DELETE_WINDOW", self.close_advanced_settings)

        notebook = ttk.Notebook(self.advanced_settings_window)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # API settings tab
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text='Perplexity API Settings')

        ttk.Label(api_frame, text="Perplexity API Key:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.perplexity_api_key_entry = ttk.Entry(api_frame, show="")
        self.perplexity_api_key_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        self.perplexity_api_key_entry.insert(0, keyring.get_password("FinancialReportApp", "perplexity_api_key") or "")

        ttk.Label(api_frame, text="API Prompt:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        prompt_text = scrolledtext.ScrolledText(api_frame, height=10, width=70, wrap=tk.WORD)
        prompt_text.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        prompt_text.insert(tk.END, APIHandler.get_default_prompt())

        ttk.Label(api_frame, text="Max Tokens:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        max_tokens_entry = ttk.Entry(api_frame)
        max_tokens_entry.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        max_tokens_entry.insert(0, str(APIHandler.get_max_tokens()))

        # DeGiro settings tab
        degiro_frame = ttk.Frame(notebook)
        notebook.add(degiro_frame, text='DeGiro')

        ttk.Label(degiro_frame, text="DeGiro Username:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.degiro_username_entry = ttk.Entry(degiro_frame)
        self.degiro_username_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        self.degiro_username_entry.insert(0, keyring.get_password("FinancialReportApp", "degiro_username") or "")

        ttk.Button(self.advanced_settings_window, text="Delete Saved Credentials", command=self.delete_saved_credentials).pack(pady=10)
        ttk.Button(self.advanced_settings_window, text="Save", command=lambda: self.save_settings(prompt_text, max_tokens_entry)).pack(pady=10)

    def save_settings(self, prompt_text, max_tokens_entry):
        APIHandler.set_default_prompt(prompt_text.get("1.0", tk.END).strip())
        APIHandler.set_max_tokens(int(max_tokens_entry.get()))
        keyring.set_password("FinancialReportApp", "perplexity_api_key", self.perplexity_api_key_entry.get())
        self.close_advanced_settings()
        messagebox.showinfo("Success", "Settings saved successfully")

    def save_credentials(self):
        env_file_path = ".env"
        set_key(dotenv_path=(env_file_path), key_to_set=("DEGIRO_USERNAME"), value_to_set=self.username_entry.get())
        set_key(dotenv_path=(env_file_path), key_to_set=("DEGIRO_PASSWORD"), value_to_set=self.password_entry.get())
        messagebox.showinfo("Success", "Credentials saved successfully")

    def load_saved_credentials(self):
        load_dotenv()
        self.username_entry.insert(0, (os.getenv("DEGIRO_USERNAME")) or "")
        self.password_entry.insert(0, (os.getenv("DEGIRO_PASSWORD")) or "")

    def delete_saved_credentials(self):
        env_file_path = ".env"
        unset_key(dotenv_path=env_file_path, key_to_unset="DEGIRO_USERNAME")
        unset_key(dotenv_path=env_file_path, key_to_unset="DEGIRO_PASSWORD")
        unset_key(dotenv_path=env_file_path, key_to_unset="PERPLEXITY_API_KEY")
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.perplexity_api_key_entry.delete(0, tk.END)
        messagebox.showinfo("Success", "Saved credentials deleted")

    def show_full_console(self):
        console_window = tk.Toplevel(self.master)
        console_window.title("Full Console Log")
        console_window.geometry("600x400")

        full_console_text = scrolledtext.ScrolledText(console_window, wrap=tk.WORD)
        full_console_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        full_console_text.insert(tk.END, self.console_text.get("1.0", tk.END))
        full_console_text.config(state='disabled')

        console_window.grid_columnconfigure(0, weight=1)
        console_window.grid_rowconfigure(0, weight=1)

    def show_advanced_settings(self):
        if self.advanced_settings_window is not None:
            self.advanced_settings_window.lift()
            return

        self.advanced_settings_window = tk.Toplevel(self.master)
        self.advanced_settings_window.title("Advanced Settings")
        self.advanced_settings_window.geometry("600x400")
        self.advanced_settings_window.protocol("WM_DELETE_WINDOW", self.close_advanced_settings)

        notebook = ttk.Notebook(self.advanced_settings_window)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        # API settings tab
        api_frame = ttk.Frame(notebook)
        notebook.add(api_frame, text='Perplexity API Settings')

        ttk.Label(api_frame, text="Perplexity API Key:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.perplexity_api_key_entry = ttk.Entry(api_frame, show="")
        self.perplexity_api_key_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        self.perplexity_api_key_entry.insert(0, keyring.get_password("FinancialReportApp", "perplexity_api_key") or "")

        ttk.Label(api_frame, text="API Prompt:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        prompt_text = scrolledtext.ScrolledText(api_frame, height=10, width=70, wrap=tk.WORD)
        prompt_text.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        prompt_text.insert(tk.END, APIHandler.get_default_prompt())

        ttk.Label(api_frame, text="Max Tokens:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        max_tokens_entry = ttk.Entry(api_frame)
        max_tokens_entry.grid(row=3, column=1, sticky='w', padx=5, pady=5)
        max_tokens_entry.insert(0, str(APIHandler.get_max_tokens()))

        # DeGiro settings tab
        degiro_frame = ttk.Frame(notebook)
        notebook.add(degiro_frame, text='DeGiro')

        ttk.Label(degiro_frame, text="DeGiro Username:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.degiro_username_entry = ttk.Entry(degiro_frame)
        self.degiro_username_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        self.degiro_username_entry.insert(0, keyring.get_password("FinancialReportApp", "degiro_username") or "")

        ttk.Button(self.advanced_settings_window, text="Delete Saved Credentials",
                   command=self.delete_saved_credentials).pack(pady=10)
        ttk.Button(self.advanced_settings_window, text="Save",
                   command=lambda: self.save_settings(prompt_text, max_tokens_entry)).pack(pady=10)

    def close_advanced_settings(self):
        self.advanced_settings_window.destroy()
        self.advanced_settings_window = None

    def validate_positive_integer(self, value):
        if value == "":
            return True
        try:
            int_value = int(value)
            return int_value > 0
        except ValueError:
            return False

    def on_double_click(self, event):
        self.add_company()

    def connect_to_degiro(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        logger.info(f"Attempting to connect with username: {username}")

        # Use the credentials from the GUI fields
        if username and password:
            # Prompt user for 2FA code
            two_factor_code = simpledialog.askstring("2FA Code", "Enter your 6-digit 2FA code:", parent=self.master)
            if not two_factor_code:
                logger.error("Error", "2FA code is required")
                return

            self.degiro_connector = DegiroConnector()
            if self.degiro_connector.connect(username, password, two_factor_code):
                # messagebox.showinfo("Success", "Connected to Degiro successfully")
                logger.info("Connected to Degiro successfully")
                self.connection_status.config(text="Connected", foreground="green")
                self.logout_button.config(state=tk.NORMAL)
            else:
                # messagebox.showerror("Error", "Failed to connect to Degiro")
                self.connection_status.config(text="Not Connected", foreground="red")
                logger.error("Failed to connect to Degiro")
                self.logout_button.config(state=tk.DISABLED)
        else:
            # messagebox.showerror("Error", "Username and password are required")
            logger.error("Error", "Username and password are required")

    def logout_from_degiro(self):
        if self.degiro_connector:
            self.degiro_connector.disconnect()
            self.degiro_connector = None
            self.connection_status.config(text="Not Connected", foreground="red")
            self.logout_button.config(state=tk.DISABLED)
            logger.info("Success", "Logged out from Degiro successfully")
        else:
            logger.info("Info", "Not connected to Degiro")

    def search_companies(self):
        if not self.degiro_connector:
            messagebox.showerror("Error", "Please connect to Degiro first")
            return

        query = self.search_entry.get()
        results = self.degiro_connector.search_companies(query)
        self.search_results.delete(0, tk.END)

        if results:
            for company in results:
                self.search_results.insert(tk.END, f"{company['name']} ({company['isin']})")
        else:
            messagebox.showinfo("No Results", "No companies found for the given search query.")

    def add_company(self):
        selection = self.search_results.curselection()
        if selection:
            company = self.search_results.get(selection[0])
            if company not in self.selected_companies:
                self.selected_companies.append(company)
                self.selected_companies_list.insert(tk.END, company)

    def remove_company(self):
        selection = self.selected_companies_list.curselection()
        if selection:
            index = selection[0]
            self.selected_companies.pop(index)
            self.selected_companies_list.delete(index)

    def generate_reports(self):
        if not self.selected_companies:
            messagebox.showerror("Error", "Please select at least one company")
            return

        if self.use_perplexity_api.get() and not self.is_perplexity_api_key_valid():
            logger.error("Perplexity API key is missing or invalid")
            messagebox.showerror("Error", "Perplexity API key is missing or invalid")
            return

        threading.Thread(target=self._generate_reports_thread, daemon=True).start()

    def _generate_reports_thread(self):
        try:
            all_company_data = []

            # Retrieve the API key from the keyring
            api_key = os.getenv('PERPLEXITY_API_KEY')
            for index, company in enumerate(self.selected_companies):
                isin = company.split('(')[1].split(')')[0]  # Extract ISIN from the company string
                data = self.degiro_connector.fetch_data([isin])  # Fetch data for the selected ISIN

                data_processor = DataProcessor(data)  # Initialize DataProcessor with fetched data
                data_processor.process_data()  # Process the financial data

                company_name = data_processor.processed_data['company_overview']['legal_name']  # Get company name

                company_data = {
                    "company_name": company_name,
                    "isin": isin,
                    "financial_data": data_processor.processed_data
                }

                if self.use_perplexity_api.get() and api_key:  # Check if using Perplexity API and if API key exists
                    api_handler = APIHandler()  # Initialize APIHandler with the retrieved API key

                    company_data["ai_insights"] = {
                        'swot_analysis': api_handler.get_swot_analysis(company_name),
                        'ai_insights': api_handler.get_ai_insights(company_name)
                    }

                all_company_data.append(company_data)  # Append processed company data to the list

                pdf_generator = PDFGenerator(data_processor.processed_data, company_data.get("ai_insights", {}),
                                             company_name)
                pdf_generator.generate_pdf()  # Generate PDF report for the current company

                self.master.after(0, lambda idx=index: self.grey_out_company(idx))  # Grey out processed company in UI

            # Create compiled JSON file
            with open("compiled_company_data.json", "w") as json_file:
                json.dump(all_company_data, json_file, indent=2)

            self.master.after(0, lambda: messagebox.showinfo("Success",
                                                             "Reports and compiled JSON generated successfully"))

        except Exception as e:
            error_message = f"Failed to generate reports: {str(e)}\n{traceback.format_exc()}"
            print(error_message)
            self.master.after(0, lambda: messagebox.showerror("Error", error_message))

    def grey_out_company(self, index):
        self.selected_companies_list.itemconfig(index, {'bg': 'light gray', 'fg': 'gray'})

    def compile_json_data(self, company_data_list):
        compiled_data = {
            "companies": company_data_list,
            "generated_at": datetime.now().isoformat()
        }
        return compiled_data

    def is_perplexity_api_key_valid(self):
        api_key = os.getenv('PERPLEXITY_API_KEY') or keyring.get_password("FinancialReportApp", "perplexity_api_key")
        return api_key is not None and len(api_key) > 0

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels of logs

    # File handler for logging to a file
    file_handler = logging.FileHandler('financial_report_app.log')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Return a queue handler for GUI logging
    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(queue_handler)
    return log_queue


def main():
    root = tk.Tk()
    app = GUIController(root)
    try:
        root.mainloop()
    finally:
        if app.degiro_connector:
            app.degiro_connector.disconnect()

if __name__ == "__main__":
    main()


