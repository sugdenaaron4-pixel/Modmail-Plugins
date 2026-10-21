import asyncio
import json
import os
from pathlib import Path

import discord
from discord.ext import commands
from discord.ui import View, Button


# ============================================================
# EASTLIGHT PRIMARY SCHOOL MODMAIL CONFIGURATION
# ============================================================

EMBED_COLOUR = 0xE02E2E
PREFIX = "-"

# Role allowed to use ?closeapp and ?openapp.
# Replace 0 with your Discord role ID.
CLOSEAPP_ALLOWED_ROLE_ID = 1553769601186144409

# Users with Administrator permission can also manage closures.
ALLOW_ADMIN_OVERRIDE = True

# Category used while a ticket awaits department selection.
AWAITING_PLACEMENT_CATEGORY = 1559299230533947484  # Replace with your category ID.

# Department categories.
# Replace the zeroes with the correct Discord category IDs.
DEPARTMENT_CATEGORIES = {
    "01": 1562212040582373376,  # General Enquiries
    "02": 1562212125860958309,  # Careers
    "03": 1562212854189264986,  # Legal & Abuse
    "04": 1562520490545774714,  # Development Enquiries — set this to its Discord category ID
}

# Department staff role IDs. Replace each 0 with the matching Discord role ID.
# Members of a department role can view and reply to that department's tickets.
# Other configured department roles are explicitly denied access to those tickets.
DEPARTMENT_ROLE_IDS = {
    "01": 1562532416134848532,  # General Enquiries staff role
    "02": 1562532476629549197,  # Careers staff role
    "03": 1562532530429763625,  # Legal & Abuse staff role
    "04": 1562532614244671598,  # Development Enquiries staff role
}

# Optional individual Careers branch categories.
# Set each ID to 0 to use the general Careers category instead.
CAREER_BRANCH_CATEGORIES = {
    "LLT": 1562212125860958309,
    "MLT": 1562212187269759108,
    "SLT": 1562212268941517001,
    "SITE": 1562212772450672670,
}

DATA_DIR = Path("data")
APPLICATION_STATUS_FILE = DATA_DIR / "application_status.json"

DEPARTMENTS = {
    "01": "General Enquiries",
    "02": "Careers",
    "03": "Legal & Abuse",
    "04": "Development Enquiries",
}

CAREER_BRANCHES = {
    "LLT": "Lower Leadership Team (LLT)",
    "MLT": "Middle Leadership Team (MLT)",
    "SLT": "Senior Leadership Team (SLT)",
    "SITE": "Site Team (SITE)",
}

AVERAGE_HANDLE_TIME = {
    "01": 5,
    "02": 8,
    "03": 10,
    "04": 8,
}

DEPARTMENT_ALIASES = {
    "01": "01",
    "1": "01",
    "general": "01",
    "general enquiries": "01",
    "general inquiries": "01",

    "02": "02",
    "2": "02",
    "careers": "02",
    "career": "02",

    "03": "03",
    "3": "03",
    "legal": "03",
    "abuse": "03",
    "legal & abuse": "03",
