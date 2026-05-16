"""Resume data loader — reads text extracted from ABDELMOUMEN MOHAMED.pdf."""

from __future__ import annotations

RAW_RESUME_TEXT = (
    "MOHAMED ABDELMOUMEN\n"
    "Technical Support Technician\n"
    "Zamora Michoacan, Mexico\n"
    "simo.abdelmoumen10@gmail.com\n\n"
    "EXPERIENCE\n"
    "EURAFRIC, Casablanca — Technical Support Technician (Oct 2023 - Jun 2024)\n"
    "Level 1 & 2 support for hardware/software/network issues\n"
    "Configured switches, routers, LAN/WAN, WiFi\n"
    "Installed servers, workstations, printers; managed Active Directory & backups\n"
    "Installed and configured antivirus solutions\n"
    "Configured professional email clients (Outlook, mobile)\n\n"
    "POL IT, Casablanca — IT Technician (Feb 2023 - Oct 2023)\n"
    "Diagnosed and resolved hardware/software issues\n"
    "Maintained and repaired computer equipment\n"
    "Provided user support; documented procedures\n\n"
    "CBI, Casablanca — IT Technician (Aug 2022 - Feb 2023)\n"
    "Maintained IT equipment; installed and configured computers\n"
    "Configured and monitored network equipment\n"
    "Assisted users with IT issues\n\n"
    "EDUCATION\n"
    "Bachelor's in Network Administration and Security — FST Settat (2025)\n"
    "Specialized Technician in Computer Networks — ISTA Beni Mellal (2022)\n\n"
    "SKILLS\n"
    "Networking: Switches, routers, LAN, WAN, WiFi\n"
    "Systems: Server administration, Active Directory, email config, antivirus\n"
    "Maintenance: Computer hardware repair and maintenance\n"
    "Languages: Arabic (Proficient), English (Proficient), "
    "French (Proficient), Spanish (Intermediate)"
)


def load_resume_text() -> str:
    return RAW_RESUME_TEXT


def extract_keywords() -> list[str]:
    return sorted({
        "technical support", "network administration", "IT support",
        "help desk", "system administrator", "Active Directory",
        "switches", "routers", "LAN", "WAN", "WiFi",
        "server administration", "antivirus", "backup",
        "hardware maintenance", "computer repair",
        "network security", "email configuration",
        "IT technician", "support technician",
    })


def get_language_profile() -> dict[str, str]:
    return {
        "arabic": "Proficient",
        "english": "Proficient",
        "french": "Proficient",
        "spanish": "Intermediate",
    }