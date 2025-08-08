#!/usr/bin/env python3
"""
Automated Fyers Trading Bot - Cloud Ready
Runs automatically Monday-Friday 9:15 AM - 3:30 PM
Includes web interface, email notifications, and auth code handling
"""

import json
import os
import time
import threading
import schedule
from datetime import datetime, timedelta
import pyotp
import smtplib
import logging
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from flask import Flask, render_template, request, jsonify, redirect, url_for
from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import gspread
from google.oauth2.service_account import Credentials

# =============================================================================
# CONFIGURATION
# =============================================================================

# Fyers API Credentials
FYERS_CLIENT_ID = "EH8TE9J6PZ-100"
FYERS_SECRET_KEY = "V8EC76L8UP"
FYERS_REDIRECT_URI = "https://fyersauth.vercel.app/"
FYERS_TOTP_SECRET = "7JKB7FFBMZNQRYYV7PQ46L7XRUQLR6FV"
FYERS_PIN = "8905"

# Email Configuration (Your Gmail Setup)
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME', 'kaushalpatil8991@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'cwycuvedbnkwoitg')
EMAIL_TO = os.environ.get('EMAIL_TO', 'dipesh.p24@fms.edu')

# Trading Configuration
INDIVIDUAL_TRADE_THRESHOLD = 30000000  # ₹3 crore
MIN_VOLUME_SPIKE = 1000

# Google Sheets Configuration
GOOGLE_SHEETS_ID = "1l_6Sx_u1czhY-5JdT22tpmCV8Os3XuZmZ3U2ShKDLHw"

# Market Hours
MARKET_START_TIME = "09:15"
MARKET_END_TIME = "15:30"

# File paths
ACCESS_TOKEN_FILE = "fyers_access_token.json"
BOT_STATE_FILE = "bot_state.json"

# Top stocks to monitor
STOCK_SYMBOLS = [
    "NSE:HDFCBANK-EQ", "NSE:ICICIBANK-EQ", "NSE:AXISBANK-EQ", "NSE:SBIN-EQ",
    "NSE:KOTAKBANK-EQ", "NSE:TCS-EQ", "NSE:INFY-EQ", "NSE:WIPRO-EQ",
    "NSE:HCLTECH-EQ", "NSE:RELIANCE-EQ", "NSE:ONGC-EQ", "NSE:IOC-EQ",
    "NSE:MARUTI-EQ", "NSE:TATAMOTORS-EQ", "NSE:M&M-EQ", "NSE:SUNPHARMA-EQ",
    "NSE:DRREDDY-EQ", "NSE:CIPLA-EQ", "NSE:HINDUNILVR-EQ", "NSE:ITC-EQ",
    "NSE:BRITANNIA-EQ", "NSE:NESTLEIND-EQ", "NSE:TATASTEEL-EQ", "NSE:HINDALCO-EQ",
    "NSE:JSWSTEEL-EQ", "NSE:NTPC-EQ", "NSE:POWERGRID-EQ", "NSE:COALINDIA-EQ",
    "NSE:ULTRACEMCO-EQ", "NSE:AMBUJACEM-EQ", "NSE:ACC-EQ", "NSE:BHARTIARTL-EQ",
    "NSE:BAJFINANCE-EQ", "NSE:BAJAJFINSV-EQ", "NSE:HDFCLIFE-EQ", "NSE:SBILIFE-EQ",
    "NSE:LT-EQ", "NSE:DLF-EQ", "NSE:GODREJPROP-EQ", "NSE:INDIGO-EQ",
    "NSE:SPICEJET-EQ", "NSE:TITAN-EQ", "NSE:TRENT-EQ", "NSE:ADANIPORTS-EQ",
    "NSE:ADANIENT-EQ", "NSE:ADANIGREEN-EQ", "NSE:ADANIPOWER-EQ", "NSE:VEDL-EQ"
]

# Complete Sector Mapping - All 1000+ Symbols
SECTOR_MAPPING = {
    # Technology Sector
    "NSE:TCS-EQ": "Information Technology",
    "NSE:INFY-EQ": "Information Technology",
    "NSE:WIPRO-EQ": "Information Technology",
    "NSE:HCLTECH-EQ": "Information Technology",
    "NSE:TECHM-EQ": "Information Technology",
    "NSE:LTIM-EQ": "Information Technology",
    "NSE:LTTS-EQ": "Information Technology",
    "NSE:MINDTREE-EQ": "Information Technology",
    "NSE:COFORGE-EQ": "Information Technology",
    "NSE:PERSISTENT-EQ": "Information Technology",
    "NSE:CYIENT-EQ": "Information Technology",
    "NSE:MPHASIS-EQ": "Information Technology",
    "NSE:INTELLECT-EQ": "Information Technology",
    "NSE:TATAELXSI-EQ": "Information Technology",
    "NSE:KPITTECH-EQ": "Information Technology",
    "NSE:MASTEK-EQ": "Information Technology",
    "NSE:NEWGEN-EQ": "Information Technology",
    "NSE:CYIENTDLM-EQ": "Information Technology",
    "NSE:OFSS-EQ": "Information Technology",
    "NSE:ZENSAR-EQ": "Information Technology",
    
    # Banking & Financial Services
    "NSE:HDFCBANK-EQ": "Banking",
    "NSE:ICICIBANK-EQ": "Banking",
    "NSE:AXISBANK-EQ": "Banking",
    "NSE:SBIN-EQ": "Banking",
    "NSE:KOTAKBANK-EQ": "Banking",
    "NSE:INDUSINDBK-EQ": "Banking",
    "NSE:BANDHANBNK-EQ": "Banking",
    "NSE:IDFCFIRSTB-EQ": "Banking",
    "NSE:FEDERALBNK-EQ": "Banking",
    "NSE:RBLBANK-EQ": "Banking",
    "NSE:YESBANK-EQ": "Banking",
    "NSE:AUBANK-EQ": "Banking",
    "NSE:BANKBARODA-EQ": "Banking",
    "NSE:PNB-EQ": "Banking",
    "NSE:CANBK-EQ": "Banking",
    "NSE:UNIONBANK-EQ": "Banking",
    "NSE:BANKINDIA-EQ": "Banking",
    "NSE:CENTRALBK-EQ": "Banking",
    "NSE:IOB-EQ": "Banking",
    "NSE:PSB-EQ": "Banking",
    "NSE:IDBI-EQ": "Banking",
    "NSE:UCOBANK-EQ": "Banking",
    "NSE:INDIANB-EQ": "Banking",
    "NSE:CSBBANK-EQ": "Banking",
    "NSE:DCBBANK-EQ": "Banking",
    "NSE:SOUTHBANK-EQ": "Banking",
    "NSE:TMB-EQ": "Banking",
    "NSE:KTKBANK-EQ": "Banking",
    "NSE:J&KBANK-EQ": "Banking",
    "NSE:DHANBANK-EQ": "Banking",
    "NSE:MAHABANK-EQ": "Banking",
    "NSE:KARURVYSYA-EQ": "Banking",
    "NSE:CUB-EQ": "Banking",
    "NSE:UTKARSHBNK-EQ": "Banking",
    "NSE:ESAFSFB-EQ": "Banking",
    "NSE:UJJIVANSFB-EQ": "Banking",
    "NSE:EQUITASBNK-EQ": "Banking",
    "NSE:CAPITALSFB-EQ": "Banking",
    "NSE:SURYODAY-EQ": "Banking",
    "NSE:FINPIPE-EQ": "Banking",
    
    # Financial Services (Non-Banking)
    "NSE:BAJFINANCE-EQ": "Financial Services",
    "NSE:BAJAJFINSV-EQ": "Financial Services",
    "NSE:HDFCLIFE-EQ": "Financial Services",
    "NSE:SBILIFE-EQ": "Financial Services",
    "NSE:ICICIGI-EQ": "Financial Services",
    "NSE:ICICIPRULI-EQ": "Financial Services",
    "NSE:LICI-EQ": "Financial Services",
    "NSE:NIACL-EQ": "Financial Services",
    "NSE:GODIGIT-EQ": "Financial Services",
    "NSE:STARHEALTH-EQ": "Financial Services",
    "NSE:NIVABUPA-EQ": "Financial Services",
    "NSE:HDFCAMC-EQ": "Financial Services",
    "NSE:UTIAMC-EQ": "Financial Services",
    "NSE:CRISIL-EQ": "Financial Services",
    "NSE:CREDITACC-EQ": "Financial Services",
    "NSE:BFSL-EQ": "Financial Services",
    "NSE:CHOLAFIN-EQ": "Financial Services",
    "NSE:MUTHOOTFIN-EQ": "Financial Services",
    "NSE:MANAPPURAM-EQ": "Financial Services",
    "NSE:PFC-EQ": "Financial Services",
    "NSE:RECLTD-EQ": "Financial Services",
    "NSE:IRFC-EQ": "Financial Services",
    "NSE:EDELWEISS-EQ": "Financial Services",
    "NSE:IIFL-EQ": "Financial Services",
    "NSE:M&MFIN-EQ": "Financial Services",
    "NSE:SHRIRAMFIN-EQ": "Financial Services",
    "NSE:BAJAJHFL-EQ": "Financial Services",
    "NSE:CANFINHOME-EQ": "Financial Services",
    "NSE:LICHSGFIN-EQ": "Financial Services",
    "NSE:PNBHOUSING-EQ": "Financial Services",
    "NSE:REPCO-EQ": "Financial Services",
    "NSE:HOMEFIRST-EQ": "Financial Services",
    "NSE:INDOSTAR-EQ": "Financial Services",
    "NSE:SPANDANA-EQ": "Financial Services",
    "NSE:PAISALO-EQ": "Financial Services",
    "NSE:JSFB-EQ": "Financial Services",
    "NSE:SBFC-EQ": "Financial Services",
    "NSE:ASIANFIN-EQ": "Financial Services",
    "NSE:RELIGARE-EQ": "Financial Services",
    "NSE:MOTILALOFS-EQ": "Financial Services",
    "NSE:ANGELONE-EQ": "Financial Services",
    "NSE:ANANDRATHI-EQ": "Financial Services",
    "NSE:ARIHANTCAP-EQ": "Financial Services",
    "NSE:GEOJITFSL-EQ": "Financial Services",
    "NSE:NUVAMA-EQ": "Financial Services",
    "NSE:KFINTECH-EQ": "Financial Services",
    "NSE:CDSL-EQ": "Financial Services",
    "NSE:BSE-EQ": "Financial Services",
    "NSE:MCX-EQ": "Financial Services",
    "NSE:IEX-EQ": "Financial Services",
    "NSE:CAMS-EQ": "Financial Services",
    "NSE:JIOFIN-EQ": "Financial Services",
    
    # Oil & Gas / Energy
    "NSE:RELIANCE-EQ": "Oil & Gas",
    "NSE:ONGC-EQ": "Oil & Gas",
    "NSE:IOC-EQ": "Oil & Gas",
    "NSE:BPCL-EQ": "Oil & Gas",
    "NSE:HINDPETRO-EQ": "Oil & Gas",
    "NSE:GAIL-EQ": "Oil & Gas",
    "NSE:OIL-EQ": "Oil & Gas",
    "NSE:MGL-EQ": "Oil & Gas",
    "NSE:IGL-EQ": "Oil & Gas",
    "NSE:GUJGASLTD-EQ": "Oil & Gas",
    "NSE:ATGL-EQ": "Oil & Gas",
    "NSE:CASTROLIND-EQ": "Oil & Gas",
    "NSE:GULF-EQ": "Oil & Gas",
    "NSE:GULFOILLUB-EQ": "Oil & Gas",
    "NSE:GULFPETRO-EQ": "Oil & Gas",
    "NSE:HINDOILEXP-EQ": "Oil & Gas",
    "NSE:SELAN-EQ": "Oil & Gas",
    "NSE:MRPL-EQ": "Oil & Gas",
    "NSE:TNPETRO-EQ": "Oil & Gas",
    "NSE:CHENNPETRO-EQ": "Oil & Gas",
    "NSE:HINDNATGLS-EQ": "Oil & Gas",
    "NSE:GSPL-EQ": "Oil & Gas",
    "NSE:ADANIGAS-EQ": "Oil & Gas",
    "NSE:GSFC-EQ": "Oil & Gas",
    
    # Power / Utilities
    "NSE:NTPC-EQ": "Power",
    "NSE:POWERGRID-EQ": "Power",
    "NSE:COALINDIA-EQ": "Power",
    "NSE:TATAPOWER-EQ": "Power",
    "NSE:ADANIPOWER-EQ": "Power",
    "NSE:ADANIGREEN-EQ": "Power",
    "NSE:JSW-ENERGY-EQ": "Power",
    "NSE:NHPC-EQ": "Power",
    "NSE:SJVN-EQ": "Power",
    "NSE:IREDA-EQ": "Power",
    "NSE:NTPCGREEN-EQ": "Power",
    "NSE:ADANIENSOL-EQ": "Power",
    "NSE:SUZLON-EQ": "Power",
    "NSE:INOXWIND-EQ": "Power",
    "NSE:ORIENTGEN-EQ": "Power",
    "NSE:JPPOWER-EQ": "Power",
    "NSE:JPINFRATEC-EQ": "Power",
    "NSE:RPOWER-EQ": "Power",
    "NSE:TORNTPOWER-EQ": "Power",
    "NSE:CESC-EQ": "Power",
    "NSE:THERMAX-EQ": "Power",
    "NSE:KEC-EQ": "Power",
    "NSE:RTNPOWER-EQ": "Power",
    "NSE:JSWENERGY-EQ": "Power",
    "NSE:INOXGREEN-EQ": "Power",
    "NSE:WAAREEENER-EQ": "Power",
    "NSE:SWSOLAR-EQ": "Power",
    "NSE:SOLARINDS-EQ": "Power",
    "NSE:INOXWI-RE-EQ": "Power",
    "NSE:WEBSOL-EQ": "Power",
    "NSE:WEBELSOLAR-EQ": "Power",
    "NSE:GREENPOWER-EQ": "Power",
    "NSE:BOROSIL-EQ": "Power",
    
    # Automobiles
    "NSE:MARUTI-EQ": "Automobiles",
    "NSE:TATAMOTORS-EQ": "Automobiles",
    "NSE:M&M-EQ": "Automobiles",
    "NSE:EICHERMOT-EQ": "Automobiles",
    "NSE:BAJAJ-AUTO-EQ": "Automobiles",
    "NSE:HEROMOTOCO-EQ": "Automobiles",
    "NSE:TVSMOTOR-EQ": "Automobiles",
    "NSE:ASHOKLEY-EQ": "Automobiles",
    "NSE:ESCORTS-EQ": "Automobiles",
    "NSE:BALKRISIND-EQ": "Automobiles",
    "NSE:MRF-EQ": "Automobiles",
    "NSE:APOLLOTYRE-EQ": "Automobiles",
    "NSE:CEAT-EQ": "Automobiles",
    "NSE:JK-TYRE-EQ": "Automobiles",
    "NSE:MOTHERSON-EQ": "Automobiles",
    "NSE:BOSCHLTD-EQ": "Automobiles",
    "NSE:EXIDEIND-EQ": "Automobiles",
    "NSE:AMARON-EQ": "Automobiles",
    "NSE:SUNDARAM-EQ": "Automobiles",
    "NSE:TIINDIA-EQ": "Automobiles",
    "NSE:LUMAX-EQ": "Automobiles",
    "NSE:MINDA-EQ": "Automobiles",
    "NSE:ENDURANCE-EQ": "Automobiles",
    "NSE:SUPRAJIT-EQ": "Automobiles",
    "NSE:SUBROS-EQ": "Automobiles",
    "NSE:TEAMLEASE-EQ": "Automobiles",
    "NSE:FORCEMOT-EQ": "Automobiles",
    "NSE:SJS-EQ": "Automobiles",
    "NSE:SANSERA-EQ": "Automobiles",
    "NSE:SANDHAR-EQ": "Automobiles",
    "NSE:SCHAEFFLER-EQ": "Automobiles",
    "NSE:TALBROS-EQ": "Automobiles",
    "NSE:RALLIS-EQ": "Automobiles",
    "NSE:AAUTOIND-EQ": "Automobiles",
    "NSE:JAMNAAUTO-EQ": "Automobiles",
    "NSE:WHEELS-EQ": "Automobiles",
    "NSE:AUTOAXLES-EQ": "Automobiles",
    "NSE:PPAP-EQ": "Automobiles",
    "NSE:FIEM-EQ": "Automobiles",
    "NSE:GABRIEL-EQ": "Automobiles",
    "NSE:JTEKT-EQ": "Automobiles",
    "NSE:VARROC-EQ": "Automobiles",
    "NSE:MSUMI-EQ": "Automobiles",
    "NSE:UNOMINDA-EQ": "Automobiles",
    "NSE:UNIPARTS-EQ": "Automobiles",
    "NSE:RICOAUTO-EQ": "Automobiles",
    "NSE:RAMKRISHNA-EQ": "Automobiles",
    "NSE:ANANDRISHIJI-EQ": "Automobiles",
    "NSE:BAJAJHLD-EQ": "Automobiles",
    "NSE:VINATIORGA-EQ": "Automobiles",
    "NSE:BAJAJCON-EQ": "Automobiles",
    "NSE:HINDMOTORS-EQ": "Automobiles",
    "NSE:OMAXAUTO-EQ": "Automobiles",
    "NSE:BHEL-EQ": "Automobiles",
    "NSE:HINDCOPPER-EQ": "Automobiles",
    "NSE:ATULAUTO-EQ": "Automobiles",
    "NSE:SHIVAMILLS-EQ": "Automobiles",
    "NSE:CUMMINSIND-EQ": "Automobiles",
    "NSE:HONDAPOWER-EQ": "Automobiles",
    "NSE:KIRLOSKP-EQ": "Automobiles",
    "NSE:SETCO-EQ": "Automobiles",
    "NSE:MAGMA-EQ": "Automobiles",
    "NSE:OLECTRA-EQ": "Automobiles",
    "NSE:OLAELEC-EQ": "Automobiles",
    "NSE:HYUNDAI-EQ": "Automobiles",
    "NSE:MAHINDCIE-EQ": "Automobiles",
    
    # Metals & Mining
    "NSE:TATASTEEL-EQ": "Metals & Mining",
    "NSE:HINDALCO-EQ": "Metals & Mining",
    "NSE:JSWSTEEL-EQ": "Metals & Mining",
    "NSE:SAIL-EQ": "Metals & Mining",
    "NSE:VEDL-EQ": "Metals & Mining",
    "NSE:HINDZINC-EQ": "Metals & Mining",
    "NSE:JINDALSTEL-EQ": "Metals & Mining",
    "NSE:NMDC-EQ": "Metals & Mining",
    "NSE:MOIL-EQ": "Metals & Mining",
    "NSE:NATIONALUM-EQ": "Metals & Mining",
    "NSE:BALRAMCHIN-EQ": "Metals & Mining",
    "NSE:APL-EQ": "Metals & Mining",
    "NSE:RATNAMANI-EQ": "Metals & Mining",
    "NSE:WELSPUNIND-EQ": "Metals & Mining",
    "NSE:JINDALPOLY-EQ": "Metals & Mining",
    "NSE:ORIENTCEM-EQ": "Metals & Mining",
    "NSE:STEELXIND-EQ": "Metals & Mining",
    "NSE:LLOYDSME-EQ": "Metals & Mining",
    "NSE:VISAKAIND-EQ": "Metals & Mining",
    "NSE:ARSS-EQ": "Metals & Mining",
    "NSE:KALYANI-EQ": "Metals & Mining",
    "NSE:KALYANIFRG-EQ": "Metals & Mining",
    "NSE:GRAPHITE-EQ": "Metals & Mining",
    "NSE:UGARSUGAR-EQ": "Metals & Mining",
    "NSE:RSWM-EQ": "Metals & Mining",
    "NSE:RAIN-EQ": "Metals & Mining",
    "NSE:GRAVITA-EQ": "Metals & Mining",
    "NSE:GVKPIL-EQ": "Metals & Mining",
    "NSE:MANORG-EQ": "Metals & Mining",
    "NSE:JKLAKSHMI-EQ": "Metals & Mining",
    "NSE:SREESTEEL-EQ": "Metals & Mining",
    "NSE:SUNFLAG-EQ": "Metals & Mining",
    "NSE:FACOR-EQ": "Metals & Mining",
    "NSE:BHUSHAN-EQ": "Metals & Mining",
    "NSE:ROHLTD-EQ": "Metals & Mining",
    "NSE:ZENITHSTL-EQ": "Metals & Mining",
    "NSE:VISHNU-EQ": "Metals & Mining",
    "NSE:UTTAMSTL-EQ": "Metals & Mining",
    "NSE:INDIACEM-EQ": "Metals & Mining",
    "NSE:RAMCOCEM-EQ": "Metals & Mining",
    "NSE:DALMIA-EQ": "Metals & Mining",
    "NSE:CENTURYPLY-EQ": "Metals & Mining",
    "NSE:CENTEXT-EQ": "Metals & Mining",
    "NSE:MAGNESITA-EQ": "Metals & Mining",
    "NSE:ORIENTREFR-EQ": "Metals & Mining",
    "NSE:MADRASFERT-EQ": "Metals & Mining",
    "NSE:MANDHANA-EQ": "Metals & Mining",
    "NSE:RAMASTEEL-EQ": "Metals & Mining",
    "NSE:PALLADINESTEEL-EQ": "Metals & Mining",
    "NSE:PALREDTEC-EQ": "Metals & Mining",
    "NSE:SALSTEEL-EQ": "Metals & Mining",
    "NSE:VSTL-EQ": "Metals & Mining",
    "NSE:STEELCAS-EQ": "Metals & Mining",
    "NSE:STEELCITY-EQ": "Metals & Mining",
    "NSE:STEL-EQ": "Metals & Mining",
    "NSE:SUNSTEEL-EQ": "Metals & Mining",
    "NSE:MAHASTEEL-EQ": "Metals & Mining",
    "NSE:HISARMETAL-EQ": "Metals & Mining",
    "NSE:ISGEC-EQ": "Metals & Mining",
    "NSE:KDDL-EQ": "Metals & Mining",
    "NSE:KIOCL-EQ": "Metals & Mining",
    "NSE:MEP-EQ": "Metals & Mining",
    "NSE:METALFORGE-EQ": "Metals & Mining",
    "NSE:MITTAL-EQ": "Metals & Mining",
    "NSE:MUKANDLTD-EQ": "Metals & Mining",
    "NSE:NCML-EQ": "Metals & Mining",
    "NSE:ORISSAMINE-EQ": "Metals & Mining",
    "NSE:POKARNA-EQ": "Metals & Mining",
    "NSE:RAMCOIND-EQ": "Metals & Mining",
    "NSE:SAMTEL-EQ": "Metals & Mining",
    "NSE:SILGO-EQ": "Metals & Mining",
    "NSE:UTTAM-EQ": "Metals & Mining",
    "NSE:WALCHANNAG-EQ": "Metals & Mining",
    "NSE:WELSPUN-EQ": "Metals & Mining",
    "NSE:ADANIENT-EQ": "Metals & Mining",
    "NSE:BEML-EQ": "Metals & Mining",
    
    # Pharmaceutical & Healthcare
    "NSE:SUNPHARMA-EQ": "Pharmaceuticals",
    "NSE:DRREDDY-EQ": "Pharmaceuticals",
    "NSE:CIPLA-EQ": "Pharmaceuticals",
    "NSE:DIVISLAB-EQ": "Pharmaceuticals",
    "NSE:LUPIN-EQ": "Pharmaceuticals",
    "NSE:BIOCON-EQ": "Pharmaceuticals",
    "NSE:AUROPHARMA-EQ": "Pharmaceuticals",
    "NSE:TORNTPHARM-EQ": "Pharmaceuticals",
    "NSE:GLENMARK-EQ": "Pharmaceuticals",
    "NSE:CADILAHC-EQ": "Pharmaceuticals",
    "NSE:ALKEM-EQ": "Pharmaceuticals",
    "NSE:LALPATHLAB-EQ": "Pharmaceuticals",
    "NSE:METROPOLIS-EQ": "Pharmaceuticals",
    "NSE:FORTIS-EQ": "Pharmaceuticals",
    "NSE:APOLLOHOSP-EQ": "Pharmaceuticals",
    "NSE:HCG-EQ": "Pharmaceuticals",
    "NSE:MAXHEALTH-EQ": "Pharmaceuticals",
    "NSE:NARAYANHRU-EQ": "Pharmaceuticals",
    "NSE:RAINBOWHSPL-EQ": "Pharmaceuticals",
    "NSE:KRSNAA-EQ": "Pharmaceuticals",
    "NSE:MEDANTA-EQ": "Pharmaceuticals",
    "NSE:KIMS-EQ": "Pharmaceuticals",
    "NSE:SHALBY-EQ": "Pharmaceuticals",
    "NSE:THYROCARE-EQ": "Pharmaceuticals",
    "NSE:SEQUENT-EQ": "Pharmaceuticals",
    "NSE:GRANULES-EQ": "Pharmaceuticals",
    "NSE:LAURUSLABS-EQ": "Pharmaceuticals",
    "NSE:JUBLPHARMA-EQ": "Pharmaceuticals",
    "NSE:CAPLIN-EQ": "Pharmaceuticals",
    "NSE:AJANTPHARM-EQ": "Pharmaceuticals",
    "NSE:ERIS-EQ": "Pharmaceuticals",
    "NSE:SUVEN-EQ": "Pharmaceuticals",
    "NSE:NATCOPHARM-EQ": "Pharmaceuticals",
    "NSE:STRIDES-EQ": "Pharmaceuticals",
    "NSE:GUFICBIO-EQ": "Pharmaceuticals",
    "NSE:MARKSANS-EQ": "Pharmaceuticals",
    "NSE:SOLARA-EQ": "Pharmaceuticals",
    "NSE:ORCHPHARMA-EQ": "Pharmaceuticals",
    "NSE:IPCA-EQ": "Pharmaceuticals",
    "NSE:IPCALAB-EQ": "Pharmaceuticals",
    "NSE:SYNGENE-EQ": "Pharmaceuticals",
    "NSE:BLISSGVS-EQ": "Pharmaceuticals",
    "NSE:NEULANDLAB-EQ": "Pharmaceuticals",
    "NSE:MANKIND-EQ": "Pharmaceuticals",
    "NSE:EMCURE-EQ": "Pharmaceuticals",
    "NSE:PFIZER-EQ": "Pharmaceuticals",
    "NSE:GLAXO-EQ": "Pharmaceuticals",
    "NSE:ABBOTINDIA-EQ": "Pharmaceuticals",
    "NSE:SANOFI-EQ": "Pharmaceuticals",
    "NSE:NOVARTIS-EQ": "Pharmaceuticals",
    "NSE:MSD-EQ": "Pharmaceuticals",
    "NSE:BAYER-EQ": "Pharmaceuticals",
    "NSE:WOCKPHARMA-EQ": "Pharmaceuticals",
    "NSE:INDOCO-EQ": "Pharmaceuticals",
    "NSE:FDC-EQ": "Pharmaceuticals",
    "NSE:CENTRALDRUG-EQ": "Pharmaceuticals",
    "NSE:JAGSONPAL-EQ": "Pharmaceuticals",
    "NSE:ARISTO-EQ": "Pharmaceuticals",
    "NSE:ALEMBICLTD-EQ": "Pharmaceuticals",
    "NSE:UNICHEMLAB-EQ": "Pharmaceuticals",
    "NSE:MOREPEN-EQ": "Pharmaceuticals",
    "NSE:UNICHEM-EQ": "Pharmaceuticals",
    "NSE:ADVENZYMES-EQ": "Pharmaceuticals",
    "NSE:TATACHEM-EQ": "Pharmaceuticals",
    "NSE:DEEPAKNTR-EQ": "Pharmaceuticals",
    "NSE:PIDILITIND-EQ": "Pharmaceuticals",
    "NSE:AKZOINDIA-EQ": "Pharmaceuticals",
    
    # FMCG & Consumer Goods
    "NSE:HINDUNILVR-EQ": "FMCG",
    "NSE:ITC-EQ": "FMCG",
    "NSE:BRITANNIA-EQ": "FMCG",
    "NSE:NESTLEIND-EQ": "FMCG",
    "NSE:DABUR-EQ": "FMCG",
    "NSE:GODREJCP-EQ": "FMCG",
    "NSE:MARICO-EQ": "FMCG",
    "NSE:COLPAL-EQ": "FMCG",
    "NSE:EMAMILTD-EQ": "FMCG",
    "NSE:JYOTHYLAB-EQ": "FMCG",
    "NSE:GILLETTE-EQ": "FMCG",
    "NSE:PGHH-EQ": "FMCG",
    "NSE:TATACONSUM-EQ": "FMCG",
    "NSE:UBL-EQ": "FMCG",
    "NSE:PATANJALI-EQ": "FMCG",
    "NSE:RADICO-EQ": "FMCG",
    "NSE:MCDOWELL-EQ": "FMCG",
    "NSE:VSTIND-EQ": "FMCG",
    "NSE:KPRMILL-EQ": "FMCG",
    "NSE:WELSPUNLIV-EQ": "FMCG",
    "NSE:VMART-EQ": "FMCG",
    "NSE:TRENT-EQ": "FMCG",
    "NSE:SHOPERSTOP-EQ": "FMCG",
    "NSE:ADITYA-EQ": "FMCG",
    "NSE:VENKEYS-EQ": "FMCG",
    "NSE:HATSUN-EQ": "FMCG",
    "NSE:SULA-EQ": "FMCG",
    "NSE:TASTYBITE-EQ": "FMCG",
    "NSE:BIKAJI-EQ": "FMCG",
    "NSE:JUBLFOOD-EQ": "FMCG",
    "NSE:HERITGFOOD-EQ": "FMCG",
    "NSE:GOCOLORS-EQ": "FMCG",
    "NSE:NYKAA-EQ": "FMCG",
    "NSE:HONASA-EQ": "FMCG",
    "NSE:MANYAVAR-EQ": "FMCG",
    "NSE:AHLUWALIA-EQ": "FMCG",
    "NSE:RELAXO-EQ": "FMCG",
    "NSE:BATA-EQ": "FMCG",
    "NSE:LIBERTSHOE-EQ": "FMCG",
    "NSE:KHADIM-EQ": "FMCG",
    "NSE:MIRZA-EQ": "FMCG",
    "NSE:VIP-EQ": "FMCG",
    "NSE:SKUMAR-EQ": "FMCG",
    "NSE:SYMPHONY-EQ": "FMCG",
    "NSE:VOLTAS-EQ": "FMCG",
    "NSE:BLUESTARCO-EQ": "FMCG",
    "NSE:HAVELLS-EQ": "FMCG",
    "NSE:CROMPTON-EQ": "FMCG",
    "NSE:ORIENT-EQ": "FMCG",
    "NSE:WHIRLPOOL-EQ": "FMCG",
    "NSE:AMBER-EQ": "FMCG",
    "NSE:BAJAJHCARE-EQ": "FMCG",
    "NSE:VGUARD-EQ": "FMCG",
    "NSE:POLYCAB-EQ": "FMCG",
    "NSE:FINOLEX-EQ": "FMCG",
    "NSE:KEI-EQ": "FMCG",
    "NSE:DIXON-EQ": "FMCG",
    "NSE:TITAN-EQ": "FMCG",
    "NSE:KALYAN-EQ": "FMCG",
    "NSE:THANGAMAY-EQ": "FMCG",
    "NSE:SENCO-EQ": "FMCG",
    "NSE:TBZ-EQ": "FMCG",
    "NSE:PCJEWELLER-EQ": "FMCG",
    "NSE:GITANJALI-EQ": "FMCG",
    
    # Cement & Construction
    "NSE:ULTRACEMCO-EQ": "Cement",
    "NSE:AMBUJACEM-EQ": "Cement",
    "NSE:ACC-EQ": "Cement",
    "NSE:SHREECEM-EQ": "Cement",
    "NSE:JKCEMENT-EQ": "Cement",
    "NSE:HEIDELBERG-EQ": "Cement",
    "NSE:RAMCOCEM-EQ": "Cement",
    "NSE:INDIACEM-EQ": "Cement",
    "NSE:KAKATCEM-EQ": "Cement",
    "NSE:KESORAMIND-EQ": "Cement",
    "NSE:NUVOCO-EQ": "Cement",
    "NSE:STARCEMENT-EQ": "Cement",
    "NSE:PRISMCEM-EQ": "Cement",
    "NSE:UDAICEMENT-EQ": "Cement",
    "NSE:MAGADH-EQ": "Cement",
    "NSE:SAURASHCEM-EQ": "Cement",
    "NSE:MANGLMCEM-EQ": "Cement",
    "NSE:DECCAN-EQ": "Cement",
    
    # Construction & Infrastructure
    "NSE:LT-EQ": "Construction",
    "NSE:DLF-EQ": "Real Estate",
    "NSE:GODREJPROP-EQ": "Real Estate",
    "NSE:OBEROIRLTY-EQ": "Real Estate",
    "NSE:BRIGADE-EQ": "Real Estate",
    "NSE:PHOENIXMILLS-EQ": "Real Estate",
    "NSE:PRESTIGE-EQ": "Real Estate",
    "NSE:SOBHA-EQ": "Real Estate",
    "NSE:SUNTECK-EQ": "Real Estate",
    "NSE:KOLTEPATIL-EQ": "Real Estate",
    "NSE:MAHLIFE-EQ": "Real Estate",
    "NSE:LODHA-EQ": "Real Estate",
    "NSE:SIGNATURE-EQ": "Real Estate",
    "NSE:RUSTOMJEE-EQ": "Real Estate",
    "NSE:MIDHANI-EQ": "Construction",
    "NSE:IRCON-EQ": "Construction",
    "NSE:RITES-EQ": "Construction",
    "NSE:RVNL-EQ": "Construction",
    "NSE:RAILTEL-EQ": "Construction",
    "NSE:CONCOR-EQ": "Construction",
    "NSE:NCC-EQ": "Construction",
    "NSE:HCC-EQ": "Construction",
    "NSE:IRB-EQ": "Construction",
    "NSE:SADBHAV-EQ": "Construction",
    "NSE:ASHOKA-EQ": "Construction",
    "NSE:KNR-EQ": "Construction",
    "NSE:PNC-EQ": "Construction",
    "NSE:PATEL-EQ": "Construction",
    "NSE:ARSS-EQ": "Construction",
    "NSE:NBCC-EQ": "Construction",
    "NSE:HUDCO-EQ": "Construction",
    "NSE:KALPATARU-EQ": "Construction",
    "NSE:GPIL-EQ": "Construction",
    "NSE:BRLM-EQ": "Construction",
    "NSE:IGARASHI-EQ": "Construction",
    "NSE:AIA-EQ": "Construction",
    "NSE:TITAGARH-EQ": "Construction",
    "NSE:TEXRAIL-EQ": "Construction",
    "NSE:MUKANDENG-EQ": "Construction",
    "NSE:BEL-EQ": "Construction",
    "NSE:HAL-EQ": "Construction",
    "NSE:GRSE-EQ": "Construction",
    "NSE:COCHINSHIP-EQ": "Construction",
    "NSE:MAZAGON-EQ": "Construction",
    "NSE:LXCHEM-EQ": "Construction",
    "NSE:HINDWAREAP-EQ": "Construction",
    "NSE:CERA-EQ": "Construction",
    "NSE:HSIL-EQ": "Construction",
    "NSE:SOMANY-EQ": "Construction",
    "NSE:KAJARIACER-EQ": "Construction",
    "NSE:ORIENTBELL-EQ": "Construction",
    "NSE:NITCO-EQ": "Construction",
    "NSE:ASTRAL-EQ": "Construction",
    "NSE:SUPREME-EQ": "Construction",
    "NSE:NILKAMAL-EQ": "Construction",
    "NSE:SINTEX-EQ": "Construction",
    "NSE:KANSAINER-EQ": "Construction",
    "NSE:PRINCEPIPE-EQ": "Construction",
    "NSE:APOLLOPIPE-EQ": "Construction",
    
    # Agriculture & Fertilizers
    "NSE:UPL-EQ": "Agriculture",
    "NSE:GODREJAGRO-EQ": "Agriculture",
    "NSE:SUMICHEM-EQ": "Agriculture",
    "NSE:BASF-EQ": "Agriculture",
    "NSE:INSECTICID-EQ": "Agriculture",
    "NSE:DHANUKA-EQ": "Agriculture",
    "NSE:SHARDACROP-EQ": "Agriculture",
    "NSE:HERANBA-EQ": "Agriculture",
    "NSE:BHARAT-EQ": "Agriculture",
    "NSE:FACT-EQ": "Agriculture",
    "NSE:RCF-EQ": "Agriculture",
    "NSE:NFL-EQ": "Agriculture",
    "NSE:CHAMBLFERT-EQ": "Agriculture",
    "NSE:KRIBHCO-EQ": "Agriculture",
    "NSE:ZUARIAGRO-EQ": "Agriculture",
    "NSE:DEEPAKFERT-EQ": "Agriculture",
    "NSE:MADRAS-EQ": "Agriculture",
    "NSE:SOUTHERN-EQ": "Agriculture",
    "NSE:MANGALORE-EQ": "Agriculture",
    "NSE:NAGARJUNA-EQ": "Agriculture",
    "NSE:PARADEEP-EQ": "Agriculture",
    "NSE:COROMANDEL-EQ": "Agriculture",
    "NSE:IFCO-EQ": "Agriculture",
    "NSE:KHAITAN-EQ": "Agriculture",
    "NSE:KRBL-EQ": "Agriculture",
    "NSE:USHAMART-EQ": "Agriculture",
    "NSE:LAXMIORG-EQ": "Agriculture",
    "NSE:PREMIER-EQ": "Agriculture",
    "NSE:AVANTIFEED-EQ": "Agriculture",
    "NSE:GODHA-EQ": "Agriculture",
    "NSE:RUCHISOYA-EQ": "Agriculture",
    "NSE:ADANIWILMAR-EQ": "Agriculture",
    "NSE:BAJAJHIND-EQ": "Agriculture",
    "NSE:JUBLAGRI-EQ": "Agriculture",
    "NSE:PARAS-EQ": "Agriculture",
    "NSE:JKAGRI-EQ": "Agriculture",
    "NSE:NAVRATNA-EQ": "Agriculture",
    "NSE:NATIONAL-EQ": "Agriculture",
    "NSE:RAJSHREE-EQ": "Agriculture",
    "NSE:DWARIKESH-EQ": "Agriculture",
    "NSE:TRIVENI-EQ": "Agriculture",
    "NSE:BALRAMPUR-EQ": "Agriculture",
    "NSE:KOTHARI-EQ": "Agriculture",
    "NSE:MAWANA-EQ": "Agriculture",
    "NSE:DHAMPURSUG-EQ": "Agriculture",
    "NSE:RENUKA-EQ": "Agriculture",
    "NSE:KSL-EQ": "Agriculture",
    "NSE:TIRUPATI-EQ": "Agriculture",
    "NSE:SAKAR-EQ": "Agriculture",
    "NSE:VISHWARAJ-EQ": "Agriculture",
    "NSE:SAKTISUG-EQ": "Agriculture",
    "NSE:ANDHRSUGAR-EQ": "Agriculture",
    "NSE:BANNARI-EQ": "Agriculture",
    "NSE:MAGADSUGAR-EQ": "Agriculture",
    "NSE:AVADHSUGAR-EQ": "Agriculture",
    
    # Textiles
    "NSE:ARVIND-EQ": "Textiles",
    "NSE:TRIDENT-EQ": "Textiles",
    "NSE:VARDHMAN-EQ": "Textiles",
    "NSE:SUTLEJ-EQ": "Textiles",
    "NSE:GRASIM-EQ": "Textiles",
    "NSE:SPENTEX-EQ": "Textiles",
    "NSE:INDORAMA-EQ": "Textiles",
    "NSE:FILATEX-EQ": "Textiles",
    "NSE:ALOKTEXT-EQ": "Textiles",
    "NSE:BTIL-EQ": "Textiles",
    "NSE:MAFATLAL-EQ": "Textiles",
    "NSE:RAYMOND-EQ": "Textiles",
    "NSE:VIPIND-EQ": "Textiles",
    "NSE:DONEAR-EQ": "Textiles",
    "NSE:HIMATSEIDE-EQ": "Textiles",
    "NSE:CENTUM-EQ": "Textiles",
    "NSE:DOLLAR-EQ": "Textiles",
    "NSE:KITEX-EQ": "Textiles",
    "NSE:SHIVTEX-EQ": "Textiles",
    "NSE:BANSWARA-EQ": "Textiles",
    "NSE:BSL-EQ": "Textiles",
    "NSE:ALBK-EQ": "Textiles",
    "NSE:BIRLA-EQ": "Textiles",
    "NSE:DHANVARSHA-EQ": "Textiles",
    "NSE:GTN-EQ": "Textiles",
    "NSE:GOKUL-EQ": "Textiles",
    "NSE:HIRA-EQ": "Textiles",
    "NSE:KGDENIM-EQ": "Textiles",
    "NSE:LOYAL-EQ": "Textiles",
    "NSE:MONACO-EQ": "Textiles",
    "NSE:MSP-EQ": "Textiles",
    "NSE:NAHAR-EQ": "Textiles",
    "NSE:NITIN-EQ": "Textiles",
    "NSE:PRADEEP-EQ": "Textiles",
    "NSE:SARLA-EQ": "Textiles",
    "NSE:SHANTIGEAR-EQ": "Textiles",
    "NSE:SOMATEX-EQ": "Textiles",
    "NSE:STYLAMIND-EQ": "Textiles",
    "NSE:TEXINFRA-EQ": "Textiles",
    "NSE:TEXMOPIPES-EQ": "Textiles",
    "NSE:UNIPHOS-EQ": "Textiles",
    "NSE:VARDHACRLC-EQ": "Textiles",
    "NSE:VARDMNPOLY-EQ": "Textiles",
    "NSE:WEIZMANIND-EQ": "Textiles",
    "NSE:WELSPUNLIV-EQ": "Textiles",
    
    # Media & Entertainment
    "NSE:ZEEL-EQ": "Media",
    "NSE:SUNTV-EQ": "Media",
    "NSE:PVRINOX-EQ": "Media",
    "NSE:NETWORK18-EQ": "Media",
    "NSE:TV18BRDCST-EQ": "Media",
    "NSE:JAGRAN-EQ": "Media",
    "NSE:SAREGAMA-EQ": "Media",
    "NSE:TIPSFILMS-EQ": "Media",
    "NSE:TIPSMUSIC-EQ": "Media",
    "NSE:RADIOCITY-EQ": "Media",
    "NSE:DBCORP-EQ": "Media",
    "NSE:HTMEDIA-EQ": "Media",
    "NSE:NAVNETEDUL-EQ": "Media",
    "NSE:NAZARA-EQ": "Media",
    "NSE:ONMOBILE-EQ": "Media",
    "NSE:UFO-EQ": "Media",
    "NSE:EROS-EQ": "Media",
    "NSE:BALAJITELE-EQ": "Media",
    "NSE:CINELINE-EQ": "Media",
    "NSE:CINEVISTA-EQ": "Media",
    "NSE:CELEBRITY-EQ": "Media",
    "NSE:SHEMAROO-EQ": "Media",
    "NSE:YASHRAJ-EQ": "Media",
    "NSE:PRITIKA-EQ": "Media",
    "NSE:RELCAPITAL-EQ": "Media",
    "NSE:RELMEDIA-EQ": "Media",
    "NSE:NEXTMEDIA-EQ": "Media",
    
    # Telecommunications
    "NSE:BHARTIARTL-EQ": "Telecommunications",
    "NSE:RJIO-EQ": "Telecommunications",
    "NSE:IDEA-EQ": "Telecommunications",
    "NSE:BSNL-EQ": "Telecommunications",
    "NSE:MTNL-EQ": "Telecommunications",
    "NSE:HFCL-EQ": "Telecommunications",
    "NSE:STLTECH-EQ": "Telecommunications",
    "NSE:GTPL-EQ": "Telecommunications",
    "NSE:DEN-EQ": "Telecommunications",
    "NSE:HATHWAY-EQ": "Telecommunications",
    "NSE:SITI-EQ": "Telecommunications",
    "NSE:ORTEL-EQ": "Telecommunications",
    "NSE:TEJAS-EQ": "Telecommunications",
    "NSE:RCOM-EQ": "Telecommunications",
    "NSE:OPTIEMUS-EQ": "Telecommunications",
    "NSE:ONEPOINT-EQ": "Telecommunications",
    "NSE:CIGNITITEC-EQ": "Telecommunications",
    "NSE:SMARTLINK-EQ": "Telecommunications",
    "NSE:VINDHYATEL-EQ": "Telecommunications",
    "NSE:TATACOMM-EQ": "Telecommunications",
    "NSE:TANLA-EQ": "Telecommunications",
    "NSE:ROUTE-EQ": "Telecommunications",
    "NSE:ZENTEC-EQ": "Telecommunications",
    "NSE:MOSCHIP-EQ": "Telecommunications",
    
    # Travel & Transportation
    "NSE:INDIGO-EQ": "Travel & Transport",
    "NSE:SPICEJET-EQ": "Travel & Transport",
    "NSE:JETAIRWAYS-EQ": "Travel & Transport",
    "NSE:TCI-EQ": "Travel & Transport",
    "NSE:VTL-EQ": "Travel & Transport",
    "NSE:ALLCARGO-EQ": "Travel & Transport",
    "NSE:BLUEDART-EQ": "Travel & Transport",
    "NSE:DELHIVERY-EQ": "Travel & Transport",
    "NSE:MAHLOG-EQ": "Travel & Transport",
    "NSE:SICAL-EQ": "Travel & Transport",
    "NSE:SNOWMAN-EQ": "Travel & Transport",
    "NSE:GATI-EQ": "Travel & Transport",
    "NSE:APOLLO-EQ": "Travel & Transport",
    "NSE:AEGISLOG-EQ": "Travel & Transport",
    "NSE:THOMASCOOK-EQ": "Travel & Transport",
    "NSE:COX&KINGS-EQ": "Travel & Transport",
    "NSE:KESARENT-EQ": "Travel & Transport",
    "NSE:YATRA-EQ": "Travel & Transport",
    "NSE:MAKEMYTRIP-EQ": "Travel & Transport",
    "NSE:EASEMYTRIP-EQ": "Travel & Transport",
    "NSE:IXIGO-EQ": "Travel & Transport",
    "NSE:ADANIPORTS-EQ": "Travel & Transport",
    "NSE:JSWINFRA-EQ": "Travel & Transport",
    "NSE:MHRIL-EQ": "Travel & Transport",
    "NSE:ESSELPACK-EQ": "Travel & Transport",
    "NSE:SAGCEM-EQ": "Travel & Transport",
    
    # Hotels & Tourism
    "NSE:INDIANHOTELS-EQ": "Hotels & Tourism",
    "NSE:LEMONTREE-EQ": "Hotels & Tourism",
    "NSE:CHALET-EQ": "Hotels & Tourism",
    "NSE:MAHINDRA-EQ": "Hotels & Tourism",
    "NSE:EIHOTEL-EQ": "Hotels & Tourism",
    "NSE:ITCHOTELS-EQ": "Hotels & Tourism",
    "NSE:ORIENTHOT-EQ": "Hotels & Tourism",
    "NSE:LEMON-EQ": "Hotels & Tourism",
    "NSE:TGBHOTELS-EQ": "Hotels & Tourism",
    "NSE:PARKHOTELS-EQ": "Hotels & Tourism",
    "NSE:KAMAT-EQ": "Hotels & Tourism",
    "NSE:ADVANI-EQ": "Hotels & Tourism",
    "NSE:SAMHI-EQ": "Hotels & Tourism",
    
    # Diversified & Conglomerates
    "NSE:RELIANCE-EQ": "Diversified",
    "NSE:BAJAJHLDNG-EQ": "Diversified",
    "NSE:GODREJIND-EQ": "Diversified",
    "NSE:SIEMENS-EQ": "Diversified",
    "NSE:ABB-EQ": "Diversified",
    "NSE:HONEYWELL-EQ": "Diversified",
    "NSE:3M-EQ": "Diversified",
    "NSE:TATA-EQ": "Diversified",
    "NSE:BHARTI-EQ": "Diversified",
    "NSE:ESSAR-EQ": "Diversified",
    "NSE:JAIPRAKASH-EQ": "Diversified",
    "NSE:GAMMON-EQ": "Diversified",
    "NSE:PUNJ-EQ": "Diversified",
    "NSE:LANCO-EQ": "Diversified",
    "NSE:GMR-EQ": "Diversified",
    "NSE:GVK-EQ": "Diversified",
    "NSE:SIMPLEX-EQ": "Diversified",
    "NSE:EMKAY-EQ": "Diversified"
}

def get_sector_for_symbol(symbol):
    """Get sector for a given symbol"""
    return SECTOR_MAPPING.get(symbol, "Others")

# Extract ALL symbols from the sector mapping for monitoring
STOCK_SYMBOLS = list(SECTOR_MAPPING.keys())

# =============================================================================
# SETUP LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fyers_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# FLASK WEB APPLICATION
# =============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# =============================================================================
# BOT STATE MANAGEMENT
# =============================================================================

class BotState:
    def __init__(self):
        self.is_running = False
        self.is_authenticated = False
        self.last_heartbeat = None
        self.total_trades = 0
        self.session_start = None
        self.auth_url = None
        self.waiting_for_auth = False
        self.load_state()
    
    def load_state(self):
        try:
            if os.path.exists(BOT_STATE_FILE):
                with open(BOT_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.total_trades = data.get('total_trades', 0)
                    self.last_heartbeat = data.get('last_heartbeat')
        except Exception as e:
            logger.error(f"Error loading bot state: {e}")
    
    def save_state(self):
        try:
            data = {
                'total_trades': self.total_trades,
                'last_heartbeat': self.last_heartbeat,
                'timestamp': datetime.now().isoformat()
            }
            with open(BOT_STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving bot state: {e}")

bot_state = BotState()

# =============================================================================
# EMAIL UTILITIES
# =============================================================================

def send_email(subject, body, is_html=False):
    """Send email notification"""
    try:
        if not EMAIL_USERNAME or not EMAIL_PASSWORD or not EMAIL_TO:
            logger.warning("Email credentials not configured")
            return False
        
        msg = MimeMultipart()
        msg['From'] = EMAIL_USERNAME
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        
        msg.attach(MimeText(body, 'html' if is_html else 'plain'))
        
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

# =============================================================================
# FYERS AUTHENTICATION
# =============================================================================

class FyersAuthenticator:
    def __init__(self):
        self.client_id = FYERS_CLIENT_ID
        self.secret_key = FYERS_SECRET_KEY
        self.redirect_uri = FYERS_REDIRECT_URI
        self.totp_secret = FYERS_TOTP_SECRET
        self.pin = FYERS_PIN
        self.access_token = None
        self.fyers_model = None
        
    def generate_totp(self):
        totp = pyotp.TOTP(self.totp_secret)
        return totp.now()
    
    def load_saved_token(self):
        try:
            if os.path.exists(ACCESS_TOKEN_FILE):
                with open(ACCESS_TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                
                current_time = time.time()
                token_time = token_data.get('timestamp', 0)
                
                # Check if token is still valid (8 hours)
                if current_time - token_time < 28800:
                    self.access_token = token_data['access_token']
                    logger.info("Using saved access token")
                    return True
                else:
                    logger.info("Saved token expired")
                    os.remove(ACCESS_TOKEN_FILE)
            
            return False
        except Exception as e:
            logger.error(f"Error loading saved token: {e}")
            return False
    
    def save_token(self, token):
        token_data = {
            'access_token': token,
            'timestamp': time.time(),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(ACCESS_TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        logger.info("Access token saved")
    
    def generate_auth_url(self):
        """Generate authentication URL and send via email"""
        try:
            session = fyersModel.SessionModel(
                client_id=self.client_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            
            auth_url = session.generate_authcode()
            totp_code = self.generate_totp()
            
            # Store auth URL
            bot_state.auth_url = auth_url
            bot_state.waiting_for_auth = True
            
            # Send email with auth URL and TOTP
            subject = "🔐 Fyers Authentication Required"
            body = f"""
            <h2>Fyers Trading Bot Authentication</h2>
            <p><strong>Please authenticate your Fyers account:</strong></p>
            
            <p><a href="{auth_url}" target="_blank" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            🔗 Click Here to Authenticate</a></p>
            
            <p><strong>TOTP Code (if required):</strong> <code style="background-color: #f0f0f0; padding: 5px; font-size: 18px;">{totp_code}</code></p>
            
            <p><strong>Instructions:</strong></p>
            <ol>
                <li>Click the authentication link above</li>
                <li>Login with your Fyers credentials</li>
                <li>Use the TOTP code if prompted for 2FA</li>
                <li>After successful login, copy the 'auth_code' from the redirect URL</li>
                <li>Enter the auth_code in the bot's web interface</li>
            </ol>
            
            <p><strong>Web Interface:</strong> <a href="http://your-app-url.onrender.com">Bot Dashboard</a></p>
            
            <hr>
            <p><small>This is an automated message from your Fyers Trading Bot</small></p>
            """
            
            send_email(subject, body, is_html=True)
            logger.info("Authentication URL sent via email")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            return None
    
    def authenticate_with_code(self, auth_code):
        """Authenticate using the provided auth code"""
        try:
            session = fyersModel.SessionModel(
                client_id=self.client_id,
                secret_key=self.secret_key,
                redirect_uri=self.redirect_uri,
                response_type="code",
                grant_type="authorization_code"
            )
            
            session.set_token(auth_code)
            token_response = session.generate_token()
            
            if token_response and token_response.get('s') == 'ok':
                self.access_token = token_response['access_token']
                self.save_token(self.access_token)
                
                self.fyers_model = fyersModel.FyersModel(
                    client_id=self.client_id,
                    token=self.access_token,
                    log_path=""
                )
                
                bot_state.is_authenticated = True
                bot_state.waiting_for_auth = False
                logger.info("Authentication successful!")
                
                # Send success email
                send_email("✅ Fyers Authentication Successful", 
                          "Your Fyers Trading Bot has been successfully authenticated and is ready to trade!")
                
                return True
            else:
                logger.error(f"Authentication failed: {token_response}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def get_fyers_model(self):
        if not self.fyers_model:
            if self.load_saved_token():
                self.fyers_model = fyersModel.FyersModel(
                    client_id=self.client_id,
                    token=self.access_token,
                    log_path=""
                )
                bot_state.is_authenticated = True
        return self.fyers_model

# =============================================================================
# GOOGLE SHEETS MANAGER
# =============================================================================

class GoogleSheetsManager:
    def __init__(self):
        self.gc = None
        self.worksheet = None
        self.lock = threading.Lock()
        self.initialize_sheets()
    
    def initialize_sheets(self):
        try:
            # Load credentials from environment or file
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            if credentials_json:
                # Load from environment variable (for cloud deployment)
                credentials_dict = json.loads(credentials_json)
                creds = Credentials.from_service_account_info(credentials_dict)
            else:
                # Load from file (for local development)
                creds = Credentials.from_service_account_file('google_sheets_credentials.json')
            
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = creds.with_scopes(scope)
            
            self.gc = gspread.authorize(creds)
            sheet = self.gc.open_by_key(GOOGLE_SHEETS_ID)
            self.worksheet = sheet.sheet1
            
            logger.info("Google Sheets connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Google Sheets: {e}")
            return False
    
    def add_trade_to_sheets(self, symbol, ltp, trade_value, sector):
        try:
            with self.lock:
                current_time = datetime.now()
                row = [
                    current_time.strftime('%Y-%m-%d'),
                    current_time.strftime('%H:%M:%S'),
                    symbol,
                    round(ltp, 2),
                    int(trade_value),
                    round(trade_value / 10000000, 2),
                    sector
                ]
                
                self.worksheet.append_row(row)
                logger.info(f"Added to sheets: {symbol} - ₹{trade_value/10000000:.2f} crore")
                return True
                
        except Exception as e:
            logger.error(f"Error adding to Google Sheets: {e}")
            return False

# =============================================================================
# TRADING BOT
# =============================================================================

class FyersTradingBot:
    def __init__(self):
        self.authenticator = FyersAuthenticator()
        self.sheets_manager = GoogleSheetsManager()
        self.fyers_ws = None
        self.previous_volumes = {}
        self.last_alert_time = {}
        self.previous_ltp = {}
        
    def detect_large_trade(self, tick_data):
        try:
            symbol = tick_data.get('symbol', '')
            ltp = float(tick_data.get('ltp', 0))
            current_volume = float(tick_data.get('vol_traded_today', 0))
            
            if not symbol or ltp <= 0 or current_volume <= 0:
                return
            
            previous_volume = self.previous_volumes.get(symbol, current_volume)
            volume_spike = current_volume - previous_volume
            self.previous_volumes[symbol] = current_volume
            
            if volume_spike <= MIN_VOLUME_SPIKE:
                return
            
            trade_value = ltp * volume_spike
            
            if trade_value >= INDIVIDUAL_TRADE_THRESHOLD:
                last_alert = self.last_alert_time.get(symbol, 0)
                if time.time() - last_alert > 60:  # 1 minute cooldown
                    self.last_alert_time[symbol] = time.time()
                    
                    sector = SECTOR_MAPPING.get(symbol, "Others")
                    
                    logger.info(f"Large trade: {symbol} ({sector}) - ₹{trade_value/10000000:.2f} crore")
                    
                    # Add to Google Sheets
                    self.sheets_manager.add_trade_to_sheets(symbol, ltp, trade_value, sector)
                    
                    # Update bot state
                    bot_state.total_trades += 1
                    bot_state.last_heartbeat = datetime.now().isoformat()
                    bot_state.save_state()
                    
        except Exception as e:
            logger.error(f"Error detecting trade: {e}")
    
    def on_tick_received(self, *args):
        try:
            message = args[-1] if args else None
            if isinstance(message, dict) and 'symbol' in message:
                self.detect_large_trade(message)
        except Exception as e:
            logger.error(f"Error in tick handler: {e}")
    
    def start_trading(self):
        try:
            if not bot_state.is_authenticated:
                logger.warning("Not authenticated, generating auth URL")
                self.authenticator.generate_auth_url()
                return
            
            fyers_model = self.authenticator.get_fyers_model()
            if not fyers_model:
                logger.error("Failed to get Fyers model")
                return
            
            # Test connection
            profile = fyers_model.get_profile()
            if profile['s'] != 'ok':
                logger.error("Fyers connection test failed")
                bot_state.is_authenticated = False
                return
            
            logger.info(f"Starting trading session for user: {profile['data']['name']}")
            
            # Create WebSocket connection
            self.fyers_ws = data_ws.FyersDataSocket(
                access_token=f"{FYERS_CLIENT_ID}:{self.authenticator.access_token}",
                log_path="",
                litemode=False,
                write_to_file=False,
                reconnect=True,
                on_message=self.on_tick_received
            )
            
            self.fyers_ws.connect()
            time.sleep(2)
            
            self.fyers_ws.subscribe(symbols=STOCK_SYMBOLS, data_type="SymbolUpdate")
            
            bot_state.is_running = True
            bot_state.session_start = datetime.now().isoformat()
            logger.info("Trading session started successfully")
            
            # Send start notification
            send_email("🚀 Trading Session Started", 
                      f"Fyers Trading Bot started monitoring {len(STOCK_SYMBOLS)} symbols at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Error starting trading: {e}")
            bot_state.is_running = False
    
    def stop_trading(self):
        try:
            if self.fyers_ws:
                self.fyers_ws.close_connection()
            
            bot_state.is_running = False
            logger.info("Trading session stopped")
            
            # Send stop notification
            send_email("⏹️ Trading Session Stopped", 
                      f"Fyers Trading Bot stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Error stopping trading: {e}")

# =============================================================================
# SCHEDULER
# =============================================================================

trading_bot = FyersTradingBot()

def is_market_day():
    """Check if today is a market day (Monday to Friday)"""
    return datetime.now().weekday() < 5  # 0-6, Monday is 0

def should_start_trading():
    """Check if trading should start now"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    return (is_market_day() and 
            current_time >= MARKET_START_TIME and 
            current_time <= MARKET_END_TIME and
            not bot_state.is_running)

def should_stop_trading():
    """Check if trading should stop now"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    return (current_time >= MARKET_END_TIME and bot_state.is_running)

def scheduled_start():
    """Scheduled function to start trading"""
    if should_start_trading():
        logger.info("Scheduled trading start")
        trading_bot.start_trading()

def scheduled_stop():
    """Scheduled function to stop trading"""
    if should_stop_trading():
        logger.info("Scheduled trading stop")
        trading_bot.stop_trading()

# Setup scheduler
schedule.every().monday.at(MARKET_START_TIME).do(scheduled_start)
schedule.every().tuesday.at(MARKET_START_TIME).do(scheduled_start)
schedule.every().wednesday.at(MARKET_START_TIME).do(scheduled_start)
schedule.every().thursday.at(MARKET_START_TIME).do(scheduled_start)
schedule.every().friday.at(MARKET_START_TIME).do(scheduled_start)

schedule.every().monday.at(MARKET_END_TIME).do(scheduled_stop)
schedule.every().tuesday.at(MARKET_END_TIME).do(scheduled_stop)
schedule.every().wednesday.at(MARKET_END_TIME).do(scheduled_stop)
schedule.every().thursday.at(MARKET_END_TIME).do(scheduled_stop)
schedule.every().friday.at(MARKET_END_TIME).do(scheduled_stop)

def run_scheduler():
    """Run the scheduler in background"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# Start scheduler in background thread
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route('/')
def dashboard():
    """Main dashboard"""
    return render_template('dashboard.html', bot_state=bot_state)

@app.route('/authenticate')
def authenticate():
    """Generate new authentication URL"""
    auth_url = trading_bot.authenticator.generate_auth_url()
    if auth_url:
        return jsonify({'success': True, 'auth_url': auth_url, 'message': 'Authentication URL sent to email'})
    else:
        return jsonify({'success': False, 'message': 'Failed to generate authentication URL'})

@app.route('/auth_code', methods=['POST'])
def submit_auth_code():
    """Submit authentication code"""
    auth_code = request.form.get('auth_code', '').strip()
    if not auth_code:
        return jsonify({'success': False, 'message': 'Please provide auth code'})
    
    success = trading_bot.authenticator.authenticate_with_code(auth_code)
    if success:
        return jsonify({'success': True, 'message': 'Authentication successful!'})
    else:
        return jsonify({'success': False, 'message': 'Authentication failed. Please try again.'})

@app.route('/start_trading')
def start_trading():
    """Manually start trading"""
    if not bot_state.is_authenticated:
        return jsonify({'success': False, 'message': 'Please authenticate first'})
    
    threading.Thread(target=trading_bot.start_trading, daemon=True).start()
    return jsonify({'success': True, 'message': 'Trading started'})

@app.route('/stop_trading')
def stop_trading():
    """Manually stop trading"""
    trading_bot.stop_trading()
    return jsonify({'success': True, 'message': 'Trading stopped'})

@app.route('/status')
def status():
    """Get bot status"""
    now = datetime.now()
    return jsonify({
        'is_running': bot_state.is_running,
        'is_authenticated': bot_state.is_authenticated,
        'waiting_for_auth': bot_state.waiting_for_auth,
        'total_trades': bot_state.total_trades,
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'market_day': is_market_day(),
        'should_run': should_start_trading(),
        'last_heartbeat': bot_state.last_heartbeat,
        'session_start': bot_state.session_start
    })

# =============================================================================
# HTML TEMPLATES (Inline for simplicity)
# =============================================================================

dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Fyers Trading Bot Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; }
        .status { padding: 15px; border-radius: 5px; margin: 10px 0; }
        .status.running { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .status.stopped { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .status.auth-needed { background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }
        .btn { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn.primary { background: #007bff; color: white; }
        .btn.success { background: #28a745; color: white; }
        .btn.danger { background: #dc3545; color: white; }
        .btn.warning { background: #ffc107; color: black; }
        .btn:hover { opacity: 0.8; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .form-group { margin: 15px 0; }
        .form-group label { display: block; margin-bottom: 5px; }
        .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-card { background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
        .schedule-info { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 10px 0; }
        #messages { margin: 20px 0; }
        .message { padding: 10px; margin: 5px 0; border-radius: 5px; }
        .message.success { background: #d4edda; color: #155724; }
        .message.error { background: #f8d7da; color: #721c24; }
        .loading { display: none; color: #007bff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>🤖 Fyers Trading Bot Dashboard</h1>
                <p>Automated trading with volume spike detection</p>
            </div>
        </div>

        <div id="messages"></div>

        <div class="card">
            <h2>📊 Bot Status</h2>
            <div id="status-container">
                <div class="status" id="bot-status">Loading...</div>
            </div>
            
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="total-trades">0</div>
                    <div>Total Trades</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="current-time">--:--</div>
                    <div>Current Time</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="market-status">Closed</div>
                    <div>Market Status</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="symbols-count">{{ stock_count }}</div>
                    <div>Symbols Monitored</div>
                </div>
            </div>
        </div>

        <div class="card" id="auth-section" style="display: none;">
            <h2>🔐 Authentication Required</h2>
            <p>The bot needs to authenticate with Fyers API to start trading.</p>
            
            <button class="btn warning" onclick="generateAuthUrl()">
                📧 Send Auth URL to Email
            </button>
            <div class="loading" id="auth-loading">Generating authentication URL...</div>
            
            <div class="form-group" style="margin-top: 20px;">
                <label for="auth-code">Enter Auth Code from Redirect URL:</label>
                <input type="text" id="auth-code" placeholder="Paste auth code here...">
                <button class="btn primary" onclick="submitAuthCode()" style="margin-top: 10px;">
                    ✅ Submit Auth Code
                </button>
            </div>
        </div>

        <div class="card">
            <h2>🎛️ Manual Controls</h2>
            <p>Override automatic scheduling if needed</p>
            
            <button class="btn success" onclick="startTrading()" id="start-btn">
                ▶️ Start Trading
            </button>
            <button class="btn danger" onclick="stopTrading()" id="stop-btn">
                ⏹️ Stop Trading
            </button>
            <button class="btn primary" onclick="refreshStatus()">
                🔄 Refresh Status
            </button>
        </div>

        <div class="card">
            <h2>📅 Automatic Schedule</h2>
            <div class="schedule-info">
                <h3>Trading Hours</h3>
                <p><strong>Monday to Friday:</strong> 9:15 AM - 3:30 PM IST</p>
                <p><strong>Weekends:</strong> Bot remains idle</p>
                
                <h3>Email Notifications</h3>
                <ul>
                    <li>🔐 Authentication URLs and TOTP codes</li>
                    <li>🚀 Trading session start/stop confirmations</li>
                    <li>📊 Large trade alerts (₹3+ crore)</li>
                    <li>⚠️ Error notifications</li>
                </ul>
                
                <h3>Google Sheets Integration</h3>
                <p>All detected trades are automatically logged to: 
                <a href="https://docs.google.com/spreadsheets/d/1l_6Sx_u1czhY-5JdT22tpmCV8Os3XuZmZ3U2ShKDLHw" target="_blank">
                📝 Trading Log Sheet
                </a></p>
            </div>
        </div>

        <div class="card">
            <h2>📈 Monitoring Configuration</h2>
            <div class="schedule-info">
                <p><strong>Symbols:</strong> Top 50 liquid NSE stocks</p>
                <p><strong>Trade Threshold:</strong> ₹3 crore (₹30,000,000)</p>
                <p><strong>Volume Spike:</strong> Minimum 1,000 shares</p>
                <p><strong>Sectors Tracked:</strong> Banking, IT, Oil & Gas, Auto, Pharma, FMCG, Metals, Power, Cement, Telecom, Financial Services, Real Estate, Construction</p>
                <p><strong>Data Source:</strong> Fyers WebSocket real-time feed</p>
            </div>
        </div>
    </div>

    <script>
        let statusInterval;

        function showMessage(text, type = 'success') {
            const messages = document.getElementById('messages');
            const message = document.createElement('div');
            message.className = `message ${type}`;
            message.textContent = text;
            messages.appendChild(message);
            
            setTimeout(() => {
                message.remove();
            }, 5000);
        }

        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const statusContainer = document.getElementById('bot-status');
                    const authSection = document.getElementById('auth-section');
                    
                    // Update status display
                    if (data.is_running) {
                        statusContainer.className = 'status running';
                        statusContainer.innerHTML = '🟢 Bot is RUNNING - Monitoring trades';
                        authSection.style.display = 'none';
                    } else if (!data.is_authenticated || data.waiting_for_auth) {
                        statusContainer.className = 'status auth-needed';
                        statusContainer.innerHTML = '🔐 Authentication Required';
                        authSection.style.display = 'block';
                    } else {
                        statusContainer.className = 'status stopped';
                        statusContainer.innerHTML = '🔴 Bot is STOPPED';
                        authSection.style.display = 'none';
                    }
                    
                    // Update stats
                    document.getElementById('total-trades').textContent = data.total_trades;
                    document.getElementById('current-time').textContent = data.current_time;
                    document.getElementById('market-status').textContent = 
                        data.market_day ? (data.should_run ? 'Open' : 'Open (After Hours)') : 'Closed (Weekend)';
                    
                    // Update button states
                    const startBtn = document.getElementById('start-btn');
                    const stopBtn = document.getElementById('stop-btn');
                    
                    startBtn.disabled = !data.is_authenticated || data.is_running;
                    stopBtn.disabled = !data.is_running;
                    
                    // Show schedule info
                    if (data.last_heartbeat) {
                        const lastHeartbeat = new Date(data.last_heartbeat);
                        const timeDiff = Date.now() - lastHeartbeat.getTime();
                        if (timeDiff < 300000) { // 5 minutes
                            statusContainer.innerHTML += ` (Last activity: ${Math.floor(timeDiff/1000)}s ago)`;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error fetching status:', error);
                    document.getElementById('bot-status').innerHTML = '❌ Connection Error';
                });
        }

        function generateAuthUrl() {
            const loading = document.getElementById('auth-loading');
            loading.style.display = 'block';
            
            fetch('/authenticate')
                .then(response => response.json())
                .then(data => {
                    loading.style.display = 'none';
                    if (data.success) {
                        showMessage('Authentication URL sent to your email! Check your inbox.', 'success');
                    } else {
                        showMessage('Failed to generate authentication URL: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    loading.style.display = 'none';
                    showMessage('Error: ' + error.message, 'error');
                });
        }

        function submitAuthCode() {
            const authCode = document.getElementById('auth-code').value.trim();
            if (!authCode) {
                showMessage('Please enter the auth code', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('auth_code', authCode);
            
            fetch('/auth_code', {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('Authentication successful! Bot is now ready.', 'success');
                        document.getElementById('auth-code').value = '';
                        updateStatus();
                    } else {
                        showMessage('Authentication failed: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showMessage('Error: ' + error.message, 'error');
                });
        }

        function startTrading() {
            fetch('/start_trading')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('Trading started successfully!', 'success');
                        updateStatus();
                    } else {
                        showMessage('Failed to start trading: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showMessage('Error: ' + error.message, 'error');
                });
        }

        function stopTrading() {
            fetch('/stop_trading')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('Trading stopped successfully!', 'success');
                        updateStatus();
                    } else {
                        showMessage('Failed to stop trading: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showMessage('Error: ' + error.message, 'error');
                });
        }

        function refreshStatus() {
            updateStatus();
            showMessage('Status refreshed', 'success');
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            updateStatus();
            statusInterval = setInterval(updateStatus, 30000); // Update every 30 seconds
        });

        // Handle Enter key in auth code input
        document.getElementById('auth-code').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submitAuthCode();
            }
        });
    </script>
</body>
</html>
"""

# Create templates directory and file if running locally
import os
if not os.path.exists('templates'):
    os.makedirs('templates')

with open('templates/dashboard.html', 'w') as f:
    f.write(dashboard_html.replace('{{ stock_count }}', str(len(STOCK_SYMBOLS))))

# =============================================================================
# HEALTH CHECK ENDPOINT
# =============================================================================

@app.route('/health')
def health_check():
    """Health check endpoint for cloud deployment"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'bot_running': bot_state.is_running,
        'authenticated': bot_state.is_authenticated
    })

# =============================================================================
# MAIN APPLICATION
# =============================================================================

if __name__ == '__main__':
    logger.info("Starting Fyers Trading Bot Web Application")
    logger.info(f"Monitoring {len(STOCK_SYMBOLS)} symbols")
    logger.info(f"Market hours: {MARKET_START_TIME} - {MARKET_END_TIME}")
    
    # Check if we should auto-start trading
    if should_start_trading() and bot_state.is_authenticated:
        logger.info("Auto-starting trading session")
        threading.Thread(target=trading_bot.start_trading, daemon=True).start()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)