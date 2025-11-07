import logging

import keyring

logging.basicConfig(filename='financial_report_app.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import json
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import os
import sys
import tkinter as tk
from tkinter import filedialog
import re
import webbrowser
from reportlab.pdfgen import canvas


# Set environment variables for TCL and TK
os.environ['TCL_LIBRARY'] = r'C:\Users\daanv\AppData\Local\Programs\Python\Python313\tcl\tcl8.6'
os.environ['TK_LIBRARY'] = r'C:\Users\daanv\AppData\Local\Programs\Python\Python313\tcl\tk8.6'

# Perplexity API key
api_key = os.getenv('PERPLEXITY_API_KEY')


class DataProcessor:
    METRIC_MAP = {
        'revenue_per_share': ['AREVPS', 'TTMREVPS', 'MRQREVPS', 'LFYREVPS'],
        'eps': ['AEPSXCLXOR', 'TTMEPS', 'MRQEPS', 'LFYEPS'],
        'book_value_per_share': ['ABVPS', 'TTMBVPS', 'MRQBVPS', 'LFYBVPS'],
        'cash_per_share': ['ACSHPS', 'TTMCSHPS', 'MRQCSHPS', 'LFYCSHPS'],
        'free_cash_flow_per_share': ['TTMFCFSHR', 'MRQFCFSHR', 'LFYFCFSHR', 'FCFPS'],
        'pe_ratio': ['APEEXCLXOR', 'TTMPE', 'MRQPE', 'LFYPE'],
        'price_to_sales': ['APR2REV', 'TTMPR2REV', 'MRQPR2REV', 'LFYPR2REV'],
        'price_to_book': ['APRICE2BK', 'TTMPRICE2BK', 'MRQPRICE2BK', 'LFYPRICE2BK'],
        'price_to_cash_flow': ['TTMPRCFPS', 'APRFCFPS', 'MRQPRCFPS', 'LFYPRCFPS'],
        'price_to_free_cash_flow': ['APRFCFPS', 'TTMPRFCFPS', 'MRQPRFCFPS', 'LFYPRFCFPS'],
        'operating_margin': ['TTMOPMGN', 'AOPMGNPCT', 'MRQOPMGN', 'LFYOPMGN'],
        'net_profit_margin': ['TTMNPMGN', 'ANPMGNPCT', 'MRQNPMGN', 'LFYNPMGN'],
        'gross_margin': ['AGROSMGN', 'TTMGROSMGN', 'MRQGROSMGN', 'LFYGROSMGN'],
        'free_cash_flow_margin': ['Focf2Rev_TTM', 'AFocf2Rev', 'MRQFocf2Rev', 'LFYFocf2Rev']
    }

    def __init__(self, json_data):
        self.raw_data = json_data
        self.processed_data = {}
        self.isin = self._extract_isin()

    def _extract_isin(self):
        """Safely extract ISIN from raw data structure"""
        try:
            if isinstance(self.raw_data, dict):
                return next(iter(self.raw_data))
            elif isinstance(self.raw_data, list) and len(self.raw_data) > 0:
                return self.raw_data[0].get('isin')
            return 'UNKNOWN'
        except Exception as e:
            logger.error(f"ISIN extraction error: {str(e)}")
            return 'UNKNOWN'

    def _search_metric(self, target_ids):
        """Enhanced metric search with path tracking"""

        def search_with_path(data, path=[]):
            if isinstance(data, dict):
                # Check for direct match
                if 'id' in data and data['id'] in target_ids:
                    return data.get('value'), data['id'], path + [data['id']]
                # Recursive search
                for k, v in data.items():
                    result = search_with_path(v, path + [k])
                    if result:
                        return result
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    result = search_with_path(item, path + [f'[{i}]'])
                    if result:
                        return result
            return (None, None, [])

        # Search both profile and ratios sections
        for section in ['ratios', 'profile']:
            section_data = self.raw_data.get(self.isin, {}).get(section, {})
            value, found_id, path = search_with_path(section_data)
            if value is not None:
                try:
                    # Handle numeric values with commas
                    if isinstance(value, str):
                        value = value.replace(',', '')
                    return float(value), found_id
                except (ValueError, TypeError) as e:
                    logger.warning(f"Value conversion failed for {found_id}: {value} ({str(e)})")
                    return value, found_id

        logger.warning(f"Metric not found: {target_ids} in {self.isin}")
        return (None, None)

    def _get_period(self, metric_id):
        """Improved period detection with fallback"""
        period_map = {
            'A': ('Annual', 1),
            'TTM': ('Trailing 12 Months', 3),
            'MRQ': ('Most Recent Quarter', 3),
            'LFY': ('Last Fiscal Year', 3)
        }

        if not metric_id:
            return 'N/A'

        # Try different prefix lengths
        for length in [3, 4, 2]:
            prefix = metric_id[:length]
            if prefix in period_map:
                return period_map[prefix][0]

        # Fallback to first character
        return period_map.get(metric_id[0], ('N/A',))[0]

    def process_data(self):
        """Main processing method with enhanced validation"""
        try:
            if not self.raw_data:
                raise ValueError("Empty raw data provided")

            self.process_company_overview()
            self.calculate_financial_metrics()
            self.calculate_valuation_ratios()
            self.calculate_efficiency_metrics()
            self._validate_output()
        except Exception as e:
            logger.error(f"Data processing failed: {str(e)}")
            raise

    def _validate_output(self):
        """Ensure required metrics exist"""
        required_sections = ['financial_metrics', 'valuation_ratios', 'efficiency_metrics']
        for section in required_sections:
            if not self.processed_data.get(section):
                raise ValueError(f"Missing critical section: {section}")

    def process_company_overview(self):
        """Robust company overview processing"""
        try:
            company_data = self.raw_data.get(self.isin, {})
            profile = company_data.get('profile', {}).get('data', {})
            contacts = profile.get('contacts', {})

            self.processed_data['company_overview'] = {
                'legal_name': contacts.get('NAME', f"Unknown Company ({self.isin})"),
                'isin': self.isin,
                'sector': profile.get('sector', 'N/A'),
                'industry': profile.get('industry', 'N/A'),
                'country': contacts.get('COUNTRY', 'N/A'),
                'website': contacts.get('WEBSITE', 'N/A'),
                'description': profile.get('description', 'N/A')[:500] + '...'  # Truncate long descriptions
            }
        except Exception as e:
            logger.error(f"Company overview error: {str(e)}")
            self.processed_data['company_overview'] = {
                'legal_name': f"Unknown Company ({self.isin})",
                'isin': self.isin,
                'sector': 'N/A',
                'industry': 'N/A',
                'country': 'N/A',
                'website': 'N/A',
                'description': 'N/A'
            }

    def calculate_financial_metrics(self):
        """Financial metrics with value validation"""
        logger.info("Calculating financial metrics...")
        metrics = {}
        for key in ['revenue_per_share', 'eps', 'book_value_per_share',
                    'cash_per_share', 'free_cash_flow_per_share']:
            value, found_id = self._search_metric(self.METRIC_MAP[key])
            period = self._get_period(found_id)

            # Validate reasonable value ranges
            if value is not None:
                if key.endswith('_per_share') and value < 0:
                    logger.warning(f"Negative value for {key}: {value}")
                    value = None
                elif key == 'eps' and abs(value) > 1000:  # Unrealistic EPS values
                    logger.warning(f"Suspicious EPS value: {value}")
                    value = None

            metrics[key] = (value, period)
        self.processed_data['financial_metrics'] = metrics

    def calculate_valuation_ratios(self):
        """Valuation ratios with sanity checks"""
        logger.info("Calculating valuation metrics...")
        ratios = {}
        for key in ['pe_ratio', 'price_to_sales', 'price_to_book',
                    'price_to_cash_flow', 'price_to_free_cash_flow']:
            value, found_id = self._search_metric(self.METRIC_MAP[key])
            period = self._get_period(found_id)

            # Validate ratio ranges
            if value is not None:
                if key == 'pe_ratio' and (value < 0 or value > 1000):
                    logger.warning(f"Unusual P/E ratio: {value}")
                elif value < 0:
                    logger.warning(f"Negative ratio for {key}: {value}")
                    value = None

            ratios[key] = (value, period)
        self.processed_data['valuation_ratios'] = ratios

    def calculate_efficiency_metrics(self):
        """Efficiency metrics with percentage handling"""
        logger.info("Calculating efficiency metrics...")
        metrics = {}
        for key in ['operating_margin', 'net_profit_margin',
                    'gross_margin', 'free_cash_flow_margin']:
            value, found_id = self._search_metric(self.METRIC_MAP[key])
            period = self._get_period(found_id)

            # Convert percentages to decimals
            if value is not None and isinstance(value, str) and '%' in value:
                try:
                    value = float(value.strip('%')) / 100
                except ValueError:
                    value = None

            metrics[key] = (value, period)
        self.processed_data['efficiency_metrics'] = metrics


class APIHandler:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.api_url = "https://api.perplexity.ai/chat/completions"
        self.config_file = 'api_settings.json'

        # Default XML-formatted prompt for individual analysis
        self._default_prompt = '''<analysis_request>
    <company>{company_name}</company>
    <sections>
        <strategic_analysis>
            <strengths>Identify 3-4 key financial and operational strengths with supporting data</strengths>
            <weaknesses>Identify 3-4 main financial and operational weaknesses with supporting data</weaknesses>
            <opportunities>List 3-4 potential growth opportunities and market advantages</opportunities>
            <threats>List 3-4 key market risks and competitive threats</threats>
        </strategic_analysis>
        <detailed_analysis>
            <market_position>Analyze current market position and competitive standing</market_position>
            <financial_health>Evaluate overall financial health including key ratios and metrics</financial_health>
            <outlook>Provide forward-looking analysis and growth potential</outlook>
            <recommendation>
                <rating>Provide a clear investment rating (Buy/Hold/Sell)</rating>
                <rationale>Explain the investment recommendation with key supporting factors</rationale>
            </recommendation>
        </detailed_analysis>
    </sections>
</analysis_request>'''

        # Default comparison prompt
        self._default_comparison_prompt = '''<comparison_request>
    <companies>{company_names}</companies>
    <sections>
        <relative_analysis>
            <valuation>Compare key valuation metrics (P/E, P/B, etc.)</valuation>
            <profitability>Compare profit margins and operational efficiency</profitability>
            <growth>Compare revenue and earnings growth trends</growth>
        </relative_analysis>
        <recommendations>
            <ranking>Rank companies by investment attractiveness</ranking>
            <rationale>Explain the ranking with supporting metrics</rationale>
        </recommendations>
    </sections>
</comparison_request>'''

        self._individual_prompt = self._default_prompt
        self._comparison_prompt = self._default_comparison_prompt
        self._max_tokens = 1000
        self._model_temperature = 0.2

        self.load_settings()

    def save_settings(self):
        settings = {
            'individual_prompt': self._individual_prompt,
            'comparison_prompt': self._comparison_prompt,
            'max_tokens': self._max_tokens,
            'model_temperature': self._model_temperature
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def load_settings(self):
        try:
            with open(self.config_file, 'r') as f:
                settings = json.load(f)
                self._individual_prompt = settings.get('individual_prompt', self._individual_prompt)
                self._comparison_prompt = settings.get('comparison_prompt', self._comparison_prompt)
                self._max_tokens = settings.get('max_tokens', self._max_tokens)
                self._model_temperature = settings.get('model_temperature', self._model_temperature)
                logger.debug(f"Loaded settings: individual_prompt='{self._individual_prompt}'")
        except FileNotFoundError:
            self.save_settings()

    # Getters and setters

    def get_individual_prompt(self):
        return self._individual_prompt

    def set_individual_prompt(self, prompt):
        self._individual_prompt = prompt
        self.save_settings()

    def get_comparison_prompt(self):
        return self._comparison_prompt

    def set_comparison_prompt(self, prompt):
        self._comparison_prompt = prompt
        self.save_settings()

    def get_max_tokens(self):
        return self._max_tokens

    def set_max_tokens(self, tokens):
        self._max_tokens = tokens
        self.save_settings()

    def get_model_temperature(self):
        return self._model_temperature

    def set_model_temperature(self, temperature):
        self._model_temperature = temperature
        self.save_settings()

    def get_individual_analysis(self, company_name):
        """Gets AI analysis for a single company based on the configured prompt"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "llama-3.1-sonar-small-128k-online",
                # "model": "llama a-3.1-70b-instruct",

                "messages": [{
                    "role": "user",
                    "content": self._individual_prompt.format(company_name=company_name)
                }],
                "max_tokens": self._max_tokens,
                "temperature": self._model_temperature,

            }

            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            response_json = response.json()

            # Print token usage information
            if 'usage' in response_json:
                usage = response_json['usage']
                print(f"\nToken Usage:")
                print(f"Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                print(f"Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                print(f"Total tokens: {usage.get('total_tokens', 'N/A')}\n")

            return response_json['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Error in individual analysis: {e}")
            return None

    def get_comparison_analysis(self, companies_data):
        """Gets AI analysis comparing multiple companies based on the configured prompt"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": [{
                    "role": "user",
                    "content": f"{self._comparison_prompt}\n{json.dumps(companies_data, indent=2)}"
                }],
                "max_tokens": self._max_tokens
            }

            response = requests.post(self.api_url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"Error in comparison analysis: {e}")
            return None


class PDFGenerator:
    def __init__(self, processed_data, ai_insights, company_name):
        self.processed_data = processed_data
        self.ai_insights = ai_insights
        self.company_name = company_name
        self.doc = SimpleDocTemplate(f"{company_name}_financial_report.pdf", pagesize=letter)
        self.styles = getSampleStyleSheet()
        self.story = []
        self.section_style = ParagraphStyle(
            'SectionHeader', parent=self.styles['Heading1'], spaceBefore=12, spaceAfter=6
        )
        self.styles['BodyText'].spaceBefore = 6
        self.styles['BodyText'].spaceAfter = 6
        self.styles.add(ParagraphStyle(name='BodyTextBold', parent=self.styles['BodyText'], fontName='Helvetica-Bold'))

    def generate_comparison_pdf(self):
        """Generates a PDF comparing multiple companies"""
        try:
            # Title
            self.story.append(Paragraph("Company Comparison Analysis", self.styles['Heading1']))

            # Financial Metrics Comparison
            self.story.append(Paragraph("Financial Metrics Comparison", self.styles['Heading2']))

            # Create table data
            metrics_data = []
            companies = [comp['company_name'] for comp in self.processed_data]

            # Headers row
            headers = ['Metric'] + companies
            metrics_data.append(headers)

            # Define metrics to compare with labels
            metrics_to_compare = {
                'PE Ratio': ('valuation_ratios', 'pe_ratio'),
                'Price to Book': ('valuation_ratios', 'price_to_book'),
                'Price to Sales': ('valuation_ratios', 'price_to_sales'),
                'Operating Margin (%)': ('efficiency_metrics', 'operating_margin'),
                'Net Profit Margin (%)': ('efficiency_metrics', 'net_profit_margin'),
                'Gross Margin (%)': ('efficiency_metrics', 'gross_margin'),
                'EPS': ('financial_metrics', 'eps'),
                'Revenue Per Share': ('financial_metrics', 'revenue_per_share')
            }

            # Add rows for each metric
            for metric_name, (section, key) in metrics_to_compare.items():
                row = [metric_name]
                for company in self.processed_data:
                    try:
                        value = company['financial_data'][section][key][0]
                        formatted_value = f"{value:.2f}" if value is not None else 'N/A'
                        row.append(formatted_value)
                    except (KeyError, IndexError, TypeError):
                        row.append('N/A')
                metrics_data.append(row)

            # Create and style the table
            table = Table(metrics_data, colWidths=[2 * inch] + [1.5 * inch] * len(companies))
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10)
            ]))

            self.story.append(table)
            self.story.append(Spacer(1, 12))

            # AI Analysis Section with proper formatting
            if self.ai_insights:
                sections = self.ai_insights.split('###')
                for section in sections:
                    if not section.strip():
                        continue

                    # Handle section titles and content
                    parts = section.strip().split('\n', 1)
                    if len(parts) == 2:
                        title, content = parts
                        self.story.append(Paragraph(title.strip(), self.styles['Heading2']))

                        # Handle subsections marked with ####
                        if '##' in content:
                            subsections = content.split('####')
                            for subsection in subsections:
                                if subsection.strip():
                                    sub_parts = subsection.strip().split('\n', 1)
                                    if len(sub_parts) == 2:
                                        subtitle, subcontent = sub_parts
                                        self.story.append(Paragraph(subtitle.strip(), self.styles['Heading3']))
                                        self.story.append(Paragraph(subcontent.strip(), self.styles['Normal']))
                        else:
                            self.story.append(Paragraph(content.strip(), self.styles['Normal']))
                    else:
                        self.story.append(Paragraph(section.strip(), self.styles['Normal']))

                    self.story.append(Spacer(1, 12))

            # Generate the PDF
            self.doc.build(self.story)

        except Exception as e:
            logger.error(f"Error generating comparison PDF: {e}")

    def generate_pdf(self):
        self.generate_company_overview(self.processed_data['company_overview'])
        self.generate_financial_snapshot()
        self.generate_valuation_analysis()
        self.generate_efficiency_and_profitability()

        # Single unified AI section that handles any response format
        if self.ai_insights:
            self.generate_ai_section()

        self.doc.build(self.story)
        logger.info(f"PDF generated for {self.company_name}")

    def generate_ai_section(self):
        """Handle any AI response format"""
        self.story.append(Paragraph("AI Analysis", self.styles['Heading1']))

        if isinstance(self.ai_insights, str):
            # Handle raw text response
            self.story.append(Paragraph(self.ai_insights, self.styles['Normal']))
        elif isinstance(self.ai_insights, dict):
            # Handle structured response
            for section, content in self.ai_insights.items():
                self.story.append(Paragraph(
                    section.replace('_', ' ').title(),
                    self.styles['Heading2']
                ))
                if isinstance(content, (list, tuple)):
                    for item in content:
                        self.story.append(Paragraph(f"• {item}", self.styles['Normal']))
                else:
                    self.story.append(Paragraph(str(content), self.styles['Normal']))
                self.story.append(Spacer(1, 12))

        self.story.append(Spacer(1, 12))

    def generate_company_pdf(self, company_data):
        self.generate_company_overview(company_data['company_overview'])
        self.generate_financial_snapshot(company_data['financial_metrics'])
        self.generate_valuation_analysis(company_data['valuation_ratios'])
        self.generate_efficiency_and_profitability(company_data['efficiency_metrics'])
        if 'swot_analysis' in company_data:
            self.generate_swot_analysis(company_data['swot_analysis'])
        if 'ai_insights' in company_data:
            self.generate_ai_insights(company_data['ai_insights'])

    def generate_table(self, title, data, columns):
        try:
            table_content = []
            table_content.append(Paragraph(title, self.section_style))
            table_data = [columns]

            for key, (value, period) in data.items():
                if value is None or value == '—':
                    formatted_value = "N/A"
                    period_label = ""
                else:
                    formatted_value = f"{float(value):.2f}" if isinstance(value, (float, int)) else str(value).replace(
                        ',', '.')
                    period_label = f"({period})" if period else ""

                interpretation = self.interpret_metric(key, formatted_value)
                table_data.append([f"{key.replace('_', ' ').title()} {period_label}", formatted_value, interpretation])

            table = Table(table_data, colWidths=[2.5 * inch, 1.5 * inch, 2 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            table_content.append(table)
            table_content.append(Spacer(1, 12))
            explanation = self.get_table_explanation(title, data)  # Pass data here
            table_content.append(Paragraph(explanation, self.styles['Normal']))

            self.story.append(KeepTogether(table_content))

        except Exception as e:
            logger.error(f"Error generating table {title}: {e}")

    def determine_period(self, key):
        if key in ['revenue_per_share', 'eps', 'free_cash_flow_per_share']:
            return "(TTM)"
        elif key in ['book_value_per_share', 'cash_per_share']:
            return "(MRQ)"
        else:
            return "(Current)"

    def generate_company_overview(self, company_overview):
        try:
            self.story.append(Paragraph("Company Overview", self.styles['Heading1']))
            for key, value in company_overview.items():
                self.story.append(Paragraph(
                    f"{key.replace('_', ' ').title()}: {value}",
                    self.styles['Normal']
                ))
                self.story.append(Spacer(1, 6))
            self.story.append(Spacer(1, 12))
        except KeyError as e:
            logger.error(f"Error generating company overview: Missing key {e}")

    def generate_financial_snapshot(self):
        try:
            metrics = self.processed_data['financial_metrics']
            self.story.append(Paragraph("Financial Snapshot", self.styles['Heading1']))
            self.generate_table("Key Financial Metrics", metrics, ["Metric", "Value", "Interpretation"])

            explanation = (
                "These metrics provide crucial insights into the company's financial health and performance. Revenue per share indicates the company's sales relative to its outstanding shares, with higher values suggesting stronger revenue generation. Earnings per Share (EPS) reflects profitability on a per-share basis, with positive values indicating profitability and negative values signaling losses. Book value per share represents the company's net asset value per share, offering insight into the underlying value of the company. Cash per share and free cash flow per share provide information about the company's liquidity and ability to generate excess cash, respectively."
            )
            self.story.append(Paragraph(explanation, self.styles['Normal']))
            self.story.append(Spacer(1, 12))
        except KeyError as e:
            logger.error(f"Error generating financial snapshot: Missing key {e}")

    def generate_valuation_analysis(self):
        try:
            ratios = self.processed_data['valuation_ratios']
            self.story.append(Paragraph("Valuation Analysis", self.styles['Heading1']))
            self.generate_table("Valuation Ratios", ratios, ["Ratio", "Value", "Interpretation"])

            explanation = (
                "These ratios help assess the company's valuation relative to its financial performance. The Price-to-Earnings (P/E) ratio compares the stock price to earnings, with lower values potentially indicating undervaluation. Price-to-Sales (P/S) and Price-to-Book (P/B) ratios offer perspectives on valuation relative to revenue and book value. Price-to-Cash Flow (P/CF) and Price-to-Free Cash Flow (P/FCF) ratios provide insights into how the market values the company's ability to generate cash. These metrics are most useful when compared to industry averages or the company's historical values."
            )
            self.story.append(Paragraph(explanation, self.styles['Normal']))
            self.story.append(Spacer(1, 12))
        except KeyError as e:
            logger.error(f"Error generating valuation analysis: Missing key {e}")

    def generate_efficiency_and_profitability(self):
        try:
            metrics = self.processed_data['efficiency_metrics']
            self.story.append(Paragraph("Efficiency and Profitability", self.styles['Heading1']))
            self.generate_table("Efficiency Metrics", metrics, ["Metric", "Value", "Interpretation"])

            explanation = (
                "These metrics demonstrate the company's operational efficiency and profitability. Operating margin shows the percentage of revenue remaining after operating expenses, indicating core business profitability. Net profit margin reveals the percentage of revenue that translates into profit after all expenses. Gross margin reflects the company's efficiency in production and pricing. The free cash flow margin indicates the company's ability to generate cash relative to its revenue, which is crucial for future growth and financial flexibility."
            )
            self.story.append(Paragraph(explanation, self.styles['Normal']))
            self.story.append(Spacer(1, 12))
        except KeyError as e:
            logger.error(f"Error generating efficiency and profitability: Missing key {e}")

    def get_table_explanation(self, title, data):
        if title == "Key Financial Metrics":
            return (
                "These numbers show how the company defis doing financially. Revenue per share tells us how much money the company makes for each share. Earnings per share shows if the company is making a profit. Book value per share represents what each share is worth based on the company's assets.")
        elif title == "Valuation Ratios":
            return (
                "These ratios help us understand if the stock price is fair. A low P/E ratio might mean the stock is cheap, while a high one could mean it's expensive. Price-to-sales and price-to-book ratios compare the stock price to the company's sales and book value.")
        elif title == "Efficiency Metrics":
            return (
                "These metrics show how well the company uses its resources. Operating margin tells us how much profit the company makes from its main business. Net profit margin shows how much of the company's sales turn into profit after all expenses.")
        else:
            return "This table provides important financial information about the company."

    # Interpretation methods...
    def interpret_metric(self, key, value):
        try:
            # Check if value is already a float
            if isinstance(value, float):
                float_value = value
            else:
                # If it's a string, replace comma with period and convert to float
                float_value = value# = float(str(value).replace(',', '.'))

            if key == 'revenue_per_share':
                return self.interpret_revenue_per_share(float_value)
            elif key == 'eps':
                return self.interpret_eps(float_value)
            elif key == 'book_value_per_share':
                return self.interpret_book_value(float_value)
            elif key == 'pe_ratio':
                return self.interpret_pe_ratio(float_value)
            elif key == 'price_to_sales':
                return self.interpret_price_to_sales(float_value)
            elif key == 'price_to_book':
                return self.interpret_price_to_book(float_value)
            elif key == 'operating_margin':
                return self.interpret_operating_margin(float_value)
            elif key == 'net_profit_margin':
                return self.interpret_net_profit_margin(float_value)
            elif key == 'cash_per_share':
                return self.interpret_cash_per_share(value)
            elif key == 'free_cash_flow_per_share':
                return self.interpret_free_cash_flow_per_share(value)
            elif key == 'price_to_cash_flow':
                return self.interpret_price_to_cash_flow(value)
            elif key == 'price_to_free_cash_flow':
                return self.interpret_price_to_cash_flow(value)  # Using same interpretation as price_to_cash_flow
            elif key == 'gross_margin':
                return self.interpret_gross_margin(value)
            elif key == 'free_cash_flow_margin':
                return self.interpret_free_cash_flow_margin(value)
            else:
                return "No interpretation available"
        except ValueError:
            return f"Unable to interpret: '{value}' (type: {type(value).__name__}) is not a valid number"

    def interpret_pe_ratio(self, value):
        try:
            value = float(value)
            if value < 15:
                return "Good: Stock might be cheap"
            elif value < 25:
                return "Neutral: Stock price seems fair"
            else:
                return "Caution: Stock might be expensive"
        except ValueError:
            return "Unable to interpret"

    def interpret_price_to_sales(self, value):
        try:
            value = float(value)
            if value < 1:
                return "Good: Stock might be undervalued"
            elif value < 2:
                return "Neutral: Stock price seems reasonable"
            else:
                return "Caution: Stock might be overvalued"
        except ValueError:
            return "Unable to interpret"

    def interpret_operating_margin(self, value):
        try:
            value = float(value)
            if value < 0:
                return "Bad: Company is losing money on operations"
            elif value < 10:
                return "Caution: Low profit from operations"
            elif value < 20:
                return "Good: Decent profit from operations"
            else:
                return "Excellent: High profit from operations"
        except ValueError:
            return "Unable to interpret"

    def interpret_price_to_book(self, value):
        try:
            value = float(value)
            if value < 1:
                return "Potentially undervalued"
            elif value < 3:
                return "Fairly valued"
            else:
                return "Potentially overvalued"
        except ValueError:
            return "Unable to interpret"

    def interpret_net_profit_margin(self, value):
        try:
            value = float(value)
            if value < 0:
                return "Company is not profitable"
            elif value < 5:
                return "Low profitability"
            elif value < 10:
                return "Moderate profitability"
            else:
                return "High profitability"
        except ValueError:
            return "Unable to interpret"

    def interpret_revenue_per_share(self, value):
        if value == "N/A":
            return "Data not available"
        try:
            value = float(value)
            if value > 10:
                return "High revenue relative to share price"
            elif value > 5:
                return "Moderate revenue relative to share price"
            else:
                return "Low revenue relative to share price"
        except ValueError:
            return f"Unable to interpret: '{value}' (type: {type(value).__name__}) is not a valid number"

    def interpret_eps(self, value):
        try:
            value = float(value)
            if value > 0:
                return "Company is profitable"
            elif value == 0:
                return "Company is breaking even"
            else:
                return "Company is operating at a loss"
        except ValueError:
            return "Unable to interpret"

    def interpret_book_value(self, value):
        try:
            value = float(value)
            if value > 0:
                return "Positive net asset value"
            else:
                return "Negative net asset value"
        except ValueError:
            return "Unable to interpret"

    def interpret_cash_per_share(self, value):
        try:
            value = float(value)
            if value > 5:
                return "Strong cash position"
            elif value > 1:
                return "Adequate cash reserves"
            else:
                return "Low cash reserves"
        except ValueError:
            return "Unable to interpret"

    def interpret_free_cash_flow_per_share(self, value):
        try:
            value = float(value)
            if value > 1:
                return "Strong cash generation"
            elif value > 0:
                return "Positive cash generation"
            else:
                return "Negative cash generation"
        except ValueError:
            return "Unable to interpret"

    def interpret_price_to_cash_flow(self, value):
        try:
            value = float(value)
            if value < 10:
                return "Potentially undervalued"
            elif value < 20:
                return "Fairly valued"
            else:
                return "Potentially overvalued"
        except ValueError:
            return "Unable to interpret"

    def interpret_gross_margin(self, value):
        try:
            value = float(value)
            if value > 40:
                return "High gross profitability"
            elif value > 20:
                return "Average gross profitability"
            else:
                return "Low gross profitability"
        except ValueError:
            return "Unable to interpret"

    def interpret_free_cash_flow_margin(self, value):
        try:
            value = float(value)
            if value > 10:
                return "Strong cash flow generation"
            elif value > 5:
                return "Good cash flow generation"
            elif value > 0:
                return "Positive cash flow generation"
            else:
                return "Negative cash flow generation"
        except ValueError:
            return "Unable to interpret"

    def generate_ai_insights(self):
        try:
            analysis = self.ai_insights.get('analysis')
            if analysis:
                # Parse SWOT section
                swot = analysis.get('swot', {})
                self.story.append(Paragraph("SWOT Analysis", self.styles['Heading1']))
                for category in ['strengths', 'weaknesses', 'opportunities', 'threats']:
                    self.story.append(Paragraph(category.title(), self.styles['Heading2']))
                    for point in swot.get(category, []):
                        self.story.append(Paragraph(f"• {point}", self.styles['Normal']))
                    self.story.append(Spacer(1, 12))

                # Parse Insights section
                insights = analysis.get('insights', {})
                self.story.append(Paragraph("Market Analysis", self.styles['Heading1']))
                for section, content in insights.items():
                    self.story.append(Paragraph(section.replace('_', ' ').title(),
                                                self.styles['Heading2']))
                    self.story.append(Paragraph(content, self.styles['Normal']))
                    self.story.append(Spacer(1, 12))
        except Exception as e:
            logger.error(f"Error generating AI insights: {e}")

    def generate_swot_analysis(self, swot_analysis):
        try:
            self.story.append(Paragraph("SWOT Analysis", self.styles['Heading1']))
            if swot_analysis and isinstance(swot_analysis, dict):
                for category in ['Strengths', 'Weaknesses', 'Opportunities', 'Threats']:
                    self.story.append(Paragraph(category, self.styles['Heading2']))
                    points = swot_analysis.get(category, [])
                    for point in points:
                        if isinstance(point, dict):
                            bullet_text = f"• {point.get('Point', '')}: {point.get('Description', '')}"
                        else:
                            bullet_text = f"• {point}"
                        self.story.append(Paragraph(bullet_text, self.styles['Normal']))
                    self.story.append(Spacer(1, 12))  # Add space between sections
            else:
                self.story.append(Paragraph("SWOT analysis not available", self.styles['Normal']))
            self.story.append(Spacer(1, 12))
        except Exception as e:
            logger.error(f"Error generating SWOT analysis: {e}")


    def generate_valuation_analysis(self):
        try:
            ratios = self.processed_data['valuation_ratios']
            self.story.append(Paragraph("Valuation Analysis", self.styles['Heading1']))
            self.generate_table("Valuation Ratios", ratios, ["Ratio", "Value", "Interpretation"])
        except KeyError as e:
            logger.error(f"Error generating valuation analysis: Missing key {e}")

    def generate_efficiency_and_profitability(self):
        try:
            metrics = self.processed_data['efficiency_metrics']
            self.story.append(Paragraph("Efficiency and Profitability", self.styles['Heading1']))
            self.generate_table("Efficiency Metrics", metrics, ["Metric", "Value", "Interpretation"])

            explanation = (
                "These metrics show how efficiently the company operates and generates profits. "
                "Operating margin indicates profitability from core business operations. "
                "Net profit margin shows overall profitability after all expenses. "
                "Gross margin reflects efficiency in production and pricing. "
                "Free cash flow margin indicates the company's ability to generate cash relative to revenue."
            )
            self.story.append(Paragraph(explanation, self.styles['Normal']))
            self.story.append(Spacer(1, 12))
        except KeyError as e:
            logger.error(f"Error generating efficiency and profitability: Missing key {e}")


def main():
    try:
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not file_path:
            logger.info("No file chosen")
            return

        with open(file_path, 'r', encoding='utf-8') as file:
            json_data = json.load(file)

        data_processor = DataProcessor(json_data)
        data_processor.process_data()

        api_handler = APIHandler()
        company_name = data_processor.processed_data['company_overview']['legal_name']

        swot_analysis = api_handler.get_swot_analysis(company_name)
        ai_insights_text = api_handler.get_ai_insights(company_name)
        ai_insights = {
            'swot_analysis': swot_analysis,
            'ai_insights': ai_insights_text
        }

        pdf_generator = PDFGenerator(data_processor.processed_data, ai_insights, company_name)
        pdf_generator.generate_pdf()
        webbrowser.open(f"{company_name}_financial_report.pdf")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()