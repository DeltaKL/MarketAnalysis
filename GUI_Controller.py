import tkinter
from tkinter.scrolledtext import ScrolledText
from CompanyComparator import CompanyComparator

from degiro_connector.trading.models.credentials import Credentials
import logging
import os
from dotenv import load_dotenv, set_key, unset_key
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog, StringVar
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


class ToolTip:
    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip = None
        self.schedule_id = None
        self.widget.bind("<Enter>", self.schedule_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def schedule_tooltip(self, event):
        self.schedule_id = self.widget.after(self.delay, lambda: self.show_tooltip(event))

    def show_tooltip(self, event):
        # Get mouse position instead of using bbox
        x = event.widget.winfo_rootx() + event.x + 25
        y = event.widget.winfo_rooty() + event.y + 25

        self.tooltip = tk.Toplevel()
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, background="lightyellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if self.schedule_id:
            self.widget.after_cancel(self.schedule_id)
            self.schedule_id = None
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class ETFDesigner:  
    def __init__(self, master, degiro_connector):
        self.window = tk.Toplevel(master)
        self.window.title("Custom ETF Designer")
        self.window.geometry("800x600")
        self.degiro_connector = degiro_connector
        self.etf_holdings = {}  # {company_name: percentage}
        self.setup_ui()

    def setup_ui(self):
        # Left Frame for ETF Details
        left_frame = ttk.LabelFrame(self.window, text="ETF Details", padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ttk.Label(left_frame, text="ETF Name:").grid(row=0, column=0, sticky="w")
        self.etf_name_entry = ttk.Entry(left_frame, width=30)
        self.etf_name_entry.grid(row=0, column=1, sticky="we", pady=5)

        ttk.Label(left_frame, text="Description:").grid(row=1, column=0, sticky="w")
        self.description_text = tk.Text(left_frame, height=4, width=30)
        self.description_text.grid(row=1, column=1, sticky="we", pady=5)

        # Right Frame for Holdings
        right_frame = ttk.LabelFrame(self.window, text="Holdings", padding="10")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Company Search
        ttk.Label(right_frame, text="Search Company:").grid(row=0, column=0, sticky="w")
        self.search_entry = ttk.Entry(right_frame, width=30)
        self.search_entry.grid(row=0, column=1, sticky="we", pady=5)
        ttk.Button(right_frame, text="Search", command=self.search_companies).grid(row=0, column=2, padx=5)

        # Search Results
        self.results_list = tk.Listbox(right_frame, height=10)
        self.results_list.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=5)
        self.results_list.bind('<Double-Button-1>', self.add_to_holdings)

        # Holdings List with Percentages
        holdings_frame = ttk.Frame(right_frame)
        holdings_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=10)

        self.holdings_tree = ttk.Treeview(holdings_frame, columns=("Percentage"), show="headings")
        self.holdings_tree.heading("Percentage", text="Allocation %")
        self.holdings_tree.grid(row=0, column=0, sticky="nsew")

        # Buttons Frame
        buttons_frame = ttk.Frame(self.window)
        buttons_frame.grid(row=1, column=0, columnspan=2, pady=10)

        ttk.Button(buttons_frame, text="Save ETF", command=self.save_etf).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Load ETF", command=self.load_etf).pack(side="left", padx=5)
        ttk.Button(buttons_frame, text="Generate Report", command=self.generate_etf_report).pack(side="left", padx=5)

        # Configure grid weights
        self.window.grid_columnconfigure(0, weight=1)
        self.window.grid_columnconfigure(1, weight=1)
        right_frame.grid_columnconfigure(1, weight=1)

    def search_companies(self):
        query = self.search_entry.get()
        if query:
            results = self.degiro_connector.search_companies(query)
            self.results_list.delete(0, tk.END)
            for company in results:
                self.results_list.insert(tk.END, f"{company['name']} ({company['isin']})")

    def add_to_holdings(self, event):
        selection = self.results_list.get(self.results_list.curselection())
        percentage = simpledialog.askfloat("Allocation",
                                           "Enter allocation percentage (0-100):",
                                           minvalue=0, maxvalue=100)
        if percentage is not None:
            self.etf_holdings[selection] = percentage
            self.update_holdings_display()

    def update_holdings_display(self):
        self.holdings_tree.delete(*self.holdings_tree.get_children())
        total = sum(self.etf_holdings.values())
        for company, percentage in self.etf_holdings.items():
            self.holdings_tree.insert("", "end", text=company, values=(f"{percentage:.2f}%",))

        if abs(total - 100) > 0.01:
            messagebox.showwarning("Warning", f"Total allocation ({total:.2f}%) does not equal 100%")

    def save_etf(self):
        if not self.etf_name_entry.get():
            messagebox.showerror("Error", "Please enter an ETF name")
            return

        etf_data = {
            "name": self.etf_name_entry.get(),
            "description": self.description_text.get("1.0", tk.END).strip(),
            "holdings": self.etf_holdings,
            "created_date": datetime.now().isoformat()
        }

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"{self.etf_name_entry.get()}_ETF.json"
        )

        if filename:
            with open(filename, 'w') as f:
                json.dump(etf_data, f, indent=4)


class GUIController:
    def __init__(self, master):
        self.use_perplexity = True
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

        # Load API settings
        api_handler = APIHandler()
        api_handler.load_settings()

        self.company_comparator = CompanyComparator()

    def show_etf_designer(self):
        if not self.degiro_connector:
            messagebox.showerror("Error", "Please connect to Degiro first")
            return

        ETFDesigner(self.master, self.degiro_connector)

    def compare_selected_companies(self):
        try:
            if not self.selected_companies:
                messagebox.showerror("Error", "Please select at least two companies for comparison")
                return

            # Fetch data for all selected companies
            companies_data = []
            for company in self.selected_companies:
                company_name = company.split('(')[0].strip()
                isin = company.split('(')[1].split(')')[0]

                data = self.degiro_connector.fetch_data([isin])
                data_processor = DataProcessor(data)
                data_processor.process_data()

                companies_data.append({
                    'company_name': company_name,
                    'isin': isin,
                    'financial_data': data_processor.processed_data
                })

            # Save compiled data
            with open('compiled_company_data.json', 'w') as f:
                json.dump(companies_data, f, indent=4)

            # Generate comparison report through CompanyComparator
            comparator = CompanyComparator()
            success = comparator.generate_comparison_report(companies_data)

            if success:
                messagebox.showinfo("Success", "Comparison report generated successfully")
            else:
                raise Exception("Failed to generate comparison report")

        except Exception as e:
            error_message = f"Failed to generate comparison report: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)
            messagebox.showerror("Error", error_message)

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

    def dropdown_value_changed(self):
        print("changed")

    def setup_ui(self, main_frame):
        # Login Frame (Top Left)
        login_frame = ttk.LabelFrame(main_frame, text="Degiro Login")
        login_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=5, pady=5)

        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, sticky=tk.W)
        self.username_entry = ttk.Entry(login_frame)
        self.username_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        ToolTip(self.username_entry, "Enter your Degiro account username")

        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky=tk.W)
        self.password_entry = ttk.Entry(login_frame, show="*")
        self.password_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))
        ToolTip(self.password_entry, "Enter your Degiro account password")

        connect_button = ttk.Button(login_frame, text="Connect", command=self.connect_to_degiro)
        connect_button.grid(row=2, column=0, sticky=tk.W)
        ToolTip(connect_button, "Connect to Degiro using your credentials")

        self.logout_button = ttk.Button(login_frame, text="Logout", command=self.logout_from_degiro, state=tk.DISABLED)
        self.logout_button.grid(row=2, column=1, sticky=tk.E)
        ToolTip(self.logout_button, "Disconnect from Degiro")

        save_cred_button = ttk.Button(login_frame, text="Save Credentials", command=self.save_credentials)
        save_cred_button.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ToolTip(save_cred_button, "Save your credentials for future use")

        self.connection_status = ttk.Label(login_frame, text="Not Connected", foreground="red")
        self.connection_status.grid(row=4, column=0, columnspan=2, sticky=tk.W)


        # Settings frame (centre left)
        quick_settings_frame = ttk.LabelFrame(main_frame, text="Quick Settings")
        quick_settings_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=0)

        #Perplexity Y/N?
        self.use_perplexity_checkbox = ttk.Checkbutton(quick_settings_frame, text="Use Perplexity API",
                                                       variable=self.use_perplexity_api)
        self.use_perplexity_checkbox.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        ToolTip(self.use_perplexity_checkbox, "Enable AI analysis in individually generated reports")

        #Dropdown (see documentation on how to implement dropdown menu
        # Create stringvar & set default
        self.selected_model_var = tk.StringVar()
        self.selected_model_var.set("sonar-pro")  # Set default value

        # Create the OptionMenu with proper parameters
        ttk.Label(quick_settings_frame, text="Select Model:").grid(row=2, column=0, columnspan=2, sticky=tk.W)
        self.selected_model = ttk.OptionMenu(
            quick_settings_frame,  # parent widget
            self.selected_model_var,  # variable to store selection
            "sonar-pro",  # default value
            "sonar-pro", "sonar", "llama-3.1-sonar-small-128k-online", "llama-3.1-sonar-large-128k-online",
            "llama-3.1-sonar-huge-128k-online"
        )
        self.selected_model.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E))
        # Add trace to monitor changes doesnt work lol
        # self.selected_model_var.trace_add("write", self.selected_model_var())

        #advanced settings button
        settings_button = ttk.Button(quick_settings_frame, text="Advanced Settings", command=self.show_advanced_settings)
        settings_button.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        ToolTip(settings_button, "Configure API settings and prompts")


        # Core Frame (Center)
        core_frame = ttk.Frame(main_frame)
        core_frame.grid(row=0, column=1, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        ttk.Label(core_frame, text="Company Search").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(core_frame)
        self.search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.search_entry.bind('<Return>', lambda event: self.search_companies())
        ToolTip(self.search_entry, "Enter company name to search")

        search_button = ttk.Button(core_frame, text="Search", command=self.search_companies)
        search_button.grid(row=0, column=2)
        ToolTip(search_button, "Search for companies matching the entered text")

        # Search results frame
        search_frame = ttk.Frame(core_frame)
        search_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.search_results = tk.Listbox(search_frame, height=20)
        self.search_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ToolTip(self.search_results, "Double-click a company to add it to your selection")

        search_scrollbar = ttk.Scrollbar(search_frame, orient=tk.VERTICAL, command=self.search_results.yview)
        search_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_results.config(yscrollcommand=search_scrollbar.set)
        self.search_results.bind('<Double-1>', self.on_double_click)


        add_button = ttk.Button(core_frame, text="Add Selected", command=self.add_company)
        add_button.grid(row=2, column=2)
        ToolTip(add_button, "Add selected company to your report list")

        ttk.Label(core_frame, text="Selected Companies").grid(row=3, column=0, columnspan=3, sticky=tk.W)

        # Selected companies frame with delete buttons
        selected_frame = ttk.Frame(core_frame)
        selected_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        list_container = ttk.Frame(selected_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.selected_companies_list = tk.Listbox(list_container, height=10)
        self.selected_companies_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ToolTip(self.selected_companies_list, "Press Delete to remove a company from the list")

        self.delete_buttons_canvas = tk.Canvas(list_container, width=20)
        self.delete_buttons_canvas.pack(side=tk.RIGHT, fill=tk.Y)

        selected_scrollbar = ttk.Scrollbar(selected_frame, orient=tk.VERTICAL,
                                           command=self.selected_companies_list.yview)
        selected_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.selected_companies_list.config(yscrollcommand=selected_scrollbar.set)

        self.selected_companies_list.bind('<Delete>', lambda e: self.remove_company())
        self.selected_companies_list.bind('<<ListboxSelect>>', self.update_delete_buttons)

        # Button frame at the bottom
        self.button_frame = ttk.Frame(core_frame)
        self.button_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        generate_button = ttk.Button(self.button_frame, text="Generate individual Reports",
                                     command=self.generate_reports)
        generate_button.pack(side=tk.LEFT)
        ToolTip(generate_button, "Generate detailed reports for all selected companies")

        compare_button = ttk.Button(self.button_frame, text="Compare Companies",
                                    command=self.compare_selected_companies)
        compare_button.pack(side=tk.LEFT, padx=5)
        ToolTip(compare_button, "Compare financial metrics between selected companies")

        # Configure grid weights
        core_frame.columnconfigure(1, weight=1)
        core_frame.rowconfigure(1, weight=1)
        core_frame.rowconfigure(4, weight=1)

        # Console Frame (Bottom)
        self.console_frame = ttk.LabelFrame(main_frame, text="Console")
        self.console_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.console_text = scrolledtext.ScrolledText(self.console_frame, height=3, wrap=tk.WORD)
        self.console_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.console_text.config(state=tk.DISABLED)
        ToolTip(self.console_text, "View application status and recent activity")

        full_log_button = ttk.Button(self.console_frame, text="Show full Log", command=self.show_full_console)
        full_log_button.grid(row=0, column=1, sticky=(tk.E))
        ToolTip(full_log_button, "View complete application log history")

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.rowconfigure(0, weight=10)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=0)

        login_frame.columnconfigure(1, weight=1)
        login_frame.rowconfigure(1, weight=2)
        quick_settings_frame.columnconfigure(1, weight=1)
        quick_settings_frame.rowconfigure(1, weight=1)
        core_frame.columnconfigure(1, weight=1)

        # etf_button = ttk.Button(main_frame, text="ETF Designer", command=self.show_etf_designer)
        # etf_button.grid(row=1, column=1, sticky=(tk.E), padx=5, pady=5)
        # ToolTip(etf_button, "Design and manage custom ETFs")


    def add_company(self):
        selection = self.search_results.curselection()
        if selection:
            company = self.search_results.get(selection[0])
            if company not in self.selected_companies:
                self.selected_companies.append(company)
                self.selected_companies_list.insert(tk.END, company)
                self.update_delete_buttons()

    def update_delete_buttons(self, event=None):
        self.delete_buttons_canvas.delete('all')
        for i in range(self.selected_companies_list.size()):
            y = i * self.selected_companies_list.bbox(i)[3]
            x = 5
            # Create red X button
            self.delete_buttons_canvas.create_text(
                x, y + 10, text='×', fill='red',
                font=('TkDefaultFont', 12, 'bold'),
                tags=f'delete_{i}'
            )
            # Bind click event
            self.delete_buttons_canvas.tag_bind(
                f'delete_{i}', '<Button-1>',
                lambda e, idx=i: self.remove_company_at_index(idx)
            )

    def remove_company_at_index(self, index):
        self.selected_companies.pop(index)
        self.selected_companies_list.delete(index)
        self.update_delete_buttons()

    def remove_company(self):
        selection = self.selected_companies_list.curselection()
        if selection:
            index = selection[0]
            self.remove_company_at_index(index)


    def on_closing(self):
        if self.degiro_connector:
            try:
                self.degiro_connector.disconnect()
            except:
                pass
        self.master.destroy()

    def save_settings(self, individual_prompt_text , comparison_prompt_text, max_tokens_entry, model_temperature_entry):
        api_handler = APIHandler()
        api_handler.set_individual_prompt(individual_prompt_text .get("1.0", tk.END).strip())
        api_handler.set_comparison_prompt(comparison_prompt_text.get("1.0", tk.END).strip())
        api_handler.set_max_tokens(int(max_tokens_entry.get()))
        api_handler.set_model_temperature(int(model_temperature_entry.get()))
        keyring.set_password("FinancialReportApp", "perplexity_api_key",self.perplexity_api_key_entry.get())
        self.advanced_settings_window.destroy()  # Close the window
        self.advanced_settings_window = None

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
        self.advanced_settings_window.geometry("600x600")
        self.advanced_settings_window.protocol("WM_DELETE_WINDOW", self.close_advanced_settings)

        notebook = ttk.Notebook(self.advanced_settings_window)
        notebook.pack(expand=True, fill='both', padx=10, pady=10)

        def api_settings_tab():
            # API settings tab
            api_frame = ttk.Frame(notebook)
            notebook.add(api_frame, text='Perplexity API Settings')
            api_handler = APIHandler()


            # API Key section
            ttk.Label(api_frame, text="Perplexity API Key:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            self.perplexity_api_key_entry = ttk.Entry(api_frame, width=50)  # Remove show="*" initially
            self.perplexity_api_key_entry.grid(row=0, column=1, sticky='w', padx=5, pady=5)
            api_key = keyring.get_password("FinancialReportApp", "perplexity_api_key") or ""
            if len(api_key) >= 6:
                visible_part = api_key[-6:]
                masked_part = '*' * (len(api_key) - 6)
                self.perplexity_api_key_entry.insert(0, masked_part + visible_part)
            else:
                self.perplexity_api_key_entry.insert(0, api_key)

            # Bind events to handle new input
            self.perplexity_api_key_entry.bind('<Key>', lambda e: self.perplexity_api_key_entry.config(show="*"))
            ToolTip(self.perplexity_api_key_entry, "Enter your Perplexity API key for AI analysis functionality")

            # Individual prompt section with reset button

            prompt_frame = ttk.Frame(api_frame)
            prompt_frame.grid(row=1, column=0, columnspan=2, sticky='we', padx=5, pady=5)
            individual_label = ttk.Label(prompt_frame, text="Individual report prompt:")
            individual_label.pack(side='left')
            ToolTip(individual_label, "Define the prompt template for analyzing individual companies")

            reset_individual_button = ttk.Button(prompt_frame, text="Reset to Default",
                                                 command=lambda: self.reset_prompt(individual_prompt_text , 'individual'))
            reset_individual_button.pack(side='right', padx=20)
            ToolTip(reset_individual_button, "Reset the individual analysis prompt to default template")

            individual_prompt_text  = scrolledtext.ScrolledText(api_frame, height=10, width=70, wrap=tk.WORD)
            individual_prompt_text .grid(row=2, column=0, columnspan=2, padx=5, pady=5)
            individual_prompt_text .insert(tk.END, api_handler.get_individual_prompt())
            ToolTip(individual_prompt_text , "Edit the prompt template for individual company analysis")

            # Comparison prompt section with reset button
            comparison_frame = ttk.Frame(api_frame)
            comparison_frame.grid(row=3, column=0, columnspan=2, sticky='we', padx=5, pady=5)
            comparison_label = ttk.Label(comparison_frame, text="Comparison prompt:")
            comparison_label.pack(side='left')
            ToolTip(comparison_label, "Define the prompt template for comparing multiple companies")

            reset_comparison_button = ttk.Button(comparison_frame, text="Reset to Default",
                                                 command=lambda: self.reset_prompt(comparison_prompt_text, 'comparison'))
            reset_comparison_button.pack(side='right', padx=20)
            ToolTip(reset_comparison_button, "Reset the comparison analysis prompt to default template")

            comparison_prompt_text = scrolledtext.ScrolledText(api_frame, height=10, width=70, wrap=tk.WORD)
            comparison_prompt_text.grid(row=4, column=0, columnspan=2, padx=5, pady=5)
            comparison_prompt_text.insert(tk.END, api_handler.get_comparison_prompt())
            ToolTip(comparison_prompt_text, "Edit the prompt template for company comparison analysis")

            # Max tokens section
            max_tokens_label = ttk.Label(api_frame, text="Max Tokens:")
            max_tokens_label.grid(row=5, column=0, sticky='w', padx=5, pady=5)
            ToolTip(max_tokens_label, "Maximum number of tokens for API responses")

            max_tokens_entry = ttk.Entry(api_frame)
            max_tokens_entry.grid(row=5, column=1, sticky='w', padx=5, pady=5)
            max_tokens_entry.insert(0, str(api_handler.get_max_tokens()))
            ToolTip(max_tokens_entry, "Set the maximum length of AI responses (higher values = longer responses)")

            # Model Temperature section
            model_temperature_label = ttk.Label(api_frame, text="Model Temperature:")
            model_temperature_label.grid(row=6, column=0, sticky='w', padx=5, pady=5)
            ToolTip(model_temperature_label, "The temperature of the model, higher = more varied output, lower = more "
                                             "consistent")

            model_temperature_entry = ttk.Entry(api_frame)
            model_temperature_entry.grid(row=6, column=1, sticky='w', padx=5, pady=5)
            model_temperature_entry.insert(0, str(api_handler.get_model_temperature()))

            # Save button at bottom
            save_button = ttk.Button(api_frame, text="Save",
                                     command=lambda: self.save_settings(individual_prompt_text , comparison_prompt_text,
                                                                        max_tokens_entry, model_temperature_entry))
            save_button.grid(row=6, column=0, columnspan=2, sticky='se', padx = 30, pady=15)
            ToolTip(save_button, "Save all settings and close the window")
        api_settings_tab()

        def other_settings_tab():
            other_settings = ttk.Frame(notebook)
            notebook.add(other_settings, text='Other settings')


        other_settings_tab()

    def reset_prompt(self, text_widget, prompt_type):
        api_handler = APIHandler()
        default_prompts = {
            'individual': '''<analysis_request>
      <company>{company_name}</company>
      <sections>
        <swot>
          <strengths>List 3-4 key financial and operational strengths</strengths>
          <weaknesses>List 3-4 main financial and operational weaknesses</weaknesses>
          <opportunities>List 3-4 potential growth opportunities and market advantages</opportunities>
          <threats>List 3-4 key market risks and competitive threats</threats>
        </swot>
        <insights>
          <market_position>Analyze current market position and competitive standing</market_position>
          <financial_health>Evaluate overall financial health and stability</financial_health>
          <future_outlook>Provide forward-looking analysis and growth potential</future_outlook>
          <investment_recommendation>Give clear investment recommendation with rationale</investment_recommendation>
        </insights>
      </sections>
    </analysis_request>''',
            'comparison': '''<comparison_request>
  <companies>{companies_data}</companies>
  <analysis_sections>
    <financial_comparison>
      <metrics>
        <valuation>Compare P/E ratios, price-to-book, and other valuation metrics between companies</valuation>
        <profitability>Analyze and compare operating margins, net profit margins, and revenue growth</profitability>
        <efficiency>Compare operational efficiency metrics and capital utilization</efficiency>
      </metrics>
    </financial_comparison>
    <dividend_analysis>
      <yield>Compare dividend yields and payout ratios if applicable</yield>
      <sustainability>Assess dividend sustainability based on cash flows and earnings</sustainability>
      <growth>Analyze historical dividend growth patterns and future potential</growth>
    </dividend_analysis>
    <competitive_analysis>
      <strengths>Identify key competitive advantages of each company</strengths>
      <market_position>Compare market positions and industry standing</market_position>
      <growth_potential>Evaluate future growth opportunities and expansion potential</growth_potential>
    </competitive_analysis>
    <investment_recommendation>
      <ranking>Rank the companies by investment attractiveness</ranking>
      <rationale>Provide detailed reasoning for the ranking</rationale>
      <risks>Highlight key risks for each company</risks>
    </investment_recommendation>
  </analysis_sections>
</comparison_request>
'''
        }

        text_widget.delete('1.0', tk.END)
        text_widget.insert(tk.END, default_prompts.get(prompt_type, ''))

    def close_advanced_settings(self):
        self.advanced_settings_window.destroy()
        self.advanced_settings_window = None

    def on_double_click(self, event):
        self.add_company()

    def connect_to_degiro(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        if username and password:
            try:
                # First attempt: with 2FA
                self.degiro_connector = DegiroConnector(prompt_for_2fa_callback=self.prompt_for_2fa)
                if self.degiro_connector.connect(username, password):
                    logger.info("Connected to Degiro successfully with 2FA")
                    self.connection_status.config(text="Connected", foreground="green")
                    self.logout_button.config(state=tk.NORMAL)
                    return

                # Second attempt: without 2FA
                logger.info("2FA connection failed, attempting without 2FA")
                self.degiro_connector = DegiroConnector(prompt_for_2fa_callback=None)
                if self.degiro_connector.connect(username, password):
                    logger.info("Connected to Degiro successfully without 2FA")
                    self.connection_status.config(text="Connected", foreground="green")
                    self.logout_button.config(state=tk.NORMAL)
                    return

                # If both attempts fail
                self.connection_status.config(text="Not Connected", foreground="red")
                logger.error("Failed to connect to Degiro with and without 2FA")
                self.logout_button.config(state=tk.DISABLED)
                messagebox.showerror("Connection Error", "Failed to connect to Degiro \n\n If you keep seeing this "
                                                         "msg, log in to deGiro via your browser. Likely bot "
                                                         "protection on deGiro backend")

            except Exception as e:
                logger.error(f"Unexpected error during Degiro connection: {str(e)}")
                messagebox.showerror("Connection Error", f"An error occurred: {str(e)}")
        else:
            logger.error("Username and password are required")
            messagebox.showerror("Input Error", "Username and password are required")

    def prompt_for_2fa(self):
        return simpledialog.askstring("2FA Code", "Enter your 6-digit 2FA code:", parent=self.master)

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
            api_handler = APIHandler()
            for company in self.selected_companies:
                company_name = company.split('(')[0].strip()
                isin = company.split('(')[1].split(')')[0]

                # Get financial data
                data = self.degiro_connector.fetch_data([isin])
                data_processor = DataProcessor(data)
                data_processor.process_data()

                # Get AI analysis if enabled
                ai_analysis = None
                if self.use_perplexity_api.get():
                    ai_analysis = api_handler.get_individual_analysis(company_name)

                # Generate PDF
                pdf_generator = PDFGenerator(
                    processed_data=data_processor.processed_data,
                    ai_insights=ai_analysis,
                    company_name=company_name
                )
                pdf_generator.generate_pdf()

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


