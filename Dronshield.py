from fpdf import FPDF


class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Fundamental Analysis Report', 0, 1, 'C')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def create_table(self, header, data):
        col_width = self.w / 2.5
        row_height = self.font_size + 2
        for item in header:
            self.cell(col_width, row_height, str(item), border=1)
        self.ln(row_height)
        for row in data:
            for item in row:
                self.cell(col_width, row_height, str(item), border=1)
            self.ln(row_height)


def create_report(filename, content, recommendations, summary, investment_recommendations):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Executive Summary", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, summary)
    pdf.ln(5)

    for section, text in content.items():
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, section, 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, text)
        pdf.ln(5)

    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Investment Recommendations", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, investment_recommendations)
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Further Research Recommendations", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, recommendations)

    pdf.output(filename)


# Content for the first report (General Fundamental Analysis)
content1 = {
    "Profitability": """
Net Profit Margin (NPM):
- TTM: 11.06%
- 1st Historical Fiscal Year: 16.95%

Operating Margin:
- FFY: 6.45%
- TTM: 2.3%
- 5-Year Avg: -23.59%

Note: Profitability ratios indicate how well the company is converting revenue into profit. The decrease in NPM and Operating Margin may suggest rising costs or competitive pressures. However, the positive trend from the negative 5-year average is encouraging.
    """,
    "Debt Levels": """
Debt-to-Equity Ratio:
- MRQ: 3.44
- LFY: 3.52

Note: Debt levels reflect the company's financial leverage. The high ratios here (above 1) indicate significant debt. This can imply higher risk but also suggest investment in growth. The slight decrease is positive, but the overall level remains high.
    """,
    "Liquidity": """
Current Ratio:
- MRQ: 6.96
- LFY: 4.18

Note: A high current ratio suggests strong liquidity, indicating the company's capability to meet short-term obligations. However, a ratio this high (above 3) may also suggest inefficient use of assets. The increase from 4.18 to 6.96 is significant and warrants further investigation.
    """,
    "Efficiency": """
Return on Equity (ROE):
- TTM: 5.94%
- LFY: 19.47%
- 5-Year Avg: -10.38%

Return on Assets (ROA):
- TTM: 5.10%
- LFY: 15.27%
- 5-Year Avg: -8.29%

Note: Efficiency ratios indicate how well the company uses its resources to generate profits. The positive trend from negative 5-year averages is good, but the recent declines from LFY to TTM in both ROE and ROA might need further exploration. This could indicate challenges in maintaining efficiency as the company grows.
    """,
    "Valuation": """
Price-to-Earnings (P/E) Ratio:
- LFY Normalized: 38.46

Price-to-Book (P/B) Ratio: 6.20

Note: These valuation ratios reflect market expectations about growth potential. The high P/E ratio suggests investors expect strong future growth. The high P/B ratio indicates the market values the company significantly above its book value. While these high values suggest optimism, they also imply higher risk if the company doesn't meet these high expectations.
    """,
    "Dividend Policy": """
The company does not currently pay dividends and is not planning to do so in the near future.

Note: This suggests a focus on reinvestment and growth rather than immediate shareholder returns. It's common for growing companies, especially in tech or innovative sectors, to prioritize reinvesting profits into the business over paying dividends.
    """,
    "Cash Flow": """
Free Cash Flow (FCF):
- TTM: -18.026M AUD
- LFY: 7.759M AUD

Note: The shift from positive to negative FCF indicates the company is currently spending more cash than it's generating from operations. This could be due to increased investments in growth, such as R&D or capital expenditures. While negative FCF can be acceptable for growing companies, it's important to monitor this trend to ensure it doesn't persist long-term.
    """,
    "R&D Investment": """
The company invested 2.3M AUD in R&D, targeting systems relevant to global Defense sectors.

Note: Significant R&D investment indicates a focus on innovation and future growth potential. This aligns with the company's no-dividend policy and negative FCF, suggesting a strong emphasis on long-term growth over short-term profitability.
    """
}

# Content for the second report (DroneShield-specific)
content2 = {
    "Company Overview": """
DroneShield is a C-UAV (Counter-Unmanned Aerial Vehicles) company, specializing in detection and mitigation solutions for drone threats.

Note: This specialized focus positions DroneShield in a niche but growing sector within the broader defense industry. The increasing prevalence of drone technology in both civilian and military applications suggests potential for market expansion.
    """,
    "Industry Context": """
- Defense market growth: $616.32B (2024) to $772.49B (2028), CAGR 5.8%
- Global military expenditure: $2.43T in 2023, 7% YoY increase
- Top 15 defense contractors: Projected $52B free cash flow by 2026

Note: These figures indicate a growing defense market, which could provide favorable conditions for DroneShield's expansion. The increase in military expenditure globally suggests potential increased demand for advanced defense technologies, including C-UAV systems.
    """,
    "Financial Overview": """
- Net Profit Margin (TTM): 11.06%
- Operating Margin (TTM): 2.3%
- Debt-to-Equity Ratio (MRQ): 3.44
- Current Ratio (MRQ): 6.96
- Return on Equity (TTM): 5.94%
- P/E Ratio (Normalized, LFY): 38.46
- Free Cash Flow (TTM): -18.026M AUD

Note: These metrics suggest a company in a growth phase. The positive profit margins indicate profitability, but the high debt ratio and negative FCF suggest significant investment in growth. The high P/E ratio reflects market expectations of future growth.
    """,
    "Growth Strategy": """
- R&D investment: 2.3M AUD
- Focus: Systems relevant to global Defense & military doctrine
- Dividend policy: No current dividends, prioritizing reinvestment

Note: This strategy aligns with a company focused on long-term growth through innovation. The significant R&D investment and the decision to forgo dividends suggest a prioritization of future market position over short-term returns to shareholders.
    """,
    "Market Position": """
- Sector: Growing C-UAV market
- Valuation: High P/E and P/B ratios indicate strong market expectations
- Cash Flow: Recent shift to negative FCF suggests heavy investment in growth

Note: DroneShield's focus on the C-UAV sector positions it in a rapidly evolving area of defense technology. The high valuation ratios suggest investor confidence in future growth, while the negative FCF aligns with a strategy of aggressive reinvestment for expansion.
    """
}

further_research_recommendations = """
1. Financial Statement Analysis: Learn how to read and interpret balance sheets, income statements, and cash flow statements in depth.

2. Valuation Techniques: Study different methods of valuing companies, including DCF (Discounted Cash Flow) analysis and comparable company analysis.

3. Industry Analysis: Understand industry-specific factors that affect financial performance, particularly in the defense sector. Look into market trends, regulatory environment, and competitive landscape.

4. Investment Strategies: Familiarize yourself with various investment strategies and how fundamental analysis fits into them. Consider learning about value investing, growth investing, and momentum strategies.

5. Online Courses: Explore platforms like Coursera, Udemy, or Khan Academy for courses on financial analysis and investing. Look for courses specifically tailored to beginners in stock market investing.

6. Financial News: Follow reputable financial news sources to stay updated on market trends and economic factors affecting investments. Consider sources like Financial Times, Wall Street Journal, or Bloomberg.

7. Risk Management: Study different types of investment risks and strategies to mitigate them. This includes understanding concepts like diversification and position sizing.

8. Technical Analysis: While this report focuses on fundamental analysis, learning the basics of technical analysis can provide additional insights for timing investments.

9. Economic Indicators: Understand how macroeconomic factors like GDP growth, inflation, and interest rates can affect stock prices and company performance.

10. Investor Psychology: Learn about behavioral finance to understand how psychological factors can influence investment decisions and market movements.
"""

summary1 = """
This report provides a comprehensive fundamental analysis of a company operating in the defense sector. The company shows signs of growth with improving profitability ratios, though recent trends indicate some challenges. High debt levels and negative free cash flow suggest significant investments in growth, supported by substantial R&D spending. The company's focus on reinvestment over dividends aligns with a long-term growth strategy. High valuation ratios indicate strong market expectations for future performance.
"""

investment_recommendations1 = """
Pros for Investment:
1. Positive trend in profitability from negative 5-year averages to current positive margins.
2. Significant R&D investment (2.3M AUD) suggests focus on innovation and future growth.
3. High liquidity (Current Ratio: 6.96) indicates strong short-term financial health.
4. Operating in the growing defense sector with potential for market expansion.

Cons for Investment:
1. High debt levels (Debt-to-Equity Ratio: 3.44) increase financial risk.
2. Recent decline in profitability metrics (NPM, Operating Margin) from LFY to TTM.
3. Negative Free Cash Flow (-18.026M AUD) in TTM period suggests heavy spending.
4. High valuation ratios (P/E: 38.46, P/B: 6.20) imply high growth expectations, increasing investment risk if not met.

Recommendation:
This investment opportunity suits investors with a high risk tolerance and long-term perspective. The company shows potential for growth in a expanding market, but faces challenges in maintaining profitability and managing debt. Careful monitoring of future financial reports and industry trends is crucial. Consider as part of a diversified portfolio, but be prepared for potential volatility.
"""

summary2 = """
DroneShield, a specialized C-UAV (Counter-Unmanned Aerial Vehicles) company, operates in a niche but growing sector within the defense industry. The company shows promising financials with positive profit margins, but also exhibits characteristics of a growth-phase company with high debt and negative free cash flow. DroneShield's focus on R&D and its position in the expanding defense market suggest potential for future growth, reflected in its high valuation ratios.
"""

investment_recommendations2 = """
Pros for Investment:
1. Specialized focus in the growing C-UAV market within the expanding defense industry.
2. Positive profit margins (Net Profit Margin: 11.06%) indicate ability to generate profits.
3. Significant R&D investment (2.3M AUD) suggests commitment to innovation and future growth.
4. Strong liquidity position (Current Ratio: 6.96) indicates ability to meet short-term obligations.

Cons for Investment:
1. High debt levels (Debt-to-Equity Ratio: 3.44) increase financial risk.
2. Negative Free Cash Flow (-18.026M AUD) in TTM period suggests heavy spending.
3. High valuation ratios (P/E: 38.46) imply high growth expectations, increasing investment risk if not met.
4. Specialized focus might make the company vulnerable to sector-specific risks or changes in defense spending.

Recommendation:
DroneShield presents an opportunity for investors interested in the defense technology sector, particularly those bullish on the future of counter-drone systems. The investment suits those with higher risk tolerance and a long-term perspective. The company's growth potential is significant, but so are the risks associated with its high debt and negative cash flow. Potential investors should closely monitor DroneShield's ability to convert its R&D investments into market share and profitability. Consider as part of a diversified portfolio, understanding the potential for volatility in this niche market.
"""

create_report("fundamental_analysis_report.pdf", content1, further_research_recommendations, summary1,
              investment_recommendations1)
create_report("droneshield_analysis_report.pdf", content2, further_research_recommendations, summary2,
              investment_recommendations2)
