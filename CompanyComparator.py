import json
from tkinter import messagebox
import logging as logger
from Generator import PDFGenerator, APIHandler


class CompanyComparator:
    def __init__(self):
        self.api_handler = APIHandler()

    def load_company_data(self, file_path='compiled_company_data.json'):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Error", "No company data found. Generate reports first.")
            return []

    def generate_comparison_report(self, selected_data):
        try:
            # Format financial data for better AI analysis
            formatted_data = {
                company['company_name']: {
                    'financial_metrics': company['financial_data']['financial_metrics'],
                    'valuation_ratios': company['financial_data']['valuation_ratios'],
                    'efficiency_metrics': company['financial_data']['efficiency_metrics']
                } for company in selected_data
            }

            # Get comparison analysis from Perplexity API
            comparison_analysis = self.api_handler.get_comparison_analysis(formatted_data)

            # Generate PDF report
            pdf_generator = PDFGenerator(
                processed_data=selected_data,  # Pass full data structure
                ai_insights=comparison_analysis,
                company_name="Companies_Comparison"
            )
            pdf_generator.generate_comparison_pdf()

            return True

        except Exception as e:
            logger.error(f"Error generating comparison report: {e}")
            return False

    def generate_comparison_prompt(self, companies_data):
        # Format the financial data for the prompt
        financial_summary = ""
        for company in companies_data:
            financial_summary += f"""
            <company name="{company['company_name']}">
                <metrics>
                    <eps>{company['financial_data']['financial_metrics']['eps'][0]}</eps>
                    <pe_ratio>{company['financial_data']['valuation_ratios']['pe_ratio'][0]}</pe_ratio>
                    <operating_margin>{company['financial_data']['efficiency_metrics']['operating_margin'][0]}</operating_margin>
                    <net_profit_margin>{company['financial_data']['efficiency_metrics']['net_profit_margin'][0]}</net_profit_margin>
                </metrics>
            </company>"""

        prompt = f"""
        <company_analysis_request>
            <data>{financial_summary}</data>
            <objective>Compare these companies' investment potential based on their financial metrics</objective>
            <analysis_requirements>
                <valuation>Analyze PE ratios and valuation metrics</valuation>
                <profitability>Compare profit margins and operational efficiency</profitability>
                <recommendation>Provide investment recommendations with rationale</recommendation>
            </analysis_requirements>
        </company_analysis_request>
        """
        return prompt

