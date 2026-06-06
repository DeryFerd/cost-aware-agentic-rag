"""Create sample SEC 10-K documents for testing."""

import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings

companies = {
    'MSFT': {
        'name': 'Microsoft Corporation',
        'revenue_2024': 245.1,
        'revenue_2023': 211.9,
        'revenue_2022': 198.3,
        'employees': 228000,
        'risks': ['Cloud competition', 'Cybersecurity threats', 'Regulatory changes'],
    },
    'AMZN': {
        'name': 'Amazon.com Inc',
        'revenue_2024': 574.0,
        'revenue_2023': 524.9,
        'revenue_2022': 469.8,
        'employees': 1540000,
        'risks': ['Competition in e-commerce', 'AWS market share', 'Labor costs'],
    },
    'META': {
        'name': 'Meta Platforms Inc',
        'revenue_2024': 164.0,
        'revenue_2023': 134.9,
        'revenue_2022': 116.6,
        'employees': 67317,
        'risks': ['Metaverse investment risk', 'Privacy regulations', 'Competition'],
    },
    'GOOG': {
        'name': 'Alphabet Inc',
        'revenue_2024': 350.0,
        'revenue_2023': 307.4,
        'revenue_2022': 282.8,
        'employees': 183323,
        'risks': ['Antitrust regulations', 'AI competition', 'Ad market volatility'],
    },
    'TSLA': {
        'name': 'Tesla Inc',
        'revenue_2024': 97.7,
        'revenue_2023': 96.8,
        'revenue_2022': 81.5,
        'employees': 140473,
        'risks': ['EV competition', 'Manufacturing scalability', 'Regulatory changes'],
    },
}

for ticker, data in companies.items():
    company_dir = settings.raw_dir / ticker
    company_dir.mkdir(parents=True, exist_ok=True)

    for year in [2022, 2023, 2024]:
        year_dir = company_dir / str(year)
        year_dir.mkdir(exist_ok=True)

        rev_key = f'revenue_{year}'
        revenue = data.get(rev_key, 100.0)
        prev_revenue = data.get(f'revenue_{year-1}', revenue * 0.9)
        growth = ((revenue / prev_revenue) - 1) * 100

        risks_text = "\n".join(f"- {risk}" for risk in data['risks'])

        content = f"""UNITED STATES
SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549

FORM 10-K

{data['name']}
(Exact name of registrant as specified in its charter)

ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d)
OF THE SECURITIES EXCHANGE ACT OF 1934

For the fiscal year ended December 31, {year}
Commission File Number: 001-XXXXX

{data['name']}
One Microsoft Way
Redmond, Washington 98052
(425) 882-8080

SECURITIES REGISTERED PURSUANT TO SECTION 12(b) OF THE ACT:
Common Stock, par value $0.0000125 per share

PART I

ITEM 1. BUSINESS

{data['name']} is a leading global technology company. We develop and license software, hardware, cloud services, and provide professional services.

Products and Services:
- Cloud computing services
- Productivity software
- Hardware devices
- Artificial intelligence services
- Digital advertising

ITEM 1A. RISK FACTORS

The following are the principal risk factors associated with our business:

{risks_text}

ITEM 5. MARK FOR COMMON EQUITY

Our common stock is listed on the NASDAQ Stock Market under the ticker symbol {ticker}.

PART II

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

Revenue Analysis:
- Fiscal Year {year}: ${revenue:.1f} billion
- Fiscal Year {year-1}: ${prev_revenue:.1f} billion
- Year-over-year growth: {growth:.1f}%

Our revenue growth was driven by increased demand for our products and services.

Employees: {data['employees']:,}

ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA

See accompanying consolidated financial statements.

SIGNATURES

Pursuant to the requirements of Section 13 or 15(d) of the Securities Exchange Act of 1934, the registrant has duly caused this report to be signed on its behalf by the undersigned.

Date: February {year + 1}

By: /s/ Chief Executive Officer
"""

        filing_path = year_dir / f"{ticker}_{year}_10K.txt"
        filing_path.write_text(content, encoding="utf-8")
        print(f"Created: {filing_path}")

print("\nSample SEC filings created!")
