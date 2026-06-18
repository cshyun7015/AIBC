import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True)

from app.agent import itsm_agent_app

print("Testing itsm_agent_app.invoke...")
try:
    final_state = itsm_agent_app.invoke({"incident_report": "테스트 장애"})
    print("Success!", final_state)
except Exception as e:
    import traceback
    traceback.print_exc()
