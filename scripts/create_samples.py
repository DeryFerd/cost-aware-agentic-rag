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
        'description': 'Microsoft Corporation is a global technology company that develops software, hardware, cloud services, and AI solutions. Our flagship products include Windows, Office 365, Azure cloud platform, and GitHub.',
        'revenue_2024': 245.1,
        'revenue_2023': 211.9,
        'revenue_2022': 198.3,
        'employees': 228000,
        'risks': ['Cloud competition from AWS and Google', 'Cybersecurity threats and data breaches', 'Regulatory changes in AI and antitrust'],
        'segment': 'Intelligent Cloud',
    },
    'AMZN': {
        'name': 'Amazon.com Inc',
        'description': 'Amazon.com Inc is a leading e-commerce and cloud computing company. Our operations include Amazon.com retail marketplace, Amazon Web Services (AWS) cloud platform, and Prime membership services.',
        'revenue_2024': 574.0,
        'revenue_2023': 524.9,
        'revenue_2022': 469.8,
        'employees': 1540000,
        'risks': ['Intense competition in e-commerce', 'AWS market share pressure', 'Rising labor and logistics costs'],
        'segment': 'North America',
    },
    'META': {
        'name': 'Meta Platforms Inc',
        'description': 'Meta Platforms Inc builds technologies that help people connect, find communities, and grow businesses. Our products include Facebook, Instagram, WhatsApp, and Quest virtual reality headsets.',
        'revenue_2024': 164.0,
        'revenue_2023': 134.9,
        'revenue_2022': 116.6,
        'employees': 67317,
        'risks': ['Metaverse investment uncertainty', 'Privacy regulations like GDPR', 'Competition from TikTok and others'],
        'segment': 'Family of Apps',
    },
    'GOOG': {
        'name': 'Alphabet Inc',
        'description': 'Alphabet Inc is the parent company of Google LLC. Our products include Google Search, Google Ads, YouTube, Google Cloud, Android operating system, and Waymo autonomous vehicles.',
        'revenue_2024': 350.0,
        'revenue_2023': 307.4,
        'revenue_2022': 282.8,
        'employees': 183323,
        'risks': ['Antitrust regulations worldwide', 'AI competition from Microsoft and OpenAI', 'Digital advertising market volatility'],
        'segment': 'Google Services',
    },
    'TSLA': {
        'name': 'Tesla Inc',
        'description': 'Tesla Inc designs, manufactures, and sells electric vehicles and energy generation systems. Our products include Model S, Model 3, Model X, Model Y, Cybertruck, and Powerwall energy storage.',
        'revenue_2024': 97.7,
        'revenue_2023': 96.8,
        'revenue_2022': 81.5,
        'employees': 140473,
        'risks': ['Electric vehicle competition', 'Manufacturing scalability challenges', 'Regulatory changes in EV incentives'],
        'segment': 'Automotive',
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

PART I

ITEM 1. BUSINESS

{data['description']}

Our primary business segment is {data['segment']}.

ITEM 1A. RISK FACTORS

The following are the principal risk factors associated with our business:

{risks_text}

ITEM 5. MARK FOR COMMON EQUITY

Our common stock is listed on the NASDAQ Stock Market under the ticker symbol {ticker}.

PART II

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

Revenue Analysis for {data['name']}:
- Fiscal Year {year}: ${revenue:.1f} billion
- Fiscal Year {year-1}: ${prev_revenue:.1f} billion
- Year-over-year growth: {growth:.1f}%

Our revenue growth was driven by increased demand for {data['segment']} products and services.

As of December 31, {year}, {data['name']} had {data['employees']:,} full-time employees.

ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA

See accompanying consolidated financial statements of {data['name']}.

SIGNATURES

Pursuant to the requirements of Section 13 or 15(d) of the Securities Exchange Act of 1934, the registrant has duly caused this report to be signed on its behalf by the undersigned.

Date: February {year + 1}

By: /s/ Chief Executive Officer
"""

        filing_path = year_dir / f"{ticker}_{year}_10K.txt"
        filing_path.write_text(content, encoding="utf-8")
        print(f"Created: {filing_path}")

print("\nSample SEC filings created!")
