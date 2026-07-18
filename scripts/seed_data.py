"""
Seed data generator for the `wholesale` MySQL/MariaDB database
(DB-Design-Schema/ + DB-Design-Schema/Views/).

Run once against a freshly-loaded, empty schema:
    .venv\\Scripts\\python.exe scripts\\seed_data.py

Volume tier: "Moderate" -- ~250 clients, 25 RMs, 40 products, each client
with a handful of accounts per product line and several months of history
on the tables that feed the chart views (ASSET_VALUE_HISTORY,
LIABILITY_VALUE_HISTORY, etc).

UNIT CONVENTION: all NUMERIC amount columns are populated in INR Crores
(matching how the app already displays money everywhere, e.g. "₹2.50 CR" in
src/multi_agent_generator.py's prompts) -- NOT raw rupees.

Surrogate BIGINT primary keys are assigned explicitly in this script (via
`new_id()`) rather than left to AUTO_INCREMENT, so every child table can
reference a parent's id deterministically without round-tripping
cursor.lastrowid per row.
"""
import sys
import os
import random
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from faker import Faker
from config.db_config import get_db_connection

random.seed(42)
Faker.seed(42)
fake = Faker("en_IN")

TODAY = datetime.date(2026, 7, 17)

# ---------------------------------------------------------------- volumes --
NUM_BRANCHES = 15
NUM_CURRENCIES = 5
NUM_SECTORS = 15
NUM_RMS = 25
NUM_PRODUCTS = 40
NUM_CLIENTS = 250

conn = get_db_connection()
cur = conn.cursor()

# Idempotent: truncate every base table (children first is unnecessary since
# FK checks are disabled for the duration) so re-running this script after a
# mid-run failure always starts from a clean, empty schema.
_ALL_TABLES_IN_TRUNCATE_ORDER = [
    "RM_DISCUSSION_OUTCOME", "RM_FOLLOWUP_ACTION", "RM_PROPOSED_SOLUTION", "RM_CLIENT_NEED_IDENTIFIED",
    "RM_DISCUSSION_TOPIC", "RM_DISCUSSION_SESSION",
    "RM_CLIENT_FEEDBACK", "RM_TARGET_ACHIEVEMENT", "RM_TRAINING_CERTIFICATION", "RM_ESCALATION_LOG",
    "RM_CLIENT_VISIT_PLAN", "RM_INTERACTION_SUMMARY", "RM_PERFORMANCE_METRICS",
    "PRODUCT_SERVICE_REQUEST", "PRODUCT_CHANNEL_USAGE", "PRODUCT_PRICING_TERMS",
    "PRODUCT_RELATIONSHIP_DEPTH_SCORE", "PRODUCT_FEE_INCOME", "PRODUCT_CROSS_SELL_OPPORTUNITY",
    "PRODUCT_UTILIZATION_HISTORY", "PRODUCT_UTILIZATION", "PRODUCT_HOLDING_SUMMARY",
    "LIABILITY_NOMINATION_DETAILS", "LIABILITY_EARLY_CLOSURE_HISTORY", "LIABILITY_RENEWAL_HISTORY",
    "LIABILITY_RISK_METRICS", "LIABILITY_VALUE_HISTORY", "LIABILITY_INTEREST_RATE_HISTORY",
    "LIABILITY_MATURITY_PROFILE", "LIABILITY_BOND_DETAILS", "LIABILITY_BORROWING_DETAILS",
    "LIABILITY_CURRENT_ACCOUNT_DETAILS", "LIABILITY_TERM_DEPOSIT_DETAILS", "LIABILITY_ACCOUNT_MASTER",
    "ASSET_WRITEOFF_RECOVERY", "ASSET_RESTRUCTURING_HISTORY", "ASSET_INSURANCE_DETAILS",
    "ASSET_GUARANTOR_DETAILS", "ASSET_COVENANT_MASTER", "ASSET_SANCTION_LIMIT",
    "ASSET_INTEREST_RATE_HISTORY", "ASSET_VALUE_HISTORY", "ASSET_QUALITY_HISTORY",
    "ASSET_NPA_CLASSIFICATION", "ASSET_COLLATERAL_LINKAGE", "ASSET_COLLATERAL_MASTER",
    "ASSET_CASH_EQUIVALENT_DETAILS", "ASSET_SECURITIES_DETAILS", "ASSET_INVESTMENT_DETAILS",
    "ASSET_TRADE_FINANCE_DETAILS", "ASSET_LOAN_REPAYMENT_SCHEDULE", "ASSET_LOAN_DISBURSEMENT_SCHEDULE",
    "ASSET_LOAN_DETAILS", "ASSET_ACCOUNT_MASTER",
    "CMS_NOTES_REMARKS", "CMS_CUSTOMER_SEGMENT_HISTORY", "CMS_ACCOUNT_BALANCE_HISTORY",
    "CMS_ACCOUNT_BALANCE_CURRENT", "CMS_DOCUMENT_REPOSITORY", "CMS_MEETING_RECORD", "CMS_CALL_LOG",
    "CMS_COMMUNICATION_LOG", "CMS_CUSTOMER_CONTACT", "CMS_CUSTOMER_ADDRESS", "CMS_CUSTOMER_PROFILE",
    "ACCOUNT_MASTER", "CLIENT_RM_MAPPING", "PRODUCT_CATALOG_FEATURE", "PRODUCT_MASTER",
    "CLIENT_MASTER", "RM_MASTER", "INDUSTRY_SECTOR_MASTER", "CURRENCY_MASTER", "BRANCH_MASTER",
]
cur.execute("SET FOREIGN_KEY_CHECKS=0")
for tbl in _ALL_TABLES_IN_TRUNCATE_ORDER:
    cur.execute(f"TRUNCATE TABLE {tbl}")
cur.execute("SET FOREIGN_KEY_CHECKS=1")
conn.commit()
print(f"Truncated {len(_ALL_TABLES_IN_TRUNCATE_ORDER)} tables -- starting clean seed run.\n")

_id_counters = {}


def new_id(table):
    _id_counters[table] = _id_counters.get(table, 0) + 1
    return _id_counters[table]


def insert_many(table, columns, rows, batch_size=2000):
    if not rows:
        return
    placeholders = ", ".join(["%s"] * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    for i in range(0, len(rows), batch_size):
        cur.executemany(sql, rows[i : i + batch_size])
    conn.commit()
    print(f"  {table}: {len(rows)} rows")


def rand_date(start, end):
    if end <= start:
        return start
    delta = (end - start).days
    return start + datetime.timedelta(days=random.randint(0, delta))


def weighted_choice(options, weights):
    return random.choices(options, weights=weights, k=1)[0]


def crore(low, high, decimals=2):
    return round(random.uniform(low, high), decimals)


SOURCE_SYSTEMS = ["CBS", "CRM", "LOS", "TREASURY", "MANUAL"]


def src():
    return random.choice(SOURCE_SYSTEMS)


def created_updated():
    created = rand_date(datetime.date(2023, 1, 1), TODAY)
    updated = rand_date(created, TODAY) if random.random() < 0.6 else None
    return created, updated


# =============================================================================
# 00_Master_Tables.sql
# =============================================================================
print("00_Master_Tables.sql")

INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Hyderabad", "Pune",
    "Ahmedabad", "Surat", "Jaipur", "Lucknow", "Kanpur", "Nagpur", "Indore",
    "Chandigarh",
]
REGIONS = ["North", "South", "East", "West", "Central"]

branch_codes = []
rows = []
for i, city in enumerate(INDIAN_CITIES[:NUM_BRANCHES], start=1):
    code = f"BR{i:03d}"
    branch_codes.append(code)
    created, updated = created_updated()
    rows.append((code, f"{city} Corporate Branch", random.choice(REGIONS), random.choice(REGIONS),
                 fake.street_address(), city, fake.state(), "India", fake.postcode(),
                 created, updated, src()))
insert_many("BRANCH_MASTER",
            ["BRANCH_CODE", "BRANCH_NAME", "REGION", "ZONE", "ADDRESS_LINE1", "CITY", "STATE",
             "COUNTRY", "PIN_CODE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

CURRENCIES = [("INR", "Indian Rupee", "₹"), ("USD", "US Dollar", "$"), ("EUR", "Euro", "€"),
              ("GBP", "British Pound", "£"), ("JPY", "Japanese Yen", "¥")]
currency_codes = []
rows = []
for code, name, symbol in CURRENCIES[:NUM_CURRENCIES]:
    currency_codes.append(code)
    created, updated = created_updated()
    rows.append((code, name, symbol, 2, created, updated, src()))
insert_many("CURRENCY_MASTER",
            ["CURRENCY_CODE", "CURRENCY_NAME", "CURRENCY_SYMBOL", "DECIMAL_PRECISION",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

SECTORS = [
    "Manufacturing", "Information Technology", "Pharmaceuticals", "Textiles", "Real Estate",
    "Infrastructure", "Automotive", "Chemicals", "FMCG", "Iron & Steel", "Power & Energy",
    "Telecom", "Agriculture & Food Processing", "Logistics & Transport", "Financial Services",
]
sector_codes = []
rows = []
for i, name in enumerate(SECTORS[:NUM_SECTORS], start=1):
    code = f"SEC{i:02d}"
    sector_codes.append(code)
    created, updated = created_updated()
    rows.append((code, name, f"{1000+i}", weighted_choice(["Low", "Medium", "High"], [0.5, 0.35, 0.15]),
                 created, updated, src()))
insert_many("INDUSTRY_SECTOR_MASTER",
            ["SECTOR_CODE", "SECTOR_NAME", "NIC_CODE", "RISK_CATEGORY",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

DESIGNATIONS = ["Relationship Manager", "Senior Relationship Manager", "Vice President",
                "Assistant Vice President", "Relationship Head"]
rm_codes = []
rm_rows_by_code = {}
senior_rms = []
rows = []
for i in range(1, NUM_RMS + 1):
    code = f"RM{i:04d}"
    rm_codes.append(code)
    name = fake.name()
    designation = random.choice(DESIGNATIONS)
    if designation in ("Vice President", "Relationship Head"):
        senior_rms.append(code)
    branch = random.choice(branch_codes)
    email = fake.email()
    phone = fake.msisdn()[:15]
    reporting = None  # filled in second pass below
    doj = rand_date(datetime.date(2015, 1, 1), datetime.date(2025, 1, 1))
    status = weighted_choice(["Active", "Inactive"], [0.92, 0.08])
    created, updated = created_updated()
    rm_rows_by_code[code] = [code, name, designation, branch, email, phone, reporting, doj, status,
                              created, updated, src()]

if not senior_rms:
    senior_rms = rm_codes[:3]
for code, row in rm_rows_by_code.items():
    if code not in senior_rms:
        row[6] = random.choice(senior_rms)

# Senior RMs (REPORTING_RM_CODE = NULL) must be inserted before the RMs that
# reference them, since RM_MASTER.REPORTING_RM_CODE is a self-referencing FK.
rows = [rm_rows_by_code[c] for c in senior_rms] + \
       [row for code, row in rm_rows_by_code.items() if code not in senior_rms]
insert_many("RM_MASTER",
            ["RM_CODE", "RM_NAME", "DESIGNATION", "BRANCH_CODE", "EMAIL", "PHONE_NUMBER",
             "REPORTING_RM_CODE", "DATE_OF_JOINING", "EMPLOYMENT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

# Product catalog, tagged by category so downstream tables can pick sensibly.
ASSET_PRODUCT_NAMES = [
    "Term Loan - Working Capital", "Term Loan - Capex", "Overdraft Facility",
    "Cash Credit Facility", "Letter of Credit", "Bank Guarantee", "Bill Discounting",
    "Export Packing Credit", "Corporate Bond Investment", "Mutual Fund Investment",
    "Equity Investment Portfolio", "G-Sec Investment", "Fixed Deposit Placement",
    "Certificate of Deposit Holding", "Commercial Paper Holding",
]
LIABILITY_PRODUCT_NAMES = [
    "Term Deposit - Corporate", "Current Account - Premium", "Current Account - Standard",
    "Short Term Borrowing", "Term Borrowing", "Refinance Facility",
    "Corporate Bond Issuance", "Subordinated Bond", "Callable Deposit",
    "Certificate of Deposit - Issued", "Commercial Paper - Issued", "Inter-Bank Borrowing",
]
CMS_PRODUCT_NAMES = [
    "Cash Management Services", "Collections Services", "Payment Gateway Services",
    "Virtual Account Services", "Sweep Account Facility",
]
TRADE_FINANCE_PRODUCT_NAMES = ["Import LC Facility", "Export LC Facility", "Trade Guarantee",
                                "Supply Chain Finance"]
TREASURY_PRODUCT_NAMES = ["FX Forward Contract", "Interest Rate Swap", "Currency Swap",
                           "Treasury Advisory Services"]

PRODUCT_GROUPS = [
    ("Asset", ASSET_PRODUCT_NAMES),
    ("Liability", LIABILITY_PRODUCT_NAMES),
    ("CMS", CMS_PRODUCT_NAMES),
    ("TradeFinance", TRADE_FINANCE_PRODUCT_NAMES),
    ("Treasury", TREASURY_PRODUCT_NAMES),
]

product_codes_by_category = {"Asset": [], "Liability": [], "CMS": [], "TradeFinance": [], "Treasury": []}
product_code_by_name = {}
rows = []
pidx = 1
for category, names in PRODUCT_GROUPS:
    for name in names:
        code = f"PRD{pidx:03d}"
        product_codes_by_category[category].append(code)
        product_code_by_name[name] = code
        created, updated = created_updated()
        rows.append((code, name, category, category, f"GL{pidx:05d}", "Y", created, updated, src()))
        pidx += 1
insert_many("PRODUCT_MASTER",
            ["PRODUCT_CODE", "PRODUCT_NAME", "PRODUCT_CATEGORY", "PRODUCT_SUB_CATEGORY", "GL_CODE",
             "IS_ACTIVE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

all_product_codes = [c for lst in product_codes_by_category.values() for c in lst]

FEATURE_TEMPLATES = ["Competitive pricing", "Flexible tenure options", "Digital onboarding",
                     "Dedicated relationship support", "Quick turnaround time", "Collateral-light structuring"]
rows = []
for category, codes in product_codes_by_category.items():
    for code in codes:
        for feat in random.sample(FEATURE_TEMPLATES, k=random.randint(2, 3)):
            fid = new_id("PRODUCT_CATALOG_FEATURE")
            created, updated = created_updated()
            rows.append((fid, code, feat, f"{feat} for {category.lower()} clients.", created, updated, src()))
insert_many("PRODUCT_CATALOG_FEATURE",
            ["FEATURE_ID", "PRODUCT_CODE", "FEATURE_NAME", "FEATURE_DESCRIPTION",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

CONSTITUTIONS = ["Private Limited", "Public Limited", "Partnership", "LLP", "Proprietorship"]
SEGMENTS = ["Large Corporate", "Mid Corporate", "Emerging Corporate"]
client_codes = []
client_sector = {}
client_branch = {}
rows = []
for i in range(1, NUM_CLIENTS + 1):
    code = f"APR{i:08d}"
    client_codes.append(code)
    sector = random.choice(sector_codes)
    branch = random.choice(branch_codes)
    client_sector[code] = sector
    client_branch[code] = branch
    incorp = rand_date(datetime.date(1980, 1, 1), datetime.date(2020, 1, 1))
    onboard = rand_date(max(incorp, datetime.date(2015, 1, 1)), datetime.date(2025, 6, 1))
    status = weighted_choice(["Active", "Dormant", "Closed"], [0.88, 0.09, 0.03])
    created, updated = created_updated()
    rows.append((code, fake.company() + " " + random.choice(["Ltd", "Pvt Ltd", "Industries", "Group"]),
                 random.choice(CONSTITUTIONS), fake.bothify("?????####").upper()[:10],
                 fake.bothify("U#####??####???######")[:21], sector, branch,
                 weighted_choice(SEGMENTS, [0.25, 0.45, 0.30]), incorp, onboard,
                 weighted_choice(["Completed", "Pending", "Under Review"], [0.85, 0.1, 0.05]),
                 status, created, updated, src()))
insert_many("CLIENT_MASTER",
            ["APR_CLIENT_CODE", "CLIENT_NAME", "CONSTITUTION_TYPE", "PAN_NUMBER", "CIN_NUMBER",
             "SECTOR_CODE", "HOME_BRANCH_CODE", "CLIENT_SEGMENT", "INCORPORATION_DATE",
             "ONBOARDING_DATE", "KYC_STATUS", "CLIENT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

client_primary_rm = {}
rows = []
for code in client_codes:
    primary_rm = random.choice(rm_codes)
    client_primary_rm[code] = primary_rm
    mid = new_id("CLIENT_RM_MAPPING")
    start = rand_date(datetime.date(2022, 1, 1), datetime.date(2024, 6, 1))
    created, updated = created_updated()
    rows.append((mid, code, primary_rm, "Primary RM", start, None, "Y", created, updated, src()))
    if random.random() < 0.2:
        prior_rm = random.choice([r for r in rm_codes if r != primary_rm])
        mid2 = new_id("CLIENT_RM_MAPPING")
        prior_end = start - datetime.timedelta(days=random.randint(30, 200))
        prior_start = prior_end - datetime.timedelta(days=random.randint(180, 720))
        created2, updated2 = created_updated()
        rows.append((mid2, code, prior_rm, "Primary RM", prior_start, prior_end, "N", created2, updated2, src()))
insert_many("CLIENT_RM_MAPPING",
            ["CLIENT_RM_MAPPING_ID", "APR_CLIENT_CODE", "RM_CODE", "MAPPING_ROLE",
             "MAPPING_START_DATE", "MAPPING_END_DATE", "IS_PRIMARY",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

# ACCOUNT_MASTER: 2-4 bank-wide accounts per client, products drawn from any category.
client_accounts = {c: [] for c in client_codes}
rows = []
acct_seq = 0
for code in client_codes:
    n = random.randint(2, 4)
    for _ in range(n):
        acct_seq += 1
        acct_no = f"ACC{acct_seq:012d}"
        client_accounts[code].append(acct_no)
        product = random.choice(all_product_codes)
        branch = client_branch[code]
        currency = "INR" if random.random() < 0.85 else random.choice(currency_codes)
        open_date = rand_date(datetime.date(2018, 1, 1), TODAY - datetime.timedelta(days=30))
        status = weighted_choice(["Active", "Dormant", "Closed"], [0.88, 0.08, 0.04])
        close_date = rand_date(open_date, TODAY) if status == "Closed" else None
        created, updated = created_updated()
        rows.append((acct_no, code, product, branch, currency, open_date, close_date, status,
                     created, updated, src()))
insert_many("ACCOUNT_MASTER",
            ["ACCOUNT_NUMBER", "APR_CLIENT_CODE", "PRODUCT_CODE", "BRANCH_CODE", "CURRENCY_CODE",
             "ACCOUNT_OPEN_DATE", "ACCOUNT_CLOSE_DATE", "ACCOUNT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

# =============================================================================
# 01_CMS.sql
# =============================================================================
print("01_CMS.sql")

RATING_GRADES = ["AAA", "AA+", "AA", "A+", "A", "BBB+", "BBB"]
rows = []
for code in client_codes:
    rel_since = rand_date(datetime.date(2015, 1, 1), datetime.date(2024, 1, 1))
    created, updated = created_updated()
    rows.append((code, fake.company() + " Group", fake.company(),
                 "https://www." + fake.domain_name(), random.choice(RATING_GRADES),
                 random.choice(["CRISIL", "ICRA", "CARE Ratings", "India Ratings"]),
                 rand_date(rel_since, TODAY), rel_since, crore(10, 5000),
                 created, updated, src()))
insert_many("CMS_CUSTOMER_PROFILE",
            ["APR_CLIENT_CODE", "GROUP_NAME", "PARENT_COMPANY_NAME", "WEBSITE_URL", "CREDIT_RATING",
             "RATING_AGENCY", "RATING_DATE", "RELATIONSHIP_SINCE_DATE", "ANNUAL_TURNOVER_AMOUNT",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

ADDRESS_TYPES = ["Registered", "Correspondence", "Branch", "Factory"]
rows = []
for code in client_codes:
    n = random.randint(1, 2)
    types = random.sample(ADDRESS_TYPES, k=n)
    for j, atype in enumerate(types):
        aid = new_id("CMS_CUSTOMER_ADDRESS")
        created, updated = created_updated()
        line2 = f"Floor {random.randint(1, 12)}, {random.choice(['Tower A', 'Tower B', 'Wing C', 'Block 2'])}" \
            if random.random() < 0.5 else None
        rows.append((aid, code, atype, fake.street_address(), line2,
                     fake.city(), fake.state(), "India", fake.postcode(), "Y" if j == 0 else "N",
                     created, updated, src()))
insert_many("CMS_CUSTOMER_ADDRESS",
            ["ADDRESS_ID", "APR_CLIENT_CODE", "ADDRESS_TYPE", "ADDRESS_LINE1", "ADDRESS_LINE2",
             "CITY", "STATE", "COUNTRY", "PIN_CODE", "IS_PRIMARY",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

CONTACT_DESIGNATIONS = ["CFO", "Finance Manager", "Managing Director", "Treasury Head", "Company Secretary"]
rows = []
for code in client_codes:
    n = random.randint(1, 2)
    for j in range(n):
        cid = new_id("CMS_CUSTOMER_CONTACT")
        created, updated = created_updated()
        rows.append((cid, code, fake.name(), random.choice(CONTACT_DESIGNATIONS), fake.email(),
                     fake.msisdn()[:15], "Y" if j == 0 else "N", created, updated, src()))
insert_many("CMS_CUSTOMER_CONTACT",
            ["CONTACT_ID", "APR_CLIENT_CODE", "CONTACT_PERSON_NAME", "DESIGNATION", "EMAIL",
             "PHONE_NUMBER", "IS_PRIMARY", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

COMM_TYPES = ["Email", "Letter", "SMS", "Notice", "Fax"]
COMM_SUBJECTS = ["Facility renewal reminder", "KYC documentation request", "Rate revision notice",
                 "Statement of account", "Compliance certificate request", "Festive greetings"]
rows = []
for code in client_codes:
    for _ in range(random.randint(5, 15)):
        comm_id = new_id("CMS_COMMUNICATION_LOG")
        dt = datetime.datetime.combine(rand_date(datetime.date(2024, 1, 1), TODAY), datetime.time(
            random.randint(9, 18), random.choice([0, 15, 30, 45])))
        created, updated = created_updated()
        rows.append((comm_id, code, client_primary_rm[code], random.choice(COMM_TYPES),
                     random.choice(["Inbound", "Outbound"]), dt, random.choice(COMM_SUBJECTS),
                     fake.sentence(nb_words=12), created, updated, src()))
insert_many("CMS_COMMUNICATION_LOG",
            ["COMMUNICATION_ID", "APR_CLIENT_CODE", "RM_CODE", "COMMUNICATION_TYPE",
             "COMMUNICATION_DIRECTION", "COMMUNICATION_DATE", "SUBJECT", "SUMMARY",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

CALL_PURPOSES = ["Facility discussion", "Documentation follow-up", "Relationship review",
                 "Cross-sell pitch", "Service request follow-up"]
rows = []
for code in client_codes:
    for _ in range(random.randint(5, 15)):
        call_id = new_id("CMS_CALL_LOG")
        d = rand_date(datetime.date(2024, 1, 1), TODAY)
        t = datetime.time(random.randint(9, 18), random.choice([0, 15, 30, 45]))
        created, updated = created_updated()
        rows.append((call_id, code, client_primary_rm[code], d, t, random.randint(3, 45),
                     random.choice(["Incoming", "Outgoing"]), random.choice(CALL_PURPOSES),
                     fake.sentence(nb_words=10), created, updated, src()))
insert_many("CMS_CALL_LOG",
            ["CALL_ID", "APR_CLIENT_CODE", "RM_CODE", "CALL_DATE", "CALL_TIME", "DURATION_MINUTES",
             "CALL_TYPE", "CALL_PURPOSE", "CALL_OUTCOME", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], rows)

MEETING_TYPES = ["In-Person", "Virtual", "Telephonic"]
meeting_ids_by_client = {c: [] for c in client_codes}
rows = []
for code in client_codes:
    for _ in range(random.randint(3, 8)):
        meeting_id = new_id("CMS_MEETING_RECORD")
        meeting_ids_by_client[code].append(meeting_id)
        d = rand_date(datetime.date(2024, 1, 1), TODAY)
        created, updated = created_updated()
        rows.append((meeting_id, code, client_primary_rm[code], d, random.choice(MEETING_TYPES),
                     fake.city() + " Office", fake.name() + ", " + fake.name(),
                     "Portfolio review and relationship update",
                     fake.paragraph(nb_sentences=3), created, updated, src()))
insert_many("CMS_MEETING_RECORD",
            ["MEETING_ID", "APR_CLIENT_CODE", "RM_CODE", "MEETING_DATE", "MEETING_TYPE", "LOCATION",
             "ATTENDEES", "AGENDA", "MINUTES_SUMMARY", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], rows)

DOC_TYPES = ["KYC", "Agreement", "BoardResolution", "FinancialStatement", "Other"]
rows = []
for code in client_codes:
    for _ in range(random.randint(2, 5)):
        doc_id = new_id("CMS_DOCUMENT_REPOSITORY")
        upload = rand_date(datetime.date(2022, 1, 1), TODAY)
        expiry = rand_date(upload, TODAY + datetime.timedelta(days=730)) if random.random() < 0.6 else None
        status = "Expired" if expiry and expiry < TODAY else weighted_choice(
            ["Valid", "PendingRenewal"], [0.85, 0.15])
        created, updated = created_updated()
        rows.append((doc_id, code, random.choice(DOC_TYPES), fake.bs().title() + " Document",
                     upload, expiry, f"/docs/{code}/{doc_id}.pdf", status, created, updated, src()))
insert_many("CMS_DOCUMENT_REPOSITORY",
            ["DOCUMENT_ID", "APR_CLIENT_CODE", "DOCUMENT_TYPE", "DOCUMENT_NAME", "UPLOAD_DATE",
             "EXPIRY_DATE", "FILE_REFERENCE", "DOCUMENT_STATUS", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], rows)

rows = []
for code in client_codes:
    for acct_no in client_accounts[code]:
        bal = crore(0.1, 50)
        created, updated = created_updated()
        rows.append((acct_no, code, TODAY, bal, round(bal * random.uniform(0.85, 1.0), 2),
                     round(bal * random.uniform(0.0, 0.1), 2), "INR", created, updated, src()))
insert_many("CMS_ACCOUNT_BALANCE_CURRENT",
            ["ACCOUNT_NUMBER", "APR_CLIENT_CODE", "AS_OF_DATE", "CURRENT_BALANCE",
             "AVAILABLE_BALANCE", "HOLD_AMOUNT", "CURRENCY_CODE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

rows = []
for code in client_codes:
    for acct_no in client_accounts[code]:
        base = crore(0.1, 50)
        for m in range(12):
            bal_date = TODAY.replace(day=1) - datetime.timedelta(days=30 * m)
            bal_date = bal_date.replace(day=min(28, bal_date.day))
            opening = round(base * random.uniform(0.9, 1.1), 2)
            closing = round(opening * random.uniform(0.95, 1.08), 2)
            bh_id = new_id("CMS_ACCOUNT_BALANCE_HISTORY")
            created, updated = created_updated()
            rows.append((bh_id, acct_no, code, bal_date, opening, closing, "INR",
                         created, updated, src()))
insert_many("CMS_ACCOUNT_BALANCE_HISTORY",
            ["BALANCE_HISTORY_ID", "ACCOUNT_NUMBER", "APR_CLIENT_CODE", "BALANCE_DATE",
             "OPENING_BALANCE", "CLOSING_BALANCE", "CURRENCY_CODE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

rows = []
for code in client_codes:
    eff_from = rand_date(datetime.date(2020, 1, 1), datetime.date(2023, 1, 1))
    created, updated = created_updated()
    rows.append((new_id("CMS_CUSTOMER_SEGMENT_HISTORY"), code, random.choice(SEGMENTS), eff_from,
                 None, client_primary_rm[code], created, updated, src()))
    if random.random() < 0.2:
        eff_to = eff_from - datetime.timedelta(days=1)
        eff_from2 = eff_from - datetime.timedelta(days=random.randint(365, 900))
        created2, updated2 = created_updated()
        rows.append((new_id("CMS_CUSTOMER_SEGMENT_HISTORY"), code, random.choice(SEGMENTS), eff_from2,
                     eff_to, client_primary_rm[code], created2, updated2, src()))
insert_many("CMS_CUSTOMER_SEGMENT_HISTORY",
            ["SEGMENT_HISTORY_ID", "APR_CLIENT_CODE", "SEGMENT_CODE", "EFFECTIVE_FROM_DATE",
             "EFFECTIVE_TO_DATE", "CLASSIFIED_BY_RM_CODE", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], rows)

NOTE_TYPES = ["Risk Observation", "Client Preference", "Internal Reminder", "Compliance Note"]
rows = []
for code in client_codes:
    for _ in range(random.randint(2, 5)):
        note_id = new_id("CMS_NOTES_REMARKS")
        created, updated = created_updated()
        rows.append((note_id, code, client_primary_rm[code], rand_date(datetime.date(2024, 1, 1), TODAY),
                     random.choice(NOTE_TYPES), fake.sentence(nb_words=15), created, updated, src()))
insert_many("CMS_NOTES_REMARKS",
            ["NOTE_ID", "APR_CLIENT_CODE", "RM_CODE", "NOTE_DATE", "NOTE_TYPE", "NOTE_TEXT",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], rows)

# =============================================================================
# 02_Asset_Base.sql
# =============================================================================
print("02_Asset_Base.sql")

ASSET_CATEGORIES = ["Corporate Loans", "Trade Finance", "Investments", "Securities", "Cash & Equivalents"]
CATEGORY_PRODUCTS = {
    "Corporate Loans": [product_code_by_name[n] for n in
                         ["Term Loan - Working Capital", "Term Loan - Capex", "Overdraft Facility", "Cash Credit Facility"]],
    "Trade Finance": [product_code_by_name[n] for n in
                       ["Letter of Credit", "Bank Guarantee", "Bill Discounting", "Export Packing Credit"]],
    "Investments": [product_code_by_name[n] for n in
                     ["Corporate Bond Investment", "Mutual Fund Investment", "Equity Investment Portfolio"]],
    "Securities": [product_code_by_name["G-Sec Investment"]],
    "Cash & Equivalents": [product_code_by_name[n] for n in
                            ["Fixed Deposit Placement", "Certificate of Deposit Holding", "Commercial Paper Holding"]],
}
NPA_CLASSES = ["Standard", "Sub-Standard", "Doubtful", "Loss"]
NPA_WEIGHTS = [0.85, 0.08, 0.05, 0.02]

t = {name: [] for name in [
    "ASSET_ACCOUNT_MASTER", "ASSET_LOAN_DETAILS", "ASSET_LOAN_DISBURSEMENT_SCHEDULE",
    "ASSET_LOAN_REPAYMENT_SCHEDULE", "ASSET_TRADE_FINANCE_DETAILS", "ASSET_INVESTMENT_DETAILS",
    "ASSET_SECURITIES_DETAILS", "ASSET_CASH_EQUIVALENT_DETAILS", "ASSET_COLLATERAL_MASTER",
    "ASSET_COLLATERAL_LINKAGE", "ASSET_NPA_CLASSIFICATION", "ASSET_QUALITY_HISTORY",
    "ASSET_VALUE_HISTORY", "ASSET_INTEREST_RATE_HISTORY", "ASSET_SANCTION_LIMIT",
    "ASSET_COVENANT_MASTER", "ASSET_GUARANTOR_DETAILS", "ASSET_INSURANCE_DETAILS",
    "ASSET_RESTRUCTURING_HISTORY", "ASSET_WRITEOFF_RECOVERY",
]}

for code in client_codes:
    chosen_cats = random.sample(ASSET_CATEGORIES, k=random.randint(1, 3))
    client_loan_accounts = []
    client_asset_products = set()

    for cat in chosen_cats:
        n_accounts = random.randint(1, 3)
        for _ in range(n_accounts):
            aid = new_id("ASSET_ACCOUNT_MASTER")
            product = random.choice(CATEGORY_PRODUCTS[cat])
            client_asset_products.add(product)
            sanction = rand_date(datetime.date(2021, 1, 1), TODAY - datetime.timedelta(days=60))
            tenor_days = {"Corporate Loans": random.randint(365, 2555),
                          "Trade Finance": random.randint(90, 365),
                          "Investments": random.randint(365, 3650),
                          "Securities": random.randint(365, 3650),
                          "Cash & Equivalents": random.randint(30, 365)}[cat]
            maturity = sanction + datetime.timedelta(days=tenor_days)
            status = weighted_choice(["Active", "Closed", "Written-Off"], [0.85, 0.12, 0.03])
            created, updated = created_updated()
            t["ASSET_ACCOUNT_MASTER"].append((aid, code, product, cat, client_branch[code], "INR",
                                               sanction, maturity, status, created, updated, src()))

            base = crore(0.5, 80)

            if cat == "Corporate Loans":
                client_loan_accounts.append(aid)
                loan_type = random.choice(["Term Loan", "Working Capital", "Overdraft", "Cash Credit"])
                disbursed = round(base * random.uniform(0.7, 1.0), 2)
                outstanding = round(disbursed * random.uniform(0.4, 0.95), 2)
                rate = round(random.uniform(8.0, 14.0), 3)
                tenure_months = tenor_days // 30
                created2, updated2 = created_updated()
                t["ASSET_LOAN_DETAILS"].append((aid, loan_type, round(base * 1.05, 2), disbursed, outstanding,
                                                 rate, random.choice(["Monthly", "Quarterly", "Bullet"]),
                                                 tenure_months, created2, updated2, src()))
                n_tranches = random.randint(1, 3)
                remaining = disbursed
                for tr in range(1, n_tranches + 1):
                    amt = round(remaining / (n_tranches - tr + 1), 2)
                    remaining = round(remaining - amt, 2)
                    d_id = new_id("ASSET_LOAN_DISBURSEMENT_SCHEDULE")
                    d_date = sanction + datetime.timedelta(days=30 * tr)
                    created3, updated3 = created_updated()
                    t["ASSET_LOAN_DISBURSEMENT_SCHEDULE"].append((d_id, aid, tr, d_date, amt,
                                                                    created3, updated3, src()))
                for inst in range(1, 13):
                    due = sanction + datetime.timedelta(days=30 * inst)
                    r_id = new_id("ASSET_LOAN_REPAYMENT_SCHEDULE")
                    p_due = round(outstanding / 12, 2)
                    i_due = round(outstanding * (rate / 100 / 12), 2)
                    if due < TODAY:
                        pay_status = weighted_choice(["Paid", "Overdue"], [0.9, 0.1])
                        paid_date = due + datetime.timedelta(days=random.randint(0, 5)) if pay_status == "Paid" else None
                    else:
                        pay_status, paid_date = "Pending", None
                    created4, updated4 = created_updated()
                    t["ASSET_LOAN_REPAYMENT_SCHEDULE"].append((r_id, aid, inst, due, p_due, i_due,
                                                                 pay_status, paid_date, created4, updated4, src()))

            elif cat == "Trade Finance":
                itype = random.choice(["LC", "BG", "BillDiscounting", "ExportFinance"])
                created2, updated2 = created_updated()
                t["ASSET_TRADE_FINANCE_DETAILS"].append((aid, itype, fake.bothify("TF#######"), sanction,
                                                           maturity, fake.company(), base, created2, updated2, src()))

            elif cat == "Investments":
                itype = random.choice(["Bonds", "MutualFund", "Equity", "AIF"])
                created2, updated2 = created_updated()
                t["ASSET_INVESTMENT_DETAILS"].append((aid, itype, fake.company() + " " + itype, fake.bothify("IN#??#####?"),
                                                        round(random.uniform(1000, 500000), 4),
                                                        round(base * 1e7 / max(random.uniform(1000, 500000), 1), 4),
                                                        base, sanction, created2, updated2, src()))

            elif cat == "Securities":
                created2, updated2 = created_updated()
                t["ASSET_SECURITIES_DETAILS"].append((aid, random.choice(["G-Sec", "CorporateBond", "Debenture", "CP"]),
                                                        base, round(random.uniform(6.0, 9.0), 3), maturity,
                                                        random.choice(RATING_GRADES),
                                                        random.choice(["CRISIL", "ICRA", "CARE Ratings"]),
                                                        created2, updated2, src()))

            else:  # Cash & Equivalents
                created2, updated2 = created_updated()
                t["ASSET_CASH_EQUIVALENT_DETAILS"].append((aid, random.choice(["FixedDeposit", "CertificateOfDeposit", "CommercialPaper"]),
                                                             base, round(random.uniform(5.0, 8.0), 3), sanction,
                                                             maturity, created2, updated2, src()))

            npa_class = "Loss" if status == "Written-Off" else weighted_choice(NPA_CLASSES, NPA_WEIGHTS)
            dpd = {"Standard": 0, "Sub-Standard": random.randint(31, 90),
                   "Doubtful": random.randint(91, 365), "Loss": random.randint(366, 900)}[npa_class]
            prov_pct = {"Standard": 0.4, "Sub-Standard": 15.0, "Doubtful": 40.0, "Loss": 100.0}[npa_class]
            npa_id = new_id("ASSET_NPA_CLASSIFICATION")
            created2, updated2 = created_updated()
            t["ASSET_NPA_CLASSIFICATION"].append((npa_id, aid, rand_date(datetime.date(2025, 1, 1), TODAY),
                                                    npa_class, dpd, round(base * prov_pct / 100, 2), prov_pct,
                                                    created2, updated2, src()))

            for m in range(3):
                q_date = TODAY.replace(day=1) - datetime.timedelta(days=90 * m)
                q_id = new_id("ASSET_QUALITY_HISTORY")
                created2, updated2 = created_updated()
                t["ASSET_QUALITY_HISTORY"].append((q_id, aid, q_date, npa_class,
                                                     round(base * random.uniform(0.9, 1.05), 2),
                                                     created2, updated2, src()))

            for m in range(12):
                v_date = TODAY.replace(day=1) - datetime.timedelta(days=30 * m)
                v_date = v_date.replace(day=min(28, v_date.day))
                v_id = new_id("ASSET_VALUE_HISTORY")
                value = round(base * random.uniform(0.88, 1.12), 2)
                created2, updated2 = created_updated()
                t["ASSET_VALUE_HISTORY"].append((v_id, aid, code, v_date, value, "INR",
                                                   created2, updated2, src()))

            for r in range(random.randint(1, 2)):
                rh_id = new_id("ASSET_INTEREST_RATE_HISTORY")
                eff_date = sanction + datetime.timedelta(days=180 * r)
                rate_type = weighted_choice(["Fixed", "Floating"], [0.55, 0.45])
                created2, updated2 = created_updated()
                t["ASSET_INTEREST_RATE_HISTORY"].append((rh_id, aid, eff_date, round(random.uniform(6.5, 13.5), 3),
                                                           rate_type, random.choice(["MCLR", "REPO", "T-Bill", "EBLR"]),
                                                           created2, updated2, src()))

            if random.random() < 0.15:
                cov_id = new_id("ASSET_COVENANT_MASTER")
                created2, updated2 = created_updated()
                t["ASSET_COVENANT_MASTER"].append((cov_id, aid, random.choice(["Financial Covenant", "Reporting Covenant", "Security Covenant"]),
                                                     "Maintain minimum debt-service coverage ratio of 1.2x",
                                                     weighted_choice(["Compliant", "Breach", "UnderReview"], [0.8, 0.1, 0.1]),
                                                     rand_date(datetime.date(2025, 1, 1), TODAY), created2, updated2, src()))
            if random.random() < 0.2:
                g_id = new_id("ASSET_GUARANTOR_DETAILS")
                created2, updated2 = created_updated()
                t["ASSET_GUARANTOR_DETAILS"].append((g_id, aid, fake.name(), random.choice(["Individual", "Corporate"]),
                                                       round(base * random.uniform(0.3, 1.0), 2), created2, updated2, src()))
            if random.random() < 0.2:
                i_id = new_id("ASSET_INSURANCE_DETAILS")
                p_start = sanction
                created2, updated2 = created_updated()
                t["ASSET_INSURANCE_DETAILS"].append((i_id, aid, fake.bothify("POL######"),
                                                       random.choice(["ICICI Lombard", "HDFC Ergo", "New India Assurance"]),
                                                       round(base * random.uniform(1.0, 1.2), 2), p_start,
                                                       p_start + datetime.timedelta(days=365), created2, updated2, src()))
            if random.random() < 0.05:
                rs_id = new_id("ASSET_RESTRUCTURING_HISTORY")
                created2, updated2 = created_updated()
                t["ASSET_RESTRUCTURING_HISTORY"].append((rs_id, aid, rand_date(datetime.date(2024, 1, 1), TODAY),
                                                           "Temporary cash flow mismatch", "Original repayment terms",
                                                           "Extended tenure by 12 months", created2, updated2, src()))
            if status == "Written-Off":
                wo_id = new_id("ASSET_WRITEOFF_RECOVERY")
                wo_date = rand_date(datetime.date(2024, 1, 1), TODAY)
                recovered = random.random() < 0.4
                created2, updated2 = created_updated()
                t["ASSET_WRITEOFF_RECOVERY"].append((wo_id, aid, wo_date, base,
                                                       wo_date + datetime.timedelta(days=random.randint(30, 300)) if recovered else None,
                                                       round(base * random.uniform(0.1, 0.4), 2) if recovered else None,
                                                       created2, updated2, src()))

    if client_asset_products:
        n_limits = random.randint(1, 2)
        for _ in range(n_limits):
            sl_id = new_id("ASSET_SANCTION_LIMIT")
            sanctioned = crore(1, 100)
            utilized = round(sanctioned * random.uniform(0.3, 0.9), 2)
            created2, updated2 = created_updated()
            t["ASSET_SANCTION_LIMIT"].append((sl_id, code, random.choice(list(client_asset_products)), sanctioned,
                                               utilized, round(sanctioned - utilized, 2),
                                               rand_date(datetime.date(2024, 1, 1), TODAY),
                                               rand_date(TODAY, TODAY + datetime.timedelta(days=365)),
                                               created2, updated2, src()))

    if client_loan_accounts:
        n_coll = random.randint(1, 2)
        collateral_ids = []
        for _ in range(n_coll):
            c_id = new_id("ASSET_COLLATERAL_MASTER")
            collateral_ids.append(c_id)
            created2, updated2 = created_updated()
            t["ASSET_COLLATERAL_MASTER"].append((c_id, code, random.choice(["Property", "Stock", "Receivables", "Guarantee", "FixedAsset"]),
                                                   fake.sentence(nb_words=8), crore(1, 60),
                                                   rand_date(datetime.date(2023, 1, 1), TODAY),
                                                   random.choice(["CBRE", "JLL", "Knight Frank"]), created2, updated2, src()))
        for aid in client_loan_accounts:
            c_id = random.choice(collateral_ids)
            lk_id = new_id("ASSET_COLLATERAL_LINKAGE")
            created2, updated2 = created_updated()
            t["ASSET_COLLATERAL_LINKAGE"].append((lk_id, c_id, aid, round(random.uniform(50, 120), 2), created2, updated2, src()))

insert_many("ASSET_ACCOUNT_MASTER",
            ["ASSET_ACCOUNT_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "ASSET_CATEGORY", "BRANCH_CODE",
             "CURRENCY_CODE", "SANCTION_DATE", "MATURITY_DATE", "ACCOUNT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_ACCOUNT_MASTER"])
insert_many("ASSET_LOAN_DETAILS",
            ["ASSET_ACCOUNT_ID", "LOAN_TYPE", "SANCTIONED_AMOUNT", "DISBURSED_AMOUNT", "OUTSTANDING_AMOUNT",
             "INTEREST_RATE", "REPAYMENT_FREQUENCY", "TENURE_MONTHS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_LOAN_DETAILS"])
insert_many("ASSET_LOAN_DISBURSEMENT_SCHEDULE",
            ["DISBURSEMENT_ID", "ASSET_ACCOUNT_ID", "TRANCHE_NUMBER", "DISBURSEMENT_DATE",
             "DISBURSEMENT_AMOUNT", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_LOAN_DISBURSEMENT_SCHEDULE"])
insert_many("ASSET_LOAN_REPAYMENT_SCHEDULE",
            ["REPAYMENT_ID", "ASSET_ACCOUNT_ID", "INSTALLMENT_NUMBER", "DUE_DATE", "PRINCIPAL_DUE",
             "INTEREST_DUE", "PAYMENT_STATUS", "PAID_DATE", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], t["ASSET_LOAN_REPAYMENT_SCHEDULE"])
insert_many("ASSET_TRADE_FINANCE_DETAILS",
            ["ASSET_ACCOUNT_ID", "TRADE_INSTRUMENT_TYPE", "INSTRUMENT_NUMBER", "ISSUE_DATE",
             "EXPIRY_DATE", "BENEFICIARY_NAME", "EXPOSURE_AMOUNT", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], t["ASSET_TRADE_FINANCE_DETAILS"])
insert_many("ASSET_INVESTMENT_DETAILS",
            ["ASSET_ACCOUNT_ID", "INVESTMENT_TYPE", "INSTRUMENT_NAME", "ISIN_CODE", "UNITS_HELD",
             "PURCHASE_PRICE", "CURRENT_MARKET_VALUE", "PURCHASE_DATE", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], t["ASSET_INVESTMENT_DETAILS"])
insert_many("ASSET_SECURITIES_DETAILS",
            ["ASSET_ACCOUNT_ID", "SECURITY_TYPE", "FACE_VALUE", "COUPON_RATE", "MATURITY_DATE",
             "CREDIT_RATING", "RATING_AGENCY", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_SECURITIES_DETAILS"])
insert_many("ASSET_CASH_EQUIVALENT_DETAILS",
            ["ASSET_ACCOUNT_ID", "INSTRUMENT_TYPE", "PRINCIPAL_AMOUNT", "INTEREST_RATE", "DEPOSIT_DATE",
             "MATURITY_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_CASH_EQUIVALENT_DETAILS"])
insert_many("ASSET_COLLATERAL_MASTER",
            ["COLLATERAL_ID", "APR_CLIENT_CODE", "COLLATERAL_TYPE", "COLLATERAL_DESCRIPTION",
             "COLLATERAL_VALUE", "VALUATION_DATE", "VALUATION_AGENCY", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], t["ASSET_COLLATERAL_MASTER"])
insert_many("ASSET_COLLATERAL_LINKAGE",
            ["LINKAGE_ID", "COLLATERAL_ID", "ASSET_ACCOUNT_ID", "COVERAGE_PERCENTAGE", "CREATED_DATE",
             "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_COLLATERAL_LINKAGE"])
insert_many("ASSET_NPA_CLASSIFICATION",
            ["NPA_ID", "ASSET_ACCOUNT_ID", "CLASSIFICATION_DATE", "ASSET_CLASSIFICATION", "DPD_DAYS",
             "PROVISION_AMOUNT", "PROVISION_PERCENTAGE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_NPA_CLASSIFICATION"])
insert_many("ASSET_QUALITY_HISTORY",
            ["QUALITY_HISTORY_ID", "ASSET_ACCOUNT_ID", "AS_OF_DATE", "ASSET_CLASSIFICATION",
             "OUTSTANDING_AMOUNT", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_QUALITY_HISTORY"])
insert_many("ASSET_VALUE_HISTORY",
            ["VALUE_HISTORY_ID", "ASSET_ACCOUNT_ID", "APR_CLIENT_CODE", "AS_OF_DATE", "ASSET_VALUE",
             "CURRENCY_CODE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_VALUE_HISTORY"])
insert_many("ASSET_INTEREST_RATE_HISTORY",
            ["RATE_HISTORY_ID", "ASSET_ACCOUNT_ID", "EFFECTIVE_DATE", "INTEREST_RATE", "RATE_TYPE",
             "BENCHMARK_NAME", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_INTEREST_RATE_HISTORY"])
insert_many("ASSET_SANCTION_LIMIT",
            ["SANCTION_LIMIT_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "SANCTIONED_LIMIT_AMOUNT",
             "UTILIZED_LIMIT_AMOUNT", "AVAILABLE_LIMIT_AMOUNT", "LIMIT_REVIEW_DATE", "LIMIT_EXPIRY_DATE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_SANCTION_LIMIT"])
insert_many("ASSET_COVENANT_MASTER",
            ["COVENANT_ID", "ASSET_ACCOUNT_ID", "COVENANT_TYPE", "COVENANT_DESCRIPTION",
             "COMPLIANCE_STATUS", "REVIEW_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_COVENANT_MASTER"])
insert_many("ASSET_GUARANTOR_DETAILS",
            ["GUARANTOR_ID", "ASSET_ACCOUNT_ID", "GUARANTOR_NAME", "GUARANTOR_TYPE", "GUARANTEE_AMOUNT",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_GUARANTOR_DETAILS"])
insert_many("ASSET_INSURANCE_DETAILS",
            ["INSURANCE_ID", "ASSET_ACCOUNT_ID", "POLICY_NUMBER", "INSURER_NAME", "SUM_INSURED_AMOUNT",
             "POLICY_START_DATE", "POLICY_END_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_INSURANCE_DETAILS"])
insert_many("ASSET_RESTRUCTURING_HISTORY",
            ["RESTRUCTURE_ID", "ASSET_ACCOUNT_ID", "RESTRUCTURE_DATE", "RESTRUCTURE_REASON",
             "OLD_TERMS", "NEW_TERMS", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_RESTRUCTURING_HISTORY"])
insert_many("ASSET_WRITEOFF_RECOVERY",
            ["WRITEOFF_ID", "ASSET_ACCOUNT_ID", "WRITEOFF_DATE", "WRITEOFF_AMOUNT", "RECOVERY_DATE",
             "RECOVERY_AMOUNT", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], t["ASSET_WRITEOFF_RECOVERY"])

# =============================================================================
# 03_Liability_Base.sql
# =============================================================================
print("03_Liability_Base.sql")

LIABILITY_CATEGORIES = ["Term Deposits", "Current Accounts", "Borrowings", "Bonds", "Other Liabilities"]
LIAB_CATEGORY_PRODUCTS = {
    "Term Deposits": [product_code_by_name[n] for n in ["Term Deposit - Corporate", "Callable Deposit"]],
    "Current Accounts": [product_code_by_name[n] for n in ["Current Account - Premium", "Current Account - Standard"]],
    "Borrowings": [product_code_by_name[n] for n in
                   ["Short Term Borrowing", "Term Borrowing", "Refinance Facility", "Inter-Bank Borrowing"]],
    "Bonds": [product_code_by_name[n] for n in ["Corporate Bond Issuance", "Subordinated Bond"]],
    "Other Liabilities": [product_code_by_name[n] for n in ["Certificate of Deposit - Issued", "Commercial Paper - Issued"]],
}
MATURITY_BUCKETS = ["<1Y", "1-3Y", "3-5Y", ">5Y"]


def maturity_bucket(days_to_maturity):
    if days_to_maturity < 365:
        return "<1Y"
    if days_to_maturity < 3 * 365:
        return "1-3Y"
    if days_to_maturity < 5 * 365:
        return "3-5Y"
    return ">5Y"


def rate_bucket(rate, rate_type):
    if rate_type == "Floating":
        return "Floating"
    if rate < 5.0:
        return "Fixed <5%"
    if rate <= 7.0:
        return "Fixed 5-7%"
    return "Fixed >7%"


tl = {name: [] for name in [
    "LIABILITY_ACCOUNT_MASTER", "LIABILITY_TERM_DEPOSIT_DETAILS", "LIABILITY_CURRENT_ACCOUNT_DETAILS",
    "LIABILITY_BORROWING_DETAILS", "LIABILITY_BOND_DETAILS", "LIABILITY_MATURITY_PROFILE",
    "LIABILITY_INTEREST_RATE_HISTORY", "LIABILITY_VALUE_HISTORY", "LIABILITY_RISK_METRICS",
    "LIABILITY_RENEWAL_HISTORY", "LIABILITY_EARLY_CLOSURE_HISTORY", "LIABILITY_NOMINATION_DETAILS",
]}

for code in client_codes:
    chosen_cats = random.sample(LIABILITY_CATEGORIES, k=random.randint(1, 3))
    for cat in chosen_cats:
        n_accounts = random.randint(1, 2)
        for _ in range(n_accounts):
            lid = new_id("LIABILITY_ACCOUNT_MASTER")
            product = random.choice(LIAB_CATEGORY_PRODUCTS[cat])
            open_date = rand_date(datetime.date(2021, 1, 1), TODAY - datetime.timedelta(days=60))
            tenor_days = {"Term Deposits": random.randint(90, 1095), "Current Accounts": 0,
                          "Borrowings": random.randint(365, 2555), "Bonds": random.randint(730, 3650),
                          "Other Liabilities": random.randint(90, 730)}[cat]
            maturity = open_date + datetime.timedelta(days=tenor_days) if tenor_days else None
            status = weighted_choice(["Active", "Closed", "Matured"], [0.85, 0.1, 0.05])
            created, updated = created_updated()
            tl["LIABILITY_ACCOUNT_MASTER"].append((lid, code, product, cat, client_branch[code], "INR",
                                                     open_date, maturity, status, created, updated, src()))

            base = crore(0.2, 60)
            rate = round(random.uniform(3.5, 9.5), 3)
            rate_type = weighted_choice(["Fixed", "Floating"], [0.7, 0.3])

            if cat == "Term Deposits":
                created2, updated2 = created_updated()
                tl["LIABILITY_TERM_DEPOSIT_DETAILS"].append((lid, base, rate, tenor_days // 30, maturity,
                                                               weighted_choice(["Y", "N"], [0.6, 0.4]),
                                                               random.choice(["Monthly", "Quarterly", "Cumulative"]),
                                                               created2, updated2, src()))
                if random.random() < 0.15:
                    ren_id = new_id("LIABILITY_RENEWAL_HISTORY")
                    renewed_maturity = maturity + datetime.timedelta(days=tenor_days)
                    created3, updated3 = created_updated()
                    tl["LIABILITY_RENEWAL_HISTORY"].append((ren_id, lid, maturity, renewed_maturity, maturity,
                                                              round(base * random.uniform(1.0, 1.1), 2),
                                                              created3, updated3, src()))
                if random.random() < 0.05:
                    cl_id = new_id("LIABILITY_EARLY_CLOSURE_HISTORY")
                    closure_date = rand_date(open_date, min(maturity, TODAY))
                    created3, updated3 = created_updated()
                    tl["LIABILITY_EARLY_CLOSURE_HISTORY"].append((cl_id, lid, closure_date, base,
                                                                    round(base * random.uniform(0.005, 0.02), 2),
                                                                    "Client liquidity requirement", created3, updated3, src()))
                nom_id = new_id("LIABILITY_NOMINATION_DETAILS")
                created3, updated3 = created_updated()
                tl["LIABILITY_NOMINATION_DETAILS"].append((nom_id, lid, fake.name(),
                                                             random.choice(["Director", "Partner", "Authorized Signatory"]),
                                                             100.0, created3, updated3, src()))

            elif cat == "Current Accounts":
                created2, updated2 = created_updated()
                tl["LIABILITY_CURRENT_ACCOUNT_DETAILS"].append((lid, base, round(base * 0.1, 2),
                                                                  round(base * random.uniform(0.2, 0.5), 2),
                                                                  created2, updated2, src()))

            elif cat == "Borrowings":
                created2, updated2 = created_updated()
                tl["LIABILITY_BORROWING_DETAILS"].append((lid, random.choice(["TermLoanTaken", "CCBorrowing", "Refinance"]),
                                                            random.choice(["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "IDFC First Bank"]),
                                                            base, rate, "Quarterly repayment over facility tenure",
                                                            created2, updated2, src()))

            elif cat == "Bonds":
                created2, updated2 = created_updated()
                tl["LIABILITY_BOND_DETAILS"].append((lid, random.choice(["NCD", "Subordinated Bond", "Perpetual Bond"]),
                                                       fake.bothify("IN#??#####?"), open_date, base, rate, maturity,
                                                       created2, updated2, src()))

            days_to_mat = (maturity - TODAY).days if maturity else 30
            for snap in range(2):
                snap_date = TODAY - datetime.timedelta(days=90 * snap)
                mp_id = new_id("LIABILITY_MATURITY_PROFILE")
                created2, updated2 = created_updated()
                tl["LIABILITY_MATURITY_PROFILE"].append((mp_id, lid, code, snap_date, maturity_bucket(max(days_to_mat, 1)),
                                                           round(base * random.uniform(0.95, 1.05), 2), created2, updated2, src()))

            for r in range(random.randint(1, 2)):
                rh_id = new_id("LIABILITY_INTEREST_RATE_HISTORY")
                eff_date = open_date + datetime.timedelta(days=180 * r)
                created2, updated2 = created_updated()
                tl["LIABILITY_INTEREST_RATE_HISTORY"].append((rh_id, lid, code, eff_date, rate, rate_type,
                                                                rate_bucket(rate, rate_type), created2, updated2, src()))

            for m in range(12):
                v_date = TODAY.replace(day=1) - datetime.timedelta(days=30 * m)
                v_date = v_date.replace(day=min(28, v_date.day))
                v_id = new_id("LIABILITY_VALUE_HISTORY")
                created2, updated2 = created_updated()
                tl["LIABILITY_VALUE_HISTORY"].append((v_id, lid, code, v_date, round(base * random.uniform(0.9, 1.1), 2),
                                                        "INR", created2, updated2, src()))

            for snap in range(2):
                rm_id = new_id("LIABILITY_RISK_METRICS")
                created2, updated2 = created_updated()
                tl["LIABILITY_RISK_METRICS"].append((rm_id, lid, TODAY - datetime.timedelta(days=90 * snap),
                                                       round(random.uniform(2, 25), 2),
                                                       random.choice(["AAA", "AA", "A", "BBB"]), created2, updated2, src()))

insert_many("LIABILITY_ACCOUNT_MASTER",
            ["LIABILITY_ACCOUNT_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "LIABILITY_CATEGORY", "BRANCH_CODE",
             "CURRENCY_CODE", "ACCOUNT_OPEN_DATE", "MATURITY_DATE", "ACCOUNT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_ACCOUNT_MASTER"])
insert_many("LIABILITY_TERM_DEPOSIT_DETAILS",
            ["LIABILITY_ACCOUNT_ID", "DEPOSIT_AMOUNT", "INTEREST_RATE", "TENURE_MONTHS", "MATURITY_DATE",
             "AUTO_RENEWAL_FLAG", "PAYOUT_FREQUENCY", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_TERM_DEPOSIT_DETAILS"])
insert_many("LIABILITY_CURRENT_ACCOUNT_DETAILS",
            ["LIABILITY_ACCOUNT_ID", "AVERAGE_MONTHLY_BALANCE", "MINIMUM_BALANCE_REQUIRED", "OVERDRAFT_LIMIT",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_CURRENT_ACCOUNT_DETAILS"])
insert_many("LIABILITY_BORROWING_DETAILS",
            ["LIABILITY_ACCOUNT_ID", "BORROWING_TYPE", "LENDER_NAME", "PRINCIPAL_AMOUNT", "INTEREST_RATE",
             "REPAYMENT_TERMS", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_BORROWING_DETAILS"])
insert_many("LIABILITY_BOND_DETAILS",
            ["LIABILITY_ACCOUNT_ID", "BOND_TYPE", "ISIN_CODE", "ISSUE_DATE", "FACE_VALUE", "COUPON_RATE",
             "MATURITY_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_BOND_DETAILS"])
insert_many("LIABILITY_MATURITY_PROFILE",
            ["MATURITY_PROFILE_ID", "LIABILITY_ACCOUNT_ID", "APR_CLIENT_CODE", "AS_OF_DATE", "MATURITY_BUCKET",
             "BUCKET_AMOUNT", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_MATURITY_PROFILE"])
insert_many("LIABILITY_INTEREST_RATE_HISTORY",
            ["RATE_HISTORY_ID", "LIABILITY_ACCOUNT_ID", "APR_CLIENT_CODE", "EFFECTIVE_DATE", "INTEREST_RATE",
             "RATE_TYPE", "RATE_BUCKET", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_INTEREST_RATE_HISTORY"])
insert_many("LIABILITY_VALUE_HISTORY",
            ["VALUE_HISTORY_ID", "LIABILITY_ACCOUNT_ID", "APR_CLIENT_CODE", "AS_OF_DATE", "LIABILITY_VALUE",
             "CURRENCY_CODE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_VALUE_HISTORY"])
insert_many("LIABILITY_RISK_METRICS",
            ["RISK_METRIC_ID", "LIABILITY_ACCOUNT_ID", "AS_OF_DATE", "CONCENTRATION_RISK_PERCENTAGE",
             "FUNDING_STABILITY_RATING", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_RISK_METRICS"])
insert_many("LIABILITY_RENEWAL_HISTORY",
            ["RENEWAL_ID", "LIABILITY_ACCOUNT_ID", "ORIGINAL_MATURITY_DATE", "RENEWED_MATURITY_DATE",
             "RENEWAL_DATE", "RENEWED_AMOUNT", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_RENEWAL_HISTORY"])
insert_many("LIABILITY_EARLY_CLOSURE_HISTORY",
            ["CLOSURE_ID", "LIABILITY_ACCOUNT_ID", "CLOSURE_DATE", "CLOSURE_AMOUNT", "PENALTY_AMOUNT",
             "CLOSURE_REASON", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_EARLY_CLOSURE_HISTORY"])
insert_many("LIABILITY_NOMINATION_DETAILS",
            ["NOMINATION_ID", "LIABILITY_ACCOUNT_ID", "NOMINEE_NAME", "RELATIONSHIP", "SHARE_PERCENTAGE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tl["LIABILITY_NOMINATION_DETAILS"])

# =============================================================================
# 04_Product_Holdings.sql
# =============================================================================
print("04_Product_Holdings.sql")

CHANNELS = ["NetBanking", "MobileApp", "API", "Branch", "RM-Assisted"]
TIERS = ["Platinum", "Gold", "Silver"]

tp = {name: [] for name in [
    "PRODUCT_HOLDING_SUMMARY", "PRODUCT_UTILIZATION", "PRODUCT_UTILIZATION_HISTORY",
    "PRODUCT_CROSS_SELL_OPPORTUNITY", "PRODUCT_FEE_INCOME", "PRODUCT_RELATIONSHIP_DEPTH_SCORE",
    "PRODUCT_PRICING_TERMS", "PRODUCT_CHANNEL_USAGE", "PRODUCT_SERVICE_REQUEST",
]}

for code in client_codes:
    held_products = random.sample(all_product_codes, k=random.randint(3, 8))
    holding_ids = []
    for product in held_products:
        h_id = new_id("PRODUCT_HOLDING_SUMMARY")
        holding_ids.append(h_id)
        activation = rand_date(datetime.date(2020, 1, 1), TODAY - datetime.timedelta(days=30))
        status = weighted_choice(["Active", "Inactive", "Dormant"], [0.8, 0.12, 0.08])
        closure = rand_date(activation, TODAY) if status == "Inactive" else None
        created, updated = created_updated()
        tp["PRODUCT_HOLDING_SUMMARY"].append((h_id, code, product, status, activation, closure,
                                               created, updated, src()))

        sanctioned = crore(0.5, 40)
        utilized = round(sanctioned * random.uniform(0.2, 0.95), 2)
        u_id = new_id("PRODUCT_UTILIZATION")
        created2, updated2 = created_updated()
        tp["PRODUCT_UTILIZATION"].append((u_id, h_id, TODAY, sanctioned, utilized,
                                           round(100 * utilized / sanctioned, 2), created2, updated2, src()))
        for m in range(6):
            uh_id = new_id("PRODUCT_UTILIZATION_HISTORY")
            snap_date = TODAY.replace(day=1) - datetime.timedelta(days=30 * m)
            created3, updated3 = created_updated()
            tp["PRODUCT_UTILIZATION_HISTORY"].append((uh_id, h_id, code, snap_date,
                                                        round(random.uniform(20, 95), 2), created3, updated3, src()))
        for _ in range(random.randint(1, 3)):
            f_id = new_id("PRODUCT_FEE_INCOME")
            created3, updated3 = created_updated()
            tp["PRODUCT_FEE_INCOME"].append((f_id, h_id, random.choice(["Processing Fee", "Commitment Fee", "Renewal Fee", "Advisory Fee"]),
                                              rand_date(datetime.date(2025, 1, 1), TODAY), crore(0.001, 0.5),
                                              "INR", created3, updated3, src()))
        p_id = new_id("PRODUCT_PRICING_TERMS")
        created3, updated3 = created_updated()
        tp["PRODUCT_PRICING_TERMS"].append((p_id, h_id, activation, random.choice(["InterestRate", "FeeSlab", "CommissionRate"]),
                                             round(random.uniform(0.5, 12.0), 4), created3, updated3, src()))

    for _ in range(random.randint(0, 2)):
        remaining = [p for p in all_product_codes if p not in held_products]
        if not remaining:
            break
        op_id = new_id("PRODUCT_CROSS_SELL_OPPORTUNITY")
        created, updated = created_updated()
        tp["PRODUCT_CROSS_SELL_OPPORTUNITY"].append((op_id, code, random.choice(remaining),
                                                       rand_date(datetime.date(2025, 1, 1), TODAY),
                                                       client_primary_rm[code],
                                                       weighted_choice(["Open", "Converted", "Rejected"], [0.5, 0.3, 0.2]),
                                                       crore(0.5, 20), created, updated, src()))

    for m in range(6):
        s_id = new_id("PRODUCT_RELATIONSHIP_DEPTH_SCORE")
        snap_date = TODAY.replace(day=1) - datetime.timedelta(days=30 * m)
        created, updated = created_updated()
        tp["PRODUCT_RELATIONSHIP_DEPTH_SCORE"].append((s_id, code, snap_date, len(held_products),
                                                         round(random.uniform(30, 95), 2),
                                                         random.choice(TIERS), created, updated, src()))

    for ch in random.sample(CHANNELS, k=random.randint(2, len(CHANNELS))):
        c_id = new_id("PRODUCT_CHANNEL_USAGE")
        created, updated = created_updated()
        tp["PRODUCT_CHANNEL_USAGE"].append((c_id, code, ch, random.randint(1, 200),
                                             rand_date(datetime.date(2025, 1, 1), TODAY), created, updated, src()))

    for _ in range(random.randint(0, 2)):
        r_id = new_id("PRODUCT_SERVICE_REQUEST")
        req_date = rand_date(datetime.date(2025, 1, 1), TODAY)
        status = weighted_choice(["Open", "InProgress", "Closed"], [0.2, 0.15, 0.65])
        closure = rand_date(req_date, TODAY) if status == "Closed" else None
        created, updated = created_updated()
        tp["PRODUCT_SERVICE_REQUEST"].append((r_id, code, random.choice(all_product_codes),
                                               random.choice(["Limit Enhancement", "Rate Query", "Statement Request", "Document Correction"]),
                                               req_date, status, closure, created, updated, src()))

insert_many("PRODUCT_HOLDING_SUMMARY",
            ["HOLDING_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "HOLDING_STATUS", "ACTIVATION_DATE",
             "CLOSURE_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_HOLDING_SUMMARY"])
insert_many("PRODUCT_UTILIZATION",
            ["UTILIZATION_ID", "HOLDING_ID", "AS_OF_DATE", "SANCTIONED_VALUE", "UTILIZED_VALUE",
             "UTILIZATION_PERCENTAGE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_UTILIZATION"])
insert_many("PRODUCT_UTILIZATION_HISTORY",
            ["UTILIZATION_HISTORY_ID", "HOLDING_ID", "APR_CLIENT_CODE", "AS_OF_DATE", "UTILIZATION_PERCENTAGE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_UTILIZATION_HISTORY"])
insert_many("PRODUCT_CROSS_SELL_OPPORTUNITY",
            ["OPPORTUNITY_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "IDENTIFIED_DATE", "IDENTIFIED_BY_RM_CODE",
             "OPPORTUNITY_STATUS", "POTENTIAL_VALUE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_CROSS_SELL_OPPORTUNITY"])
insert_many("PRODUCT_FEE_INCOME",
            ["FEE_ID", "HOLDING_ID", "FEE_TYPE", "FEE_DATE", "FEE_AMOUNT", "CURRENCY_CODE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_FEE_INCOME"])
insert_many("PRODUCT_RELATIONSHIP_DEPTH_SCORE",
            ["SCORE_ID", "APR_CLIENT_CODE", "AS_OF_DATE", "ACTIVE_PRODUCT_COUNT", "RELATIONSHIP_SCORE",
             "RELATIONSHIP_TIER", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_RELATIONSHIP_DEPTH_SCORE"])
insert_many("PRODUCT_PRICING_TERMS",
            ["PRICING_ID", "HOLDING_ID", "EFFECTIVE_DATE", "PRICING_TYPE", "PRICING_VALUE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_PRICING_TERMS"])
insert_many("PRODUCT_CHANNEL_USAGE",
            ["CHANNEL_USAGE_ID", "APR_CLIENT_CODE", "CHANNEL_NAME", "USAGE_COUNT", "LAST_USED_DATE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_CHANNEL_USAGE"])
insert_many("PRODUCT_SERVICE_REQUEST",
            ["REQUEST_ID", "APR_CLIENT_CODE", "PRODUCT_CODE", "REQUEST_TYPE", "REQUEST_DATE",
             "REQUEST_STATUS", "CLOSURE_DATE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tp["PRODUCT_SERVICE_REQUEST"])

# =============================================================================
# 05_RM_Details_Interactions.sql
# =============================================================================
print("05_RM_Details_Interactions.sql")

METRIC_TYPES = ["WalletShare", "RevenueContribution", "CrossSellRatio"]

tr = {name: [] for name in [
    "RM_PERFORMANCE_METRICS", "RM_INTERACTION_SUMMARY", "RM_CLIENT_VISIT_PLAN", "RM_ESCALATION_LOG",
    "RM_TRAINING_CERTIFICATION", "RM_TARGET_ACHIEVEMENT", "RM_CLIENT_FEEDBACK",
]}

for code in client_codes:
    rm = client_primary_rm[code]
    for mtype in random.sample(METRIC_TYPES, k=random.randint(2, 3)):
        m_id = new_id("RM_PERFORMANCE_METRICS")
        created, updated = created_updated()
        val = round(random.uniform(5, 90), 2) if mtype != "CrossSellRatio" else round(random.uniform(0.5, 4.0), 2)
        tr["RM_PERFORMANCE_METRICS"].append((m_id, rm, code, TODAY, mtype, val, created, updated, src()))

    for q in range(random.randint(2, 3)):
        s_id = new_id("RM_INTERACTION_SUMMARY")
        period_end = TODAY - datetime.timedelta(days=90 * q)
        period_start = period_end - datetime.timedelta(days=90)
        created, updated = created_updated()
        tr["RM_INTERACTION_SUMMARY"].append((s_id, code, rm, period_start, period_end,
                                              random.randint(3, 15), random.randint(2, 8), random.randint(3, 15),
                                              rand_date(period_start, period_end), created, updated, src()))

    for _ in range(random.randint(1, 2)):
        v_id = new_id("RM_CLIENT_VISIT_PLAN")
        planned = rand_date(TODAY - datetime.timedelta(days=180), TODAY + datetime.timedelta(days=90))
        status = "Planned" if planned >= TODAY else weighted_choice(["Completed", "Cancelled"], [0.85, 0.15])
        created, updated = created_updated()
        tr["RM_CLIENT_VISIT_PLAN"].append((v_id, code, rm, planned,
                                            random.choice(["Quarterly review", "Facility discussion", "Courtesy visit"]),
                                            status, created, updated, src()))

    if random.random() < 0.15:
        e_id = new_id("RM_ESCALATION_LOG")
        esc_date = rand_date(datetime.date(2025, 1, 1), TODAY)
        status = weighted_choice(["Open", "Resolved"], [0.3, 0.7])
        resolved_date = rand_date(esc_date, TODAY) if status == "Resolved" else None
        created, updated = created_updated()
        tr["RM_ESCALATION_LOG"].append((e_id, code, rm, random.choice(senior_rms), esc_date,
                                         random.choice(["Pricing dissatisfaction", "TAT delay", "Documentation dispute"]),
                                         status, resolved_date, created, updated, src()))

    for _ in range(random.randint(1, 2)):
        fb_id = new_id("RM_CLIENT_FEEDBACK")
        created, updated = created_updated()
        tr["RM_CLIENT_FEEDBACK"].append((fb_id, code, rm, rand_date(datetime.date(2025, 1, 1), TODAY),
                                          random.randint(3, 5), fake.sentence(nb_words=12), created, updated, src()))

CERT_NAMES = ["Certified Credit Professional", "Treasury Management Certification", "AML/KYC Certification",
              "Wealth Management Certification"]
for rm in rm_codes:
    for _ in range(random.randint(1, 2)):
        c_id = new_id("RM_TRAINING_CERTIFICATION")
        cert_date = rand_date(datetime.date(2020, 1, 1), TODAY)
        created, updated = created_updated()
        tr["RM_TRAINING_CERTIFICATION"].append((c_id, rm, random.choice(CERT_NAMES), cert_date,
                                                  cert_date + datetime.timedelta(days=1095), created, updated, src()))
    for q in range(4):
        t_id = new_id("RM_TARGET_ACHIEVEMENT")
        target = crore(20, 200)
        created, updated = created_updated()
        tr["RM_TARGET_ACHIEVEMENT"].append((t_id, rm, f"Q{q+1}-FY26", random.choice(["Revenue", "Book Growth", "New Client Acquisition"]),
                                             target, round(target * random.uniform(0.6, 1.15), 2), created, updated, src()))

insert_many("RM_PERFORMANCE_METRICS",
            ["METRIC_ID", "RM_CODE", "APR_CLIENT_CODE", "AS_OF_DATE", "METRIC_TYPE", "METRIC_VALUE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_PERFORMANCE_METRICS"])
insert_many("RM_INTERACTION_SUMMARY",
            ["SUMMARY_ID", "APR_CLIENT_CODE", "RM_CODE", "PERIOD_START_DATE", "PERIOD_END_DATE",
             "TOTAL_CALLS_COUNT", "TOTAL_MEETINGS_COUNT", "TOTAL_EMAILS_COUNT", "LAST_INTERACTION_DATE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_INTERACTION_SUMMARY"])
insert_many("RM_CLIENT_VISIT_PLAN",
            ["VISIT_ID", "APR_CLIENT_CODE", "RM_CODE", "PLANNED_DATE", "VISIT_PURPOSE", "VISIT_STATUS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_CLIENT_VISIT_PLAN"])
insert_many("RM_ESCALATION_LOG",
            ["ESCALATION_ID", "APR_CLIENT_CODE", "RM_CODE", "ESCALATED_TO_RM_CODE", "ESCALATION_DATE",
             "ESCALATION_REASON", "RESOLUTION_STATUS", "RESOLUTION_DATE", "CREATED_DATE", "UPDATED_DATE",
             "SOURCE_SYSTEM"], tr["RM_ESCALATION_LOG"])
insert_many("RM_TRAINING_CERTIFICATION",
            ["CERTIFICATION_ID", "RM_CODE", "CERTIFICATION_NAME", "CERTIFICATION_DATE", "EXPIRY_DATE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_TRAINING_CERTIFICATION"])
insert_many("RM_TARGET_ACHIEVEMENT",
            ["TARGET_ID", "RM_CODE", "PERIOD_LABEL", "TARGET_TYPE", "TARGET_VALUE", "ACHIEVED_VALUE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_TARGET_ACHIEVEMENT"])
insert_many("RM_CLIENT_FEEDBACK",
            ["FEEDBACK_ID", "APR_CLIENT_CODE", "RM_CODE", "FEEDBACK_DATE", "RATING", "FEEDBACK_COMMENTS",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], tr["RM_CLIENT_FEEDBACK"])

# =============================================================================
# 06_RM_Discussion.sql
# =============================================================================
print("06_RM_Discussion.sql")

TOPIC_CATEGORIES = ["Facility Renewal", "New Product Pitch", "Pricing Negotiation", "Compliance Update",
                     "Market Outlook", "Relationship Review"]
NEED_CATEGORIES = ["Working Capital", "Trade Finance", "Treasury Solutions", "Digital Banking", "Investment Advisory"]

td = {name: [] for name in [
    "RM_DISCUSSION_SESSION", "RM_DISCUSSION_TOPIC", "RM_CLIENT_NEED_IDENTIFIED", "RM_PROPOSED_SOLUTION",
    "RM_FOLLOWUP_ACTION", "RM_DISCUSSION_OUTCOME",
]}

for code in client_codes:
    rm = client_primary_rm[code]
    n_sessions = random.randint(5, 15)
    for _ in range(n_sessions):
        d_id = new_id("RM_DISCUSSION_SESSION")
        disc_date = rand_date(datetime.date(2024, 6, 1), TODAY)
        meeting_id = random.choice(meeting_ids_by_client[code]) if meeting_ids_by_client[code] and random.random() < 0.4 else None
        created, updated = created_updated()
        td["RM_DISCUSSION_SESSION"].append((d_id, code, rm, meeting_id, disc_date,
                                             random.choice(MEETING_TYPES), created, updated, src()))

        for _ in range(random.randint(1, 3)):
            tp_id = new_id("RM_DISCUSSION_TOPIC")
            created2, updated2 = created_updated()
            td["RM_DISCUSSION_TOPIC"].append((tp_id, d_id, random.choice(TOPIC_CATEGORIES),
                                               fake.sentence(nb_words=14), created2, updated2, src()))

        need_ids = []
        for _ in range(random.randint(1, 2)):
            n_id = new_id("RM_CLIENT_NEED_IDENTIFIED")
            need_ids.append(n_id)
            created2, updated2 = created_updated()
            td["RM_CLIENT_NEED_IDENTIFIED"].append((n_id, d_id, random.choice(NEED_CATEGORIES),
                                                      fake.sentence(nb_words=14),
                                                      random.choice(["High", "Medium", "Low"]), created2, updated2, src()))

        for _ in range(random.randint(0, 2)):
            s_id = new_id("RM_PROPOSED_SOLUTION")
            created2, updated2 = created_updated()
            td["RM_PROPOSED_SOLUTION"].append((s_id, d_id, random.choice(need_ids) if need_ids and random.random() < 0.8 else None,
                                                random.choice(all_product_codes), crore(0.5, 25),
                                                weighted_choice(["Proposed", "Accepted", "Declined", "UnderReview"], [0.35, 0.3, 0.15, 0.2]),
                                                created2, updated2, src()))

        for _ in range(random.randint(0, 2)):
            a_id = new_id("RM_FOLLOWUP_ACTION")
            due = disc_date + datetime.timedelta(days=random.randint(3, 30))
            status = "Open" if due >= TODAY else weighted_choice(["Completed", "Overdue"], [0.75, 0.25])
            created2, updated2 = created_updated()
            td["RM_FOLLOWUP_ACTION"].append((a_id, d_id, fake.sentence(nb_words=10), rm, due, status,
                                              created2, updated2, src()))

        o_id = new_id("RM_DISCUSSION_OUTCOME")
        created2, updated2 = created_updated()
        td["RM_DISCUSSION_OUTCOME"].append((o_id, d_id, fake.paragraph(nb_sentences=2),
                                             fake.sentence(nb_words=10),
                                             disc_date + datetime.timedelta(days=random.randint(30, 120)),
                                             created2, updated2, src()))

insert_many("RM_DISCUSSION_SESSION",
            ["DISCUSSION_ID", "APR_CLIENT_CODE", "RM_CODE", "MEETING_ID", "DISCUSSION_DATE",
             "DISCUSSION_MODE", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_DISCUSSION_SESSION"])
insert_many("RM_DISCUSSION_TOPIC",
            ["TOPIC_ID", "DISCUSSION_ID", "TOPIC_CATEGORY", "TOPIC_DESCRIPTION", "CREATED_DATE",
             "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_DISCUSSION_TOPIC"])
insert_many("RM_CLIENT_NEED_IDENTIFIED",
            ["NEED_ID", "DISCUSSION_ID", "NEED_CATEGORY", "NEED_DESCRIPTION", "PRIORITY", "CREATED_DATE",
             "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_CLIENT_NEED_IDENTIFIED"])
insert_many("RM_PROPOSED_SOLUTION",
            ["SOLUTION_ID", "DISCUSSION_ID", "NEED_ID", "PROPOSED_PRODUCT_CODE", "PROPOSED_VALUE",
             "PROPOSAL_STATUS", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_PROPOSED_SOLUTION"])
insert_many("RM_FOLLOWUP_ACTION",
            ["ACTION_ID", "DISCUSSION_ID", "ACTION_DESCRIPTION", "OWNER_RM_CODE", "DUE_DATE",
             "ACTION_STATUS", "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_FOLLOWUP_ACTION"])
insert_many("RM_DISCUSSION_OUTCOME",
            ["OUTCOME_ID", "DISCUSSION_ID", "OUTCOME_SUMMARY", "NEXT_STEP", "NEXT_REVIEW_DATE",
             "CREATED_DATE", "UPDATED_DATE", "SOURCE_SYSTEM"], td["RM_DISCUSSION_OUTCOME"])

cur.close()
conn.close()

total_rows = sum(_id_counters.values())
print(f"\nDone. {len(_id_counters)} tables seeded via explicit IDs, ~{total_rows} rows via those tables alone")
print("(plus natural-key tables: branches, currencies, sectors, RMs, products, clients, accounts).")
