import os

from dotenv import load_dotenv


load_dotenv()

# Sent on every outbound request (Lee County API + geocoders). Set USER_AGENT in
# the environment / .env; the geocoders' usage policies ask for a real contact.
USER_AGENT = os.environ.get("USER_AGENT") or "LeeCountyIncidentMap/1.0 (senior-design; contact@email.com)"