import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./issues.db")

# On Fly.io / Docker, DB lives on persistent volume
db_path = DATABASE_URL.replace("sqlite:///", "")
if not os.path.isabs(db_path) and not db_path.startswith("."):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", db_path)
    DATABASE_URL = f"sqlite:///{db_path}"

# SQLite needs check_same_thread=False; PostgreSQL doesn't
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    constituency_id = Column(String, index=True)
    ward = Column(String, nullable=True, index=True)
    mla_name = Column(String, nullable=True)
    complainant_name = Column(String, nullable=True)
    complainant_address = Column(String, nullable=True)
    contact_number = Column(String, nullable=True)
    issue_summary = Column(Text, nullable=False)
    issue_category = Column(String, nullable=True, default="Garbage")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    images = Column(Text, nullable=True)
    resolution_photo = Column(String, nullable=True)
    upvotes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)


class WatchSubscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, nullable=True, index=True)     # Telegram chat ID
    email = Column(String, nullable=True, index=True)        # Legacy email
    constituency_id = Column(String, nullable=True)
    ward = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    unsubscribe_token = Column(String, nullable=True, unique=True)


# ═══════════════════════════════════════════════
# MCD 250 Wards → Assembly Constituency Mapping
# Built from Delhi Gazette post-2022 delimitation.
# Each ward belongs to exactly one constituency.
# ═══════════════════════════════════════════════
#
# CONSTITUENCY ID → NAME (from GeoJSON):
#   1=NARELA  2=BURARI  3=TIMARPUR  4=ADARSH NAGAR  5=BADLI  6=RITHALA
#   7=BAWANA  8=MUNDKA  9=KIRARI  10=SULTANPUR MAJRA  11=NANGLOI JAT
#   12=MANGOL PURI  13=ROHINI  14=SHALIMAR BAGH  15=SHAKUR BASTI
#   16=TRI NAGAR  17=WAZIRPUR  18=MODEL TOWN  19=SADAR BAZAR
#   20=CHANDNI CHOWK  21=MATIA MAHAL  22=BALLIMARAN  23=KAROL BAGH
#   24=PATEL NAGAR  25=MOTI NAGAR  26=MADIPUR  27=RAJOURI GARDEN
#   28=HARI NAGAR  29=TILAK NAGAR  30=JANAKPURI  31=VIKASPURI
#   32=UTTAM NAGAR  33=DWARKA  34=MATIALA  35=NAJAFGARH
#   36=BIJWASAN  37=PALAM  38=DELHI CANTONMENT  39=RAJINDER NAGAR
#   40=NEW DELHI  41=JANGPURA  42=KASTURBA NAGAR  43=MALVIYA NAGAR
#   44=R K PURAM  45=MEHRAULI  46=CHHATARPUR  47=DEOLI
#   48=AMBEDKAR NAGAR  49=SANGAM VIHAR  50=GREATER KAILASH
#   51=KALKAJI  52=TUGHLAKABAD  53=BADARPUR  54=OKHLA
#   55=TRILOKPURI  56=KONDLI  57=PATPARGANJ  58=LAXMI NAGAR
#   59=VISHWAS NAGAR  60=KRISHNA NAGAR  61=GANDHI NAGAR
#   62=SHAHDARA  63=SEEMAPURI  64=ROHTAS NAGAR  65=SEELAMPUR
#   66=GHONDA  67=BABARPUR  68=GOKALPUR  69=MUSTAFABAD  70=KARAWAL NAGAR

# Each tuple: (ward_name, constituency_id)
MCD_WARDS = [
    # ═══ NARELA ZONE (Wards 1–26) ═══
    ("Ward 001-N - Narela", 1),
    ("Ward 002-N - Holambi Kalan", 1),
    ("Ward 003-N - Alipur", 1),
    ("Ward 004-N - Bakhtawarpur", 1),
    ("Ward 005-N - Bankner", 1),
    ("Ward 006-N - Lampur", 1),
    ("Ward 007-N - Bawana", 7),
    ("Ward 008-N - Pooth Khurd", 7),
    ("Ward 009-N - Bawana Industrial", 7),
    ("Ward 010-N - Katewara", 7),
    ("Ward 011-N - Auchandi", 7),
    ("Ward 012-N - Kanjhawala", 7),
    ("Ward 013-N - Rani Khera", 8),
    ("Ward 014-N - Mundka", 8),
    ("Ward 015-N - Bakkarwala", 8),
    ("Ward 016-N - Tikri Kalan", 8),
    ("Ward 017-N - Ghevra", 8),
    ("Ward 018-N - Nangloi", 11),
    ("Ward 019-N - Nangloi East", 11),
    ("Ward 020-N - Nilothi", 11),
    ("Ward 021-N - Nihal Vihar", 11),
    ("Ward 022-N - Kirari Suleman Nagar", 9),
    ("Ward 023-N - Kirari", 9),
    ("Ward 024-N - Mubarakpur Dabas", 9),
    ("Ward 025-N - Prem Nagar", 9),
    ("Ward 026-N - Sultanpuri", 10),

    # ═══ CIVIL LINES ZONE (Wards 27–52) ═══
    ("Ward 027-C - Burari", 2),
    ("Ward 028-C - Jagatpur", 2),
    ("Ward 029-C - Mukundpur", 2),
    ("Ward 030-C - Bhalswa", 2),
    ("Ward 031-C - Jahangirpuri", 2),
    ("Ward 032-C - Adarsh Nagar", 4),
    ("Ward 033-C - Sarai Pipal Thala", 4),
    ("Ward 034-C - Badli", 5),
    ("Ward 035-C - Samaypur", 5),
    ("Ward 036-C - Libaspur", 5),
    ("Ward 037-C - Bhalswa Dairy", 5),
    ("Ward 038-C - Swaroop Nagar", 1),
    ("Ward 039-C - Singhola", 1),
    ("Ward 040-C - Timarpur", 3),
    ("Ward 041-C - Civil Lines", 3),
    ("Ward 042-C - GTB Nagar", 3),
    ("Ward 043-C - Mukherjee Nagar", 3),
    ("Ward 044-C - Dhirpur", 3),
    ("Ward 045-C - Model Town", 18),
    ("Ward 046-C - Gujranwala Town", 18),
    ("Ward 047-C - Derawal Nagar", 18),
    ("Ward 048-C - Kamla Nagar", 18),
    ("Ward 049-C - Shakti Nagar", 19),
    ("Ward 050-C - Mori Gate", 19),
    ("Ward 051-C - Chandni Chowk", 20),
    ("Ward 052-C - Daryaganj", 20),

    # ═══ SADAR PAHARGANJ ZONE (Wards 53–77) ═══
    ("Ward 053-SP - Sadar Bazar", 19),
    ("Ward 054-SP - Qasabpura", 19),
    ("Ward 055-SP - Idgah Road", 19),
    ("Ward 056-SP - Paharganj", 21),
    ("Ward 057-SP - Ram Nagar", 21),
    ("Ward 058-SP - Bazar Sita Ram", 21),
    ("Ward 059-SP - Jama Masjid", 20),
    ("Ward 060-SP - Ballimaran", 22),
    ("Ward 061-SP - Chitli Qabar", 22),
    ("Ward 062-SP - Hauz Qazi", 20),
    ("Ward 063-SP - Turkman Gate", 22),
    ("Ward 064-SP - Ajmeri Gate", 22),
    ("Ward 065-SP - Matia Mahal", 21),
    ("Ward 066-SP - Suiwalan", 21),
    ("Ward 067-SP - Karol Bagh", 23),
    ("Ward 068-SP - Dev Nagar", 23),
    ("Ward 069-SP - Pusa", 23),
    ("Ward 070-SP - Inderpuri", 23),
    ("Ward 071-SP - Naraina", 23),
    ("Ward 072-SP - Rajinder Nagar", 39),
    ("Ward 073-SP - Prasad Nagar", 39),
    ("Ward 074-SP - New Rajinder Nagar", 39),
    ("Ward 075-SP - Old Rajinder Nagar", 39),
    ("Ward 076-SP - Patel Nagar", 24),
    ("Ward 077-SP - Ranjit Nagar", 24),

    # ═══ KESHAV PURAM ZONE (Wards 78–103) ═══
    ("Ward 078-KP - Keshav Puram", 14),
    ("Ward 079-KP - Pitampura", 14),
    ("Ward 080-KP - Shalimar Bagh", 14),
    ("Ward 081-KP - Saraswati Vihar", 14),
    ("Ward 082-KP - Rani Bagh", 15),
    ("Ward 083-KP - Shakur Basti", 15),
    ("Ward 084-KP - Tri Nagar", 16),
    ("Ward 085-KP - Wazirpur", 17),
    ("Ward 086-KP - Ashok Vihar", 17),
    ("Ward 087-KP - Rithala", 6),
    ("Ward 088-KP - Rohini North", 13),
    ("Ward 089-KP - Rohini Sector 11", 13),
    ("Ward 090-KP - Rohini Sector 16", 13),
    ("Ward 091-KP - Rohini Sector 3", 13),
    ("Ward 092-KP - Mangolpuri", 12),
    ("Ward 093-KP - Mangolpuri Industrial", 12),
    ("Ward 094-KP - Sultanpuri C Block", 10),
    ("Ward 095-KP - Sultanpuri D Block", 10),
    ("Ward 096-KP - Budh Vihar", 9),
    ("Ward 097-KP - Vijay Vihar", 6),
    ("Ward 098-KP - Rohini Sector 24", 13),
    ("Ward 099-KP - Rohini Sector 19", 13),
    ("Ward 100-KP - Prashant Vihar", 6),
    ("Ward 101-KP - Sector 14 Rohini", 13),
    ("Ward 102-KP - Sector 15 Rohini", 13),
    ("Ward 103-KP - Sector 9 Rohini", 13),

    # ═══ WEST ZONE (Wards 104–128) ═══
    ("Ward 104-W - Madipur", 26),
    ("Ward 105-W - Punjabi Bagh", 26),
    ("Ward 106-W - Shivaji Park", 26),
    ("Ward 107-W - Moti Nagar", 25),
    ("Ward 108-W - Kirti Nagar", 25),
    ("Ward 109-W - Ramesh Nagar", 27),
    ("Ward 110-W - Rajouri Garden", 27),
    ("Ward 111-W - Tagore Garden", 27),
    ("Ward 112-W - Vishnu Garden", 27),
    ("Ward 113-W - Tilak Nagar", 29),
    ("Ward 114-W - Tilak Vihar", 29),
    ("Ward 115-W - Fateh Nagar", 29),
    ("Ward 116-W - Hari Nagar", 28),
    ("Ward 117-W - Subhash Nagar", 28),
    ("Ward 118-W - Mayapuri", 28),
    ("Ward 119-W - Janakpuri North", 30),
    ("Ward 120-W - Janakpuri South", 30),
    ("Ward 121-W - Janakpuri West", 30),
    ("Ward 122-W - Vikaspuri", 31),
    ("Ward 123-W - Vikas Nagar", 31),
    ("Ward 124-W - Hastsal", 32),
    ("Ward 125-W - Uttam Nagar", 32),
    ("Ward 126-W - Mohan Garden", 32),
    ("Ward 127-W - Bindapur", 32),
    ("Ward 128-W - Dabri", 33),

    # ═══ NAJAFGARH ZONE (Wards 129–154) ═══
    ("Ward 129-NJ - Dwarka Sector 6", 33),
    ("Ward 130-NJ - Dwarka Sector 10", 33),
    ("Ward 131-NJ - Dwarka Sector 23", 33),
    ("Ward 132-NJ - Kakrola", 34),
    ("Ward 133-NJ - Matiala", 34),
    ("Ward 134-NJ - Chhawla", 34),
    ("Ward 135-NJ - Najafgarh", 35),
    ("Ward 136-NJ - Dichaon Kalan", 35),
    ("Ward 137-NJ - Roshanpura", 35),
    ("Ward 138-NJ - Khera Dabar", 35),
    ("Ward 139-NJ - Mitraon", 35),
    ("Ward 140-NJ - Jharoda Kalan", 35),
    ("Ward 141-NJ - Palam", 37),
    ("Ward 142-NJ - Mahipalpur", 37),
    ("Ward 143-NJ - Raj Nagar", 37),
    ("Ward 144-NJ - Madhu Vihar", 37),
    ("Ward 145-NJ - Bijwasan", 36),
    ("Ward 146-NJ - Kapashera", 36),
    ("Ward 147-NJ - Samalkha", 36),
    ("Ward 148-NJ - Shahbad Mohammadpur", 36),
    ("Ward 149-NJ - Dwarka Sector 8", 33),
    ("Ward 150-NJ - Pochanpur", 33),
    ("Ward 151-NJ - Dwaraka Sector 3", 33),
    ("Ward 152-NJ - Sagarpur", 33),
    ("Ward 153-NJ - Manglapuri", 37),
    ("Ward 154-NJ - Sadh Nagar", 37),

    # ═══ SOUTH ZONE (Wards 155–180) ═══
    ("Ward 155-S - Malviya Nagar", 43),
    ("Ward 156-S - Safdarjung Enclave", 43),
    ("Ward 157-S - Hauz Khas", 43),
    ("Ward 158-S - Green Park", 50),
    ("Ward 159-S - Greater Kailash I", 50),
    ("Ward 160-S - Chittaranjan Park", 50),
    ("Ward 161-S - Kalkaji", 51),
    ("Ward 162-S - Govindpuri", 51),
    ("Ward 163-S - Tughlakabad Extension", 52),
    ("Ward 164-S - Sangam Vihar", 49),
    ("Ward 165-S - Deoli", 47),
    ("Ward 166-S - Tigri", 47),
    ("Ward 167-S - Khanpur", 47),
    ("Ward 168-S - Ambedkar Nagar", 48),
    ("Ward 169-S - Dakshinpuri", 48),
    ("Ward 170-S - Madangir", 48),
    ("Ward 171-S - Chhatarpur", 46),
    ("Ward 172-S - Mehrauli", 45),
    ("Ward 173-S - Lado Sarai", 45),
    ("Ward 174-S - Vasant Kunj", 45),
    ("Ward 175-S - Munirka", 44),
    ("Ward 176-S - R K Puram", 44),
    ("Ward 177-S - Nanakpura", 44),
    ("Ward 178-S - Vasant Vihar", 44),
    ("Ward 179-S - Lajpat Nagar", 42),
    ("Ward 180-S - Kotla Mubarakpur", 42),

    # ═══ CENTRAL ZONE (Wards 181–203) ═══
    ("Ward 181-CZ - New Delhi", 40),
    ("Ward 182-CZ - Connaught Place", 40),
    ("Ward 183-CZ - Gole Market", 40),
    ("Ward 184-CZ - Mandir Marg", 40),
    ("Ward 185-CZ - Delhi Cantt", 38),
    ("Ward 186-CZ - Naraina Village", 38),
    ("Ward 187-CZ - Nangal Raya", 38),
    ("Ward 188-CZ - Jangpura", 41),
    ("Ward 189-CZ - Bhogal", 41),
    ("Ward 190-CZ - Nizamuddin", 41),
    ("Ward 191-CZ - Sarai Kale Khan", 41),
    ("Ward 192-CZ - Kasturba Nagar", 42),
    ("Ward 193-CZ - Andrews Ganj", 42),
    ("Ward 194-CZ - Defence Colony", 42),
    ("Ward 195-CZ - Okhla", 54),
    ("Ward 196-CZ - Zakir Nagar", 54),
    ("Ward 197-CZ - Shaheen Bagh", 54),
    ("Ward 198-CZ - Abul Fazal Enclave", 54),
    ("Ward 199-CZ - Badarpur", 53),
    ("Ward 200-CZ - Jaitpur", 53),
    ("Ward 201-CZ - Molarband", 53),
    ("Ward 202-CZ - Meethapur", 53),
    ("Ward 203-CZ - Hari Nagar Ext", 28),

    # ═══ SHAHDARA NORTH ZONE (Wards 204–226) ═══
    ("Ward 204-SN - Shahdara", 62),
    ("Ward 205-SN - Nand Nagri", 64),
    ("Ward 206-SN - Rohtas Nagar", 64),
    ("Ward 207-SN - Babarpur", 67),
    ("Ward 208-SN - Maujpur", 67),
    ("Ward 209-SN - Seelampur", 65),
    ("Ward 210-SN - Gautampuri", 65),
    ("Ward 211-SN - Jafrabad", 65),
    ("Ward 212-SN - Welcome Colony", 64),
    ("Ward 213-SN - Seemapuri", 63),
    ("Ward 214-SN - Dilshad Colony", 63),
    ("Ward 215-SN - Dilshad Garden", 63),
    ("Ward 216-SN - Vivek Vihar", 59),
    ("Ward 217-SN - Vishwas Nagar", 59),
    ("Ward 218-SN - Karkardooma", 59),
    ("Ward 219-SN - Anand Vihar", 59),
    ("Ward 220-SN - Jhilmil", 63),
    ("Ward 221-SN - Tahirpur", 63),
    ("Ward 222-SN - New Seelampur", 65),
    ("Ward 223-SN - Gandhi Nagar", 61),
    ("Ward 224-SN - Krishna Nagar", 60),
    ("Ward 225-SN - Geeta Colony", 60),
    ("Ward 226-SN - Kanti Nagar", 60),

    # ═══ SHAHDARA SOUTH ZONE (Wards 227–250) ═══
    ("Ward 227-SS - Laxmi Nagar", 58),
    ("Ward 228-SS - Shakarpur", 58),
    ("Ward 229-SS - Pandav Nagar", 58),
    ("Ward 230-SS - Patparganj", 57),
    ("Ward 231-SS - Mayur Vihar Phase I", 57),
    ("Ward 232-SS - Mayur Vihar Phase II", 57),
    ("Ward 233-SS - Trilokpuri", 55),
    ("Ward 234-SS - Kalyanpuri", 55),
    ("Ward 235-SS - Kondli", 56),
    ("Ward 236-SS - Dallupura", 56),
    ("Ward 237-SS - New Ashok Nagar", 56),
    ("Ward 238-SS - Chilla Village", 57),
    ("Ward 239-SS - Vinod Nagar", 57),
    ("Ward 240-SS - Mandawali", 57),
    ("Ward 241-SS - IP Extension", 58),
    ("Ward 242-SS - Ghonda", 66),
    ("Ward 243-SS - Yamuna Vihar", 66),
    ("Ward 244-SS - Bhajanpura", 66),
    ("Ward 245-SS - Gokalpur", 68),
    ("Ward 246-SS - Karawal Nagar", 70),
    ("Ward 247-SS - Mustafabad", 69),
    ("Ward 248-SS - Dayalpur", 70),
    ("Ward 249-SS - Sadatpur", 70),
    ("Ward 250-SS - Sonia Vihar", 70),
]

# Build lookup: constituency_id → list of ward names
CONSTITUENCY_WARDS = {}
for ward_name, const_id in MCD_WARDS:
    const_id_str = str(const_id)
    if const_id_str not in CONSTITUENCY_WARDS:
        CONSTITUENCY_WARDS[const_id_str] = []
    CONSTITUENCY_WARDS[const_id_str].append(ward_name)

# MCD Zone → official complaint email
# Constituency → zone derived from ward assignments
MCD_ZONE_EMAILS = {
    "Narela": "complaint-narela@mcd.org.in",
    "Civil Lines": "complaint-civil-lines@mcd.org.in",
    "Sadar Paharganj": "complaint-sadar-paharganj@mcd.org.in",
    "Keshav Puram": "complaint-keshav-puram@mcd.org.in",
    "West": "complaint-west@mcd.org.in",
    "Najafgarh": "complaint-najafgarh@mcd.org.in",
    "South": "complaint-south@mcd.org.in",
    "Central": "complaint-central@mcd.org.in",
    "Shahdara North": "complaint-shahdara-north@mcd.org.in",
    "Shahdara South": "complaint-shahdara-south@mcd.org.in",
}

# Map constituency ID → MCD zone name (derived from ward suffixes)
CONSTITUENCY_MCD_ZONE = {}
zone_suffix_map = {
    "N": "Narela", "C": "Civil Lines", "SP": "Sadar Paharganj",
    "KP": "Keshav Puram", "W": "West", "NJ": "Najafgarh",
    "S": "South", "CZ": "Central", "SN": "Shahdara North",
    "SS": "Shahdara South",
}
for ward_name, const_id in MCD_WARDS:
    for suffix, zone in zone_suffix_map.items():
        if f"-{suffix} " in ward_name or ward_name.endswith(f"-{suffix}"):
            CONSTITUENCY_MCD_ZONE[str(const_id)] = zone
            break

Base.metadata.create_all(bind=engine)
